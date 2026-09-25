"""Test: el LLMRunner sin ANTHROPIC_API_KEY funciona limpiamente —
no consulta el API, devuelve un sentinel auditable, y el evaluador
del Benchmark trata `correct` como None (no como False) cuando el
LLM no respondió.
"""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from experiment_10.benchmark import Benchmark, SystemRunner
from experiment_10.benchmark.llm_runner import LLMRunner


class LLMRunnerHandlesMissingKeyTest(unittest.TestCase):
    def test_runner_unavailable_without_key(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            runner = LLMRunner()
            self.assertFalse(runner.is_available)

    def test_ask_without_key_returns_skipped_sentinel(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            runner = LLMRunner()
            resp = runner.ask("¿algo?")
            self.assertTrue(resp.model_used.startswith("(skipped"))
            self.assertIn("no API key", resp.answer_text)
            self.assertIsNone(resp.error)

    def test_benchmark_correct_is_none_when_llm_skipped(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            bench = Benchmark(
                system_runner=SystemRunner(),
                llm_runner=LLMRunner(),
            )
            summary = bench.run()
            for r in summary.results:
                self.assertIsNone(
                    r.correct,
                    f"{r.question.qid}: correct debería ser None cuando "
                    f"el LLM no respondió; fue {r.correct!r}",
                )


if __name__ == "__main__":
    unittest.main()
