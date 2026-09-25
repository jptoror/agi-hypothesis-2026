"""Persiste un especialista validado al disco (exp_21).

Reusa el formato del exp_19:

  <root>/
    manifest.json
    graphs/<spec_id>.json
    sources/<spec_id>.md      <- COPIA del documento fuente

Política:
  - Atómico por archivo (`os.replace` sobre `.tmp`). El manifest se
    actualiza en sitio: leer → modificar la lista → reescribir.
    NO toca grafos de otros especialistas.
  - Idempotente: persistir dos veces con `overwrite=True` produce
    el mismo resultado byte-a-byte.
  - `overwrite=False` y especialista ya existe → error explícito.
  - El documento fuente se COPIA, no se mueve. Esto preserva
    auditabilidad y permite reload posterior sin depender del path
    original.
"""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from experiment_01.knowledge_graph import KnowledgeGraph
from experiment_06.document_parser import (
    GraphBuilder,
    NodeExtractor,
    StructureExtractor,
)
from experiment_19.persistence.manifest import (
    SpecialistEntry,
    SystemManifest,
    _atomic_write,
)
from experiment_19.persistence.serialization import (
    FORMAT_VERSION,
    serialize_graph,
)

from .preview import SpecialistPreview, build_preview


@dataclass(frozen=True)
class PersistedSpecialist:
    specialist_id: str
    graph_path: Path
    document_path: Path        # copia en <root>/sources/...
    manifest_updated: bool
    nodes_persisted: int


_SPECIALIST_CLASS_DEFAULT = (
    "experiment_04.subdomain_specialist.SubdomainAdapter"
)


def persist_specialist(
    document_path: str | Path,
    preview: SpecialistPreview,
    target_root: str | Path,
    *,
    overwrite: bool = False,
    specialist_class: str = _SPECIALIST_CLASS_DEFAULT,
    known_specialists: dict | None = None,
) -> PersistedSpecialist:
    """Materializa el especialista descrito por `preview` en
    `target_root`. Devuelve `PersistedSpecialist` con los paths
    finales.

    `known_specialists` (opcional): mapa `spec_id → KnowledgeGraph`
    que el GraphBuilder usa como `base_graph`. Necesario cuando el
    documento referencia nodos de otros especialistas — sin esto, el
    builder rechaza la inserción de nodos cuya foundation no existe
    localmente. El validador del exp_21 ya marca estas referencias
    como cross-spec en el preview; el persister las MATERIALIZA acá.
    """
    src = Path(document_path)
    root = Path(target_root)
    spec_id = preview.proposed_specialist_id

    graphs_dir = root / "graphs"
    sources_dir = root / "sources"
    sessions_dir = root / "sessions"
    graphs_dir.mkdir(parents=True, exist_ok=True)
    sources_dir.mkdir(parents=True, exist_ok=True)
    sessions_dir.mkdir(parents=True, exist_ok=True)

    graph_file = graphs_dir / f"{spec_id}.json"
    source_copy = sources_dir / f"{spec_id}.md"

    if graph_file.exists() and not overwrite:
        raise FileExistsError(
            f"el especialista '{spec_id}' ya existe en {graph_file}. "
            f"Usá overwrite=True (o `--overwrite` en CLI) para "
            f"reemplazarlo."
        )

    # 1. Construir el grafo desde el documento. El validador ya
    # garantizó que esto no falla; el preview ya tiene los
    # external_ids que necesita el extractor.
    raw = src.read_text(encoding="utf-8")
    structure = StructureExtractor().extract_text(raw)
    # Reusar las cross-refs detectadas por el preview para que el
    # NodeExtractor acepte foundations externas.
    external_ids = {
        c.foundation_ref for c in preview.cross_specialist_references
    } | {
        c.target_node for c in preview.cross_specialist_references
    }
    parse_report = NodeExtractor().extract(
        structure, external_ids=external_ids,
    )
    # Reescribimos foundations cross-spec a su forma canónica (`node_id`
    # sin prefijo) para que el `base_graph` del builder los reconozca.
    # El motor del exp_06 espera ids puros — el prefijo `spec::` es
    # convención del exp_19 para `external_foundations`, NO para
    # foundations locales del especialista que se está construyendo.
    if known_specialists:
        _strip_cross_spec_prefixes(parse_report, known_specialists)
    base_graph = _union_base_graph(
        known_specialists=known_specialists,
        cross_refs=preview.cross_specialist_references,
    )
    build_report = GraphBuilder().build(
        parse_report, base_graph=base_graph,
    )
    if build_report.graph is None:
        # Defensivo. Si llegamos acá con preview válido pero build
        # roto, es un bug del validador — preferimos error duro.
        raise RuntimeError(
            f"build_report sin grafo para '{spec_id}'. Esto indica un "
            f"desajuste entre validator y builder; reportar."
        )
    graph = build_report.graph

    # 2. Serializar grafo (formato exp_19, atómico).
    graph_payload = json.dumps(
        serialize_graph(graph), indent=2, ensure_ascii=False,
    )
    _atomic_write(graph_file, graph_payload)

    # 3. Copiar documento fuente.
    shutil.copyfile(src, source_copy)

    # 4. Actualizar manifest in-place.
    manifest_updated = _update_manifest(
        root=root,
        spec_id=spec_id,
        specialist_class=specialist_class,
        graph_relpath=f"graphs/{spec_id}.json",
        source_relpath=f"sources/{spec_id}.md",
    )

    return PersistedSpecialist(
        specialist_id=spec_id,
        graph_path=graph_file,
        document_path=source_copy,
        manifest_updated=manifest_updated,
        nodes_persisted=len(graph),
    )


