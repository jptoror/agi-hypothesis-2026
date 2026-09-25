"""EpistemicMapper: inventaría conocimiento relevante a una consulta.

No infiere. No predice. Para cada semilla declarada por el caller:
  1. Normaliza (lowercase, sin tildes) la semilla y los textos de los
     grafos. Útil porque los grafos de este proyecto están en
     castellano y 'consciencia' / 'conciencia' difieren sólo por la
     tilde.
  2. Busca por substring en:
       - el id del nodo
       - el statement del nodo
       - el rationale del nodo
  3. Si hay al menos un hit, la semilla se marca como CONOCIDA;
     si no, entra a `unknown_concepts`.
  4. Expansión opcional: para cada semilla con hits, reporta hasta
     `max_related` vecinos (foundations directos) como
     'hallazgos colaterales'.

El mapper NO afirma nada más allá de 'este id existe en este grafo
y este string matchea'. La interpretación epistemológica (¿es esto
un gap de tipo X? ¿la ausencia es por frontera del sistema?) la
hace el gap_classifier_v2.
"""
from __future__ import annotations

import unicodedata

from experiment_01.knowledge_graph import KnowledgeGraph, KnowledgeNode

from .concept_query import ConceptQuery
from .inventory import EpistemicInventory, KnowledgeNodeRef


def _normalize(s: str) -> str:
    """lowercase + quita tildes. Normalización reversible a efectos
    de búsqueda — no altera los datos del grafo."""
    s = s.lower()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s


class EpistemicMapper:
    def __init__(self, max_related: int = 5) -> None:
        self.max_related = max_related

    def map(
        self,
        query: ConceptQuery,
        graphs: dict[str, KnowledgeGraph],
    ) -> EpistemicInventory:
        inv = EpistemicInventory(
            query_text=query.question_text,
            seeds=query.seed_concepts,
        )

        for seed in query.seed_concepts:
            hits = self._find_hits(seed, graphs)
            if hits:
                inv.hits_per_seed[seed] = hits
                # Expansión: foundations directas de los nodos hit,
                # excluyendo los que ya son hits de esta misma semilla.
                related = self._expand_related(hits, graphs)
                if related:
                    inv.related_discoveries[seed] = related
            else:
                inv.unknown_concepts.append(seed)

        return inv

    # -- búsqueda -------------------------------------------------------

    @staticmethod
    def _find_hits(
        seed: str,
        graphs: dict[str, KnowledgeGraph],
    ) -> list[KnowledgeNodeRef]:
        needle = _normalize(seed)
        hits: list[KnowledgeNodeRef] = []
        for graph_name, graph in graphs.items():
            for node in graph:
                if (
                    needle in _normalize(node.id)
                    or needle in _normalize(node.statement)
                    or needle in _normalize(node.rationale or "")
                ):
                    hits.append(KnowledgeNodeRef(
                        graph_name=graph_name,
                        node_id=node.id,
                        status=node.status.value,
                        statement=node.statement,
                    ))
        return hits

    # -- expansión ------------------------------------------------------

    def _expand_related(
        self,
        hits: list[KnowledgeNodeRef],
        graphs: dict[str, KnowledgeGraph],
    ) -> list[KnowledgeNodeRef]:
        seen: set[tuple[str, str]] = {(h.graph_name, h.node_id) for h in hits}
        related: list[KnowledgeNodeRef] = []
        for hit in hits:
            graph = graphs.get(hit.graph_name)
            if graph is None or not graph.has(hit.node_id):
                continue
            node = graph.get(hit.node_id)
            for foundation_id in node.foundations:
                key = (hit.graph_name, foundation_id)
                if key in seen:
                    continue
                if not graph.has(foundation_id):
                    continue
                dep: KnowledgeNode = graph.get(foundation_id)
                related.append(KnowledgeNodeRef(
                    graph_name=hit.graph_name,
                    node_id=dep.id,
                    status=dep.status.value,
                    statement=dep.statement,
                ))
                seen.add(key)
                if len(related) >= self.max_related:
                    return related
        return related
