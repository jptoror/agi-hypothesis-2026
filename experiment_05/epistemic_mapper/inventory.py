"""Inventario epistémico: el output del EpistemicMapper.

Proyección estructurada y auditable de lo que el sistema sabe
respecto a una consulta. Dos principios:

  1. Por grafo, no global — preserva 'cada dominio sabe lo suyo'.
  2. Sin afirmaciones sobre semántica — sólo presencia/ausencia
     de identificadores y substrings en statements.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class KnowledgeNodeRef:
    """Proyección ligera de un nodo encontrado durante el mapeo.

    No lleva `compute` ni `foundations` — es metadato suficiente para
    que un clasificador posterior decida qué hacer. Evita acoplar el
    inventario a la clase KnowledgeNode (que podría evolucionar).
    """

    graph_name: str
    node_id: str
    status: str
    statement: str

    def render(self) -> str:
        return f"[{self.status:11}] {self.graph_name}::{self.node_id} — {self.statement}"


@dataclass
class EpistemicInventory:
    """Lo que el sistema encontró (y no encontró) para una consulta.

    Campos:
      - hits_per_seed: por cada semilla del caller, los nodos que
        coinciden por substring en id o statement, agrupados por grafo.
        Si una semilla no tiene hits en NINGÚN grafo, aparece en
        `unknown_concepts`.
      - unknown_concepts: semillas sin coincidencia en ningún grafo.
      - related_discoveries: por cada semilla encontrada, hasta N
        nodos 'vecinos' (foundations directas de los hits) que el
        mapper descubrió al expandir. Son hallazgos colaterales —
        cosa que el sistema sabe aunque el caller no preguntara.
    """

    query_text: str
    seeds: tuple[str, ...]
    hits_per_seed: dict[str, list[KnowledgeNodeRef]] = field(default_factory=dict)
    unknown_concepts: list[str] = field(default_factory=list)
    related_discoveries: dict[str, list[KnowledgeNodeRef]] = field(default_factory=dict)

    # -- métricas --------------------------------------------------------

    @property
    def known_concepts(self) -> list[str]:
        return [s for s in self.seeds if s not in self.unknown_concepts]

    def coverage_ratio(self) -> float:
        """Proporción de semillas con al menos un hit en algún grafo."""
        if not self.seeds:
            return 0.0
        return len(self.known_concepts) / len(self.seeds)

    # -- render ---------------------------------------------------------

    def render(self) -> str:
        lines = [
            "=" * 72,
            "INVENTARIO EPISTÉMICO",
            "=" * 72,
            f"pregunta: {self.query_text}",
            f"semillas: {len(self.seeds)}",
            "",
            "── RECONOCIMIENTO POR SEMILLA ──",
        ]
        for seed in self.seeds:
            hits = self.hits_per_seed.get(seed, [])
            if not hits:
                lines.append(f"  ✗ '{seed}'  →  no encontrado en ningún grafo")
                continue
            graphs = sorted({h.graph_name for h in hits})
            lines.append(
                f"  ✓ '{seed}'  →  encontrado en: {', '.join(graphs)}"
            )
            for h in hits:
                lines.append(f"      · {h.render()}")

        lines.append("")
        lines.append("── HALLAZGOS COLATERALES (fundamentos vecinos) ──")
        if not self.related_discoveries:
            lines.append("  (ninguno)")
        else:
            for seed, refs in self.related_discoveries.items():
                lines.append(f"  · a partir de '{seed}':")
                for r in refs:
                    lines.append(f"      ↪ {r.render()}")

        lines.append("")
        lines.append("── RESUMEN EPISTÉMICO ──")
        lines.append(
            f"  reconocidas: {len(self.known_concepts)}/{len(self.seeds)} "
            f"(coverage={self.coverage_ratio():.2f})"
        )
        if self.unknown_concepts:
            lines.append(f"  desconocidas (candidatas a gap): {self.unknown_concepts}")
        return "\n".join(lines)
