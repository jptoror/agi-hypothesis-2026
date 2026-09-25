"""Test: si el especialista de lenguaje no produce un Problem válido,
álgebra NO se invoca. El resultado es informativo: refleja la causa
del fallo (parse incompleto) sin pretender resolver.
"""
from __future__ import annotations

import unittest

from experiment_07.orchestrator import LanguageToAlgebraOrchestrator


class IncompleteParseDoesNotInvokeAlgebraTest(unittest.TestCase):
    def setUp(self) -> None:
        self.orch = LanguageToAlgebraOrchestrator()

    def test_missing_target_yields_no_problem(self) -> None:
        # Sin variable objetivo (no aparece x/y/z) → no produce Problem.
        result = self.orch.run("resuelve para a=3, b=6")
        self.assertFalse(result.parse_result.is_complete)
        self.assertIsNone(result.parse_result.problem)
        self.assertIsNone(result.solve_result)
        self.assertFalse(result.success)
        self.assertIsNone(result.final_value)

    def test_missing_data_yields_no_problem(self) -> None:
        # Sin asignaciones → la inferencia de kind no dispara
        # → no hay 'kind' → Problem incompleto.
        result = self.orch.run("resuelve x")
        self.assertFalse(result.parse_result.is_complete)
        self.assertIsNone(result.solve_result)
        self.assertFalse(result.success)

    def test_only_language_steps_when_parse_incomplete(self) -> None:
        # No deberían aparecer pasos del especialista de álgebra si
        # el parse fue incompleto.
        result = self.orch.run("resuelve para a=3, b=6")
        for u in result.sourced_steps:
            self.assertEqual(
                u.source, "lenguaje",
                f"se filtró un step de algebra cuando el parse era incompleto: {u.step.node_id}",
            )


if __name__ == "__main__":
    unittest.main()
