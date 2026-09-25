"""Serialización JSON de un KnowledgeGraph.

Formato del JSON (estable y legible):

  {
    "schema_version": 1,
    "node_count": <int>,
    "nodes": [
      {
        "id": "...",
        "statement": "...",
        "status": "axiom" | "definition" | "theorem" | "hypothesis",
        "kind": "concept" | "relation" | "procedure",
        "foundations": ["...", ...],
        "validity_conditions": ["...", ...],
        "inputs": ["...", ...],
        "outputs": ["...", ...],
        "rationale": "...",
        "properties": {...},      # serializable como JSON
        "has_compute": true | false
      },
      ...
    ]
  }

El ORDEN de los nodos en el JSON refleja el orden de inserción al
grafo. Al cargar, los nodos se insertan en ese mismo orden — eso
preserva los invariantes del grafo (los foundations existen antes
de los nodos que los usan).

Política con `properties` no serializables a JSON (p. ej. callables
en metadata): el dump SUSTITUYE por su `repr` y registra el id en
`SerializationReport.lossy_properties`. Decisión honesta: la
información se preserva en forma legible aunque no sea ejecutable
tras load. Los nodos del proyecto actual no tienen properties no
serializables; este caso queda como salvaguarda futura.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from experiment_01.knowledge_graph import (
    EpistemicStatus,
    KnowledgeGraph,
    KnowledgeNode,
    NodeKind,
)

from .registry import ComputeRegistry


_SCHEMA_VERSION = 1


@dataclass
class SerializationReport:
    path: str
    node_count: int
    nodes_with_compute: int
    lossy_properties: list[str] = field(default_factory=list)

    def render(self) -> str:
        lines = [
            f"DUMP → {self.path}",
            f"  nodos: {self.node_count}",
            f"  con compute (commitment): {self.nodes_with_compute}",
        ]
        if self.lossy_properties:
            lines.append(
                f"  ⚠ properties no serializables (repr): "
                f"{self.lossy_properties}"
            )
        return "\n".join(lines)


@dataclass
class DeserializationReport:
    path: str
    graph: KnowledgeGraph
    nodes_loaded: int
    computes_resolved: list[str] = field(default_factory=list)
    unresolved_computes: list[str] = field(default_factory=list)

    @property
    def is_complete(self) -> bool:
        return not self.unresolved_computes

    def render(self) -> str:
        lines = [
            f"LOAD ← {self.path}",
            f"  nodos cargados: {self.nodes_loaded}",
            f"  computes resueltos: {len(self.computes_resolved)}/"
            f"{len(self.computes_resolved) + len(self.unresolved_computes)}",
        ]
        if self.unresolved_computes:
            lines.append(
                f"  ⚠ computes sin resolver (nodo cargado sin compute): "
                f"{self.unresolved_computes}"
            )
        return "\n".join(lines)


# ---------------------------------------------------------------------
# dump
# ---------------------------------------------------------------------

def dump(graph: KnowledgeGraph, path: str | Path) -> SerializationReport:
    """Serializa el grafo completo a un archivo JSON."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    lossy: list[str] = []
    nodes_payload: list[dict] = []
    nodes_with_compute = 0
    for node in graph:
        props_serializable, props_lossy = _safe_serialize_properties(
            node.properties or {}
        )
        if props_lossy:
            lossy.append(node.id)
        if node.is_executable():
            nodes_with_compute += 1
        nodes_payload.append({
            "id": node.id,
            "statement": node.statement,
            "status": node.status.value,
            "kind": node.kind.value,
            "foundations": list(node.foundations),
            "validity_conditions": list(node.validity_conditions),
            "inputs": list(node.inputs),
            "outputs": list(node.outputs),
            "rationale": node.rationale or "",
            "properties": props_serializable,
            "has_compute": node.is_executable(),
        })

    payload = {
        "schema_version": _SCHEMA_VERSION,
        "node_count": len(nodes_payload),
        "nodes": nodes_payload,
    }
    p.write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                 encoding="utf-8")
    return SerializationReport(
        path=str(p),
        node_count=len(nodes_payload),
        nodes_with_compute=nodes_with_compute,
        lossy_properties=lossy,
    )


# ---------------------------------------------------------------------
# load
# ---------------------------------------------------------------------

def load(
    path: str | Path,
    registry: ComputeRegistry | None = None,
) -> DeserializationReport:
    """Reconstruye un KnowledgeGraph desde el JSON.

    `registry` aporta los compute callables. Si None, ningún compute
    se reconecta — el grafo cargado tendrá `is_executable() == False`
    en todos los nodos que originalmente tenían compute. El caller
    puede inspeccionar `DeserializationReport.unresolved_computes`
    para diagnosticar.
    """
    p = Path(path)
    payload = json.loads(p.read_text(encoding="utf-8"))
    schema = payload.get("schema_version")
    if schema != _SCHEMA_VERSION:
        raise ValueError(
            f"schema_version {schema!r} no soportado "
            f"(esperado {_SCHEMA_VERSION})"
        )

    graph = KnowledgeGraph()
    resolved: list[str] = []
    unresolved: list[str] = []

    for n in payload.get("nodes", []):
        node_id = n["id"]
        compute = None
        if n.get("has_compute"):
            if registry is not None and registry.has(node_id):
                compute = registry.get(node_id)
                resolved.append(node_id)
            else:
                unresolved.append(node_id)

        graph.add(KnowledgeNode(
            id=node_id,
            statement=n["statement"],
            status=EpistemicStatus(n["status"]),
            kind=NodeKind(n["kind"]),
            foundations=list(n.get("foundations", [])),
            validity_conditions=list(n.get("validity_conditions", [])),
            inputs=list(n.get("inputs", [])),
            outputs=list(n.get("outputs", [])),
            rationale=n.get("rationale", ""),
            properties=dict(n.get("properties", {})),
            compute=compute,
        ))

    return DeserializationReport(
        path=str(p),
        graph=graph,
        nodes_loaded=len(graph),
        computes_resolved=resolved,
        unresolved_computes=unresolved,
    )


# ---------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------

def _safe_serialize_properties(props: dict) -> tuple[dict, bool]:
    """Devuelve (props_serializables, hubo_lossy_substitution).

    Si un valor no es JSON-serializable, se sustituye por su `repr`
    y se marca lossy. Recursivo para dicts anidados.
    """
    lossy = False

    def _scrub(v):
        nonlocal lossy
        if isinstance(v, dict):
            return {k: _scrub(vv) for k, vv in v.items()}
        if isinstance(v, (list, tuple)):
            return [_scrub(x) for x in v]
        if isinstance(v, (str, int, float, bool)) or v is None:
            return v
        # No serializable: callable, tipo custom, etc.
        lossy = True
        return repr(v)

    out = _scrub(props)
    return out, lossy
