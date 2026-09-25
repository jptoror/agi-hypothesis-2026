from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from ..knowledge_graph import KnowledgeGraph
from ..specialist import KnowledgeGap, Problem


class GapCategory(str, Enum):
    """Tipos de gap que el orquestador sabe reconocer.

    MISSING_RELATION    — ningún nodo ejecutable produce la variable pedida.
    MISSING_INPUT       — la variable no aportada podría derivarse si tuviéramos
                          otra medida que el usuario no ha dado.
    INAPPLICABLE_NODES  — hay nodos que producen la variable pero sus
                          condiciones de validez no se cumplen para la figura.
    CYCLE               — se detectó una dependencia circular.
    UNKNOWN             — no encaja en ninguno de los anteriores.
    """

    MISSING_RELATION = "missing_relation"
    MISSING_INPUT = "missing_input"
    INAPPLICABLE_NODES = "inapplicable_nodes"
    CYCLE = "cycle"
    UNKNOWN = "unknown"


@dataclass
class GapClassification:
    """Diagnóstico estructurado de un gap."""

    category: GapCategory
    summary: str
    suggestions: list[str] = field(default_factory=list)
    raw_gap: KnowledgeGap | None = None

    def render(self) -> str:
        lines = [
            f"CATEGORÍA: {self.category.value}",
            f"  resumen: {self.summary}",
        ]
        if self.suggestions:
            lines.append("  sugerencias:")
            for s in self.suggestions:
                lines.append(f"    • {s}")
        return "\n".join(lines)


def classify_gap(
    gap: KnowledgeGap,
    problem: Problem,
    graph: KnowledgeGraph,
) -> GapClassification:
    """Clasifica un gap inspeccionando el grafo y el problema.

    No usa heurísticas estadísticas — comprueba hechos explícitos del
    grafo: ¿existen nodos que producen la variable? ¿sus condiciones
    exigen otro tipo de figura? ¿sus entradas son conocidas?
    """
    missing = gap.missing_variable

    # 1) Ciclo detectado por el especialista.
    if "ciclo" in gap.context.lower():
        return GapClassification(
            category=GapCategory.CYCLE,
            summary=(
                f"detección de ciclo al derivar '{missing}'. "
                f"Cadena activa: {' → '.join(gap.chain_at_failure)}"
            ),
            suggestions=[
                "revisar las dependencias del grafo para romper la circularidad",
            ],
            raw_gap=gap,
        )

    producers = graph.find_relations_producing(missing)

    # 2) No hay ningún productor en el grafo. Distinguimos dos sub-casos:
    #    (a) la variable faltante es una entrada esperada por los productores
    #        del objetivo — entonces el usuario simplemente no aportó un dato
    #        (MISSING_INPUT).
    #    (b) nadie produce esta variable y tampoco es un input esperado —
    #        entonces falta un teorema/definición (MISSING_RELATION).
    if not producers:
        target_producers = graph.find_relations_producing(problem.target)
        expected_as_input = any(missing in tp.inputs for tp in target_producers)
        if expected_as_input:
            alternative_inputs = sorted({
                inp
                for tp in target_producers
                for inp in tp.inputs
            })
            return GapClassification(
                category=GapCategory.MISSING_INPUT,
                summary=(
                    f"'{missing}' es una entrada esperada por algún teorema que "
                    f"produce '{problem.target}', pero no se aportó ni puede "
                    f"derivarse del contexto actual."
                ),
                suggestions=[
                    f"proporcionar al menos uno de: {', '.join(alternative_inputs)}",
                ],
                raw_gap=gap,
            )
        return GapClassification(
            category=GapCategory.MISSING_RELATION,
            summary=(
                f"el grafo no contiene ningún nodo ejecutable que produzca "
                f"'{missing}'."
            ),
            suggestions=[
                f"añadir un teorema o definición operativa que compute '{missing}'",
                "si es un dato de entrada, pedirlo explícitamente al usuario",
            ],
            raw_gap=gap,
        )

    # 3) Hay productores, pero ninguno es aplicable a la figura actual.
    figure_kind_short = problem.context.kind.split(".")[-1].lower()
    inapplicable = []
    applicable = []
    for p in producers:
        cond_txt = " ".join(p.validity_conditions).lower()
        mentions_other_figure = (
            ("cuadrado" in cond_txt or "square" in cond_txt)
            and figure_kind_short != "square"
        ) or (
            ("triángulo" in cond_txt or "triangle" in cond_txt)
            and "triangle" not in figure_kind_short
        )
        if mentions_other_figure:
            inapplicable.append(p.id)
        else:
            applicable.append(p)

    if producers and not applicable:
        return GapClassification(
            category=GapCategory.INAPPLICABLE_NODES,
            summary=(
                f"existen nodos que producen '{missing}' pero sus condiciones "
                f"de validez no se cumplen para {problem.context.describe()}."
            ),
            suggestions=[
                f"nodos descartados por condiciones: {', '.join(inapplicable)}",
                "añadir un teorema específico para este tipo de figura",
            ],
            raw_gap=gap,
        )

    # 4) Hay productores aplicables, pero alguna de sus entradas no es derivable.
    needed_inputs: set[str] = set()
    for p in applicable:
        for inp in p.inputs:
            if inp not in problem.context.known:
                needed_inputs.add(inp)
    if needed_inputs:
        return GapClassification(
            category=GapCategory.MISSING_INPUT,
            summary=(
                f"los nodos aplicables que producen '{missing}' requieren "
                f"variables que no se pueden derivar del contexto: "
                f"{', '.join(sorted(needed_inputs))}."
            ),
            suggestions=[
                f"proporcionar al menos uno de: {', '.join(sorted(needed_inputs))}",
                "añadir un teorema que derive esas variables del contexto actual",
            ],
            raw_gap=gap,
        )

    return GapClassification(
        category=GapCategory.UNKNOWN,
        summary=f"gap al derivar '{missing}' no clasificable con las reglas actuales.",
        raw_gap=gap,
    )
