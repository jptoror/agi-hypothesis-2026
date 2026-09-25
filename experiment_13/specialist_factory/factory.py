"""Factory del especialista de colas — paralelo al StackSpecialistFactory.

Reutiliza el pipeline completo del exp_06 (parser + builder) y el
grafo base de complejidad del exp_09 sin modificación. La única
diferencia operativa es:
  - documento de partida: data_structures_queue.md
  - implicit_figure_kind="queue"
  - specialist_name="queue"

Demuestra que el patrón es reutilizable para cualquier nuevo
dominio de estructuras de datos: basta con un documento que use
la convención de marcadores y un factory que apunte a él.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from experiment_03.inter_specialist_protocol import SpecialistRegistry
from experiment_06.specialist_factory import (
    RegistrationResult,
    SpecialistFactory,
)

from experiment_09.knowledge_graph import build_complexity_base_graph


_DEFAULT_DOC = (
    Path(__file__).resolve().parent.parent.parent
    / "experiment_09" / "sample_documents" / "data_structures_queue.md"
)


@dataclass
class QueueRegistrationResult:
    """Wrapper sobre RegistrationResult con conteos de auditoría
    distinguiendo nodos del documento vs nodos importados del base."""

    underlying: RegistrationResult
    base_graph_node_count: int
    document_node_count: int

    @property
    def specialist_name(self) -> str:
        return self.underlying.specialist_name

    @property
    def specialist(self):
        return self.underlying.specialist

    @property
    def adapter(self):
        return self.underlying.adapter

    @property
    def registered(self) -> bool:
        return self.underlying.registered

    @property
    def graph(self):
        return self.underlying.build_report.graph

    @property
    def errors(self) -> list[str]:
        return self.underlying.errors

    def render(self) -> str:
        lines = [
            "=" * 72,
            "QUEUE SPECIALIST REGISTRATION",
            "=" * 72,
            f"specialist_name: {self.specialist_name}",
            f"registered:      {self.registered}",
            f"nodos del documento:    {self.document_node_count}",
            f"nodos del base (refs):  {self.base_graph_node_count}",
            f"nodos en grafo final:   "
            f"{len(self.graph) if self.graph else None}",
        ]
        if self.errors:
            lines.append("errores:")
            for e in self.errors:
                lines.append(f"  ✗ {e}")
        return "\n".join(lines)


class QueueSpecialistFactory:
    """Construye el especialista de colas anclado al grafo base de
    complejidad."""

    def __init__(
        self,
        registry: SpecialistRegistry | None = None,
        domain_terms: list[list[str]] | None = None,
    ) -> None:
        self.registry = registry or SpecialistRegistry()
        self.factory = SpecialistFactory(
            registry=self.registry,
            implicit_figure_kind="queue",
            domain_terms=domain_terms,
        )

    def build(
        self,
        doc_path: str | Path = _DEFAULT_DOC,
        specialist_name: str | None = None,
    ) -> QueueRegistrationResult:
        base = build_complexity_base_graph()
        result = self.factory.from_document(
            path=doc_path,
            specialist_name=specialist_name or "queue",
            base_graph=base,
        )
        doc_count = len(result.parse_report.nodes_extracted)
        base_count = (
            len(result.build_report.graph) - doc_count
            if result.build_report.graph else 0
        )
        return QueueRegistrationResult(
            underlying=result,
            base_graph_node_count=base_count,
            document_node_count=doc_count,
        )
