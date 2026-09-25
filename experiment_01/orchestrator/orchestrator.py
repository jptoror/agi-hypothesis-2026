from __future__ import annotations

from dataclasses import dataclass, field

from ..knowledge_graph import KnowledgeGraph
from ..specialist import GeometrySpecialist, Problem, SolveResult
from .gap_classifier import GapClassification, classify_gap


@dataclass
class RobustnessCheck:
    """Resultado de resolver tras desactivar un único nodo.

    Si el problema sigue resolviéndose, el nodo era redundante en el grafo
    para este caso. Si falla, el nodo era crítico y la clasificación del
    gap emergente describe qué se rompe al quitarlo.
    """

    disabled_node: str
    still_solved: bool
    alternative_steps: list[str] = field(default_factory=list)
    induced_gap: GapClassification | None = None

    def render(self) -> str:
        if self.still_solved:
            ruta = " → ".join(self.alternative_steps) or "(sin pasos)"
            return (
                f"  - sin '{self.disabled_node}': sigue resuelto por ruta "
                f"alternativa {ruta}"
            )
        gap_txt = self.induced_gap.summary if self.induced_gap else "sin clasificación"
        return (
            f"  - sin '{self.disabled_node}': NO resuelto — {gap_txt}"
        )


@dataclass
class OrchestratorReport:
    """Informe completo del orquestador sobre un problema."""

    problem: Problem
    primary_result: SolveResult
    gap_classification: GapClassification | None
    robustness: list[RobustnessCheck] = field(default_factory=list)

    def render(self) -> str:
        lines = [
            "=" * 72,
            "INFORME DEL ORQUESTADOR",
            "=" * 72,
            "",
            self.primary_result.render(),
            "",
        ]
        if self.gap_classification is not None:
            lines.append("--- CLASIFICACIÓN DEL GAP ---")
            lines.append(self.gap_classification.render())
            lines.append("")
        if self.robustness:
            lines.append("--- ANÁLISIS DE ROBUSTEZ (un nodo desactivado por vez) ---")
            for rc in self.robustness:
                lines.append(rc.render())
        return "\n".join(lines)


class Orchestrator:
    """Orquestador que detecta gaps y evalúa la robustez de la derivación.

    Dos responsabilidades:
    1. Correr el especialista y, si falla, clasificar el gap.
    2. Si tiene éxito, probar la robustez: ¿qué pasa si desactivamos uno
       a uno los nodos que usó? Esto diferencia dependencias críticas
       (gap latente) de redundancias (el grafo tiene rutas alternativas).
    """

    def __init__(self, graph: KnowledgeGraph) -> None:
        self.graph = graph

    def run(self, problem: Problem) -> OrchestratorReport:
        specialist = GeometrySpecialist(self.graph)
        result = specialist.solve(problem)

        classification: GapClassification | None = None
        robustness: list[RobustnessCheck] = []

        if not result.success and result.gap is not None:
            classification = classify_gap(result.gap, problem, self.graph)
        elif result.success:
            robustness = self._robustness_sweep(problem, result)

        return OrchestratorReport(
            problem=problem,
            primary_result=result,
            gap_classification=classification,
            robustness=robustness,
        )

    # -- internals ------------------------------------------------------

    def _robustness_sweep(
        self,
        problem: Problem,
        baseline: SolveResult,
    ) -> list[RobustnessCheck]:
        checks: list[RobustnessCheck] = []
        used_nodes = baseline.trace.nodes_used()
        for node_id in used_nodes:
            probe = GeometrySpecialist(self.graph, disabled_nodes={node_id})
            r = probe.solve(problem)
            if r.success:
                checks.append(RobustnessCheck(
                    disabled_node=node_id,
                    still_solved=True,
                    alternative_steps=r.trace.nodes_used(),
                ))
            else:
                induced = (
                    classify_gap(r.gap, problem, self.graph)
                    if r.gap is not None
                    else None
                )
                checks.append(RobustnessCheck(
                    disabled_node=node_id,
                    still_solved=False,
                    induced_gap=induced,
                ))
        return checks
