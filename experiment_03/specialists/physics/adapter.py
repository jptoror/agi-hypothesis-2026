"""Adapter del PhysicsSpecialist al protocolo inter-dominio.

En el escenario del experimento 03 Física es el iniciador y Geometría el
responder, así que `handle` casi no se usa. Se implementa por simetría
y para pruebas futuras donde Física pueda ser delegada.
"""
from __future__ import annotations

from experiment_01.knowledge_graph import KnowledgeGraph
from experiment_01.specialist import (
    DomainContext,
    KnowledgeGap,
    Problem,
)

from experiment_03.inter_specialist_protocol import (
    GapRequest,
    GapResponse,
    ResponseStatus,
    SpecialistAdapter,
)
from experiment_03.inter_specialist_protocol.adapter import DelegateFn

from .specialist import PhysicsSpecialist


class PhysicsAdapter(SpecialistAdapter):
    name = "physics"

    def __init__(self, graph: KnowledgeGraph) -> None:
        self.graph = graph
        self.specialist = PhysicsSpecialist(graph)
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
        ctx = DomainContext(kind="physics.object", known=known)
        problem = Problem(
            statement=f"(delegado) obtener {request.target_variable}",
            target=request.target_variable,
            context=ctx,
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
        gap = result.gap or KnowledgeGap(
            missing_variable=request.target_variable,
            context="Física no pudo resolver la consulta delegada.",
        )
        return GapResponse(
            request_id=request.request_id,
            responder=self.name,
            status=ResponseStatus.UNRESOLVABLE,
            failure=gap,
        )
