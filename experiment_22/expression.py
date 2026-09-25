"""Expresiones aritméticas seguras + análisis dimensional.

El LLM propone fórmulas como TEXTO (p. ej. "4 * l"). Nunca se
evalúan con `eval`: se parsean con `ast` y sólo se aceptan nodos de
una gramática mínima y declarada:

    número | variable | pi | ( expr ) | -expr
    expr (+ | - | * | / | **) expr
    sqrt(expr)

Cualquier otra construcción (llamadas arbitrarias, atributos,
subíndices, comparaciones, lambdas...) se rechaza con
`UnsafeExpression`. La gramática es deliberadamente pequeña: una
hipótesis que no cabe en ella no es verificable por este sistema, y
eso es un resultado — no un fallo a esconder.

Además de evaluar, el módulo infiere la DIMENSIÓN física de la
expresión (exponentes de masa M, longitud L y tiempo T) a partir de
las dimensiones declaradas de sus variables. Es el check más barato
y más general que existe contra fórmulas inventadas: `P = l²` no
puede ser un perímetro porque tiene dimensión L², no L.
"""
from __future__ import annotations

import ast
import math
from dataclasses import dataclass
from fractions import Fraction
from typing import Mapping


class UnsafeExpression(ValueError):
    """La expresión contiene construcciones fuera de la gramática."""


class DimensionError(ValueError):
    """La expresión mezcla dimensiones de forma inválida (p. ej. L + M)."""


# ---------------------------------------------------------------------
# Dimensiones
# ---------------------------------------------------------------------

_BASES = ("M", "L", "T")


@dataclass(frozen=True)
class Dimension:
    """Exponentes de masa (M), longitud (L) y tiempo (T).

    Se usan fracciones para que sqrt(L²) = L sea exacto y para que
    exponentes como 1/2 no introduzcan error de coma flotante en la
    comparación.
    """

    M: Fraction = Fraction(0)
    L: Fraction = Fraction(0)
    T: Fraction = Fraction(0)

    @staticmethod
    def of(M: float = 0, L: float = 0, T: float = 0) -> "Dimension":
        return Dimension(
            Fraction(M).limit_denominator(12),
            Fraction(L).limit_denominator(12),
            Fraction(T).limit_denominator(12),
        )

    @staticmethod
    def from_mapping(m: Mapping[str, float]) -> "Dimension":
        return Dimension.of(**{b: m.get(b, 0) for b in _BASES})

    def __mul__(self, other: "Dimension") -> "Dimension":
        return Dimension(self.M + other.M, self.L + other.L, self.T + other.T)

    def __truediv__(self, other: "Dimension") -> "Dimension":
        return Dimension(self.M - other.M, self.L - other.L, self.T - other.T)

    def __pow__(self, k: Fraction) -> "Dimension":
        return Dimension(self.M * k, self.L * k, self.T * k)

    @property
    def is_dimensionless(self) -> bool:
        return self.M == 0 and self.L == 0 and self.T == 0

    def render(self) -> str:
        parts = []
        for base in _BASES:
            exp = getattr(self, base)
            if exp == 0:
                continue
            parts.append(base if exp == 1 else f"{base}^{exp}")
        return "·".join(parts) or "1"


DIMENSIONLESS = Dimension()


# ---------------------------------------------------------------------
# Expresión segura
# ---------------------------------------------------------------------

_ALLOWED_BINOPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)
_ALLOWED_FUNCS = {"sqrt"}
_CONSTANTS = {"pi": math.pi}


