"""Tests del set de preguntas y del benchmark en modo oráculo."""
from __future__ import annotations

import math
import unittest

from experiment_22.benchmark.questions import QUESTIONS, Category
from experiment_22.benchmark.runner import (
    oracle_llm,
    render_report,
    run_engine,
    run_hybrid,
    score,
    summarize,
)
from experiment_22.gateway import EngineGateway
from experiment_22.pipeline import HybridPipeline


class QuestionSetTest(unittest.TestCase):
    def test_size_and_unique_ids(self) -> None:
        self.assertGreaterEqual(len(QUESTIONS), 60)
        self.assertEqual(len({q.qid for q in QUESTIONS}), len(QUESTIONS))
        self.assertEqual(len({q.text for q in QUESTIONS}), len(QUESTIONS))

    def test_traps_expect_abstention_and_others_a_value(self) -> None:
        for q in QUESTIONS:
            with self.subTest(qid=q.qid):
                if q.category == Category.TRAP:
                    self.assertIsNone(q.expected)
                else:
                    self.assertTrue(math.isfinite(q.expected))

    def test_scoring(self) -> None:
        q = next(q for q in QUESTIONS if q.qid == "IN-G1")
        trap = next(q for q in QUESTIONS if q.category == Category.TRAP)
        self.assertEqual(score(q, 25.0), "correct")
        self.assertEqual(score(q, 25.01), "correct")      # dentro de 1e-3 relativo
        self.assertEqual(score(q, 26.0), "wrong")
        self.assertEqual(score(q, None), "missed")
        self.assertEqual(score(trap, None), "correct_abstention")
        self.assertEqual(score(trap, 0.0), "wrong")


class OracleBenchmarkTest(unittest.TestCase):
    """Con traducciones perfectas, el motor no se equivoca nunca y el
    híbrido supera al motor sin introducir respuestas incorrectas."""

    @classmethod
    def setUpClass(cls) -> None:
        gateway = EngineGateway()
        cls.engine = summarize(run_engine(QUESTIONS, gateway))
        cls.hybrid = summarize(
            run_hybrid(QUESTIONS, HybridPipeline(oracle_llm(QUESTIONS), gateway=gateway))
        )

    def test_engine_answers_every_in_domain_question_and_never_errs(self) -> None:
        self.assertEqual(self.engine.counts.get("wrong", 0), 0)
        for cat in ("IN", "PRECISION", "CROSS"):
            d = self.engine.by_category[cat]
            self.assertEqual(d.get("correct", 0), sum(d.values()), cat)
        self.assertEqual(self.engine.by_category["TRAP"].get("correct_abstention"), 7)

    def test_hybrid_extends_coverage_without_errors(self) -> None:
        self.assertEqual(self.hybrid.counts.get("wrong", 0), 0)
        self.assertGreater(self.hybrid.coverage, self.engine.coverage)
        self.assertGreater(self.hybrid.accuracy, self.engine.accuracy)

    def test_learn_tiers(self) -> None:
        self.assertEqual(self.hybrid.by_tier["corroborated"].get("correct"), 3)
        self.assertEqual(self.hybrid.by_tier["conditional"].get("correct"), 5)
        # Tres límites documentados en FINDINGS: P fuera del contrato (LE-8),
        # g sin dimensión (LE-10), división por cero en el check de ejecución (LE-11).
        self.assertEqual(self.hybrid.by_category["LEARN"].get("missed"), 3)

    def test_report_renders(self) -> None:
        report = render_report([self.engine, self.hybrid], "oracle")
        self.assertIn("| engine |", report)
        self.assertIn("| verified |", report)


if __name__ == "__main__":
    unittest.main()
