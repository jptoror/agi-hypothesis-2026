"""Orquestador del experimento 07 — lenguaje → álgebra → respuesta.

Compone dos especialistas independientes:

  1. LanguageSpecialist (este experimento) — convierte una
     instrucción semi-estructurada en un Problem verificado.
  2. Especialista de álgebra (construido vía SpecialistFactory del
     exp_06 a partir de algebra_ch3.md) — resuelve el Problem.

El orchestrator no conoce ni nodos de lenguaje ni nodos de álgebra.
Sólo compone: invoca al primero, valida que produjo un Problem
completo, y delega al segundo.

La traza unificada tiene prefijo explícito por especialista:
  [lenguaje] ...
  [algebra]  ...

Esa marca de origen es el invariante de auditabilidad: cualquier
lector puede saber exactamente qué especialista produjo cada paso.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from experiment_01.specialist import (
    Problem,
    ReasoningStep,
    ReasoningTrace,
    SolveResult,
)
from experiment_03.inter_specialist_protocol import SpecialistRegistry
from experiment_06.specialist_factory import SpecialistFactory

from experiment_07.knowledge_graph import build_spanish_base_graph
from experiment_07.specialist import LanguageParseResult, LanguageSpecialist


_DEFAULT_ALGEBRA_DOC = (
    Path(__file__).resolve().parent.parent
    / "experiment_06" / "sample_documents" / "algebra_ch3.md"
)


@dataclass
class UnifiedStep:
    """ReasoningStep con marca de procedencia.

    Mantenemos el step original intacto para auditoría y añadimos un
    `source` que identifica al especialista que lo produjo. La traza
    unificada se imprime con prefijo `[<source>]` por línea inicial.
    """

    source: str          # 'lenguaje' | 'algebra'
    step: ReasoningStep

    def render(self) -> str:
        # Render con prefijo en cada línea para que la procedencia
        # sea legible incluso al copiar fragmentos.
        prefix = f"[{self.source}]"
        return "\n".join(
            f"{prefix} {line}" if i == 0 else f"{' ' * (len(prefix) + 1)}{line}"
            for i, line in enumerate(self.step.render().splitlines())
        )


@dataclass
class LanguageToAlgebraResult:
    parse_result: LanguageParseResult
    solve_result: SolveResult | None
    unified_steps: list[ReasoningStep]
    final_value: float | None
    success: bool

    # Auxiliar: la versión con prefijos para imprimir/auditar. Los
    # `unified_steps` son los ReasoningStep planos para que el caller
    # pueda inspeccionarlos sin desempaquetar; este campo es la vista.
    sourced_steps: list[UnifiedStep] = field(default_factory=list)

    def render(self) -> str:
        lines = [
            "=" * 72,
            "LANGUAGE → ALGEBRA",
            "=" * 72,
            f"success: {self.success}",
            f"final_value: {self.final_value}",
            f"unrecognized_tokens: {self.parse_result.unrecognized_tokens}",
            f"is_complete (parse): {self.parse_result.is_complete}",
            "",
            "── traza unificada ──",
        ]
        for u in self.sourced_steps:
            lines.append(u.render())
            lines.append("")
        if self.success:
            lines.append(f"RESULTADO: {self.parse_result.problem.target} = {self.final_value}")
        else:
            lines.append("RESULTADO: no resuelto")
            if not self.parse_result.is_complete:
                lines.append(
                    "  motivo: parse incompleto — el lenguaje no produjo Problem."
                )
            elif self.solve_result is not None and self.solve_result.gap is not None:
                lines.append(f"  gap: {self.solve_result.gap.context}")
        return "\n".join(lines)


class LanguageToAlgebraOrchestrator:
    """Pipeline lenguaje → álgebra."""

    def __init__(
        self,
        algebra_doc: str | Path = _DEFAULT_ALGEBRA_DOC,
        language_graph=None,
    ) -> None:
        # Especialista de lenguaje sobre su grafo base.
        self.language_graph = language_graph or build_spanish_base_graph()
        self.language_specialist = LanguageSpecialist(self.language_graph)

        # Especialista de álgebra construido desde el documento del
        # exp_06. Reusamos SpecialistFactory para no duplicar pipeline.
        registry = SpecialistRegistry()
        factory = SpecialistFactory(
            registry=registry,
            implicit_figure_kind="linear_equation",
        )
        result = factory.from_document(Path(algebra_doc))
        if not result.registered:
            raise RuntimeError(
                f"no se pudo registrar el especialista de álgebra: {result.errors}"
            )
        self.algebra_registration = result
        self.algebra_specialist = result.specialist
        self.algebra_graph = result.build_report.graph

    # -- API pública ---------------------------------------------------

    def run(self, text: str) -> LanguageToAlgebraResult:
        # Fase 1: lenguaje.
        parse = self.language_specialist.parse(text)
        sourced: list[UnifiedStep] = [
            UnifiedStep(source="lenguaje", step=s) for s in parse.steps
        ]

        if not parse.is_complete or parse.problem is None:
            return LanguageToAlgebraResult(
                parse_result=parse,
                solve_result=None,
                unified_steps=list(parse.steps),
                final_value=None,
                success=False,
                sourced_steps=sourced,
            )

        # Fase 2: álgebra.
        solve = self.algebra_specialist.solve(parse.problem)
        for s in solve.trace.steps:
            sourced.append(UnifiedStep(source="algebra", step=s))

        unified_plain: list[ReasoningStep] = [
            *parse.steps,
            *solve.trace.steps,
        ]

        return LanguageToAlgebraResult(
            parse_result=parse,
            solve_result=solve,
            unified_steps=unified_plain,
            final_value=solve.value if solve.success else None,
            success=solve.success,
            sourced_steps=sourced,
        )


# ---------------------------------------------------------------------
# Demo canónico del experimento 07.
# ---------------------------------------------------------------------

def main() -> None:
    orch = LanguageToAlgebraOrchestrator()
    result = orch.run("resuelve x para a=3, b=6")
    print(result.render())


if __name__ == "__main__":
    main()
