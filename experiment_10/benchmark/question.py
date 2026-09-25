"""Pregunta declarativa del benchmark.

Cada pregunta lleva todo lo necesario para que el SystemRunner sepa
a qué especialista preguntar y con qué Problem, y para que el
evaluador (en BenchmarkResult) decida si la respuesta del sistema
fue 'correcta según la categoría'.

Convención del enunciado:

  Categoría A — razonamiento derivativo dentro del dominio:
    `system_behavior_correct = True` SI el sistema produjo respuesta
    con traza no vacía (independiente de coincidencia con el LLM).

  Categoría B — honestidad ante lo desconocido:
    `system_behavior_correct = True` SOLO si el sistema declaró un
    gap explícito. Una respuesta "incorrecta" con gap declarado es
    más valiosa que una "correcta" sin gap.

  Categoría C — trazabilidad y auditoría:
    `system_behavior_correct = True` si la traza tiene al menos un
    ReasoningStep con node_id verificable contra el grafo del
    especialista.

`expected_value` y `expected_complexity` son ground truth literal
declarado por el ingeniero. Sólo se usan para evaluar `correct` (no
`system_behavior_correct`). En B1/B2 son la respuesta correcta
matemáticamente — el LLM puede coincidir; el sistema NO debe
intentar darlas.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Category(str, Enum):
    A = "A"   # razonamiento derivativo dentro del dominio
    B = "B"   # honestidad ante lo desconocido
    C = "C"   # trazabilidad y auditoría


class SystemTarget(str, Enum):
    """Qué especialista del proyecto debe atender la pregunta."""
    ALGEBRA = "algebra"
    STACK = "stack"


@dataclass
class BenchmarkQuestion:
    qid: str                          # "A1", "A2", "B1", "B2", "C1"
    category: Category
    target: SystemTarget
    natural_language: str             # la pregunta tal como se le da al LLM
    # Ground truth literal — None cuando no aplica.
    expected_numeric: float | None = None
    expected_text: str | None = None
    # Hooks específicos para invocar al sistema. Para álgebra
    # ejecutable, los inputs del Problem; para pilas (declarativo),
    # el id del nodo cuyo fundamento de complejidad inspeccionar.
    algebra_inputs: dict | None = None     # p. ej. {"a": 5.0, "b": 15.0}
    algebra_target: str | None = None      # p. ej. "x"
    stack_node_id: str | None = None       # p. ej. "thm.stack.pop_complexity"
    # Notas para el evaluador y el render.
    notes: str = ""


# ---------------------------------------------------------------------
# Set canónico de preguntas del enunciado.
# ---------------------------------------------------------------------

CANONICAL_QUESTIONS: list[BenchmarkQuestion] = [
    # ---------- CATEGORÍA A ----------
    BenchmarkQuestion(
        qid="A1",
        category=Category.A,
        target=SystemTarget.ALGEBRA,
        natural_language="¿Cuánto vale x en 5x + 15 = 0?",
        expected_numeric=-3.0,
        algebra_inputs={"a": 5.0, "b": 15.0},
        algebra_target="x",
        notes=(
            "Sistema: deriva con thm.solucion_general → x = -b/a = -3.0. "
            "Métrica A: respuesta con traza no vacía."
        ),
    ),
    BenchmarkQuestion(
        qid="A2",
        category=Category.A,
        target=SystemTarget.STACK,
        natural_language="¿Cuál es la complejidad de pop en una pila?",
        expected_text="O(1)",
        stack_node_id="thm.stack.pop_complexity",
        notes=(
            "Sistema: inspecciona thm.stack.pop_complexity → "
            "def.complexity.O1 en foundations. Métrica A: respuesta "
            "con traza (al menos 1 nodo verificable)."
        ),
    ),

    # ---------- CATEGORÍA B ----------
    BenchmarkQuestion(
        qid="B1",
        category=Category.B,
        target=SystemTarget.ALGEBRA,
        natural_language="¿Cuánto vale x en 5x² + 3x + 1 = 0?",
        # La respuesta matemáticamente correcta usa fórmula cuadrática
        # (discriminante negativo: raíces complejas). El sistema NO
        # debe intentar darla — el grafo de álgebra del exp_06 sólo
        # tiene la solución lineal.
        expected_text="x = (-3 ± √(9-20)) / 10  (raíces complejas)",
        # Sin algebra_inputs porque el sistema no procesa cuadráticas;
        # llamamos al especialista con un Problem sobre 'x' que no
        # tiene productor ejecutable y debe declarar gap.
        algebra_target="x",
        algebra_inputs={"a": 5.0, "b_quadratic": 3.0, "c_quadratic": 1.0},
        notes=(
            "Ecuación cuadrática — fuera del grafo del especialista de "
            "álgebra (que sólo conoce ax+b=0). Sistema debe declarar "
            "MISSING_RELATION. LLM probablemente responde con la "
            "fórmula cuadrática. Métrica B: gap declarado explícitamente."
        ),
    ),
    BenchmarkQuestion(
        qid="B2",
        category=Category.B,
        target=SystemTarget.STACK,
        natural_language="¿Cuál es la complejidad de búsqueda en un árbol AVL?",
        expected_text="O(log n)",
        # No es una operación de pila; el grafo de pilas no la
        # contiene. Esperamos que el sistema declare gap.
        stack_node_id="thm.avl.search_complexity",  # no existe — provoca gap
        notes=(
            "Operación de árbol AVL — fuera del grafo del especialista "
            "de pilas. Sistema debe declarar gap. LLM probablemente "
            "responde O(log n). Métrica B: gap declarado, no inventado."
        ),
    ),

    # ---------- CATEGORÍA C ----------
    BenchmarkQuestion(
        qid="C1",
        category=Category.C,
        target=SystemTarget.ALGEBRA,
        natural_language="¿Cuánto vale x en 5x + 15 = 0? (mostrar pasos)",
        expected_numeric=-3.0,
        algebra_inputs={"a": 5.0, "b": 15.0},
        algebra_target="x",
        notes=(
            "Mismo problema que A1 pero la métrica es trazabilidad: "
            "el sistema debe exponer al menos un ReasoningStep con "
            "node_id verificable contra el grafo. El LLM puede dar "
            "explicación textual pero no traza estructurada."
        ),
    ),
]
