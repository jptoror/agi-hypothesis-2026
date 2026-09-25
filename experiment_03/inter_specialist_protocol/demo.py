"""Demo del protocolo inter-especialista con adapters mock.

Ejercita los cinco principios:
  1. Mensajes estructurados (GapRequest/GapResponse).
  2. Descubrimiento vía registry (A+C: output_variables + can_handle).
  3. Traza transitiva (sub-traza incrustada en ReasoningStep).
  4. Detección de ciclos (pila activa en DelegationContext).
  5. Límite de profundidad (depth > max_depth aborta).

Uso:
    python -m experiment_03.inter_specialist_protocol.demo
"""
from __future__ import annotations

from experiment_01.specialist import KnowledgeGap, ReasoningStep, ReasoningTrace

from .adapter import SpecialistAdapter
from .delegation_context import DelegationContext
from .messages import GapRequest, GapResponse, ResponseStatus
from .registry import SpecialistRegistry


class _MockResponder(SpecialistAdapter):
    """Adapter mock que devuelve un valor fijo para una variable fija."""

    def __init__(self, name: str, variable: str, value: float) -> None:
        self.name = name
        self.output_variables = frozenset({variable})
        self._variable = variable
        self._value = value

    def handle(self, request: GapRequest) -> GapResponse:
        trace = ReasoningTrace()
        trace.add(ReasoningStep(
            index=1,
            node_id=f"mock.{self.name}.produce_{self._variable}",
            node_statement=f"(mock) {self._variable} = {self._value}",
            purpose=f"responder a {request.requester}",
            inputs={},
            outputs={self._variable: self._value},
            rationale="valor fijo del adapter mock.",
        ))
        return GapResponse(
            request_id=request.request_id,
            responder=self.name,
            status=ResponseStatus.RESOLVED,
            value={self._variable: self._value},
            trace=trace,
        )


def main() -> None:
    # --- Principio 1 + 2: mensajes estructurados y registry ---
    reg = SpecialistRegistry()
    reg.register(_MockResponder("geometry_mock", "l", 5.656854))

    req = GapRequest(
        requester="physics_mock",
        target_variable="l",
        domain_context={"figure_kind": "square", "d": 8.0},
        rationale="necesito el lado para computar v.",
    )
    print(req.render())

    adapter = reg.find_for(req)
    assert adapter is not None, "registry debería encontrar el responder"
    resp = adapter.handle(req)
    print(resp.render())
    print()

    # --- Principio 3: traza transitiva ---
    parent_trace = ReasoningTrace()
    parent_trace.add(ReasoningStep(
        index=1,
        node_id="delegated:geometry_mock:mock.geometry_mock.produce_l",
        node_statement="(delegación a geometry_mock para obtener l)",
        purpose="Física delega la obtención de l",
        inputs={},
        outputs=resp.value or {},
        rationale=f"request_id={resp.request_id[:8]}",
        delegated_trace=resp.trace,
    ))
    print("Traza padre con sub-traza delegada:")
    print(parent_trace.render())
    print()

    # --- Principio 4: detección de ciclos ---
    ctx = DelegationContext(max_depth=5)
    cycle_req = GapRequest(requester="physics_mock", target_variable="l", depth=1)
    with ctx.track(cycle_req):
        assert ctx.is_cycle(cycle_req), "mismo par (requester, target) debería ser ciclo"
        print(f"Principio 4 ✓ — ciclo detectado para {cycle_req.render()}")
    assert not ctx.is_cycle(cycle_req), "al salir del context manager, el ciclo debe limpiarse"
    print()

    # --- Principio 5: límite de profundidad ---
    deep_req = GapRequest(requester="x", target_variable="y", depth=6)
    assert ctx.exceeds_depth(deep_req), "depth=6 debe exceder max_depth=5"
    print(f"Principio 5 ✓ — depth={deep_req.depth} > max_depth={ctx.max_depth} "
          f"→ el orchestrator abortará con DELEGATION_DEPTH_EXCEEDED.")


if __name__ == "__main__":
    main()
