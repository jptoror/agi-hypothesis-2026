"""Orquestador del experimento 08 — clarificación en el pipeline.

Encadena: LanguageSpecialist → ClarificationResolver →
SpecialistFactory(álgebra). El resolver evalúa los
`unrecognized_tokens` que el lenguaje no procesó. Si alguno
desencadena `AMBIGUOUS` o `UNKNOWN`, el pipeline PARA y devuelve la
`ClarificationRequest` sin invocar a álgebra. Si todos son
`SUFFICIENT` (o no hay tokens no reconocidos), el pipeline continúa
normalmente.

Este es el invariante del experimento: el sistema sabe cuándo no
tiene contexto suficiente y pide aclaración en lugar de asumir.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from experiment_01.specialist import (
    Problem,
    ReasoningStep,
    SolveResult,
)
from experiment_03.inter_specialist_protocol import (
    GapRequest,
    GapResponse,
    ResponseStatus,
    SpecialistAdapter,
    SpecialistRegistry,
)
from experiment_06.specialist_factory import SpecialistFactory
from experiment_07.knowledge_graph import build_spanish_base_graph
from experiment_07.specialist import LanguageParseResult, LanguageSpecialist

from .clarification import (
    ClarificationRequest,
    ClarificationResolver,
    SufficiencyAssessment,
)


_DEFAULT_ALGEBRA_DOC = (
    Path(__file__).resolve().parent.parent
    / "experiment_06" / "sample_documents" / "algebra_ch3.md"
)


# Adapter mínimo para que el especialista de lenguaje aparezca en
# la registry — el resolver lo necesita para excluirlo. NO se invoca
# vía protocolo en este experimento; sólo se registra para que el
# resolver pueda nombrarlo como `initiating_specialist`.
class _LanguageBusAdapter(SpecialistAdapter):
    name = "language"
    output_variables = frozenset()

    def __init__(self, graph) -> None:
        self.graph = graph

    def handle(self, request: GapRequest, delegate=None) -> GapResponse:
        return GapResponse(
            request_id=request.request_id,
            responder=self.name,
            status=ResponseStatus.UNRESOLVABLE,
        )


@dataclass
class ClarifyingPipelineResult:
    """Resultado del pipeline lenguaje → clarificación → álgebra."""

    parse_result: LanguageParseResult
    sufficiency_assessments: list[SufficiencyAssessment] = field(default_factory=list)
    clarification_request: ClarificationRequest | None = None
    solve_result: SolveResult | None = None
    final_value: float | None = None
    success: bool = False

    def render(self) -> str:
        lines = [
            "=" * 72,
            "EXPERIMENTO 08 — pipeline con clarificación",
            "=" * 72,
            f"input: {self.parse_result.problem.statement if self.parse_result.problem else '(sin problem)'!r}",
            f"unrecognized_tokens: {self.parse_result.unrecognized_tokens}",
            "",
            "── evaluaciones de suficiencia ──",
        ]
        if not self.sufficiency_assessments:
            lines.append("  (ninguna — todos los tokens fueron reconocidos)")
        for a in self.sufficiency_assessments:
            lines.append("  " + a.render().replace("\n", "\n  "))
        lines.append("")
        if self.clarification_request is not None:
            lines.append("── PIPELINE PAUSADO: se requiere clarificación ──")
            lines.append(self.clarification_request.render())
        elif self.success:
            target = self.parse_result.problem.target if self.parse_result.problem else "?"
            lines.append(f"RESULTADO: {target} = {self.final_value}")
        else:
            lines.append("RESULTADO: no resuelto")
        return "\n".join(lines)


class ClarifyingOrchestrator:
    """Pipeline lenguaje → clarificación → álgebra."""

    def __init__(
        self,
        algebra_doc: str | Path = _DEFAULT_ALGEBRA_DOC,
        language_graph=None,
        registry: SpecialistRegistry | None = None,
        clarification_terms: Iterable[str] | None = None,
    ) -> None:
        # Lenguaje.
        self.language_graph = language_graph or build_spanish_base_graph()
        self.language_specialist = LanguageSpecialist(self.language_graph)

        # Bus + álgebra.
        self.registry = registry or SpecialistRegistry()
        # Registramos el lenguaje como ciudadano del bus para que el
        # resolver pueda excluirlo como iniciador.
        if not any(a.name == "language" for a in self.registry.all()):
            self.registry.register(_LanguageBusAdapter(self.language_graph))

        # Si la registry no trae ya un especialista de álgebra, lo
        # construimos desde el documento del exp_06.
        if not any(a.name == "algebra_ch3" for a in self.registry.all()):
            factory = SpecialistFactory(
                registry=self.registry,
                implicit_figure_kind="linear_equation",
            )
            algebra_reg = factory.from_document(Path(algebra_doc))
            if not algebra_reg.registered:
                raise RuntimeError(
                    f"no se pudo registrar álgebra: {algebra_reg.errors}"
                )
            self.algebra_adapter = algebra_reg.adapter
        else:
            self.algebra_adapter = next(
                a for a in self.registry.all() if a.name == "algebra_ch3"
            )

        # Resolver — excluye `language` como iniciador.
        self.resolver = ClarificationResolver(
            registry=self.registry,
            initiating_specialist="language",
        )

        # Términos sobre los que aplicar clarificación. Por defecto,
        # TODOS los unrecognized_tokens del lenguaje. El caller puede
        # restringir a un subconjunto pasando `clarification_terms`.
        # Stop-words simples ("para", "con", "el", "la", "de") quedan
        # excluidas por defecto — no son conceptos a clarificar.
        self._stopwords: set[str] = (
            {t.lower() for t in clarification_terms}
            if clarification_terms is not None
            else {
                "el", "la", "los", "las", "de", "del", "para",
                "con", "por", "y", "o", "u", "a", "en", "un", "una",
                "que", "si", "se", "es",
            }
        )
        self._restrict_to: set[str] | None = (
            {t.lower() for t in clarification_terms}
            if clarification_terms is not None
            else None
        )

    # -- API pública ---------------------------------------------------

    def run(
        self,
        text: str,
        hints: dict | None = None,
    ) -> ClarifyingPipelineResult:
        hints = hints or {}

        # Fase 1: lenguaje.
        parse = self.language_specialist.parse(text)

        # Fase 2: para cada token no reconocido (que no sea stopword),
        # consultar al resolver. Se evalúa sobre el SET único de
        # tokens — un mismo token repetido se evalúa una sola vez.
        terms_to_assess = self._select_terms(parse.unrecognized_tokens)
        assessments: list[SufficiencyAssessment] = []
        for concept in terms_to_assess:
            a = self.resolver.assess(concept, available_context=hints)
            assessments.append(a)
            if not a.is_sufficient:
                # PARA — el sistema admite que no sabe y pide ayuda.
                return ClarifyingPipelineResult(
                    parse_result=parse,
                    sufficiency_assessments=assessments,
                    clarification_request=a.clarification_request,
                    solve_result=None,
                    final_value=None,
                    success=False,
                )

        # Fase 3: si el lenguaje no produjo Problem completo, no
        # invocamos álgebra. Devolvemos el estado para diagnóstico.
        if not parse.is_complete or parse.problem is None:
            return ClarifyingPipelineResult(
                parse_result=parse,
                sufficiency_assessments=assessments,
                clarification_request=None,
                solve_result=None,
                final_value=None,
                success=False,
            )

        # Fase 4: álgebra.
        solve = self.algebra_adapter.specialist.solve(parse.problem)
        return ClarifyingPipelineResult(
            parse_result=parse,
            sufficiency_assessments=assessments,
            clarification_request=None,
            solve_result=solve,
            final_value=solve.value if solve.success else None,
            success=solve.success,
        )

    # -- helpers internos ---------------------------------------------

    def _select_terms(self, tokens: list[str]) -> list[str]:
        """Filtra los tokens no reconocidos a los que vale la pena
        evaluar para clarificación.

        - Excluye stop-words declaradas (artículos, preposiciones).
        - Si el caller declaró `clarification_terms`, sólo evaluamos
          esos.
        - Deduplica preservando orden de primera aparición.
        """
        seen: set[str] = set()
        out: list[str] = []
        for tok in tokens:
            t = tok.lower()
            if t in seen:
                continue
            if self._restrict_to is not None and t not in self._restrict_to:
                continue
            if t in self._stopwords:
                continue
            seen.add(t)
            out.append(tok)
        return out


# ---------------------------------------------------------------------
# Demo canónico del experimento 08.
# ---------------------------------------------------------------------

def main() -> None:
    instruction = "calcula el coeficiente para x con a=3, b=6"

    # Setup A: orchestrator con bus realista (álgebra solamente).
    orch = ClarifyingOrchestrator()

    print("=" * 72)
    print("CAMINO 1 — sin hints (suficiencia por unicidad del candidato)")
    print("=" * 72)
    r1 = orch.run(instruction)
    print(r1.render())
    print()

    print("=" * 72)
    print("CAMINO 2 — con hints={'domain': 'algebra'} (declaración explícita)")
    print("=" * 72)
    r2 = orch.run(instruction, hints={"domain": "algebra"})
    print(r2.render())
    print()

    print("=" * 72)
    print("EVIDENCIA CENTRAL")
    print("=" * 72)
    print(f"  CAMINO 1 → success={r1.success} value={r1.final_value} "
          f"clarification={r1.clarification_request is None and 'no necesaria' or 'requerida'}")
    print(f"  CAMINO 2 → success={r2.success} value={r2.final_value} "
          f"clarification={r2.clarification_request is None and 'no necesaria' or 'requerida'}")
    print(
        "\nLa diferencia entre los dos caminos es CÓMO se alcanzó la suficiencia\n"
        "(unicidad de candidato vs declaración explícita), no el resultado."
    )


if __name__ == "__main__":
    main()
