"""Test 2: el especialista de pilas, construido desde el documento,
tiene `def.complexity.O1` como fundamento del teorema de push.

Verifica que el marcador `**Complejidad:**` del documento se tradujo
a una entrada real en `foundations`, y que el cierre transitivo
trajo el nodo del grafo base.
"""
from __future__ import annotations

import unittest

from experiment_09.specialist_factory import StackSpecialistFactory


class PushComplexityIsO1Test(unittest.TestCase):
    def setUp(self) -> None:
        factory = StackSpecialistFactory()
        self.result = factory.build()
        self.graph = self.result.graph

    def test_specialist_registered(self) -> None:
        self.assertTrue(self.result.registered)
        self.assertIsNotNone(self.graph)

    def test_push_theorem_has_O1_as_foundation(self) -> None:
        push = self.graph.get("thm.stack.push_complexity")
        self.assertIn("def.complexity.O1", push.foundations)

    def test_O1_node_imported_from_base(self) -> None:
        # El nodo def.complexity.O1 vive en el grafo del especialista
        # — fue importado del base_graph por el cierre transitivo.
        self.assertTrue(self.graph.has("def.complexity.O1"))
        o1 = self.graph.get("def.complexity.O1")
        self.assertEqual(o1.properties.get("order"), 1)
        self.assertEqual(o1.properties.get("symbol"), "O(1)")

    def test_axiom_of_total_order_imported_transitively(self) -> None:
        # El cierre transitivo de def.complexity.O1 trae también su
        # fundamento — el axioma del orden total.
        self.assertTrue(self.graph.has("ax.complexity.total_order"))


if __name__ == "__main__":
    unittest.main()
