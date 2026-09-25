"""Tests del especialista del capítulo 1 (algorithms_ch1).

Paralelos a los tests del especialista de pilas (exp_09) y de
colas (exp_13). Verifican el contrato canónico del patrón:

  1. graph.validate() limpio.
  2. 0 nodos construidos a mano.
  3. Pregunta específica del capítulo resuelve correctamente.
  4. Procedencia auditable de cada nodo del grafo final.

Más asserts específicos sobre el primer nodo ALGORITHM real del
proyecto en producción.
"""
from __future__ import annotations

import unittest

from experiment_01.knowledge_graph import EpistemicStatus
from experiment_09.knowledge_graph import build_complexity_base_graph

from experiment_15.specialist_factory import (
    AlgorithmsCh1SpecialistFactory,
)


class AlgorithmsCh1SpecialistTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = AlgorithmsCh1SpecialistFactory().build()
        cls.graph = cls.result.graph
        cls.base_ids = {n.id for n in build_complexity_base_graph()}

    # -- 1. validate() ---------------------------------------------

    def test_specialist_registers_correctly(self) -> None:
        self.assertTrue(self.result.registered)
        self.assertEqual(self.result.errors, [])

    def test_graph_validates_clean(self) -> None:
        errors, warnings = self.graph.validate_with_warnings()
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    # -- 2. 0 nodos manuales ---------------------------------------

    def test_zero_manual_nodes(self) -> None:
        manual = []
        for n in self.graph:
            from_doc = (n.properties or {}).get("extracted_from_document")
            from_base = n.id in self.base_ids
            if not from_doc and not from_base:
                manual.append(n.id)
        self.assertEqual(
            manual, [],
            f"se esperaba 0 nodos manuales; se encontraron {manual}"
        )

    # -- 3. Pregunta específica del capítulo -----------------------

    def test_greedy_coloring_complexity_is_O_n3(self) -> None:
        target = "thm.greedy_coloring.complejidad"
        self.assertTrue(self.graph.has(target))
        thm = self.graph.get(target)
        # El teorema declara la complejidad como fundamento.
        self.assertIn("def.complexity.On3", thm.foundations)
        # El nodo de complejidad referenciado tiene order=6.
        cnode = self.graph.get("def.complexity.On3")
        self.assertEqual(cnode.properties.get("order"), 6)

    # -- 4. Conteos esperados --------------------------------------

    def test_node_counts(self) -> None:
        # 33 del documento + 3 del base (def.complexity.On3,
        # def.complexity.On2, ax.complexity.total_order) = 36.
        from_doc = sum(
            1 for n in self.graph
            if (n.properties or {}).get("extracted_from_document")
        )
        from_base = sum(1 for n in self.graph if n.id in self.base_ids)
        self.assertEqual(from_doc, 33)
        self.assertEqual(from_base, 3)
        self.assertEqual(len(self.graph), 36)

    def test_imported_base_chain(self) -> None:
        """Verifica que el cierre transitivo trajo la cadena
        completa: thm.greedy_coloring.complejidad → On3 → On2 →
        ax.complexity.total_order. On2 entra aunque el documento
        no lo referencia directamente — es fundamento de On3."""
        for nid in (
            "def.complexity.On3",
            "def.complexity.On2",
            "ax.complexity.total_order",
        ):
            self.assertTrue(
                self.graph.has(nid),
                f"se esperaba {nid} en el grafo final"
            )

    # -- ALGORITHM ejercitado por primera vez en documento real ----

    def test_first_algorithm_node_in_real_document(self) -> None:
        """alg.greedy_coloring es el primer nodo ALGORITHM real
        del proyecto (no fixture de test). Verifica que el soporte
        del exp_14 funciona end-to-end sobre un documento."""
        self.assertTrue(self.graph.has("alg.greedy_coloring"))
        alg = self.graph.get("alg.greedy_coloring")
        self.assertEqual(alg.status, EpistemicStatus.ALGORITHM)
        # Inputs y outputs deben estar en properties (P literal del
        # exp_14: ALGORITHM lleva I/O en properties además del
        # atributo top-level).
        props = alg.properties or {}
        self.assertIsInstance(props.get("inputs"), list)
        self.assertGreater(len(props["inputs"]), 0)
        self.assertIsInstance(props.get("outputs"), list)
        self.assertGreater(len(props["outputs"]), 0)


if __name__ == "__main__":
    unittest.main()
