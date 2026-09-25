"""Orquestador del experimento 02 — aprendizaje on-demand.

Ata los componentes en un único flujo auditable:

    detect gap  ─►  propose hypothesis  ─►  validate
        │               │                      │
        └── orch exp_01 └── hypothesis_engine  └── consistency_validator
                              │
                              ▼
                        adopt (HYPOTHESIS)  ─►  solve  ─►  record usage  ─►  consolidate (THEOREM)
                              │                   │             │                │
                              └── graph.add       └── specialist └── consolidator └── consolidator

La salida incluye la evidencia central pedida:

    "Grafo antes: N nodos | Grafo después: N+1 nodos"
    "Nodo nuevo: thm.<id> | status: THEOREM"
    "Fundamentos: ..."

Uso:
    python -m experiment_02.orchestrator
"""
from __future__ import annotations

from dataclasses import dataclass, field

from experiment_01.knowledge_graph import (
    KnowledgeGraph,
    build_geometry_2d_graph,
)
from experiment_01.orchestrator import Orchestrator as Exp1Orchestrator
from experiment_01.specialist import DomainContext, GeometrySpecialist, Problem

from .consistency_validator import ConsistencyValidator, ValidationResult
from .consolidation import ConsolidationResult, Consolidator
from .hypothesis_engine import HypothesisCandidate, HypothesisEngine


@dataclass
class LearningCycleReport:
    """Informe del ciclo completo para un problema."""

    problem: Problem
    nodes_before: int
    nodes_after: int

    gap_detected: bool
    gap_category: str | None
    missing_variable: str | None

    candidate: HypothesisCandidate | None
    validation: ValidationResult | None
    adopted_node_id: str | None
    solve_value: float | None
    solve_steps: list[str] = field(default_factory=list)
    consolidation: ConsolidationResult | None = None

    # Cuenta cuántas fases 2-6 se ejecutaron. 0 = el grafo ya tenía
    # todo lo necesario y no hubo ciclo de aprendizaje.
    learning_phases_executed: int = 0

    def render(self) -> str:
        line = "=" * 72
        lines = [
            line,
            "EXPERIMENTO 02 — CICLO DE APRENDIZAJE ON-DEMAND",
            line,
            f"Problema: {self.problem.statement}",
            f"Figura: {self.problem.context.describe()} | objetivo: {self.problem.target}",
            "",
            "── FASE 1: detección del gap ──",
        ]
        if not self.gap_detected:
            lines.append("  no se detectó gap — experimento no aplica.")
            return "\n".join(lines)
        lines.append(f"  gap detectado: '{self.missing_variable}' ({self.gap_category})")

        lines.append("")
        lines.append("── FASE 2: propuesta de hipótesis ──")
        if self.candidate is None:
            lines.append("  el engine no produjo candidatos.")
            return "\n".join(lines)
        lines.append(f"  candidato: {self.candidate.node.id}")
        lines.append(f"  patrón: {self.candidate.pattern_name}")
        lines.append(f"  enunciado: {self.candidate.node.statement}")

        lines.append("")
        lines.append("── FASE 3: validación ──")
        if self.validation is None:
            lines.append("  no validado.")
            return "\n".join(lines)
        lines.append(f"  válido: {self.validation.valid}")
        lines.append(f"  checks pasados: {', '.join(self.validation.checks_passed)}")
        if self.validation.checks_failed:
            lines.append(f"  checks fallidos: {', '.join(self.validation.checks_failed)}")

        lines.append("")
        lines.append("── FASE 4: adopción como HYPOTHESIS ──")
        if self.adopted_node_id is None:
            lines.append("  no se adoptó (validador rechazó).")
            return "\n".join(lines)
        lines.append(f"  nodo añadido al grafo: {self.adopted_node_id} (status: HYPOTHESIS)")

        lines.append("")
        lines.append("── FASE 5: resolución del problema ──")
        if self.solve_value is None:
            lines.append("  no resuelto tras adopción.")
        else:
            lines.append(f"  pasos: {' → '.join(self.solve_steps)}")
            lines.append(f"  resultado: {self.problem.target} = {self.solve_value}")

        lines.append("")
        lines.append("── FASE 6: consolidación HYPOTHESIS → THEOREM ──")
        if self.consolidation is None:
            lines.append("  no intentada.")
        else:
            lines.append(self.consolidation.render())

        lines.append("")
        lines.append("── EVIDENCIA DEL APRENDIZAJE ──")
        lines.append(
            f"Grafo antes: {self.nodes_before} nodos | "
            f"Grafo después: {self.nodes_after} nodos"
        )
        if (
            self.consolidation is not None
            and self.consolidation.promoted
            and self.consolidation.new_node_id is not None
        ):
            lines.append("Nodo nuevo: " + self.consolidation.new_node_id + " | status: THEOREM")
        elif self.adopted_node_id is not None:
            lines.append("Nodo nuevo: " + self.adopted_node_id + " | status: HYPOTHESIS")
        return "\n".join(lines)


