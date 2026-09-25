"""Tests del TranslationChecker: lo que el LLM traduce no se cree por defecto."""
from __future__ import annotations

import unittest

from experiment_22.catalog import DomainCatalog
from experiment_22.gateway import EngineGateway
from experiment_22.translator import TranslationChecker, TranslationStatus, numbers_in


def _ok(domain="geometry", kind="square", target="A", known=None, bindings=None, partner=""):
    return {
        "status": "ok", "reason": "", "domain": domain, "context_kind": kind,
        "target": target, "target_quantity": "",
        "known": [{"name": k, "value": v} for k, v in (known or {}).items()],
        "variable_bindings": [{"from": a, "to": b} for a, b in (bindings or {}).items()],
        "partner_context_kind": partner,
    }


class TranslationCheckerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.checker = TranslationChecker(DomainCatalog(EngineGateway().graphs))

    def test_accepts_grounded_translation(self) -> None:
        t = self.checker.check("Area of a square with side 5?", _ok(known={"l": 5}))
        self.assertEqual(t.status, TranslationStatus.OK)
        self.assertEqual(t.query.known, {"l": 5.0})
        self.assertFalse(t.new_target)

    def test_rejects_invented_value(self) -> None:
        t = self.checker.check("What is the area of a square?", _ok(known={"l": 1}))
        self.assertEqual(t.status, TranslationStatus.REJECTED)
        self.assertIn("grounding", t.reason)

    def test_sign_rewrite_is_grounded(self) -> None:
        t = self.checker.check(
            "Find x if 7x = 21.",
            _ok("algebra", "linear_equation", "x", {"a": 7, "b": -21}),
        )
        self.assertEqual(t.status, TranslationStatus.OK)

    def test_rejects_unknown_domain_kind_and_variable(self) -> None:
        cases = [
            _ok(domain="chemistry"),
            _ok(kind="circle"),
            _ok(known={"r": 5}),
        ]
        for raw in cases:
            with self.subTest(raw=raw):
                t = self.checker.check("side 5 radius 5", raw)
                self.assertEqual(t.status, TranslationStatus.REJECTED)

    def test_rejects_target_given_as_known(self) -> None:
        t = self.checker.check("area 25 side 5", _ok(known={"A": 25, "l": 5}))
        self.assertEqual(t.status, TranslationStatus.REJECTED)

    def test_new_target_is_flagged(self) -> None:
        t = self.checker.check("Perimeter of a square with side 5?", _ok(target="P", known={"l": 5}))
        self.assertEqual(t.status, TranslationStatus.OK)
        self.assertTrue(t.new_target)

    def test_cross_domain_allows_partner_variables(self) -> None:
        raw = _ok("physics", "physics.object", "Ec", {"m": 2, "d": 8},
                  bindings={"v": "l"}, partner="square")
        t = self.checker.check("mass 2 kg, speed equal to the side of a square of diagonal 8", raw)
        self.assertEqual(t.status, TranslationStatus.OK)
        self.assertEqual(t.query.variable_bindings, {"v": "l"})

    def test_non_ok_statuses_pass_through(self) -> None:
        for status in ("out_of_scope", "insufficient_data"):
            raw = dict(_ok(), status=status, reason="because")
            self.assertEqual(self.checker.check("q", raw).status.value, status)

    def test_numbers_in_handles_thousands_separator(self) -> None:
        self.assertEqual(numbers_in("1,289.7 and 5x + 15"), [1289.7, 5.0, 15.0])


if __name__ == "__main__":
    unittest.main()
