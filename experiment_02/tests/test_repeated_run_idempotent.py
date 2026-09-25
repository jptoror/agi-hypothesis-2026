"""Test 4 — correr el mismo problema dos veces sobre el mismo grafo no
duplica el aprendizaje. La segunda ejecución no añade nodos.

Comprueba: 'aprender es persistente; el grafo crece monotónicamente
respecto a problemas distintos, no respecto a repeticiones'.
"""
from __future__ import annotations

import unittest

from experiment_01.knowledge_graph import build_geometry_2d_graph
from experiment_01.specialist import DomainContext, Problem

from experiment_02.orchestrator import LearningOrchestrator


class RepeatedRunIdempotentTest(unittest.TestCase):
    def test_second_run_does_not_grow_graph(self) -> None:
        graph = build_geometry_2d_graph()
        orch = LearningOrchestrator(graph)
        nodes_initial = len(graph)

        problem = Problem(
            statement="¿Cuál es el perímetro de un cuadrado de lado 5?",
            target="P",
            context=DomainContext(kind="square", known={"l": 5.0}),
        )

        first = orch.run(problem, problem_id="test.idempotent.first")
        nodes_after_first = len(graph)

        # Tras el primer run, esperamos crecimiento de exactamente 1 nodo
        # y consolidación a teorema.
        self.assertEqual(nodes_after_first, nodes_initial + 1)
        self.assertTrue(first.consolidation.promoted)

        # Segundo run sobre el mismo problema con el mismo grafo: como
        # ahora existe el teorema, no debe haber gap.
        second = orch.run(problem, problem_id="test.idempotent.second")

        self.assertFalse(second.gap_detected)
        self.assertEqual(second.solve_value, 20.0)
        self.assertEqual(second.learning_phases_executed, 0)
        self.assertEqual(len(graph), nodes_after_first)


if __name__ == "__main__":
    unittest.main()
