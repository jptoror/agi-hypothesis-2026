"""Unit tests del parser y resolutor de plantillas (exp_18).

Cubren los invariantes del contrato:
  - Tokenización correcta (literales, refs, escapes).
  - Errores explícitos (no degradación silenciosa).
  - Whitespace dentro de las llaves se tolera.
"""
from __future__ import annotations

import unittest

from experiment_18.expression import (
    TemplateParseError,
    TemplateRef,
    UnresolvedReferenceError,
    parse_template,
    render_template,
)


# Resolver que rechaza todo: usar para tests donde no se espera
# `{node.X}` o donde queremos verificar que el error sale por la
# ruta correcta.
def _no_node_resolver(target: str) -> str:
    raise UnresolvedReferenceError("node", target, "resolver vacío")


class ParseTest(unittest.TestCase):
    def test_no_refs_returns_single_literal(self) -> None:
        self.assertEqual(parse_template("hola mundo"), ["hola mundo"])

    def test_single_self_ref(self) -> None:
        self.assertEqual(
            parse_template("{self.name}"),
            [TemplateRef(kind="self", target="name")],
        )

    def test_mixed_literal_and_ref(self) -> None:
        self.assertEqual(
            parse_template("a={input.x} b"),
            ["a=", TemplateRef(kind="input", target="x"), " b"],
        )

    def test_whitespace_inside_braces_is_tolerated(self) -> None:
        self.assertEqual(
            parse_template("{  node.foo  }"),
            [TemplateRef(kind="node", target="foo")],
        )

    def test_escaped_braces_are_literal(self) -> None:
        self.assertEqual(parse_template("{{x}}"), ["{x}"])
        self.assertEqual(
            parse_template("usa {{node.X}} para referir"),
            ["usa {node.X} para referir"],
        )

    def test_unclosed_brace_raises(self) -> None:
        with self.assertRaises(TemplateParseError):
            parse_template("hola {self.name")

    def test_dangling_close_brace_raises(self) -> None:
        with self.assertRaises(TemplateParseError):
            parse_template("hola}")

    def test_unknown_kind_raises(self) -> None:
        with self.assertRaises(TemplateParseError):
            parse_template("{magic.foo}")

    def test_missing_dot_raises(self) -> None:
        with self.assertRaises(TemplateParseError):
            parse_template("{noinnerdot}")

    def test_empty_target_raises(self) -> None:
        with self.assertRaises(TemplateParseError):
            parse_template("{node.}")


class RenderTest(unittest.TestCase):
    def test_literal_only(self) -> None:
        out = render_template(
            "hola", bindings={}, resolver=_no_node_resolver,
            self_statement="ignored",
        )
        self.assertEqual(out, "hola")

    def test_self_resolves_to_statement(self) -> None:
        out = render_template(
            "es {self.name}",
            bindings={},
            resolver=_no_node_resolver,
            self_statement="el nodo X",
        )
        self.assertEqual(out, "es el nodo X")

    def test_input_binding(self) -> None:
        out = render_template(
            "valor={input.x}",
            bindings={"input": {"x": 42}},
            resolver=_no_node_resolver,
            self_statement="",
        )
        self.assertEqual(out, "valor=42")

    def test_output_binding(self) -> None:
        out = render_template(
            "salida={output.y}",
            bindings={"output": {"y": "ok"}},
            resolver=_no_node_resolver,
            self_statement="",
        )
        self.assertEqual(out, "salida=ok")

    def test_node_ref_invokes_resolver(self) -> None:
        captured = []

        def _r(target: str) -> str:
            captured.append(target)
            return f"<{target}>"

        out = render_template(
            "{node.def.alfa} y {node.def.beta}",
            bindings={}, resolver=_r, self_statement="",
        )
        self.assertEqual(out, "<def.alfa> y <def.beta>")
        self.assertEqual(captured, ["def.alfa", "def.beta"])

    def test_missing_input_raises(self) -> None:
        with self.assertRaises(UnresolvedReferenceError) as ctx:
            render_template(
                "{input.x}", bindings={"input": {}},
                resolver=_no_node_resolver, self_statement="",
            )
        self.assertEqual(ctx.exception.kind, "input")
        self.assertEqual(ctx.exception.target, "x")

    def test_missing_output_raises(self) -> None:
        with self.assertRaises(UnresolvedReferenceError):
            render_template(
                "{output.y}", bindings={},
                resolver=_no_node_resolver, self_statement="",
            )

    def test_missing_step_raises(self) -> None:
        with self.assertRaises(UnresolvedReferenceError):
            render_template(
                "{step.1}", bindings={"step": {}},
                resolver=_no_node_resolver, self_statement="",
            )

    def test_step_binding_uses_string_key(self) -> None:
        # Las claves de `step` se almacenan tal cual viene la
        # plantilla — string. El caller decide la convención.
        out = render_template(
            "ver paso {step.1}.",
            bindings={"step": {"1": "P1"}},
            resolver=_no_node_resolver, self_statement="",
        )
        self.assertEqual(out, "ver paso P1.")

    def test_escaped_brace_around_ref(self) -> None:
        # `{{` y `}}` siguen siendo literales aun en presencia de
        # refs reales en la misma plantilla.
        out = render_template(
            "set={{ {input.x} }}",
            bindings={"input": {"x": 7}},
            resolver=_no_node_resolver, self_statement="",
        )
        self.assertEqual(out, "set={ 7 }")


if __name__ == "__main__":
    unittest.main()
