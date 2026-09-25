"""Serialización estricta de KnowledgeGraph (exp_19).

Política diferente a `experiment_02/persistence/serialize.py`:

  - **Errores explícitos en lugar de degradación silenciosa.**
    `properties` con tipos no JSON-serializables → excepción
    `UnsupportedPropertyError`. exp_02 sustituía por `repr` y
    marcaba `lossy_properties`; exp_19 prefiere el corte limpio
    (la conversación que se está persistiendo no debe quedar a
    medias por una propiedad sospechosa).

  - **`compute_ref` por nombre de procedure.** El callable no se
    serializa; sí se serializa el id que el GraphBuilder ya guarda
    en `properties["procedure_name"]`. La resolución pasa por
    `ProcedureRefRegistry`, un índice global poblado por el caller
    (típicamente con las bibliotecas del exp_06 + exp_16).

  - **`format_version: "1.0"` (string).** Reservado para migración
    futura. Cargar un JSON sin ese campo → `UnsupportedSchemaError`
    explícito.

El formato es DISTINTO al del exp_02 (`schema_version: 1` int) y
los dos coexisten — exp_02 sigue verde, ningún test del proyecto
mezcla ambos formatos.
"""
from __future__ import annotations

import json
from typing import Iterable

from experiment_01.knowledge_graph import (
    EpistemicStatus,
    KnowledgeGraph,
    KnowledgeNode,
    NodeKind,
)


FORMAT_VERSION = "1.0"


# ---------------------------------------------------------------------
# Errores tipados
# ---------------------------------------------------------------------

class SerializationError(ValueError):
    """Error genérico de serialización exp_19."""


class UnsupportedPropertyError(SerializationError):
    """Una entrada de `properties` no es JSON-serializable y exp_19
    NO degrada silenciosamente. El caller debe limpiar la propiedad
    o registrarla bajo otra clave que sí lo sea."""

    def __init__(self, node_id: str, key_path: str, value_repr: str) -> None:
        self.node_id = node_id
        self.key_path = key_path
        self.value_repr = value_repr
        super().__init__(
            f"propiedad no serializable en nodo '{node_id}' "
            f"clave '{key_path}': {value_repr}"
        )


class UnsupportedSchemaError(SerializationError):
    """`format_version` ausente o no soportado."""


class ProcedureNotResolvableError(SerializationError):
    """`compute_ref` apunta a un procedure que no está registrado."""

    def __init__(self, node_id: str, procedure_ref: str) -> None:
        self.node_id = node_id
        self.procedure_ref = procedure_ref
        super().__init__(
            f"nodo '{node_id}' declara compute_ref='{procedure_ref}' "
            f"pero no hay procedure registrado con ese nombre"
        )


# ---------------------------------------------------------------------
# Registro de procedures (callable lookup)
# ---------------------------------------------------------------------

class ProcedureRefRegistry:
    """Índice global `procedure_name → callable` para resolver
    `compute_ref` al deserializar.

    Patrón canónico:
        from experiment_19.persistence import (
            ProcedureRefRegistry, register_procedures_from,
        )
        from experiment_06.specialist_factory import PROCEDURES

        reg = ProcedureRefRegistry()
        register_procedures_from(reg, PROCEDURES)
        load_system(path, procedure_registry=reg)
    """

    def __init__(self) -> None:
        self._procs: dict = {}

    def register(self, name: str, fn) -> None:
        if not callable(fn):
            raise TypeError(f"procedure '{name}' no es callable")
        self._procs[name] = fn

    def get(self, name: str):
        return self._procs.get(name)

    def has(self, name: str) -> bool:
        return name in self._procs

    def names(self) -> list[str]:
        return sorted(self._procs.keys())

    def __len__(self) -> int:
        return len(self._procs)


def register_procedures_from(
    registry: ProcedureRefRegistry,
    library: dict,
) -> int:
    """Conveniencia: importa al `registry` cada `(name, spec)` de un
    dict tipo `PROCEDURES` (exp_06) o `CPP_PROCEDURES` (exp_16). El
    `spec` debe tener atributo `fn` callable."""
    n = 0
    for name, spec in library.items():
        fn = getattr(spec, "fn", None)
        if not callable(fn):
            raise TypeError(
                f"procedure '{name}' del library no expone 'fn' callable"
            )
        registry.register(name, fn)
        n += 1
    return n


# ---------------------------------------------------------------------
# Properties: validación estricta
# ---------------------------------------------------------------------

_JSON_PRIMITIVES = (str, int, float, bool, type(None))


