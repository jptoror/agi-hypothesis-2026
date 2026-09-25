"""SystemManifest — configuración persistente del sistema completo.

Estructura en disco:

    root/
      manifest.json                   <- este archivo
      graphs/{specialist_id}.json     <- un grafo por especialista
      sessions/{session_id}.json      <- una sesión por archivo

`manifest.json` declara qué especialistas hay, cómo instanciarlos
(qualified class name) y dónde está su grafo serializado.

Atomicidad por archivo (escritura → `.tmp` → `os.replace`). NO hay
transacción multi-archivo: si el proceso muere a mitad de
`save_system`, el manifest puede quedar referenciando un grafo no
escrito. Eso es una limitación honesta de exp_19 — el caller que
necesite garantía total puede orquestar un backup previo.

Errores explícitos en todos los caminos de fallo:
  - `graph_path` faltante en disco          → `ManifestError`
  - `specialist_class` no importable        → `ManifestError`
  - `format_version` ausente o no soportado → `UnsupportedSchemaError`
"""
from __future__ import annotations

import importlib
import json
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from experiment_01.knowledge_graph import KnowledgeGraph
from experiment_03.inter_specialist_protocol import (
    SpecialistAdapter,
    SpecialistRegistry,
)

from .serialization import (
    FORMAT_VERSION,
    ProcedureRefRegistry,
    UnsupportedSchemaError,
    deserialize_graph,
    serialize_graph,
)


class ManifestError(RuntimeError):
    """Error de manifest: archivo faltante, clase no importable,
    formato corrupto, etc."""


# ---------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------

@dataclass
class SpecialistEntry:
    """Una entrada del manifest por especialista."""

    specialist_id: str
    specialist_class: str            # qualified: "module.path.Class"
    graph_path: str                  # relativo al manifest
    source_document: str | None = None
    # Kwargs adicionales para el constructor del especialista. Hoy
    # vacío para el caso canónico (`SubdomainAdapter`); reservado
    # para que adapters con configuración no-default puedan
    # declararla.
    init_kwargs: dict = field(default_factory=dict)


@dataclass
class SystemManifest:
    format_version: str
    specialists: list[SpecialistEntry]
    created_at: str
    last_modified: str

    def to_dict(self) -> dict:
        return {
            "format_version": self.format_version,
            "specialists": [
                {
                    "specialist_id": s.specialist_id,
                    "specialist_class": s.specialist_class,
                    "graph_path": s.graph_path,
                    "source_document": s.source_document,
                    "init_kwargs": dict(s.init_kwargs),
                }
                for s in self.specialists
            ],
            "created_at": self.created_at,
            "last_modified": self.last_modified,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SystemManifest":
        fv = data.get("format_version")
        if fv != FORMAT_VERSION:
            raise UnsupportedSchemaError(
                f"manifest.format_version {fv!r} no soportado "
                f"(esperado {FORMAT_VERSION!r})"
            )
        return cls(
            format_version=fv,
            specialists=[
                SpecialistEntry(
                    specialist_id=e["specialist_id"],
                    specialist_class=e["specialist_class"],
                    graph_path=e["graph_path"],
                    source_document=e.get("source_document"),
                    init_kwargs=dict(e.get("init_kwargs", {})),
                )
                for e in data.get("specialists", [])
            ],
            created_at=data.get("created_at", ""),
            last_modified=data.get("last_modified", ""),
        )


# ---------------------------------------------------------------------
# Sistema cargado — contenedor explícito (NO subclase del orchestrator
# de ningún experimento; cada experimento tiene el suyo)
# ---------------------------------------------------------------------

@dataclass
class LoadedSystem:
    """Estado del sistema reconstruido desde disco.

    Contiene la `SpecialistRegistry` con todos los adapters
    reinstanciados y el `VocabularyRegistry` reconstruido a partir de
    las `surface_forms` declaradas en cada grafo. El caller usa este
    objeto para resumir orquestadores o iniciar uno nuevo
    (`SessionOrchestrator` del exp_19)."""

    root_path: Path
    manifest: SystemManifest
    specialist_registry: SpecialistRegistry
    vocabulary_registry: object  # VocabularyRegistry (lazy import)
    graphs: dict  # specialist_id → KnowledgeGraph


# ---------------------------------------------------------------------
# Escritura atómica
# ---------------------------------------------------------------------

def _atomic_write(path: Path, content: str) -> None:
    """Escribe `content` a `path` atómicamente vía `os.replace`."""
    path.parent.mkdir(parents=True, exist_ok=True)
    # tempfile en el MISMO directorio para que `os.replace` sea
    # atómico bajo POSIX (cross-FS no garantiza atomicidad).
    fd, tmp = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, path)
    except Exception:
        # Limpia el tmp si quedó.
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------
# save_system
# ---------------------------------------------------------------------