@dataclass(frozen=True)
class SafeExpression:
    """Expresión parseada y validada contra la gramática."""

    source: str
    tree: ast.Expression
    variables: frozenset[str]

    @staticmethod
    def parse(source: str) -> "SafeExpression":
        text = (source or "").strip().replace("^", "**").replace("·", "*")
        if not text:
            raise UnsafeExpression("expresión vacía")
        if len(text) > 200:
            raise UnsafeExpression("expresión demasiado larga (>200 caracteres)")
        try:
            tree = ast.parse(text, mode="eval")
        except SyntaxError as e:
            raise UnsafeExpression(f"sintaxis inválida: {e.msg}") from e
        variables: set[str] = set()
        _check_node(tree.body, variables)
        return SafeExpression(source=text, tree=tree, variables=frozenset(variables))

    def evaluate(self, values: Mapping[str, float]) -> float:
        missing = self.variables - set(values)
        if missing:
            raise KeyError(f"faltan valores para: {', '.join(sorted(missing))}")
        return float(_eval(self.tree.body, values))

    def dimension(self, dims: Mapping[str, Dimension]) -> Dimension:
        missing = self.variables - set(dims)
        if missing:
            raise DimensionError(
                f"variables sin dimensión declarada: {', '.join(sorted(missing))}"
            )
        return _dim(self.tree.body, dims)


def _check_node(node: ast.AST, variables: set[str]) -> None:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise UnsafeExpression(f"constante no numérica: {node.value!r}")
        return
    if isinstance(node, ast.Name):
        if node.id not in _CONSTANTS:
            variables.add(node.id)
        return
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        _check_node(node.operand, variables)
        return
    if isinstance(node, ast.BinOp) and isinstance(node.op, _ALLOWED_BINOPS):
        _check_node(node.left, variables)
        _check_node(node.right, variables)
        return
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in _ALLOWED_FUNCS
        and len(node.args) == 1
        and not node.keywords
    ):
        _check_node(node.args[0], variables)
        return
    raise UnsafeExpression(f"construcción no permitida: {type(node).__name__}")


def _eval(node: ast.AST, values: Mapping[str, float]) -> float:
    if isinstance(node, ast.Constant):
        return float(node.value)
    if isinstance(node, ast.Name):
        if node.id in _CONSTANTS:
            return _CONSTANTS[node.id]
        return float(values[node.id])
    if isinstance(node, ast.UnaryOp):
        v = _eval(node.operand, values)
        return -v if isinstance(node.op, ast.USub) else v
    if isinstance(node, ast.BinOp):
        a, b = _eval(node.left, values), _eval(node.right, values)
        if isinstance(node.op, ast.Add):
            return a + b
        if isinstance(node.op, ast.Sub):
            return a - b
        if isinstance(node.op, ast.Mult):
            return a * b
        if isinstance(node.op, ast.Div):
            return a / b
        return a ** b
    if isinstance(node, ast.Call):
        return math.sqrt(_eval(node.args[0], values))
    raise UnsafeExpression(f"nodo inesperado: {type(node).__name__}")


def _constant_exponent(node: ast.AST) -> Fraction:
    """El exponente de `**` debe ser una constante numérica: una
    dimensión elevada a una variable no tiene sentido físico."""
    if isinstance(node, ast.Constant):
        return Fraction(node.value).limit_denominator(12)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_constant_exponent(node.operand)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        return _constant_exponent(node.left) / _constant_exponent(node.right)
    raise DimensionError("el exponente de una potencia debe ser una constante numérica")


def _dim(node: ast.AST, dims: Mapping[str, Dimension]) -> Dimension:
    if isinstance(node, ast.Constant):
        return DIMENSIONLESS
    if isinstance(node, ast.Name):
        if node.id in _CONSTANTS:
            return DIMENSIONLESS
        return dims[node.id]
    if isinstance(node, ast.UnaryOp):
        return _dim(node.operand, dims)
    if isinstance(node, ast.BinOp):
        if isinstance(node.op, ast.Pow):
            base = _dim(node.left, dims)
            if base.is_dimensionless:
                return DIMENSIONLESS
            return base ** _constant_exponent(node.right)
        left, right = _dim(node.left, dims), _dim(node.right, dims)
        if isinstance(node.op, (ast.Add, ast.Sub)):
            if left != right:
                raise DimensionError(
                    f"suma/resta de dimensiones distintas: {left.render()} y {right.render()}"
                )
            return left
        if isinstance(node.op, ast.Mult):
            return left * right
        return left / right
    if isinstance(node, ast.Call):
        return _dim(node.args[0], dims) ** Fraction(1, 2)
    raise DimensionError(f"nodo inesperado: {type(node).__name__}")
