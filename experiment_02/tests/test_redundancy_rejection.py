"""Test 2 — un candidato redundante (que duplica una variable ya producida
por el grafo) debe ser rechazado por el validador y NO mutar el grafo.

Comprueba el invariante: 'el sistema no aprende lo que ya sabe'.
"""
from __future__ import annotations

import unittest

from experiment_01.knowledge_graph import (
    EpistemicStatus,
    KnowledgeNode,
    NodeKind,
    build_geometry_2d_graph,
)

from experiment_02.consistency_validator import ConsistencyValidator
from experiment_02.hypothesis_engine import HypothesisCandidate


class RedundancyRejectionTest(unittest.TestCase):
    def test_validator_rejects_duplicate_producer(self) -> None:
        graph = build_geometry_2d_graph()
        nodes_before = len(graph)

        # Candidato manual que pretende producir 'A' (área), ya producida
        # por thm.square.area_from_side y thm.square.area_from_diagonal.
        redundant_node = KnowledgeNode(
            id="hyp.square.area_dup",
            statement="(redundante) A = l * l",
            status=EpistemicStatus.HYPOTHESIS,
            kind=NodeKind.RELATION,
            foundations=["def.square", "ax.arithmetic.real_numbers"],
            validity_conditions=["la figura debe ser un square", "l >= 0"],
            inputs=["l"],
            outputs=["A"],
            compute=lambda v: {"A": v["l"] * v["l"]},
        )
        candidate = HypothesisCandidate(
            node=redundant_node,
            pattern_name="(manual)",
            source_nodes=["def.square"],
            justification="prueba de rechazo por redundancia.",
        )

        result = ConsistencyValidator().validate(candidate, graph)

        self.assertFalse(result.valid)
        self.assertIn("not_redundant", result.checks_failed)

        # El validador no debe mutar el grafo.
        self.assertEqual(len(graph), nodes_before)
        self.assertFalse(graph.has("hyp.square.area_dup"))


if __name__ == "__main__":
    unittest.main()
