"""Test: dos especialistas que se consultan mutuamente activan la
detección de ciclos del orchestrator en vez de loopear indefinidamente.

Estructura del escenario:
  - A necesita 'xb' para producir 'xa' → delega a B.
  - B necesita 'xa' para producir 'xb' → delega a A.
  El orchestrator debe abortar con CYCLE_DETECTED.
"""
from __future__ import annotations

import unittest

from experiment_01.specialist import DomainContext, KnowledgeGap, Problem, ReasoningTrace

from experiment_03.inter_specialist_protocol import (
    GapRequest,
    GapResponse,
    ResponseStatus,
    SpecialistAdapter,
    SpecialistRegistry,
)
from experiment_03.inter_specialist_protocol.adapter import DelegateFn
from experiment_03.orchestrator import CrossDomainOrchestrator


class _MutualDelegator(SpecialistAdapter):
    """Adapter mock que, al recibir una consulta por su output, delega
    siempre al otro especialista pidiendo una variable específica.

    Si el delegate devuelve RESOLVED, empaqueta un value trivial y
    devuelve RESOLVED. Si la delegación falla (ciclo/depth/mismatch),
    propaga el error como UNRESOLVABLE.

    La clave del escenario: el adapter NO sabe resolver localmente.
    Sólo sabe 'para computar X, necesito Y del otro'. Si los dos
    adapters se piden cosas cruzadas, hay ciclo.
    """

    def __init__(self, name: str, produces: str, needs_from_peer: str) -> None:
        self.name = name
        self.output_variables = frozenset({produces})
        self._needs = needs_from_peer

    # Soporta también el uso como iniciador (no relevante en este test).
    class _FakeSpecialist:
        def __init__(self, outer: "_MutualDelegator") -> None:
            self._outer = outer

        def solve(self, problem, delegate=None):  # pragma: no cover - inalcanzable
            raise NotImplementedError

    @property
    def specialist(self):  # pragma: no cover - no se usa en este test
        return self._FakeSpecialist(self)

    def handle(
        self,
        request: GapRequest,
        delegate: DelegateFn | None = None,
    ) -> GapResponse:
        if delegate is None:
            # Sin canal de delegación, admitimos que no podemos.
            return GapResponse(
                request_id=request.request_id,
                responder=self.name,
                status=ResponseStatus.UNRESOLVABLE,
                failure=KnowledgeGap(
                    missing_variable=request.target_variable,
                    context=f"{self.name}: sin delegate no puedo resolver.",
                ),
            )

        sub = GapRequest(
            requester=self.name,
            target_variable=self._needs,
            domain_context=dict(request.domain_context),
            rationale=f"{self.name} necesita '{self._needs}' para producir "
                      f"'{request.target_variable}'.",
            depth=0,
        )
        sub_resp = delegate(sub)

        if sub_resp.status != ResponseStatus.RESOLVED:
            # Propagamos el fallo con el status original. El contexto
            # del gap incluye el status.value literal para que un test
            # pueda asertar sobre él aunque el gap viaje a través de
            # varios saltos y se re-envuelva.
            inner_ctx = sub_resp.failure.context if sub_resp.failure else ""
            return GapResponse(
                request_id=request.request_id,
                responder=self.name,
                status=sub_resp.status,
                failure=KnowledgeGap(
                    missing_variable=request.target_variable,
                    context=(
                        f"{self.name}: sub-consulta a '{self._needs}' "
                        f"terminó en {sub_resp.status.value}. {inner_ctx}"
                    ).strip(),
                ),
            )

        # Éxito trivial (valor fijo); en este test nunca debería llegar
        # porque los adapters son cíclicos entre sí.
        return GapResponse(
            request_id=request.request_id,
            responder=self.name,
            status=ResponseStatus.RESOLVED,
            value={request.target_variable: 0.0},
            trace=ReasoningTrace(),
        )


class CycleDetectionTest(unittest.TestCase):
    def test_cycle_between_two_specialists_aborts_with_cycle_detected(self) -> None:
        # A produce 'xa' necesitando 'xb'; B produce 'xb' necesitando 'xa'.
        a = _MutualDelegator(name="A", produces="xa", needs_from_peer="xb")
        b = _MutualDelegator(name="B", produces="xb", needs_from_peer="xa")

        registry = SpecialistRegistry()
        registry.register(a)
        registry.register(b)
        orch = CrossDomainOrchestrator(registry=registry, max_depth=10)

        # Iniciador artificial: un tercer adapter que delega pidiendo 'xa'
        # una sola vez, para arrancar la cadena A→B→A.
        class _Starter(SpecialistAdapter):
            name = "starter"
            output_variables = frozenset({"result"})

            class _Spec:
                def solve(self, problem, delegate=None):
                    sub = GapRequest(
                        requester="starter",
                        target_variable="xa",
                        rationale="kick off the A↔B cycle",
                        depth=0,
                    )
                    resp = delegate(sub)
                    from experiment_01.specialist import SolveResult
                    if resp.status == ResponseStatus.RESOLVED:
                        return SolveResult(
                            problem=problem, success=True,
                            value=resp.value.get("xa"),
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

        registry.register(_Starter())

        problem = Problem(
            statement="(test) ciclo A↔B",
            target="result",
            context=DomainContext(kind="mock", known={}),
        )
        result = orch.solve(problem, initiating_domain="starter")

        self.assertFalse(result.solve_result.success)
        self.assertIsNone(result.solve_result.value)
        gap = result.solve_result.gap
        self.assertIsNotNone(gap)
        # La cadena que observamos es:
        #   starter pide xa       → A lo maneja;
        #     A delega pidiendo xb → B lo maneja;
        #       B delega pidiendo xa → A lo maneja de nuevo;
        #         A delega pidiendo xb → CYCLE_DETECTED.
        # El gap que vuelve al iniciador menciona ese estado.
        self.assertIn(
            ResponseStatus.CYCLE_DETECTED.value,
            gap.context,
            f"el gap debería indicar CYCLE_DETECTED; fue: {gap.context!r}",
        )


if __name__ == "__main__":
    unittest.main()
