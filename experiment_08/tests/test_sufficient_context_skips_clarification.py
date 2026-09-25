"""Test 2: con hints={'domain': 'algebra'} declarado por el caller,
el orchestrator no emite ClarificationRequest y procede al
SolveResult — incluso si el bus tendría candidatos múltiples.

Usa el orchestrator REAL con bus realista (álgebra). Esa
configuración tiene un único candidato y por tanto es SUFFICIENT
sin hints también — pero el test verifica que CON hints también lo
es, y que la resolución se completa.
"""
from __future__ import annotations

import unittest

from experiment_08.orchestrator import ClarifyingOrchestrator


class SufficientContextSkipsClarificationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.orch = ClarifyingOrchestrator()
        self.instruction = "calcula el coeficiente para x con a=3, b=6"

    def test_with_hint_no_clarification(self) -> None:
        result = self.orch.run(self.instruction, hints={"domain": "algebra"})
        self.assertIsNone(result.clarification_request)

    def test_with_hint_solve_result_present(self) -> None:
        result = self.orch.run(self.instruction, hints={"domain": "algebra"})
        self.assertIsNotNone(result.solve_result)
        self.assertTrue(result.success)
        self.assertEqual(result.final_value, -2.0)

    def test_assessment_records_sufficient_by_hint(self) -> None:
        result = self.orch.run(self.instruction, hints={"domain": "algebra"})
        # Al menos una assessment SUFFICIENT con domain='algebra'
        # (el hint se aplica al primer concepto evaluado).
        suffs = [a for a in result.sufficiency_assessments if a.is_sufficient]
        self.assertTrue(any(a.domain == "algebra" for a in suffs),
                        f"se esperaba al menos una assessment SUFFICIENT con "
                        f"domain='algebra'; assessments: "
                        f"{[(a.concept, a.domain) for a in suffs]}")


if __name__ == "__main__":
    unittest.main()
