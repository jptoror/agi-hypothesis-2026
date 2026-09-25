"""Tests de la gramática segura y del análisis dimensional (exp_22)."""
from __future__ import annotations

import math
import unittest

from experiment_22.catalog import AREA, ENERGY, LENGTH, MASS, SPEED, quantity_dimension
from experiment_22.expression import (
    Dimension,
    DimensionError,
    SafeExpression,
    UnsafeExpression,
)


class SafeExpressionTest(unittest.TestCase):
    def test_evaluates_allowed_grammar(self) -> None:
        expr = SafeExpression.parse("sqrt(2 * A) + pi - l^2 / 4")
        self.assertEqual(expr.variables, frozenset({"A", "l"}))
        self.assertAlmostEqual(
            expr.evaluate({"A": 8.0, "l": 2.0}), math.sqrt(16) + math.pi - 1.0,
        )

    def test_rejects_code_injection(self) -> None:
        for src in [
            "__import__('os').system('ls')",
            "l.real",
            "[l for l in range(3)]",
            "open('x')",
            "l if l > 0 else 0",
            "lambda: 1",
            "abs(l)",
            "'text'",
        ]:
            with self.subTest(src=src), self.assertRaises(UnsafeExpression):
                SafeExpression.parse(src)

    def test_missing_value_is_reported(self) -> None:
        with self.assertRaises(KeyError):
            SafeExpression.parse("m * v").evaluate({"m": 1.0})


class DimensionTest(unittest.TestCase):
    dims = {"l": LENGTH, "d": LENGTH, "A": AREA, "m": MASS, "v": SPEED}

    def test_infers_dimensions(self) -> None:
        cases = {
            "4 * l": LENGTH,
            "l ** 2": AREA,
            "sqrt(2 * A)": LENGTH,
            "0.5 * m * v ** 2": ENERGY,
            "d / sqrt(2)": LENGTH,
        }
        for src, expected in cases.items():
            with self.subTest(src=src):
                self.assertEqual(SafeExpression.parse(src).dimension(self.dims), expected)

    def test_adding_different_dimensions_is_an_error(self) -> None:
        with self.assertRaises(DimensionError):
            SafeExpression.parse("l + A").dimension(self.dims)

    def test_variable_exponent_is_an_error(self) -> None:
        with self.assertRaises(DimensionError):
            SafeExpression.parse("l ** m").dimension(self.dims)

    def test_quantity_table(self) -> None:
        self.assertEqual(quantity_dimension("perimeter"), LENGTH)
        self.assertEqual(quantity_dimension("the perimeter of the square"), LENGTH)
        self.assertEqual(quantity_dimension("momentum"), Dimension.of(M=1, L=1, T=-1))
        self.assertIsNone(quantity_dimension("happiness"))


if __name__ == "__main__":
    unittest.main()