def _qualified_class_name(obj: object) -> str:
    klass = obj.__class__
    return f"{klass.__module__}.{klass.__qualname__}"


def save_system(
    specialist_registry: SpecialistRegistry,
    root_path: str | Path,
    *,
    source_documents: dict[str, str] | None = None,
) -> SystemManifest:
    """Guarda manifest + grafos de cada especialista en `root_path`.

    `source_documents` opcional: mapa `specialist_id → path` para
    poblar `SpecialistEntry.source_document` cuando el caller lo
    conoce (típicamente la `SpecialistFactory` lo lleva). Si no se
    provee, queda `None`.

    Retorna el manifest persistido. Por contrato, idempotente:
    invocar dos veces con el mismo estado produce los mismos
    archivos."""
    root = Path(root_path)
    graphs_dir = root / "graphs"
    graphs_dir.mkdir(parents=True, exist_ok=True)

    src_map = dict(source_documents or {})
    entries: list[SpecialistEntry] = []
    for adapter in specialist_registry.all():
        sid = getattr(adapter, "name", None) or _qualified_class_name(adapter)
        graph = _adapter_graph(adapter)
        if graph is None:
            raise ManifestError(
                f"especialista '{sid}' no expone .graph (ni .specialist.graph); "
                f"no se puede serializar"
            )
        graph_path = f"graphs/{sid}.json"
        _atomic_write(
            root / graph_path,
            json.dumps(serialize_graph(graph), indent=2, ensure_ascii=False),
        )
        entries.append(SpecialistEntry(
            specialist_id=sid,
            specialist_class=_qualified_class_name(adapter),
            graph_path=graph_path,
            source_document=src_map.get(sid),
            init_kwargs={},
        ))

    now = datetime.now(timezone.utc).isoformat()
    manifest_path = root / "manifest.json"
    created = now
    if manifest_path.exists():
        try:
            prev = json.loads(manifest_path.read_text(encoding="utf-8"))
            created = prev.get("created_at", now)
        except (json.JSONDecodeError, OSError):
            pass

    manifest = SystemManifest(
        format_version=FORMAT_VERSION,
        specialists=entries,
        created_at=created,
        last_modified=now,
    )
    _atomic_write(
        manifest_path,
        json.dumps(manifest.to_dict(), indent=2, ensure_ascii=False),
    )
    # Asegura que el directorio de sesiones existe (puede quedar
    # vacío hasta que el SessionOrchestrator persista la primera).
    (root / "sessions").mkdir(parents=True, exist_ok=True)
    return manifest


# ---------------------------------------------------------------------
# load_system
# ---------------------------------------------------------------------

