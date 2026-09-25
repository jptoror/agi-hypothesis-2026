"""Test 1 — happy path: el sistema aprende el teorema del perímetro."""
from __future__ import annotations

import unittest

from experiment_01.knowledge_graph import (
    EpistemicStatus,
    build_geometry_2d_graph,
)
from experiment_01.specialist import DomainContext, Problem

from experiment_02.orchestrator import LearningOrchestrator


class PerimeterLearningTest(unittest.TestCase):
    def test_learns_perimeter_theorem(self) -> None:
        graph = build_geometry_2d_graph()
        orch = LearningOrchestrator(graph)
        nodes_before = len(graph)

        problem = Problem(
            statement="¿Cuál es el perímetro de un cuadrado de lado 5?",
            target="P",
            context=DomainContext(kind="square", known={"l": 5.0}),
        )
        report = orch.run(problem, problem_id="test.perimeter_learning.l5")

        self.assertTrue(report.gap_detected)
        self.assertEqual(report.missing_variable, "P")
        self.assertIsNotNone(report.candidate)
        self.assertIsNotNone(report.validation)
        self.assertTrue(report.validation.valid)

        # Adopción + resolución.
        self.assertIsNotNone(report.adopted_node_id)
        self.assertEqual(report.solve_value, 20.0)

        # Consolidación a teorema.
        self.assertIsNotNone(report.consolidation)
        self.assertTrue(report.consolidation.promoted)
        self.assertEqual(
            report.consolidation.new_node_id,
            "thm.square.perimeter_from_side",
        )

        # Evidencia central del experimento: el grafo creció en 1 nodo
        # auditable y ese nodo es THEOREM con fundamentos reales.
        self.assertEqual(len(graph), nodes_before + 1)
        new_node = graph.get("thm.square.perimeter_from_side")
        self.assertEqual(new_node.status, EpistemicStatus.THEOREM)
        self.assertIn("def.square", new_node.foundations)
        self.assertIn("ax.arithmetic.real_numbers", new_node.foundations)
        for f in new_node.foundations:
            self.assertTrue(graph.has(f), f"fundamento '{f}' no está en el grafo")

        # Hubo un ciclo de aprendizaje completo: 5 fases (2..6).
        self.assertEqual(report.learning_phases_executed, 5)


if __name__ == "__main__":
    unittest.main()