# ---------------------------------------------------------------------
# Union base_graph (cross-spec foundations → import en build)
# ---------------------------------------------------------------------

def _union_base_graph(
    known_specialists: dict | None,
    cross_refs,
) -> KnowledgeGraph | None:
    """Devuelve un grafo que contiene la unión de TODOS los nodos de
    los especialistas conocidos. El GraphBuilder usa este grafo
    como `base_graph`: importa por cierre transitivo solo lo
    realmente referenciado, así que pasar la unión completa es
    seguro y evita búsqueda fina."""
    if not known_specialists:
        return None
    if not cross_refs:
        # Si el documento no tiene cross-refs no hace falta base.
        return None
    union = KnowledgeGraph()
    seen: set[str] = set()
    # Inserción topológica: cada grafo ya está en orden de
    # foundations; copiamos en ese orden y saltamos duplicados.
    for spec_id, graph in known_specialists.items():
        for n in graph:
            if n.id in seen:
                continue
            try:
                union.add(_dc_replace(n))
                seen.add(n.id)
            except (ValueError, KeyError):
                # Foundation faltante (porque vino de OTRO grafo cuya
                # importación todavía no llegó). Saltamos; el cierre
                # transitivo del builder la traerá si es necesaria.
                continue
    return union


def _dc_replace(node):
    """Copia superficial del nodo. KnowledgeNode es @dataclass; usamos
    `dataclasses.replace` con override vacío para una nueva instancia
    independiente (preserva todos los atributos)."""
    from dataclasses import replace as _replace
    return _replace(node)


def _strip_cross_spec_prefixes(parse_report, known_specialists: dict) -> None:
    """Mutación in-place de `ExtractedNode.foundations`: cualquier
    referencia `spec_id::node_id` cuya forma corta exista en algún
    grafo conocido se reemplaza por `node_id`. Esto canoniza los
    foundations al formato que el GraphBuilder espera (id puro), de
    modo que el `base_graph` los pueda importar via cierre
    transitivo."""
    known_ids: dict[str, set[str]] = {
        sid: {n.id for n in g} for sid, g in known_specialists.items()
    }
    for node in parse_report.nodes_extracted:
        new_foundations: list[str] = []
        for f in node.foundations:
            if "::" in f:
                spec_id, _, node_id = f.partition("::")
                if (
                    spec_id in known_ids
                    and node_id in known_ids[spec_id]
                ):
                    new_foundations.append(node_id)
                    continue
            new_foundations.append(f)
        node.foundations = new_foundations


# ---------------------------------------------------------------------
# Manifest update in-place
# ---------------------------------------------------------------------

def _update_manifest(
    root: Path,
    spec_id: str,
    specialist_class: str,
    graph_relpath: str,
    source_relpath: str,
) -> bool:
    """Lee manifest.json (si existe), agrega/reemplaza la entry de
    `spec_id`, y reescribe atómicamente. Si el manifest no existe,
    lo crea desde cero."""
    manifest_path = root / "manifest.json"
    now = datetime.now(timezone.utc).isoformat()
    if manifest_path.exists():
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise RuntimeError(
                f"manifest.json corrupto en {manifest_path}: {e}"
            ) from e
        manifest = SystemManifest.from_dict(data)
    else:
        manifest = SystemManifest(
            format_version=FORMAT_VERSION,
            specialists=[],
            created_at=now,
            last_modified=now,
        )

    # Reemplazar o agregar la entry.
    new_entry = SpecialistEntry(
        specialist_id=spec_id,
        specialist_class=specialist_class,
        graph_path=graph_relpath,
        source_document=source_relpath,
        init_kwargs={},
    )
    replaced = False
    for i, e in enumerate(manifest.specialists):
        if e.specialist_id == spec_id:
            manifest.specialists[i] = new_entry
            replaced = True
            break
    if not replaced:
        manifest.specialists.append(new_entry)
    manifest.last_modified = now
    if not manifest.created_at:
        manifest.created_at = now

    _atomic_write(
        manifest_path,
        json.dumps(manifest.to_dict(), indent=2, ensure_ascii=False),
    )
    return True


# ---------------------------------------------------------------------
# Helpers para CLI: list / show / remove
# ---------------------------------------------------------------------

def list_specialists(target_root: str | Path) -> list[SpecialistEntry]:
    root = Path(target_root)
    manifest_path = root / "manifest.json"
    if not manifest_path.exists():
        return []
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    return list(SystemManifest.from_dict(data).specialists)


def remove_specialist(
    target_root: str | Path,
    specialist_id: str,
    *,
    delete_files: bool = True,
) -> bool:
    """Elimina la entrada del manifest. Si `delete_files=True`
    también borra el grafo y la copia del documento. Devuelve True
    si la entrada estaba registrada (False si no existía)."""
    root = Path(target_root)
    manifest_path = root / "manifest.json"
    if not manifest_path.exists():
        return False
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest = SystemManifest.from_dict(data)
    before = len(manifest.specialists)
    manifest.specialists = [
        e for e in manifest.specialists if e.specialist_id != specialist_id
    ]
    if len(manifest.specialists) == before:
        return False
    manifest.last_modified = datetime.now(timezone.utc).isoformat()
    _atomic_write(
        manifest_path,
        json.dumps(manifest.to_dict(), indent=2, ensure_ascii=False),
    )
    if delete_files:
        for sub in ("graphs", "sources"):
            for ext in (".json", ".md"):
                p = root / sub / f"{specialist_id}{ext}"
                if p.exists():
                    p.unlink()
    return True
