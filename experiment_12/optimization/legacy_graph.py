"""Snapshot del KnowledgeGraph PRE-OPTIMIZACIÓN del exp_12.

Este es un congelado literal de la implementación de
`experiment_01/knowledge_graph/graph.py` ANTES de aplicar:

  - Índice de outputs (PROB-09)
  - Memoización persistente de transitive_foundations (PROB-09)
  - Versión iterativa con stack explícito (PROB-08)

Existe sólo para que el benchmark del exp_12 pueda medir "antes vs
después" en el mismo run, sobre la misma máquina, con la misma
carga del sistema. NO debe usarse en producción — el código
canónico es el del exp_01 ya optimizado.
"""
from __future__ import annotations

from typing import Iterable, Iterator, Optional

from experiment_01.knowledge_graph import (
    EpistemicStatus,
    KnowledgeNode,
    NodeKind,
)


class LegacyKnowledgeGraph:
    """Versión pre-optimización. Idéntica al código original del
    exp_01 antes del exp_12. Mantenida sólo para benchmark
    comparativo."""

    def __init__(self) -> None:
        self._nodes: dict[str, KnowledgeNode] = {}

    # -- construcción ---------------------------------------------------

    def add(self, node: KnowledgeNode) -> KnowledgeNode:
        if node.id in self._nodes:
            raise ValueError(f"nodo duplicado: {node.id}")
        for dep in node.foundations:
            if dep not in self._nodes:
                raise ValueError(
                    f"fundamento inexistente '{dep}' para el nodo '{node.id}'. "
                    "Los fundamentos deben añadirse antes que los nodos que los usan."
                )
        self._nodes[node.id] = node
        return node

    # -- acceso ---------------------------------------------------------

    def get(self, node_id: str) -> KnowledgeNode:
        if node_id not in self._nodes:
            raise KeyError(f"nodo no encontrado: {node_id}")
        return self._nodes[node_id]

    def has(self, node_id: str) -> bool:
        return node_id in self._nodes

    def __iter__(self) -> Iterator[KnowledgeNode]:
        return iter(self._nodes.values())

    def __len__(self) -> int:
        return len(self._nodes)

    # -- búsqueda -------------------------------------------------------

    def find_by_concept(self, concept: str) -> list[KnowledgeNode]:
        needle = concept.lower()
        return [
            n
            for n in self._nodes.values()
            if needle in n.id.lower() or needle in n.statement.lower()
        ]

    def find_relations_producing(self, variable: str) -> list[KnowledgeNode]:
        """Implementación O(N) — itera el grafo entero."""
        return [
            n
            for n in self._nodes.values()
            if n.is_executable() and variable in n.outputs
        ]

    def by_status(self, status: EpistemicStatus) -> list[KnowledgeNode]:
        return [n for n in self._nodes.values() if n.status == status]

    def by_kind(self, kind: NodeKind) -> list[KnowledgeNode]:
        return [n for n in self._nodes.values() if n.kind == kind]

    # -- recorrido ------------------------------------------------------

    def foundations_of(self, node_id: str) -> list[KnowledgeNode]:
        return [self._nodes[dep] for dep in self._nodes[node_id].foundations]

    def transitive_foundations(self, node_id: str) -> list[KnowledgeNode]:
        """Implementación RECURSIVA — revienta con cadenas > sys.recursionlimit
        (PROB-08) y recalcula desde cero en cada llamada (PROB-09)."""
        seen: set[str] = set()
        order: list[str] = []

        def visit(nid: str) -> None:
            for dep in self._nodes[nid].foundations:
                if dep not in seen:
                    seen.add(dep)
                    visit(dep)
                    order.append(dep)

        visit(node_id)
        return [self._nodes[nid] for nid in order]

    # -- mutación segura ------------------------------------------------

    def remove(self, node_id: str) -> KnowledgeNode:
        if node_id not in self._nodes:
            raise KeyError(f"nodo no encontrado: {node_id}")
        referers = [
            n.id for n in self._nodes.values()
            if node_id in n.foundations and n.id != node_id
        ]
        if referers:
            raise ValueError(
                f"no se puede eliminar '{node_id}': lo referencian como "
                f"fundamento {referers}"
            )
        return self._nodes.pop(node_id)

    # -- integridad -----------------------------------------------------

    def validate(self) -> list[str]:
        errors: list[str] = []
        for node in self._nodes.values():
            for dep in node.foundations:
                if dep not in self._nodes:
                    errors.append(f"{node.id} referencia fundamento inexistente {dep}")
            if node.status == EpistemicStatus.THEOREM and not node.foundations:
                errors.append(f"{node.id} es TEOREMA pero no declara fundamentos")
        return errors

    # -- extensión ------------------------------------------------------

    def extend(self, nodes: Iterable[KnowledgeNode]) -> None:
        for node in nodes:
            self.add(node)
