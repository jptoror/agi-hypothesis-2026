"""Unit tests del ExpressionRenderer (exp_18).

Verifican:
  - Render de un nodo individual con plantilla simple y recursiva.
  - Detección de ciclos en `{node.X}`.
  - Fallback al statement cuando no hay plantilla.
  - Reproducibilidad (mismo input → mismo output).
  - Render de traza con conectores rotativos determinísticos.
"""
from __future__ import annotations

import unittest

from experiment_01.knowledge_graph import (
    EpistemicStatus,
    KnowledgeGraph,
    KnowledgeNode,
    NodeKind,
)
from experiment_01.specialist import ReasoningStep, ReasoningTrace
from experiment_18.expression import (
    CyclicReferenceError,
    ExpressionRenderer,
    UnresolvedReferenceError,
)


def _node(node_id, statement, template=None, foundations=None):
    props: dict = {}
    if template is not None:
        props["expression_template"] = template
    return KnowledgeNode(
        id=node_id,
        statement=statement,
        status=EpistemicStatus.DEFINITION,
        kind=NodeKind.CONCEPT,
        foundations=list(foundations or []),
        properties=props,
    )


def _graph(*nodes) -> KnowledgeGraph:
    g = KnowledgeGraph()
    for n in nodes:
        g.add(n)
    return g


class RenderNodeTest(unittest.TestCase):
    def test_simple_template(self) -> None:
        g = _graph(_node("def.x", "literal del nodo", template="hola {self.name}"))
        r = ExpressionRenderer(g)
        self.assertEqual(r.render_node("def.x"), "hola literal del nodo")

    def test_fallback_to_statement_when_no_template(self) -> None:
        # Compatibilidad total con nodos pre-exp_18: sin plantilla,
        # el render devuelve el statement tal cual.
        g = _graph(_node("def.x", "este es el statement"))
        r = ExpressionRenderer(g)
        self.assertEqual(r.render_node("def.x"), "este es el statement")

    def test_recursive_node_ref(self) -> None:
        g = _graph(
            _node("def.a", "el a", template="A({node.def.b})"),
            _node("def.b", "el b", template="B-fin"),
        )
        r = ExpressionRenderer(g)
        # def.b no tiene `{self.name}` → usa el literal "B-fin".
        # def.a expande {node.def.b} a "B-fin" → "A(B-fin)".
        self.assertEqual(r.render_node("def.a"), "A(B-fin)")

    def test_cycle_is_detected(self) -> None:
        g = _graph(
            _node("def.a", "a", template="{node.def.b}"),
            _node("def.b", "b", template="{node.def.a}"),
        )
        r = ExpressionRenderer(g)
        with self.assertRaises(CyclicReferenceError) as ctx:
            r.render_node("def.a")
        # Camino completo en el error.
        self.assertEqual(ctx.exception.path, ["def.a", "def.b", "def.a"])

    def test_self_cycle_is_detected(self) -> None:
        g = _graph(_node("def.a", "a", template="{node.def.a}"))
        r = ExpressionRenderer(g)
        with self.assertRaises(CyclicReferenceError):
            r.render_node("def.a")

    def test_unknown_node_raises_explicit_error(self) -> None:
        g = _graph(_node("def.a", "a", template="{node.def.ghost}"))
        r = ExpressionRenderer(g)
        with self.assertRaises(UnresolvedReferenceError) as ctx:
            r.render_node("def.a")
        self.assertEqual(ctx.exception.kind, "node")
        self.assertEqual(ctx.exception.target, "def.ghost")

    def test_render_is_deterministic(self) -> None:
        # Mismo input → mismo output, siempre. Sin libertad creativa.
        g = _graph(_node("def.x", "literal", template="L: {self.name}"))
        r = ExpressionRenderer(g)
        a = r.render_node("def.x")
        b = r.render_node("def.x")
        self.assertEqual(a, b)


class RenderTraceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.g = _graph(
            _node("def.a", "el a", template="el a vale {input.k}"),
            _node("def.b", "el b", template="el b se conecta con a"),
            _node("def.c", "el c", template="el c cierra el paso"),
        )
        self.r = ExpressionRenderer(self.g)

    def _step(self, idx, node_id, inputs=None, outputs=None):
        return ReasoningStep(
            index=idx,
            node_id=node_id,
            node_statement="(no usado)",
            purpose="(no usado)",
            inputs=dict(inputs or {}),
            outputs=dict(outputs or {}),
        )

    def test_trace_concatenates_with_default_connectors(self) -> None:
        trace = ReasoningTrace(steps=[
            self._step(1, "def.a", inputs={"k": 7}),
            self._step(2, "def.b"),
            self._step(3, "def.c"),
        ])
        out = self.r.render_trace(trace)
        # Primer paso sin conector; segundo y tercero con los dos
        # primeros conectores por defecto rotando.
        self.assertEqual(
            out,
            "el a vale 7 Luego, el b se conecta con a "
            "A continuación, el c cierra el paso",
        )

    def test_custom_connectors_rotate_deterministically(self) -> None:
        trace = ReasoningTrace(steps=[
            self._step(1, "def.b"),
            self._step(2, "def.b"),
            self._step(3, "def.b"),
            self._step(4, "def.b"),
            self._step(5, "def.b"),
        ])
        out = self.r.render_trace(trace, connectors=[". Pero ", ". Y "])
        # Paso 1 sin conector. Pasos 2-5 alternan: ". Pero ", ". Y ",
        # ". Pero ", ". Y ".
        expected = (
            "el b se conecta con a"
            ". Pero el b se conecta con a"
            ". Y el b se conecta con a"
            ". Pero el b se conecta con a"
            ". Y el b se conecta con a"
        )
        self.assertEqual(out, expected)

    def test_empty_trace_renders_empty_string(self) -> None:
        self.assertEqual(self.r.render_trace(ReasoningTrace()), "")

    def test_trace_render_is_reproducible(self) -> None:
        trace = ReasoningTrace(steps=[
            self._step(1, "def.a", inputs={"k": 1}),
            self._step(2, "def.b"),
        ])
        a = self.r.render_trace(trace)
        b = self.r.render_trace(trace)
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
