"""Test: los nodos del grafo de lenguaje y los del grafo de álgebra
forman conjuntos disjuntos.

Demuestra que los dos especialistas son GENUINAMENTE INDEPENDIENTES:
comparten el bus (ambos producen ReasoningStep, ambos pueden vivir
en una SpecialistRegistry) pero NO comparten conocimiento. Cada uno
opera sobre su propio grafo cerrado.
"""
from __future__ import annotations

import unittest

from experiment_07.orchestrator import LanguageToAlgebraOrchestrator


class LanguageGraphIsDistinctFromAlgebraGraphTest(unittest.TestCase):
    def setUp(self) -> None:
        self.orch = LanguageToAlgebraOrchestrator()
        self.lang_ids = {n.id for n in self.orch.language_graph}
        self.alg_ids = {n.id for n in self.orch.algebra_graph}

    def test_node_id_sets_are_disjoint(self) -> None:
        intersection = self.lang_ids & self.alg_ids
        self.assertEqual(
            intersection, set(),
            f"se esperaba intersección vacía; nodos compartidos: {intersection}",
        )

    def test_language_has_only_linguistic_nodes(self) -> None:
        # Todo nodo del grafo de lenguaje (excepto el axioma base)
        # tiene un `linguistic_role` declarado.
        for n in self.orch.language_graph:
            props = n.properties or {}
            if n.id == "ax.spanish.tokenizable":
                continue
            self.assertIn(
                "linguistic_role", props,
                f"nodo de lenguaje '{n.id}' sin linguistic_role declarado",
            )

    def test_algebra_has_no_linguistic_role(self) -> None:
        # Ningún nodo del grafo de álgebra debe declarar
        # `linguistic_role` — eso sería confusión de dominios.
        for n in self.orch.algebra_graph:
            props = n.properties or {}
            self.assertNotIn(
                "linguistic_role", props,
                f"nodo de álgebra '{n.id}' lleva linguistic_role — confusión de dominios",
            )

    def test_both_graphs_are_non_empty_and_independent_in_size(self) -> None:
        self.assertGreater(len(self.lang_ids), 0)
        self.assertGreater(len(self.alg_ids), 0)
        # Sanity: cada uno tiene un orden de magnitud razonable.
        self.assertGreaterEqual(len(self.lang_ids), 5)
        self.assertGreaterEqual(len(self.alg_ids), 5)


if __name__ == "__main__":
    unittest.main()
