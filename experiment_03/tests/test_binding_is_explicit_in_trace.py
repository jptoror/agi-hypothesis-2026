"""Test: los bindings ontológicos declarados en el problema aparecen
como un paso explícito en la traza, entre el momento en que el
iniciador detecta el gap y el momento en que resuelve con los valores
obtenidos del especialista delegado.

Criterio científico: nada en el razonamiento debe ser silencioso. Un
binding no es una inferencia del sistema — es un dato del enunciado —
y la traza debe hacerlo legible como tal.
"""
from __future__ import annotations

import unittest

from experiment_01.knowledge_graph import build_geometry_2d_graph
from experiment_01.specialist import DomainContext, Problem

from experiment_03.inter_specialist_protocol import SpecialistRegistry
from experiment_03.orchestrator import CrossDomainOrchestrator
from experiment_03.specialists.geometry import GeometryAdapter
from experiment_03.specialists.physics import PhysicsAdapter, build_physics_graph


class BindingIsExplicitInTraceTest(unittest.TestCase):
    def _run_canonical_problem(self):
        registry = SpecialistRegistry()
        registry.register(GeometryAdapter(build_geometry_2d_graph()))
        registry.register(PhysicsAdapter(build_physics_graph()))
        orch = CrossDomainOrchestrator(registry=registry, max_depth=5)

        problem = Problem(
            statement=(
                "¿Cuánta energía cinética tiene un objeto de masa 2 kg "
                "a velocidad igual al lado de un cuadrado de diagonal 8?"
            ),
            target="Ec",
            context=DomainContext(
                kind="physics.object",
                known={"m": 2.0, "d": 8.0},
            ),
            variable_bindings={"v": "l"},
            delegation_hints={"figure_kind": "square"},
        )
        return orch.solve(problem, initiating_domain="physics")

    def test_trace_contains_exactly_one_binding_step(self) -> None:
        result = self._run_canonical_problem()
        self.assertTrue(result.solve_result.success)
        self.assertAlmostEqual(result.solve_result.value, 32.0, places=10)

        steps = result.solve_result.trace.steps
        binding_steps = [s for s in steps if s.node_id.startswith("binding:")]
        self.assertEqual(
            len(binding_steps), 1,
            f"se esperaba exactamente 1 paso binding:*, hubo {len(binding_steps)}"
        )
        self.assertEqual(binding_steps[0].node_id, "binding:v→l")

    def test_binding_step_is_before_delegation_and_before_final_resolution(self) -> None:
        result = self._run_canonical_problem()
        steps = result.solve_result.trace.steps
        idx_binding = next(
            i for i, s in enumerate(steps) if s.node_id.startswith("binding:")
        )
        idx_delegation = next(
            i for i, s in enumerate(steps) if s.node_id.startswith("delegated:")
        )
        idx_final = next(
            i for i, s in enumerate(steps) if s.node_id == "thm.kinetic_energy"
        )

        # El binding se emite antes de la delegación (es la razón por la
        # que el orchestrator rescribe el target) y antes de la resolución
        # final del iniciador.
        self.assertLess(idx_binding, idx_delegation)
        self.assertLess(idx_delegation, idx_final)

    def test_binding_rationale_marks_it_as_ontological_link(self) -> None:
        result = self._run_canonical_problem()
        step = next(
            s for s in result.solve_result.trace.steps
            if s.node_id.startswith("binding:")
        )
        self.assertIn("vínculo ontológico", step.rationale)
        self.assertIn("no inferido", step.rationale)


if __name__ == "__main__":
    unittest.main()
