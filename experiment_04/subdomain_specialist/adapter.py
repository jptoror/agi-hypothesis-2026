"""Adapter para el SubdomainSpecialist."""
from __future__ import annotations

from experiment_01.knowledge_graph import KnowledgeGraph
from experiment_01.specialist import DomainContext, KnowledgeGap, Problem

from experiment_03.inter_specialist_protocol import (
    GapRequest,
    GapResponse,
    ResponseStatus,
    SpecialistAdapter,
)
from experiment_03.inter_specialist_protocol.adapter import DelegateFn

from .specialist import SubdomainSpecialist


class SubdomainAdapter(SpecialistAdapter):
    def __init__(
        self,
        graph: KnowledgeGraph,
        domain: str,
        implicit_figure_kind: str | None = None,
        domain_terms: list[list[str]] | None = None,
    ) -> None:
        self.name = domain
        self.graph = graph
        self.specialist = SubdomainSpecialist(
            graph=graph,
            domain=domain,
            implicit_figure_kind=implicit_figure_kind,
            domain_terms=domain_terms,
        )
        self.implicit_figure_kind = implicit_figure_kind
        self.domain_terms = [list(g) for g in (domain_terms or [])]

        outs: set[str] = set()
        for n in graph:
            if n.is_executable():
                outs.update(n.outputs)
        self.output_variables = frozenset(outs)

    def handle(
        self,
        request: GapRequest,
        delegate: DelegateFn | None = None,
    ) -> GapResponse:
        known = dict(request.domain_context.get("known", {}))
        figure_kind = request.domain_context.get(
            "figure_kind",
            self.implicit_figure_kind or "unknown",
        )
        problem = Problem(
            statement=f"(delegado al subdominio {self.name}) obtener {request.target_variable}",
            target=request.target_variable,
            context=DomainContext(kind=figure_kind, known=known),
        )
        result = self.specialist.solve(problem, delegate=delegate)
        if result.success:
            return GapResponse(
                request_id=request.request_id,
                responder=self.name,
                status=ResponseStatus.RESOLVED,
                value={request.target_variable: result.value},
                trace=result.trace,
            )
        return GapResponse(
            request_id=request.request_id,
            responder=self.name,
            status=ResponseStatus.UNRESOLVABLE,
            failure=result.gap or KnowledgeGap(
                missing_variable=request.target_variable,
                context=f"{self.name}: no pudo resolver.",
            ),
        )
