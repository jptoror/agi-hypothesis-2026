"""Test 4: el especialista de pilas se construye SIN nodos manuales.

Mismo invariante que el test crítico del exp_06: contar cuántos
nodos del grafo final NO llevan `extracted_from_document=True`.
Para los nodos importados del grafo base de complejidad, también
debe haber procedencia auditable — son nodos del base, no
construidos a mano.
"""
from __future__ import annotations

import unittest

from experiment_09.knowledge_graph import build_complexity_base_graph
from experiment_09.specialist_factory import StackSpecialistFactory


class SpecialistBuiltFromDocumentTest(unittest.TestCase):
    def setUp(self) -> None:
        factory = StackSpecialistFactory()
        self.result = factory.build()
        self.graph = self.result.graph
        self.base = build_complexity_base_graph()
        self.base_ids = {n.id for n in self.base}

    def test_specialist_registered(self) -> None:
        self.assertTrue(self.result.registered)

    def test_zero_manual_nodes(self) -> None:
        """Cada nodo del grafo final tiene procedencia conocida:
        o viene del documento (extracted_from_document=True), o
        viene del grafo base (su id está en base_ids). Cualquier
        nodo sin esas dos procedencias sería un nodo manual.
        """
        manual_nodes = []
        for n in self.graph:
            from_doc = (n.properties or {}).get("extracted_from_document")
            from_base = n.id in self.base_ids
            if not from_doc and not from_base:
                manual_nodes.append(n.id)
        self.assertEqual(
            manual_nodes, [],
            f"se esperaba 0 nodos manuales; se encontraron {manual_nodes}"
        )

    def test_node_provenance_breakdown(self) -> None:
        """Verifica los conteos exactos: 8 nodos del documento +
        2 importados del base (def.complexity.O1 y su fundamento
        ax.complexity.total_order)."""
        from_doc = sum(
            1 for n in self.graph
            if (n.properties or {}).get("extracted_from_document")
        )
        from_base = sum(
            1 for n in self.graph if n.id in self.base_ids
        )
        self.assertEqual(from_doc, 8)
        self.assertEqual(from_base, 2)
        self.assertEqual(len(self.graph), 10)

    def test_graph_validates(self) -> None:
        """El grafo final con cierre transitivo del base es válido."""
        self.assertEqual(self.graph.validate(), [])


if __name__ == "__main__":
    unittest.main()