class LearningOrchestrator:
    """Orquestador del ciclo completo de aprendizaje."""

    def __init__(
        self,
        graph: KnowledgeGraph,
        engine: HypothesisEngine | None = None,
        validator: ConsistencyValidator | None = None,
        consolidator: Consolidator | None = None,
    ) -> None:
        self.graph = graph
        self.engine = engine or HypothesisEngine()
        self.validator = validator or ConsistencyValidator()
        self.consolidator = consolidator or Consolidator(
            min_uses=1, validator=self.validator
        )
        self._exp1_orch = Exp1Orchestrator(graph)

    def run(self, problem: Problem, problem_id: str | None = None) -> LearningCycleReport:
        pid = problem_id or problem.statement
        nodes_before = len(self.graph)

        # Fase 1: detección del gap vía orchestrator del exp_01.
        first_report = self._exp1_orch.run(problem)
        if first_report.primary_result.success:
            # No hubo gap → no se ejecuta ningún paso del ciclo de aprendizaje.
            return LearningCycleReport(
                problem=problem,
                nodes_before=nodes_before,
                nodes_after=len(self.graph),
                gap_detected=False,
                gap_category=None,
                missing_variable=None,
                candidate=None,
                validation=None,
                adopted_node_id=None,
                solve_value=first_report.primary_result.value,
                solve_steps=first_report.primary_result.trace.nodes_used(),
                learning_phases_executed=0,
            )

        gap_class = first_report.gap_classification
        if gap_class is None or gap_class.raw_gap is None:
            return LearningCycleReport(
                problem=problem,
                nodes_before=nodes_before,
                nodes_after=len(self.graph),
                gap_detected=True,
                gap_category=None,
                missing_variable=None,
                candidate=None,
                validation=None,
                adopted_node_id=None,
                solve_value=None,
            )

        missing = gap_class.raw_gap.missing_variable
        phases_executed = 0

        # Fase 2: proponer hipótesis.
        candidates = self.engine.generate(missing, problem, self.graph)
        phases_executed += 1
        if not candidates:
            return LearningCycleReport(
                problem=problem,
                nodes_before=nodes_before,
                nodes_after=len(self.graph),
                gap_detected=True,
                gap_category=gap_class.category.value,
                missing_variable=missing,
                candidate=None,
                validation=None,
                adopted_node_id=None,
                solve_value=None,
                learning_phases_executed=phases_executed,
            )

        candidate = candidates[0]

        # Fase 3: validar.
        vres = self.validator.validate(candidate, self.graph)
        phases_executed += 1
        if not vres.valid:
            return LearningCycleReport(
                problem=problem,
                nodes_before=nodes_before,
                nodes_after=len(self.graph),
                gap_detected=True,
                gap_category=gap_class.category.value,
                missing_variable=missing,
                candidate=candidate,
                validation=vres,
                adopted_node_id=None,
                solve_value=None,
                learning_phases_executed=phases_executed,
            )

        # Fase 4: adoptar como HYPOTHESIS.
        self.graph.add(candidate.node)
        adopted_id = candidate.node.id
        phases_executed += 1

        # Fase 5: resolver usando el grafo ya extendido.
        specialist = GeometrySpecialist(self.graph)
        solve_result = specialist.solve(problem)
        phases_executed += 1

        solve_value: float | None = None
        solve_steps: list[str] = []
        if solve_result.success:
            solve_value = solve_result.value
            solve_steps = solve_result.trace.nodes_used()
            # Registrar uso exitoso si la hipótesis se usó en la derivación.
            if adopted_id in solve_steps:
                step = next(s for s in solve_result.trace.steps if s.node_id == adopted_id)
                self.consolidator.record_usage(
                    node_id=adopted_id,
                    problem_id=pid,
                    inputs_used=step.inputs,
                    output_produced=step.outputs,
                )

        # Fase 6: consolidar.
        consol = self.consolidator.try_consolidate(
            node_id=adopted_id,
            graph=self.graph,
            candidate=candidate,
        )
        phases_executed += 1

        return LearningCycleReport(
            problem=problem,
            nodes_before=nodes_before,
            nodes_after=len(self.graph),
            gap_detected=True,
            gap_category=gap_class.category.value,
            missing_variable=missing,
            candidate=candidate,
            validation=vres,
            adopted_node_id=adopted_id,
            solve_value=solve_value,
            solve_steps=solve_steps,
            consolidation=consol,
            learning_phases_executed=phases_executed,
        )


def main() -> None:
    graph = build_geometry_2d_graph()
    orch = LearningOrchestrator(graph)

    problem = Problem(
        statement="¿Cuál es el perímetro de un cuadrado de lado 5?",
        target="P",
        context=DomainContext(kind="square", known={"l": 5.0}),
    )
    report = orch.run(problem, problem_id="exp02.square_perimeter_l5")
    print(report.render())

    # Resumen compacto exigido por el enunciado del experimento.
    print()
    print("-" * 72)
    print("RESUMEN EJECUTIVO")
    print("-" * 72)
    print(f"Grafo antes: {report.nodes_before} nodos | "
          f"Grafo después: {report.nodes_after} nodos")
    if (
        report.consolidation is not None
        and report.consolidation.promoted
        and report.consolidation.new_node_id is not None
    ):
        new_id = report.consolidation.new_node_id
        new_node = graph.get(new_id)
        print(f"Nodo nuevo: {new_id} | status: {new_node.status.value.upper()}")
        print(f"Fundamentos: {', '.join(new_node.foundations)}")


if __name__ == "__main__":
    main()
