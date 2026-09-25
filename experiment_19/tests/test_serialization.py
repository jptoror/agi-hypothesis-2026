"""Tests del serializer estricto de exp_19.

Cubren los invariantes del contrato:
  - Round-trip exacto (serialize → deserialize → serialize == primero).
  - Resolución de compute_ref vía ProcedureRefRegistry.
  - Errores explícitos: procedure no resoluble, properties no
    serializables, format_version ausente o incompatible.
  - Preservación de surface_forms, expression_template, foundations,
    validity_conditions y promotion_candidate.
"""
from __future__ import annotations

import unittest

from experiment_01.knowledge_graph import (
    EpistemicStatus,
    KnowledgeGraph,
    KnowledgeNode,
    NodeKind,
)
from experiment_19.persistence import (
    FORMAT_VERSION,
    ProcedureNotResolvableError,
    ProcedureRefRegistry,
    UnsupportedPropertyError,
    UnsupportedSchemaError,
    deserialize_graph,
    deserialize_node,
    serialize_graph,
    serialize_node,
)


def _node(node_id, statement="x", status=EpistemicStatus.DEFINITION,
          kind=NodeKind.CONCEPT, foundations=None,
          validity_conditions=None, properties=None, compute=None,
          inputs=None, outputs=None):
    return KnowledgeNode(
        id=node_id,
        statement=statement,
        status=status,
        kind=kind,
        foundations=list(foundations or []),
        validity_conditions=list(validity_conditions or []),
        properties=dict(properties or {}),
        compute=compute,
        inputs=list(inputs or []),
        outputs=list(outputs or []),
    )


class NodeRoundTripTest(unittest.TestCase):
    def test_minimal_node(self) -> None:
        n = _node("def.alfa", statement="el alfa")
        d = serialize_node(n)
        n2 = deserialize_node(d)
        self.assertEqual(n2.id, "def.alfa")
        self.assertEqual(n2.statement, "el alfa")
        self.assertEqual(n2.status, EpistemicStatus.DEFINITION)
        self.assertIsNone(n2.compute)

    def test_node_with_rich_properties(self) -> None:
        props = {
            "surface_forms": ["alfa", "el alfa"],
            "expression_template": "el {self.name} vale {input.x}",
            "section": "1.1",
            "extracted_from_document": True,
            "promotion_candidate": False,
        }
        n = _node("def.x", properties=props,
                  validity_conditions=["a >= 0", "el cuadrado debe ser válido"])
        d = serialize_node(n)
        n2 = deserialize_node(d)
        self.assertEqual(n2.properties, props)
        self.assertEqual(
            n2.validity_conditions,
            ["a >= 0", "el cuadrado debe ser válido"],
        )

    def test_node_with_compute_ref(self) -> None:
        reg = ProcedureRefRegistry()
        called = {"n": 0}

        def fn(v):
            called["n"] += 1
            return {"y": v["x"] * 2}

        reg.register("doubler", fn)
        n = _node(
            "thm.double",
            properties={"procedure_name": "doubler"},
            compute=fn,
            inputs=["x"],
            outputs=["y"],
        )
        d = serialize_node(n)
        self.assertEqual(d["compute_ref"], "doubler")
        n2 = deserialize_node(d, procedure_registry=reg)
        self.assertIsNotNone(n2.compute)
        self.assertEqual(n2.compute({"x": 7})["y"], 14)


class UnsupportedPropertyTest(unittest.TestCase):
    def test_callable_in_properties_raises(self) -> None:
        n = _node("def.x", properties={"hack": lambda v: v})
        with self.assertRaises(UnsupportedPropertyError) as ctx:
            serialize_node(n)
        self.assertEqual(ctx.exception.node_id, "def.x")
        self.assertIn("hack", ctx.exception.key_path)

    def test_set_in_nested_property_raises(self) -> None:
        n = _node("def.x", properties={"nested": {"k": {1, 2, 3}}})
        with self.assertRaises(UnsupportedPropertyError):
            serialize_node(n)

    def test_non_string_dict_key_raises(self) -> None:
        n = _node("def.x", properties={"meta": {1: "uno"}})
        with self.assertRaises(UnsupportedPropertyError):
            serialize_node(n)


class GraphRoundTripTest(unittest.TestCase):
    def test_simple_graph(self) -> None:
        g = KnowledgeGraph()
        g.add(_node("def.a", statement="el a"))
        g.add(_node("def.b", statement="el b", foundations=["def.a"]))
        d = serialize_graph(g)
        g2 = deserialize_graph(d)
        self.assertEqual(len(g2), 2)
        self.assertEqual(g2.get("def.b").foundations, ["def.a"])

    def test_round_trip_is_exact(self) -> None:
        # serialize(deserialize(serialize(g))) == serialize(g)
        g = KnowledgeGraph()
        g.add(_node("def.a", properties={"surface_forms": ["A"]}))
        g.add(_node(
            "def.b", foundations=["def.a"],
            properties={"surface_forms": ["B"], "expression_template": "B={node.def.a}"},
        ))
        ser1 = serialize_graph(g)
        g2 = deserialize_graph(ser1)
        ser2 = serialize_graph(g2)
        self.assertEqual(ser1, ser2)

    def test_format_version_present(self) -> None:
        g = KnowledgeGraph()
        g.add(_node("def.a"))
        d = serialize_graph(g)
        self.assertEqual(d["format_version"], FORMAT_VERSION)


class ErrorPathsTest(unittest.TestCase):
    def test_procedure_not_resolvable(self) -> None:
        # Nodo serializado declara compute_ref pero el registry no
        # lo conoce → error explícito al deserializar.
        data = {
            "id": "thm.x", "statement": "x", "status": "theorem",
            "kind": "relation", "foundations": [],
            "validity_conditions": [], "inputs": [], "outputs": [],
            "rationale": "", "properties": {},
            "compute_ref": "ghost",
        }
        with self.assertRaises(ProcedureNotResolvableError) as ctx:
            deserialize_node(data, procedure_registry=ProcedureRefRegistry())
        self.assertEqual(ctx.exception.procedure_ref, "ghost")

    def test_procedure_ref_without_registry_raises(self) -> None:
        data = {
            "id": "thm.x", "statement": "x", "status": "theorem",
            "kind": "relation", "foundations": [],
            "validity_conditions": [], "inputs": [], "outputs": [],
            "rationale": "", "properties": {}, "compute_ref": "p",
        }
        with self.assertRaises(ProcedureNotResolvableError):
            deserialize_node(data, procedure_registry=None)

    def test_unsupported_format_version(self) -> None:
        with self.assertRaises(UnsupportedSchemaError):
            deserialize_graph({"format_version": "0.9", "nodes": []})

    def test_missing_format_version(self) -> None:
        with self.assertRaises(UnsupportedSchemaError):
            deserialize_graph({"nodes": []})

    def test_node_without_compute_ref_loads_without_compute(self) -> None:
        # Nodo cuyo compute_ref es None → compute permanece None
        # tras deserializar, sin error. Eso refleja "el nodo no
        # tenía compute" (caso normal de DEFINITION).
        data = {
            "id": "def.x", "statement": "x", "status": "definition",
            "kind": "concept", "foundations": [],
            "validity_conditions": [], "inputs": [], "outputs": [],
            "rationale": "", "properties": {}, "compute_ref": None,
        }
        n = deserialize_node(data)
        self.assertIsNone(n.compute)


if __name__ == "__main__":
    unittest.main()
