"""Resultado de la síntesis de un subdominio emergente.

Un SynthesisResult es la proyección auditable de la operación:
proyecta exactamente qué se creó y de dónde vino cada parte. La
auditabilidad del origen de cada nodo es clave para el paper —
permite responder con precisión "¿qué parte de este subdominio es
nueva (binding) y qué parte se heredó?".
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from experiment_01.knowledge_graph import KnowledgeGraph
from experiment_04.pattern_detector import Pattern


def _utc_iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class SynthesisResult:
    subgraph: KnowledgeGraph
    specialist_name: str
    binding_nodes: list[str]
    nodes_from_initiator: list[str]
    nodes_from_responder: list[str]
    pattern: Pattern
    timestamp: str

    @classmethod
    def new(
        cls,
        subgraph: KnowledgeGraph,
        specialist_name: str,
        binding_nodes: list[str],
        nodes_from_initiator: list[str],
        nodes_from_responder: list[str],
        pattern: Pattern,
    ) -> "SynthesisResult":
        return cls(
            subgraph=subgraph,
            specialist_name=specialist_name,
            binding_nodes=binding_nodes,
            nodes_from_initiator=nodes_from_initiator,
            nodes_from_responder=nodes_from_responder,
            pattern=pattern,
            timestamp=_utc_iso_now(),
        )

    def render(self) -> str:
        lines = [
            f"SÍNTESIS [{self.timestamp}]",
            f"  subdominio: {self.specialist_name}",
            f"  subgrafo: {len(self.subgraph)} nodos",
            f"  bindings consolidados: {self.binding_nodes}",
            f"  nodos heredados del iniciador "
            f"({self.pattern.sample_record.initiator if self.pattern.sample_record else '?'}): "
            f"{self.nodes_from_initiator}",
            f"  nodos heredados del responder "
            f"({self.pattern.sample_record.responder if self.pattern.sample_record else '?'}): "
            f"{self.nodes_from_responder}",
            f"  patrón de origen: count={self.pattern.count}, "
            f"problem_ids={sorted(self.pattern.problem_ids)}",
        ]
        return "\n".join(lines)
