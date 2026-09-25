"""Factory del especialista de pilas.

Combina:
  - el grafo base de complejidad (experiment_09)
  - el documento data_structures_stack.md (con marcadores
    **Complejidad:** apuntando a ids del grafo base)

Y produce un especialista listo en la registry. Reutiliza
SpecialistFactory del exp_06 con `base_graph=...` para que el
builder importe los nodos de complejidad referenciados por el
documento, con cierre transitivo.

El especialista resultante razona sobre un grafo único que mezcla:
  - los nodos del documento (def.stack, def.op.*, thm.stack.*)
  - los nodos del grafo base de complejidad importados
    (def.complexity.O1 y su fundamento ax.complexity.total_order)
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
    Path(__file__).resolve().parent.parent
    / "sample_documents" / "data_structures_stack.md"
)


@dataclass
class StackRegistrationResult:
    """Wrapper sobre RegistrationResult que añade el grafo base
    usado, para auditoría posterior."""

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
            "STACK SPECIALIST REGISTRATION",
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


class StackSpecialistFactory:
    """Construye el especialista de pilas anclado al grafo base de
    complejidad."""

    def __init__(
        self,
        registry: SpecialistRegistry | None = None,
        domain_terms: list[list[str]] | None = None,
    ) -> None:
        self.registry = registry or SpecialistRegistry()
        # No declaramos términos de dominio porque las condiciones
        # del grafo de pilas son numéricas o prosa libre — sin
        # nombres de figuras geométricas. El default vacío es lo
        # correcto.
        self.factory = SpecialistFactory(
            registry=self.registry,
            implicit_figure_kind="stack",
            domain_terms=domain_terms,
        )

    def build(
        self,
        doc_path: str | Path = _DEFAULT_DOC,
        specialist_name: str | None = None,
    ) -> StackRegistrationResult:
        base = build_complexity_base_graph()
        result = self.factory.from_document(
            path=doc_path,
            specialist_name=specialist_name or "stack",
            base_graph=base,
        )
        # Conteos para auditoría.
        doc_count = len(result.parse_report.nodes_extracted)
        base_count = (
            len(result.build_report.graph) - doc_count
            if result.build_report.graph else 0
        )
        return StackRegistrationResult(
            underlying=result,
            base_graph_node_count=base_count,
            document_node_count=doc_count,
        )
