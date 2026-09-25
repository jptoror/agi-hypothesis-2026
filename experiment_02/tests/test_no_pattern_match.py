"""Test 3 — si ningún patrón sabe proponer una hipótesis para la variable
faltante, el ciclo termina sin adopción y el grafo permanece intacto.

Comprueba el invariante: 'no inventamos lo que no sabemos formular'.
"""
from __future__ import annotations

import unittest

from experiment_01.knowledge_graph import build_geometry_2d_graph
from experiment_01.specialist import DomainContext, Problem

from experiment_02.orchestrator import LearningOrchestrator


class NoPatternMatchTest(unittest.TestCase):
    def test_unknown_variable_yields_no_adoption(self) -> None:
        graph = build_geometry_2d_graph()
        nodes_before = len(graph)
        orch = LearningOrchestrator(graph)

        # 'Q' no está en SumOfEqualParts.known_magnitudes y ningún otro
        # patrón está cargado por defecto. El sistema debe reportar el
        # gap pero NO incorporar nada al grafo.
        problem = Problem(
            statement="¿Cuál es el valor de Q para un cuadrado de lado 5?",
            target="Q",
            context=DomainContext(kind="square", known={"l": 5.0}),
        )
        report = orch.run(problem, problem_id="test.no_pattern.Q")

        self.assertTrue(report.gap_detected)
        self.assertEqual(report.missing_variable, "Q")
        self.assertIsNone(report.candidate)
        self.assertIsNone(report.adopted_node_id)
        self.assertIsNone(report.solve_value)

        # Sólo se ejecutó la fase 2 (proponer) — devolvió lista vacía.
        self.assertEqual(report.learning_phases_executed, 1)

        # Invariante: el grafo no creció ni se vio modificado.
        self.assertEqual(len(graph), nodes_before)


if __name__ == "__main__":
    unittest.main()
