"""Tests de la guarda de precondiciones del gateway (hallazgos del exp_22).

Cada test fija un comportamiento que el razonador del exp_01 tenía
mal: condiciones numéricas declaradas pero nunca evaluadas y
Pitágoras aplicado a triángulos no rectángulos.
"""
from __future__ import annotations

import unittest

from experiment_22.gateway import EngineGateway, StructuredQuery, parse_numeric_condition


class PreconditionGuardTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.gateway = EngineGateway()

    def solve(self, domain, kind, target, known, **kw):
        return self.gateway.solve(StructuredQuery(domain, kind, target, known, **kw))

    def test_parse_numeric_condition(self) -> None:
        self.assertEqual(parse_numeric_condition("a ≠ 0"), ("a", "≠", 0.0))
        self.assertEqual(parse_numeric_condition("l >= 0"), ("l", ">=", 0.0))
        self.assertIsNone(parse_numeric_condition("la figura debe ser un cuadrado"))

    def test_zero_coefficient_is_a_declared_gap_not_a_crash(self) -> None:
        result = self.solve("algebra", "linear_equation", "x", {"a": 0.0, "b": 5.0})
        self.assertFalse(result.success)
        self.assertIn("a ≠ 0", result.precondition_violation)

    def test_negative_length_violates_precondition(self) -> None:
        result = self.solve("geometry", "square", "A", {"l": -4.0})
        self.assertFalse(result.success)
        self.assertIn("l >= 0", result.precondition_violation)

    def test_pythagoras_needs_a_right_triangle(self) -> None:
        right = self.solve("geometry", "triangle.right", "c", {"a": 3.0, "b": 4.0})
        self.assertTrue(right.success)
        self.assertEqual(right.value, 5.0)
        generic = self.solve("geometry", "triangle", "c", {"a": 3.0, "b": 4.0})
        self.assertFalse(generic.success)

    def test_valid_problems_still_derive_with_trace(self) -> None:
        result = self.solve("geometry", "square", "A", {"d": 8.0})
        self.assertTrue(result.success)
        self.assertEqual(result.trace_node_ids, ["thm.square.area_from_diagonal"])

    def test_cross_domain_trace_includes_delegation(self) -> None:
        result = self.solve(
            "physics", "physics.object", "Ec", {"m": 2.0, "d": 8.0},
            variable_bindings={"v": "l"}, partner_context_kind="square",
        )
        self.assertTrue(result.success)
        self.assertAlmostEqual(result.value, 32.0)
        self.assertIn("thm.square.side_from_diagonal", result.trace_node_ids)
        self.assertIn("thm.kinetic_energy", result.trace_node_ids)

    def test_queries_are_isolated(self) -> None:
        """Una hipótesis inyectada en una consulta no aparece en la siguiente."""
        from experiment_01.knowledge_graph import EpistemicStatus, KnowledgeNode, NodeKind

        node = KnowledgeNode(
            id="hyp.test.P", statement="P = 4l", status=EpistemicStatus.HYPOTHESIS,
            kind=NodeKind.RELATION, foundations=["def.square"],
            compute=lambda v: {"P": 4 * v["l"]}, inputs=["l"], outputs=["P"],
        )
        q = StructuredQuery("geometry", "square", "P", {"l": 5.0})
        self.assertTrue(self.gateway.solve(q, extra_nodes=[node]).success)
        self.assertFalse(self.gateway.solve(q).success)


if __name__ == "__main__":
    unittest.main()