def load_system(
    root_path: str | Path,
    *,
    procedure_registry: ProcedureRefRegistry | None = None,
    vocabulary_registry=None,
) -> LoadedSystem:
    """Reconstruye `SpecialistRegistry` + `VocabularyRegistry` a
    partir de los archivos de `root_path`. Cada `specialist_class`
    se importa dinámicamente; si falla, `ManifestError` explícito.

    `vocabulary_registry`: si None, se crea uno nuevo aislado. Si se
    pasa, se REUSA — el caller controla si quiere reemplazar el
    DEFAULT_REGISTRY global o trabajar aislado."""
    root = Path(root_path)
    manifest_path = root / "manifest.json"
    if not manifest_path.exists():
        raise ManifestError(f"no existe manifest en {manifest_path}")

    try:
        manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ManifestError(f"manifest.json corrupto: {e}") from e

    manifest = SystemManifest.from_dict(manifest_data)

    from experiment_17.vocabulary import VocabularyRegistry
    vreg = vocabulary_registry or VocabularyRegistry()
    sreg = SpecialistRegistry()
    graphs: dict = {}

    for entry in manifest.specialists:
        gpath = root / entry.graph_path
        if not gpath.exists():
            raise ManifestError(
                f"grafo declarado en manifest no existe: {gpath}"
            )
        try:
            graph_data = json.loads(gpath.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise ManifestError(
                f"grafo '{entry.graph_path}' corrupto: {e}"
            ) from e
        graph = deserialize_graph(
            graph_data, procedure_registry=procedure_registry,
        )
        graphs[entry.specialist_id] = graph

        adapter = _instantiate_specialist(entry, graph)
        sreg.register(adapter)

        # Reconstruye el VocabularyRegistry: surface_forms declaradas
        # en cada nodo del grafo se reindexan automáticamente. Sin
        # esto, las consultas que dependen del registry (exp_17) no
        # podrían operar tras un reinicio.
        vreg.register(
            specialist_id=entry.specialist_id,
            graph=graph,
            source_document=entry.source_document,
        )

    return LoadedSystem(
        root_path=root,
        manifest=manifest,
        specialist_registry=sreg,
        vocabulary_registry=vreg,
        graphs=graphs,
    )


# ---------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------

def _adapter_graph(adapter: SpecialistAdapter) -> KnowledgeGraph | None:
    """El adapter canónico (`SubdomainAdapter` del exp_04) expone
    `.graph` directamente; algunos llevan un especialista interno
    con `.specialist.graph`. Probamos ambos por convención."""
    g = getattr(adapter, "graph", None)
    if isinstance(g, KnowledgeGraph):
        return g
    spec = getattr(adapter, "specialist", None)
    if spec is not None:
        g = getattr(spec, "graph", None)
        if isinstance(g, KnowledgeGraph):
            return g
    return None


def _instantiate_specialist(
    entry: SpecialistEntry,
    graph: KnowledgeGraph,
) -> SpecialistAdapter:
    """Importa la clase declarada y la instancia con el grafo. Los
    constructores aceptan `graph=...` como kwarg — esa es la
    convención del proyecto (`SubdomainAdapter`, adapters
    personalizados). `init_kwargs` se mezcla en la llamada."""
    module_name, _, class_name = entry.specialist_class.rpartition(".")
    if not module_name or not class_name:
        raise ManifestError(
            f"specialist_class inválido: {entry.specialist_class!r}"
        )
    try:
        module = importlib.import_module(module_name)
    except ImportError as e:
        raise ManifestError(
            f"no se pudo importar módulo '{module_name}' para "
            f"reconstruir '{entry.specialist_id}': {e}"
        ) from e
    klass = getattr(module, class_name, None)
    if klass is None:
        raise ManifestError(
            f"clase '{class_name}' no existe en módulo '{module_name}'"
        )

    kwargs = dict(entry.init_kwargs)
    kwargs.setdefault("graph", graph)
    # SubdomainAdapter exige `domain` — si no viene en init_kwargs,
    # lo derivamos del specialist_id (convención canónica del exp_06).
    kwargs.setdefault("domain", entry.specialist_id)
    try:
        return klass(**kwargs)
    except TypeError as e:
        raise ManifestError(
            f"constructor de '{entry.specialist_class}' rechazó kwargs "
            f"{list(kwargs)}: {e}"
        ) from e
