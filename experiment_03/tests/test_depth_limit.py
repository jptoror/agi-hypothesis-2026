"""Test: cadena lineal de delegación A→B→C→D→E→F; con max_depth=4 el
orchestrator aborta con DELEGATION_DEPTH_EXCEEDED antes de llegar al
final.

Este test verifica la 'fatiga cognitiva' del sistema: un sistema con
metacognición real sabe cuándo una cadena de dependencias es demasiado
larga y aborta para buscar otra ruta.
"""
from __future__ import annotations

import unittest

from experiment_01.specialist import (
    DomainContext,
    KnowledgeGap,
    Problem,
    ReasoningTrace,
    SolveResult,
)

from experiment_03.inter_specialist_protocol import (
    GapRequest,
    GapResponse,
    ResponseStatus,
    SpecialistAdapter,
    SpecialistRegistry,
)
from experiment_03.inter_specialist_protocol.adapter import DelegateFn
from experiment_03.orchestrator import CrossDomainOrchestrator


class _ChainLink(SpecialistAdapter):
    """Eslabón de una cadena lineal: produce `produces` delegando a
    `needs` si está definido. Si `needs` es None, resuelve con un valor
    fijo sin delegar (eslabón terminal).
    """

    def __init__(self, name: str, produces: str, needs: str | None) -> None:
        self.name = name
        self.output_variables = frozenset({produces})
        self._produces = produces
        self._needs = needs

    @property
    def specialist(self):  # pragma: no cover - no usado en este test
        raise NotImplementedError

    def handle(
        self,
        request: GapRequest,
        delegate: DelegateFn | None = None,
    ) -> GapResponse:
        if self._needs is None:
            # Eslabón terminal: devuelve un valor fijo.
            return GapResponse(
                request_id=request.request_id,
                responder=self.name,
                status=ResponseStatus.RESOLVED,
                value={self._produces: 1.0},
                trace=ReasoningTrace(),
            )

        if delegate is None:
            return GapResponse(
                request_id=request.request_id,
                responder=self.name,
                status=ResponseStatus.UNRESOLVABLE,
                failure=KnowledgeGap(
                    missing_variable=self._produces,
                    context=f"{self.name}: sin delegate no puedo resolver.",
                ),
            )

        sub = GapRequest(
            requester=self.name,
            target_variable=self._needs,
            domain_context=dict(request.domain_context),
            rationale=f"{self.name} necesita '{self._needs}'",
            depth=0,
        )
        sub_resp = delegate(sub)

        if sub_resp.status != ResponseStatus.RESOLVED:
            inner = sub_resp.failure.context if sub_resp.failure else ""
            return GapResponse(
                request_id=request.request_id,
                responder=self.name,
                status=sub_resp.status,
                failure=KnowledgeGap(
                    missing_variable=self._produces,
                    context=(
                        f"{self.name}: sub-consulta a '{self._needs}' "
                        f"terminó en {sub_resp.status.value}. {inner}"
                    ).strip(),
                ),
            )
        # Éxito transparente: devolvemos el mismo valor que nos llegó,
        # bajo nuestra clave.
        return GapResponse(
            request_id=request.request_id,
            responder=self.name,
            status=ResponseStatus.RESOLVED,
            value={self._produces: list(sub_resp.value.values())[0]},
            trace=sub_resp.trace,
        )


class _Starter(SpecialistAdapter):
    """Iniciador minimalista: al resolver, delega una vez pidiendo 'xa'
    y propaga el resultado.
    """

    name = "starter"
    output_variables = frozenset({"result"})

    class _Spec:
        def solve(self, problem, delegate=None):
            sub = GapRequest(
                requester="starter",
                target_variable="xa",
                rationale="kick off the chain",
                depth=0,
            )
            resp = delegate(sub)
            if resp.status == ResponseStatus.RESOLVED:
                return SolveResult(
                    problem=problem, success=True,
                    value=list(resp.value.values())[0],
                    trace=ReasoningTrace(), gap=None,
                    relevant_nodes=[],
                )
            inner = resp.failure.context if resp.failure else ""
            return SolveResult(
                problem=problem, success=False, value=None,
                trace=ReasoningTrace(),
                gap=KnowledgeGap(
                    missing_variable="xa",
                    context=f"starter: {resp.status.value}. {inner}".strip(),
                ),
                relevant_nodes=[],
            )

    specialist = _Spec()

    def handle(self, request, delegate=None):  # pragma: no cover
        raise NotImplementedError


class DepthLimitTest(unittest.TestCase):
    def test_chain_exceeding_max_depth_aborts_with_depth_exceeded(self) -> None:
        # Cadena: starter → A(xa) → B(xb) → C(xc) → D(xd) → E(xe) → F(xf terminal).
        # Con max_depth=4, el orchestrator aceptará hasta depth 4 y
        # abortará cuando algún request llegue con depth>4.
        links = [
            _ChainLink("A", produces="xa", needs="xb"),
            _ChainLink("B", produces="xb", needs="xc"),
            _ChainLink("C", produces="xc", needs="xd"),
            _ChainLink("D", produces="xd", needs="xe"),
            _ChainLink("E", produces="xe", needs="xf"),
            _ChainLink("F", produces="xf", needs=None),
        ]
        registry = SpecialistRegistry()
        for link in links:
            registry.register(link)
        registry.register(_Starter())

        orch = CrossDomainOrchestrator(registry=registry, max_depth=4)

        problem = Problem(
            statement="(test) cadena larga",
            target="result",
            context=DomainContext(kind="mock", known={}),
        )
        result = orch.solve(problem, initiating_domain="starter")

        self.assertFalse(result.solve_result.success)
        self.assertIsNone(result.solve_result.value)

        gap = result.solve_result.gap
        self.assertIsNotNone(gap)
        self.assertIn(
            ResponseStatus.DELEGATION_DEPTH_EXCEEDED.value,
            gap.context,
            f"el gap debería indicar DELEGATION_DEPTH_EXCEEDED; fue: {gap.context!r}",
        )

        # Sanity: se ejecutaron algunas delegaciones pero MENOS de las
        # 6 necesarias para llegar a F. Esto es la evidencia de que el
        # sistema 'abandonó' antes de agotar la cadena.
        self.assertLess(
            len(result.delegation_history), 6,
            f"debería haber abortado antes de 6 delegaciones; "
            f"se hicieron {len(result.delegation_history)}",
        )


if __name__ == "__main__":
    unittest.main()
