"""Test: el GeminiRunner sin api_key funciona limpiamente — no
consulta el API, devuelve un sentinel auditable, y el benchmark
trata `correct` como None y `llm_provider` como 'skipped'.

Paralelo al test del LLMRunner (Anthropic) sin key. Ambos runners
implementan la misma política de skip honesto.
"""
from __future__ import annotations

import unittest

from experiment_10.benchmark import Benchmark, GeminiRunner, SystemRunner


class GeminiRunnerHandlesMissingKeyTest(unittest.TestCase):
    def test_runner_unavailable_without_key(self) -> None:
        runner = GeminiRunner(api_key=None)
        self.assertFalse(runner.is_available)

    def test_runner_unavailable_with_empty_key(self) -> None:
        runner = GeminiRunner(api_key="")
        self.assertFalse(runner.is_available)

    def test_ask_without_key_returns_skipped_sentinel(self) -> None:
        runner = GeminiRunner(api_key=None)
        resp = runner.ask("¿algo?")
        self.assertTrue(resp.model_used.startswith("(skipped"))
        self.assertEqual(resp.provider, "skipped")
        self.assertIn("no API key", resp.answer_text)
        self.assertIsNone(resp.error)

    def test_benchmark_correct_is_none_when_gemini_skipped(self) -> None:
        bench = Benchmark(
            system_runner=SystemRunner(),
            llm_runner=GeminiRunner(api_key=None),
        )
        summary = bench.run()
        for r in summary.results:
            self.assertIsNone(r.correct)
            self.assertEqual(r.llm_provider, "skipped")


if __name__ == "__main__":
    unittest.main()
