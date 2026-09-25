"""Test 1: el grafo base de complejidad pasa graph.validate() limpio.

Sanity de la pieza autónoma del exp_09 — independiente del parser
y del especialista. Es el cimiento sobre el que se anclan los
documentos de estructuras de datos.
"""
from __future__ import annotations

import unittest

from experiment_01.knowledge_graph import EpistemicStatus
from experiment_09.knowledge_graph import build_complexity_base_graph


class ComplexityGraphValidatesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.graph = build_complexity_base_graph()

    def test_validate_returns_no_errors(self) -> None:
        self.assertEqual(self.graph.validate(), [])

    def test_node_count_is_eight(self) -> None:
        # 1 axioma + 6 definiciones (O1, Ologn, On, Onlogn, On2, On3)
        # + 1 teorema. El nodo def.complexity.On3 se añadió en
        # iteración posterior; el conteo se actualizó de 7 a 8.
        self.assertEqual(len(self.graph), 8)

    def test_axiom_present(self) -> None:
        self.assertTrue(self.graph.has("ax.complexity.total_order"))
        ax = self.graph.get("ax.complexity.total_order")
        self.assertEqual(ax.status, EpistemicStatus.AXIOM)

    def test_all_complexity_classes_present_with_order(self) -> None:
        expected = {
            "def.complexity.O1": 1,
            "def.complexity.Ologn": 2,
            "def.complexity.On": 3,
            "def.complexity.Onlogn": 4,
            "def.complexity.On2": 5,
            "def.complexity.On3": 6,   # añadido en iteración posterior
        }
        for nid, order in expected.items():
            self.assertTrue(self.graph.has(nid), f"falta {nid}")
            n = self.graph.get(nid)
            self.assertEqual(n.status, EpistemicStatus.DEFINITION)
            self.assertEqual(n.properties.get("order"), order)

    def test_comparison_theorem_is_executable(self) -> None:
        thm = self.graph.get("thm.complexity.comparison")
        self.assertEqual(thm.status, EpistemicStatus.THEOREM)
        self.assertTrue(thm.is_executable())
        self.assertEqual(thm.inputs, ["order_a", "order_b"])
        self.assertEqual(thm.outputs, ["more_efficient"])


if __name__ == "__main__":
    unittest.main()
