"""Test de la categoría C — trazabilidad y auditoría.

`system_behavior_correct = True` si la traza tiene ≥1 ReasoningStep
con node_id verificable contra el grafo del especialista.

El LLM puede dar explicación textual extensa pero `llm_has_trace`
sigue siendo False — porque la prosa generada NO es una traza
estructurada verificable contra ningún grafo.
"""
from __future__ import annotations

import unittest

from experiment_10.benchmark import Benchmark, Category, SystemRunner
from experiment_10.tests._helpers import _MockLLMRunner


class CategoryCBehaviorTest(unittest.TestCase):
    def setUp(self) -> None:
        # LLM mock que da explicación extensa con pasos en prosa.
        # Aunque parezca una "traza", llm_has_trace es invariante
        # False — porque no es estructurada ni verificable.
        mock = _MockLLMRunner({
            "¿Cuánto vale x en 5x + 15 = 0? (mostrar pasos)":
                "Paso 1: aislar x. 5x = -15. Paso 2: dividir entre 5. x = -3.",
        })
        self.bench = Benchmark(
            system_runner=SystemRunner(),
            llm_runner=mock,
        )
        self.summary = self.bench.run()
        self.results_by_qid = {r.question.qid: r for r in self.summary.results}

    def test_C1_system_trace_has_verifiable_node(self) -> None:
        r = self.results_by_qid["C1"]
        self.assertEqual(r.question.category, Category.C)
        self.assertTrue(r.system_behavior_correct)
        self.assertIsNotNone(r.system_trace)
        # El nodo de la traza debe existir en el grafo del especialista
        # (la verificación la hace el evaluador internamente; aquí
        # comprobamos que efectivamente contiene el id esperado).
        self.assertIn("thm.solucion_general", r.system_trace)

    def test_C1_llm_has_trace_is_invariant_false(self) -> None:
        """Aunque el LLM dé una explicación con apariencia de pasos,
        llm_has_trace sigue siendo False. La prosa generada NO es
        traza estructurada."""
        r = self.results_by_qid["C1"]
        self.assertFalse(r.llm_has_trace)
        # Sin embargo, la prosa SÍ está disponible para auditar
        # cualitativamente lo que el LLM dijo.
        self.assertIn("Paso 1", r.llm_explanation_text)

    def test_C1_explanation_text_is_not_treated_as_trace(self) -> None:
        """El texto de explicación está separado del trace estructurado
        — el campo no se confunde con `llm_has_trace`."""
        r = self.results_by_qid["C1"]
        self.assertGreater(len(r.llm_explanation_text), 0)
        self.assertFalse(r.llm_has_trace)


if __name__ == "__main__":
    unittest.main()