def _validate_json_value(node_id: str, key_path: str, value) -> None:
    """Recursivo. Lanza `UnsupportedPropertyError` ante cualquier tipo
    que no sea JSON-nativo. NO mutila el valor — la validación es
    pura."""
    if isinstance(value, dict):
        for k, v in value.items():
            if not isinstance(k, str):
                raise UnsupportedPropertyError(
                    node_id, f"{key_path}.<{type(k).__name__}>",
                    repr(k),
                )
            _validate_json_value(node_id, f"{key_path}.{k}", v)
        return
    if isinstance(value, (list, tuple)):
        for i, item in enumerate(value):
            _validate_json_value(node_id, f"{key_path}[{i}]", item)
        return
    if isinstance(value, _JSON_PRIMITIVES):
        return
    raise UnsupportedPropertyError(node_id, key_path, repr(value))


# ---------------------------------------------------------------------
# Nodo
# ---------------------------------------------------------------------

def serialize_node(node: KnowledgeNode) -> dict:
    """Serializa un único nodo. Lanza `UnsupportedPropertyError` si
    `properties` lleva valores no JSON-nativos.

    `compute_ref` se deriva de `properties["procedure_name"]` cuando
    el nodo tiene `compute` resuelto. Eso reusa la convención que ya
    pone el GraphBuilder del exp_06: el documento declara el
    procedure por nombre, el builder guarda ese nombre, el
    serializer lo emite. Sin acoplar al callable concreto."""
    props = dict(node.properties or {})
    _validate_json_value(node.id, "properties", props)

    # `compute_ref`: SOLO si hay compute Y hay procedure_name. Un
    # nodo con compute pero sin procedure_name (caso atípico) se
    # serializa con compute_ref=None — el load lo dejará sin compute
    # y el caller lo verá explícitamente al inspeccionar el nodo.
    compute_ref = None
    if node.compute is not None:
        pn = props.get("procedure_name")
        if isinstance(pn, str) and pn:
            compute_ref = pn

    return {
        "id": node.id,
        "statement": node.statement,
        "status": node.status.value,
        "kind": node.kind.value,
        "foundations": list(node.foundations),
        "validity_conditions": list(node.validity_conditions),
        "inputs": list(node.inputs),
        "outputs": list(node.outputs),
        "rationale": node.rationale or "",
        "properties": props,
        "compute_ref": compute_ref,
    }


def deserialize_node(
    data: dict,
    procedure_registry: ProcedureRefRegistry | None = None,
) -> KnowledgeNode:
    """Reconstruye un `KnowledgeNode`. Si el nodo lleva `compute_ref`
    no None, se resuelve contra `procedure_registry`. Si no
    resuelve → `ProcedureNotResolvableError` explícito."""
    compute_ref = data.get("compute_ref")
    compute = None
    if compute_ref is not None:
        if procedure_registry is None or not procedure_registry.has(compute_ref):
            raise ProcedureNotResolvableError(
                node_id=data["id"], procedure_ref=compute_ref,
            )
        compute = procedure_registry.get(compute_ref)

    return KnowledgeNode(
        id=data["id"],
        statement=data["statement"],
        status=EpistemicStatus(data["status"]),
        kind=NodeKind(data["kind"]),
        foundations=list(data.get("foundations", [])),
        validity_conditions=list(data.get("validity_conditions", [])),
        inputs=list(data.get("inputs", [])),
        outputs=list(data.get("outputs", [])),
        rationale=data.get("rationale", ""),
        properties=dict(data.get("properties", {})),
        compute=compute,
    )


# ---------------------------------------------------------------------
# Grafo
# ---------------------------------------------------------------------

def serialize_graph(graph: KnowledgeGraph) -> dict:
    """Serializa un grafo completo. El orden de nodos en el JSON es
    el orden de inserción al grafo — preserva la propiedad de que
    los foundations existen antes que los nodos que los usan."""
    return {
        "format_version": FORMAT_VERSION,
        "node_count": len(graph),
        "nodes": [serialize_node(n) for n in graph],
    }


def deserialize_graph(
    data: dict,
    procedure_registry: ProcedureRefRegistry | None = None,
) -> KnowledgeGraph:
    """Reconstruye un grafo desde su dict serializado.

    Validaciones:
      - `format_version` debe coincidir con `FORMAT_VERSION`.
      - El orden de inserción se respeta — el caller que produjo el
        JSON ya garantizó que los foundations vienen antes que sus
        consumidores.
    """
    fv = data.get("format_version")
    if fv != FORMAT_VERSION:
        raise UnsupportedSchemaError(
            f"format_version {fv!r} no soportado "
            f"(esperado {FORMAT_VERSION!r})"
        )
    graph = KnowledgeGraph()
    for n in data.get("nodes", []):
        graph.add(deserialize_node(n, procedure_registry=procedure_registry))
    return graph


# ---------------------------------------------------------------------
# Conveniencia: round-trip a/desde JSON string
# ---------------------------------------------------------------------

def graph_to_json(graph: KnowledgeGraph) -> str:
    return json.dumps(serialize_graph(graph), indent=2, ensure_ascii=False)


def graph_from_json(
    text: str,
    procedure_registry: ProcedureRefRegistry | None = None,
) -> KnowledgeGraph:
    return deserialize_graph(json.loads(text), procedure_registry=procedure_registry)
