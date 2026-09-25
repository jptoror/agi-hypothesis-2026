"""Tests de la categoría A — razonamiento derivativo dentro del dominio.

`system_behavior_correct = True` cuando el sistema produjo respuesta
con traza no vacía, independiente del ground truth o del LLM.
"""
from __future__ import annotations

import unittest

from experiment_10.benchmark import Benchmark, Category, SystemRunner
from experiment_10.tests._helpers import _MockLLMRunner


class CategoryABehaviorTest(unittest.TestCase):
    def setUp(self) -> None:
        # LLM con respuestas que mencionan los valores esperados.
        mock = _MockLLMRunner({
            "¿Cuánto vale x en 5x + 15 = 0?": "x = -3",
            "¿Cuál es la complejidad de pop en una pila?":
                "La operación pop tiene complejidad O(1).",
        })
        self.bench = Benchmark(
            system_runner=SystemRunner(),
            llm_runner=mock,
        )
        self.summary = self.bench.run()
        self.results_by_qid = {r.question.qid: r for r in self.summary.results}

    def test_A1_system_resolves_with_trace(self) -> None:
        r = self.results_by_qid["A1"]
        self.assertEqual(r.question.category, Category.A)
        self.assertTrue(r.system_behavior_correct)
        self.assertIn("-3.0", r.system_answer)
        self.assertIsNotNone(r.system_trace)
        self.assertGreaterEqual(len(r.system_trace), 1)
        self.assertIn("thm.solucion_general", r.system_trace)

    def test_A2_stack_inspection_with_trace(self) -> None:
        r = self.results_by_qid["A2"]
        self.assertEqual(r.question.category, Category.A)
        self.assertTrue(r.system_behavior_correct)
        self.assertEqual(r.system_answer, "O(1)")
        self.assertIn("thm.stack.pop_complexity", r.system_trace)
        self.assertIn("def.complexity.O1", r.system_trace)

    def test_A_llm_correct_when_answer_matches_ground_truth(self) -> None:
        # Con LLM mockeado que da la respuesta correcta literal.
        self.assertTrue(self.results_by_qid["A1"].correct)
        self.assertTrue(self.results_by_qid["A2"].correct)

    def test_A_llm_has_no_trace(self) -> None:
        self.assertFalse(self.results_by_qid["A1"].llm_has_trace)
        self.assertFalse(self.results_by_qid["A2"].llm_has_trace)


if __name__ == "__main__":
    unittest.main()
