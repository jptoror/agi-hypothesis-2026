"""Helpers para el subgrafo conversacional (exp_19).

**No es un tipo nuevo.** Un `conversation_graph` es un
`KnowledgeGraph` normal. Lo que cambia es la POLÍTICA de uso:

  1. Sus foundations pueden apuntar a nodos de grafos de
     especialistas externos. Esa referencia se codifica con el
     prefijo `<specialist_id>::<node_id>` para que sea distinguible
     de un id local.

  2. Cada nodo lleva el campo `promotion_candidate: bool = False`
     en `properties`. Es un MARCADOR RESERVADO: hoy nadie lo setea
     a `True` ni nadie lo consulta — exp_21/22 implementará la
     consolidación episódica→semántica usando ese campo. Reservarlo
     ahora evita migración de datos cuando esa funcionalidad
     llegue.

Estas dos políticas se aplican vía funciones helper, NO via
subclase de `KnowledgeGraph`. Eso preserva la equivalencia
estructural exigida por el spec ("la diferencia es política, no
estructural").
"""
from __future__ import annotations

from experiment_01.knowledge_graph import (
    KnowledgeGraph,
    KnowledgeNode,
)


CROSS_GRAPH_PREFIX_SEP = "::"


def new_conversation_graph() -> KnowledgeGraph:
    """Constructor de conveniencia. Devuelve un `KnowledgeGraph`
    pelado — la convención conversacional vive en los nodos que se
    le agregan, no en la clase del contenedor."""
    return KnowledgeGraph()


# ---------------------------------------------------------------------
# Foundations cross-graph
# ---------------------------------------------------------------------

CROSS_GRAPH_PREFIX = CROSS_GRAPH_PREFIX_SEP  # exportado para que el
# caller pueda buscar el separador sin importar la constante interna.


def cross_graph_foundation(specialist_id: str, node_id: str) -> str:
    """Codifica una referencia a un nodo de OTRO grafo en el formato
    canónico `specialist::node`. Las foundations del
    conversation_graph que apuntan fuera usan esta forma para que
    la serialización y el resolver puedan distinguirlas de ids
    locales."""
    if not specialist_id or not node_id:
        raise ValueError("specialist_id y node_id no pueden ser vacíos")
    if CROSS_GRAPH_PREFIX_SEP in specialist_id:
        raise ValueError(
            f"specialist_id contiene el separador "
            f"'{CROSS_GRAPH_PREFIX_SEP}': {specialist_id!r}"
        )
    return f"{specialist_id}{CROSS_GRAPH_PREFIX_SEP}{node_id}"


def is_cross_graph_foundation(ref: str) -> bool:
    return CROSS_GRAPH_PREFIX_SEP in (ref or "")


def parse_cross_graph_foundation(ref: str) -> tuple[str, str]:
    """`'alg_demo::alg.greedy_coloring'` → `('alg_demo', 'alg.greedy_coloring')`.
    Lanza `ValueError` si `ref` no tiene formato cross-graph."""
    if not is_cross_graph_foundation(ref):
        raise ValueError(f"no es referencia cross-graph: {ref!r}")
    specialist_id, _, node_id = ref.partition(CROSS_GRAPH_PREFIX_SEP)
    return specialist_id, node_id


# ---------------------------------------------------------------------
# promotion_candidate (reservado para exp_21/22)
# ---------------------------------------------------------------------

def set_promotion_candidate(node: KnowledgeNode, value: bool) -> None:
    """Setea `properties["promotion_candidate"]`. Helper explícito
    para que cuando exp_21/22 implemente la consolidación, busque
    este nombre sin sorpresas."""
    if node.properties is None:
        node.properties = {}
    node.properties["promotion_candidate"] = bool(value)


def is_promotion_candidate(node: KnowledgeNode) -> bool:
    return bool((node.properties or {}).get("promotion_candidate", False))


def ensure_promotion_candidate_field(node: KnowledgeNode) -> None:
    """Asegura que el nodo lleve `promotion_candidate` en
    `properties` (default `False`). Llamado por el orquestador
    cuando agrega nodos al conversation_graph — así el campo siempre
    está presente y el serializer lo preserva en round-trip."""
    if node.properties is None:
        node.properties = {}
    node.properties.setdefault("promotion_candidate", False)
