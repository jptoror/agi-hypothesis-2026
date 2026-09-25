"""Adapter del GeometrySpecialist al protocolo inter-dominio.

Responsabilidades:
  - Declarar las variables que Geometría puede producir
    (output_variables) para el registry.
  - Traducir un GapRequest en un Problem que GeometrySpecialist entiende,
    reconstruyendo la Figure desde `domain_context`.
  - Empaquetar el SolveResult como GapResponse con trace incluida.

No añade lógica de razonamiento — sólo es el traductor entre dialectos.
"""
from __future__ import annotations

from experiment_01.knowledge_graph import KnowledgeGraph
from experiment_01.specialist import (
    DomainContext,
    GeometrySpecialist,
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


class GeometryAdapter(SpecialistAdapter):
    name = "geometry"

    # Variables que el grafo de Geometría sabe producir como salida
    # ejecutable. Se deriva dinámicamente del grafo — así no
    # duplicamos la lista en código y si el grafo crece (p. ej. tras
    # consolidar un teorema del exp_02), el adapter lo refleja.
    def __init__(self, graph: KnowledgeGraph) -> None:
        self.graph = graph
        self.specialist = GeometrySpecialist(graph)
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
        figure_kind = request.domain_context.get("figure_kind", "unknown")
        known = dict(request.domain_context.get("known", {}))
        # Sembramos el DomainContext con los valores conocidos que el
        # requester nos pasó. Geometría no toca variables físicas (m, Ec),
        # pero las dejamos en `known` por si algún teorema futuro las
        # cruza — son inofensivas porque los nodos actuales no las usan.
        ctx = DomainContext(kind=figure_kind, known=known)
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
            context="Geometría no pudo resolver la consulta delegada.",
        )
        return GapResponse(
            request_id=request.request_id,
            responder=self.name,
            status=ResponseStatus.UNRESOLVABLE,
            value=None,
            trace=result.trace if result.trace.steps else None,
            failure=gap,
        )
