"""Set de preguntas del benchmark del exp_22.

63 preguntas en seis categorías. La respuesta correcta se CALCULA
con `math` en este archivo — nunca se escribe a mano un número que
pueda estar mal copiado.

  IN         dentro de dominio, una relación conocida.
  PRECISION  dentro de dominio con números "incómodos": mide
             aritmética exacta, no conocimiento.
  CROSS      requiere dos especialistas (Física + Geometría).
  LEARN      la relación NO está en el grafo: sólo se responde si
             una hipótesis del LLM supera la verificación.
  OUT        fuera de todos los dominios del sistema.
  TRAP       mal planteadas o con datos insuficientes: la respuesta
             correcta es NO responder (expected = None).

Cada pregunta lleva además la traducción "oráculo" (la consulta
estructurada correcta) y, para LEARN, la hipótesis correcta. Sirven
para dos cosas: el modo `engine-only` (el motor recibe la consulta
perfecta, como en el exp_10) y el modo `oracle` del pipeline (techo
del sistema con un LLM perfecto). Ninguna de las dos se usa cuando
el benchmark corre contra un LLM real.

Lo que el set NO es: una muestra representativa de "preguntas del
mundo". Está diseñado para ejercitar cada camino del pipeline. Los
porcentajes describen el comportamiento del sistema sobre ESTE set.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum


class Category(str, Enum):
    IN = "IN"
    PRECISION = "PRECISION"
    CROSS = "CROSS"
    LEARN = "LEARN"
    OUT = "OUT"
    TRAP = "TRAP"


@dataclass
class Question:
    qid: str
    category: Category
    text: str
    expected: float | None            # None → la respuesta correcta es abstenerse
    oracle: dict                       # traducción correcta (formato TRANSLATION_SCHEMA)
    oracle_hypotheses: dict[str, dict] = field(default_factory=dict)  # missing_var → propuesta
    note: str = ""

    @property
    def rel_tol(self) -> float:
        return 1e-6 if self.category == Category.PRECISION else 1e-3


# -- constructores de traducciones oráculo ---------------------------------

def _ok(domain, kind, target, known, quantity="", bindings=None, partner=""):
    return {
        "status": "ok", "reason": "", "domain": domain, "context_kind": kind,
        "target": target, "target_quantity": quantity,
        "known": [{"name": k, "value": v} for k, v in known.items()],
        "variable_bindings": [{"from": a, "to": b} for a, b in (bindings or {}).items()],
        "partner_context_kind": partner,
    }


def _status(status, reason):
    return {
        "status": status, "reason": reason, "domain": "", "context_kind": "", "target": "",
        "target_quantity": "", "known": [], "variable_bindings": [], "partner_context_kind": "",
    }


def _hyp(output, expression, inputs, foundations, dim, statement=""):
    return {
        "status": "proposed", "reason": "", "statement": statement or f"{output} = {expression}",
        "output": output, "inputs": inputs, "expression": expression,
        "foundations": foundations, "output_dimension": dict(zip("MLT", dim)),
    }


SQ2 = math.sqrt(2)


def _questions() -> list[Question]:
    q: list[Question] = []
    add = q.append

    # ---------------- IN — geometría ----------------
    for i, side in enumerate([5, 12, 7.5, 0.4], 1):
        text = [
            f"What is the area of a square with side {side}?",
            f"A square has sides of length {side} cm. Find its area.",
            f"Compute the area of a square whose side measures {side}.",
            f"If each side of a square is {side} m long, what is the area?",
        ][i - 1]
        add(Question(f"IN-G{i}", Category.IN, text, side**2,
                     _ok("geometry", "square", "A", {"l": side})))
    for i, d in enumerate([8, 10, 3, 14], 5):
        add(Question(f"IN-G{i}", Category.IN,
                     f"What is the area of a square whose diagonal is {d}?", d**2 / 2,
                     _ok("geometry", "square", "A", {"d": d})))
    for i, d in enumerate([8, 5, 20], 9):
        add(Question(f"IN-G{i}", Category.IN,
                     f"The diagonal of a square is {d}. How long is its side?", d / SQ2,
                     _ok("geometry", "square", "l", {"d": d})))
    for i, (a, b) in enumerate([(3, 4), (5, 12), (8, 15), (1, 1)], 12):
        add(Question(f"IN-G{i}", Category.IN,
                     f"A right triangle has legs {a} and {b}. What is the hypotenuse?",
                     math.hypot(a, b),
                     _ok("geometry", "triangle.right", "c", {"a": a, "b": b})))

    # ---------------- IN — física ----------------
    for i, (m, v) in enumerate([(2, 3), (10, 4), (0.5, 20), (1200, 25), (70, 9.8)], 1):
        add(Question(f"IN-P{i}", Category.IN,
                     f"What is the kinetic energy of an object of mass {m} kg moving at {v} m/s?",
                     0.5 * m * v**2,
                     _ok("physics", "physics.object", "Ec", {"m": m, "v": v})))

    # ---------------- IN — álgebra ----------------
    for i, (text, a, b) in enumerate([
        ("Solve for x: 5x + 15 = 0", 5, 15),
        ("What value of x satisfies 3x - 12 = 0?", 3, -12),
        ("Find x if 7x = 21.", 7, -21),
        ("Solve 2x + 9 = 0.", 2, 9),
        ("Solve for x: -4x + 10 = 0", -4, 10),
        ("Find x such that 0.5x - 3 = 0.", 0.5, -3),
    ], 1):
        add(Question(f"IN-A{i}", Category.IN, text, -b / a,
                     _ok("algebra", "linear_equation", "x", {"a": a, "b": b})))

    # ---------------- PRECISION ----------------
    add(Question("PR-1", Category.PRECISION,
                 "What is the kinetic energy of a 73.519 kg object moving at 1289.7 m/s?",
                 0.5 * 73.519 * 1289.7**2,
                 _ok("physics", "physics.object", "Ec", {"m": 73.519, "v": 1289.7})))
    add(Question("PR-2", Category.PRECISION,
                 "Kinetic energy of a mass of 0.0047 kg at 315.25 m/s?",
                 0.5 * 0.0047 * 315.25**2,
                 _ok("physics", "physics.object", "Ec", {"m": 0.0047, "v": 315.25})))
    add(Question("PR-3", Category.PRECISION,
                 "A right triangle has legs 12345.678 and 98765.4321. What is the hypotenuse?",
                 math.hypot(12345.678, 98765.4321),
                 _ok("geometry", "triangle.right", "c", {"a": 12345.678, "b": 98765.4321})))
    add(Question("PR-4", Category.PRECISION,
                 "What is the area of a square whose diagonal is 9876.54321?",
                 9876.54321**2 / 2,
                 _ok("geometry", "square", "A", {"d": 9876.54321})))
    add(Question("PR-5", Category.PRECISION,
                 "What is the area of a square with side 3.14159?", 3.14159**2,
                 _ok("geometry", "square", "A", {"l": 3.14159})))
    add(Question("PR-6", Category.PRECISION, "Solve for x: 13.7x + 291.4 = 0",
                 -291.4 / 13.7,
                 _ok("algebra", "linear_equation", "x", {"a": 13.7, "b": 291.4})))
    add(Question("PR-7", Category.PRECISION,
                 "A right triangle has legs 0.0123 and 0.0456. What is the hypotenuse?",
                 math.hypot(0.0123, 0.0456),
                 _ok("geometry", "triangle.right", "c", {"a": 0.0123, "b": 0.0456})))
    add(Question("PR-8", Category.PRECISION,
                 "The diagonal of a square is 1234.5678. How long is its side?",
                 1234.5678 / SQ2,
                 _ok("geometry", "square", "l", {"d": 1234.5678})))

    # ---------------- CROSS ----------------
    for i, (m, d) in enumerate([(2, 8), (3, 10), (5, 6), (1.5, 12)], 1):
        add(Question(f"CR-{i}", Category.CROSS,
                     f"What is the kinetic energy of an object of mass {m} kg moving at a "
                     f"speed equal to the side of a square whose diagonal is {d}?",
                     0.5 * m * (d / SQ2) ** 2,
                     _ok("physics", "physics.object", "Ec", {"m": m, "d": d},
                         bindings={"v": "l"}, partner="square")))

    # ---------------- LEARN ----------------
    perimeter = _hyp("P", "4 * l", ["l"], ["def.square"], (0, 1, 0))
    for i, side in enumerate([5, 12.5, 0.8], 1):
        add(Question(f"LE-{i}", Category.LEARN,
                     f"What is the perimeter of a square with side {side}?", 4 * side,
                     _ok("geometry", "square", "P", {"l": side}, quantity="perimeter"),
                     {"P": perimeter},
                     note="el patrón SumOfEqualParts del exp_02 deriva P = 4·l → CORROBORATED"))
    diag = _hyp("d", "l * sqrt(2)", ["l"], ["def.square", "thm.pythagoras"], (0, 1, 0))
    for i, side in enumerate([5, 3], 4):
        add(Question(f"LE-{i}", Category.LEARN,
                     f"How long is the diagonal of a square with side {side}?", side * SQ2,
                     _ok("geometry", "square", "d", {"l": side}),
                     {"d": diag},
                     note="ningún patrón propio deriva d desde l → CONDITIONAL"))
    d_from_area = _hyp("d", "sqrt(2 * A)", ["A"], ["def.square", "thm.square.area_from_diagonal"],
                       (0, 1, 0))
    for i, area in enumerate([49, 2.25], 6):
        add(Question(f"LE-{i}", Category.LEARN,
                     f"A square has an area of {area}. How long is its side?", math.sqrt(area),
                     _ok("geometry", "square", "l", {"A": area}),
                     {"d": d_from_area},
                     note="el motor declara el gap en 'd' (l ← d); la hipótesis cubre ese eslabón"))
    add(Question("LE-8", Category.LEARN,
                 "A square has a perimeter of 20. What is its area?", 25.0,
                 _ok("geometry", "square", "A", {"P": 20}, quantity="area"),
                 {"d": _hyp("d", "P * sqrt(2) / 4", ["P"], ["def.square"], (0, 1, 0))},
                 note="P no está en el catálogo de variables: la traducción oráculo se rechaza"))
    add(Question("LE-9", Category.LEARN,
                 "What is the momentum of a 3 kg object moving at 4 m/s?", 12.0,
                 _ok("physics", "physics.object", "p", {"m": 3, "v": 4}, quantity="momentum"),
                 {"p": _hyp("p", "m * v", ["m", "v"], ["def.mass", "def.velocity"], (1, 1, -1))},
                 note="p = m·v, dimensión M·L·T⁻¹ desde la tabla de magnitudes → CONDITIONAL"))
    add(Question("LE-10", Category.LEARN,
                 "What is the weight of a 10 kg object on Earth, in newtons?", 98.1,
                 _ok("physics", "physics.object", "W", {"m": 10}, quantity="weight"),
                 {"W": _hyp("W", "9.81 * m", ["m"], ["def.mass"], (1, 1, -2))},
                 note="límite declarado: g es una constante sin dimensión en la gramática → "
                      "el check dimensional rechaza W = 9.81·m"))
    add(Question("LE-11", Category.LEARN,
                 "An object of mass 8 kg has a kinetic energy of 100 J. What is its speed?", 5.0,
                 _ok("physics", "physics.object", "v", {"m": 8, "Ec": 100}),
                 {"v": _hyp("v", "sqrt(2 * Ec / m)", ["Ec", "m"],
                            ["thm.kinetic_energy"], (0, 1, -1))},
                 note="límite declarado: el check de ejecución del exp_02 prueba con m = 0 → "
                      "división por cero → rechazo"))

    # ---------------- OUT ----------------
    for i, (text, value) in enumerate([
        ("How many seconds are in 3.5 hours?", 3.5 * 3600),
        ("What is 15% of 240?", 36.0),
        ("What is the simple interest on 1000 dollars at 5% per year for 3 years?", 150.0),
        ("What is the area of a circle with radius 3?", math.pi * 9),
        ("What is the average of 4, 8 and 15?", 9.0),
        ("What is the volume of a cube with edge 4?", 64.0),
    ], 1):
        add(Question(f"OUT-{i}", Category.OUT, text, value,
                     _status("out_of_scope", "not about squares, right triangles, "
                             "moving objects or linear equations")))

    # ---------------- TRAP ----------------
    traps = [
        ("What is the area of a square?", "insufficient_data", "no side or diagonal given"),
        ("What is the kinetic energy of an object with mass 3 kg?",
         "insufficient_data", "speed missing"),
        ("What is the hypotenuse of a right triangle with one leg of 5?",
         "insufficient_data", "second leg missing"),
        ("What is the kinetic energy of a car moving at 20 m/s?",
         "insufficient_data", "mass missing"),
    ]
    for i, (text, status, reason) in enumerate(traps, 1):
        add(Question(f"TR-{i}", Category.TRAP, text, None, _status(status, reason)))
    add(Question("TR-5", Category.TRAP, "Solve for x: 0x + 5 = 0", None,
                 _ok("algebra", "linear_equation", "x", {"a": 0, "b": 5}),
                 note="sin solución: la guarda de precondiciones ('a ≠ 0') debe abstenerse"))
    add(Question("TR-6", Category.TRAP, "What is the area of a square with side -4?", None,
                 _ok("geometry", "square", "A", {"l": -4}),
                 note="longitud negativa: viola 'l >= 0'"))
    add(Question("TR-7", Category.TRAP,
                 "A triangle has two sides of length 3 and 4. How long is the third side?",
                 None,
                 _status("insufficient_data", "the angle between the sides is not given"),
                 note="no dice que sea rectángulo: responder 5 es suponer. Si el traductor "
                      "lo manda al motor como 'triangle', Pitágoras queda desactivado por la "
                      "guarda y una hipótesis sqrt(a²+b²) se rechaza por redundante"))
    return q


QUESTIONS: list[Question] = _questions()
