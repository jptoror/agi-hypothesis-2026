"""Test canónico del experimento 07: la instrucción
'resuelve x para a=3, b=6' produce x = -2.0 con la traza esperada
de 5 pasos (4 lenguaje + 1 álgebra), cada uno con su procedencia
correctamente marcada.
"""
from __future__ import annotations

import unittest

from experiment_07.orchestrator import LanguageToAlgebraOrchestrator


class CanonicalPipelineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.orch = LanguageToAlgebraOrchestrator()
        self.result = self.orch.run("resuelve x para a=3, b=6")

    def test_pipeline_resolves_to_minus_two(self) -> None:
        self.assertTrue(self.result.success)
        self.assertEqual(self.result.final_value, -2.0)
        self.assertEqual(self.result.parse_result.problem.target, "x")
        self.assertEqual(
            self.result.parse_result.problem.context.kind, "linear_equation"
        )
        self.assertEqual(
            self.result.parse_result.problem.context.known,
            {"a": 3.0, "b": 6.0},
        )

    def test_unified_steps_count_is_five(self) -> None:
        # 4 del lenguaje + 1 de álgebra.
        self.assertEqual(len(self.result.unified_steps), 5)
        self.assertEqual(len(self.result.sourced_steps), 5)

    def test_sourced_steps_have_correct_provenance(self) -> None:
        sources = [u.source for u in self.result.sourced_steps]
        self.assertEqual(sources, ["lenguaje"] * 4 + ["algebra"])

    def test_first_four_steps_are_expected_language_nodes(self) -> None:
        ids = [u.step.node_id for u in self.result.sourced_steps[:4]]
        self.assertEqual(ids, [
            "def.instruction.solve",
            "def.target_marker.variable",
            "def.data.assignment",
            "def.kind.linear_equation",
        ])

    def test_last_step_is_algebra_solution(self) -> None:
        last = self.result.sourced_steps[-1]
        self.assertEqual(last.source, "algebra")
        self.assertEqual(last.step.node_id, "thm.solucion_general")
        self.assertEqual(last.step.outputs.get("x"), -2.0)


if __name__ == "__main__":
    unittest.main()
