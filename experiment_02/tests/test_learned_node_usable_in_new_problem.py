"""Test 5 — el test central del paper.

Después de aprender thm.square.perimeter_from_side resolviendo el primer
problema (lado=5 → P=20), un SEGUNDO problema distinto que también pida
perímetro (lado=12 → P=48) debe resolverse SIN ciclo de aprendizaje:

  - el orchestrator no detecta gap,
  - no propone, no valida, no adopta,
  - el grafo permanece en 20 nodos,
  - el especialista deriva la respuesta usando directamente el teorema.

Esta es la diferencia entre memorizar (caso particular) y aprender
(generalización reutilizable). El nodo aprendido se comporta exactamente
como un teorema 'nativo' del grafo original.
"""
from __future__ import annotations

import unittest

from experiment_01.knowledge_graph import (
    EpistemicStatus,
    build_geometry_2d_graph,
)
from experiment_01.specialist import DomainContext, Problem

from experiment_02.orchestrator import LearningOrchestrator


class LearnedNodeUsableInNewProblemTest(unittest.TestCase):
    def test_learned_theorem_solves_new_problem_without_relearning(self) -> None:
        graph = build_geometry_2d_graph()
        orch = LearningOrchestrator(graph)

        # === Fase de aprendizaje (problema A) ===
        problem_a = Problem(
            statement="¿Cuál es el perímetro de un cuadrado de lado 5?",
            target="P",
            context=DomainContext(kind="square", known={"l": 5.0}),
        )
        report_a = orch.run(problem_a, problem_id="test.learned.A")

        self.assertTrue(report_a.consolidation.promoted)
        self.assertEqual(len(graph), 20)
        learned_id = report_a.consolidation.new_node_id
        self.assertEqual(learned_id, "thm.square.perimeter_from_side")
        self.assertEqual(graph.get(learned_id).status, EpistemicStatus.THEOREM)

        # === Fase de reutilización (problema B, distinto) ===
        problem_b = Problem(
            statement="¿Cuál es el perímetro de un cuadrado de lado 12?",
            target="P",
            context=DomainContext(kind="square", known={"l": 12.0}),
        )
        report_b = orch.run(problem_b, problem_id="test.learned.B")

        # 1. NO hubo ciclo de aprendizaje en el problema B.
        self.assertEqual(report_b.learning_phases_executed, 0)
        self.assertFalse(report_b.gap_detected)

        # 2. El grafo no creció.
        self.assertEqual(len(graph), 20)

        # 3. La respuesta es correcta.
        self.assertEqual(report_b.solve_value, 48.0)

        # 4. El teorema aprendido fue el que se usó en la derivación.
        self.assertIn(learned_id, report_b.solve_steps)


if __name__ == "__main__":
    unittest.main()
