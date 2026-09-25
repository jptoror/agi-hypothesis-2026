"""Tests de los 4 patrones de definición declarados (exp_20)."""
from __future__ import annotations

import unittest

from experiment_20.patterns import (
    DEFINITION_PATTERNS,
    match_definition,
)


class CanonicalMatchesTest(unittest.TestCase):
    def test_llamemos_matches(self) -> None:
        m = match_definition("llamemos H a G sin el vértice 4")
        self.assertIsNotNone(m)
        self.assertEqual(m.symbol, "H")
        self.assertEqual(m.body, "G sin el vértice 4")
        self.assertEqual(m.pattern_id, "def_pat.llamemos")

    def test_sea_equals(self) -> None:
        m = match_definition("sea x = 7")
        self.assertEqual(m.pattern_id, "def_pat.sea_igual")
        self.assertEqual(m.symbol, "x")
        self.assertEqual(m.body, "7")

    def test_sea_igual_a(self) -> None:
        m = match_definition("sea x igual a 7")
        self.assertEqual(m.pattern_id, "def_pat.sea_igual")
        self.assertEqual(m.body, "7")

    def test_definamos(self) -> None:
        m = match_definition("definamos K como el grafo completo de 4 vértices")
        self.assertEqual(m.pattern_id, "def_pat.definamos")
        self.assertEqual(m.symbol, "K")
        self.assertEqual(m.body, "el grafo completo de 4 vértices")

    def test_representa(self) -> None:
        m = match_definition("G representa el grafo de la figura anterior")
        self.assertEqual(m.pattern_id, "def_pat.representa")
        self.assertEqual(m.symbol, "G")


class NonMatchesTest(unittest.TestCase):
    def test_normal_question_does_not_match(self) -> None:
        self.assertIsNone(match_definition("cuál es el coloreado voraz de H?"))

    def test_blocked_symbol_in_representa(self) -> None:
        # "el" no puede ser symbol del patrón "X representa Y".
        self.assertIsNone(match_definition("el representa algo"))

    def test_empty_body_rejected(self) -> None:
        self.assertIsNone(match_definition("sea x ="))
        self.assertIsNone(match_definition("sea x igual a"))
        self.assertIsNone(match_definition("definamos K como"))
        self.assertIsNone(match_definition("llamemos H a"))

    def test_empty_symbol_rejected(self) -> None:
        # Sin token entre `llamemos` y `a`.
        self.assertIsNone(match_definition("llamemos    a algo"))

    def test_unrelated_sentence(self) -> None:
        self.assertIsNone(match_definition("calculá el coloreado de G"))


class CapitalizationTest(unittest.TestCase):
    def test_symbol_capitalization_preserved(self) -> None:
        m = match_definition("Llamemos Foo a el cuadrado")
        self.assertEqual(m.symbol, "Foo")

    def test_h_and_lowercase_h_are_distinct(self) -> None:
        m_upper = match_definition("llamemos H a G")
        m_lower = match_definition("llamemos h a G")
        self.assertEqual(m_upper.symbol, "H")
        self.assertEqual(m_lower.symbol, "h")


class WhitespaceTest(unittest.TestCase):
    def test_extra_whitespace_tolerated(self) -> None:
        m = match_definition("   sea    x   =    7   ")
        self.assertIsNotNone(m)
        self.assertEqual(m.symbol, "x")
        self.assertEqual(m.body, "7")

    def test_trailing_punctuation_trimmed_from_body(self) -> None:
        m = match_definition("definamos K como el grafo completo.")
        self.assertEqual(m.body, "el grafo completo")


class OrderingTest(unittest.TestCase):
    def test_first_declared_pattern_wins(self) -> None:
        # "llamemos H a Foo representa bar" matchea pattern 1 (llamemos)
        # antes de poder ser leído como "Foo representa bar". Es la
        # propiedad documentada: orden de DEFINITION_PATTERNS gana.
        m = match_definition("llamemos H a Foo representa bar")
        self.assertEqual(m.pattern_id, "def_pat.llamemos")

    def test_pattern_order_is_stable(self) -> None:
        # Aserta el orden canónico documentado en el módulo. Si se
        # reordena DEFINITION_PATTERNS, este test falla — eso es
        # intencional: la decisión es un cambio de política.
        self.assertEqual(
            [p.pattern_id for p in DEFINITION_PATTERNS],
            [
                "def_pat.llamemos",
                "def_pat.sea_igual",
                "def_pat.definamos",
                "def_pat.representa",
            ],
        )


if __name__ == "__main__":
    unittest.main()
