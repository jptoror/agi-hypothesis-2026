"""ResearchPathProposer — dada una clasificación de gap, propone una
ruta de cierre cuando es honesto hacerlo.

Mapping rígido EpistemicGapType → Feasibility:
  MISSING_CONCEPT   → ENGINEERING
  FRONTIER_GAP      → RESEARCH
  PHILOSOPHICAL_GAP → OPEN_PROBLEM

Para OPEN_PROBLEM, proposed_action es SIEMPRE None y la justificación
sigue el patrón circular pedido por el experimento:

  "Este gap precede a cualquier solución técnica. Resolverlo requiere
   primero resolver [X] — que es el gap mismo."

Esa circularidad es información, no error. Refleja que el problema
no es de ingeniería: cualquier acción concreta sería una alucinación.
"""
from __future__ import annotations

from experiment_05.gap_classifier_v2 import (
    EpistemicGapType,
    GapClassificationResult,
)

from .feasibility import Feasibility
from .proposal import ResearchProposal


# Estimaciones de complejidad por feasibility — declaradas como
# tabla auditable, no inferidas. Las cifras son intencionalmente
# generosas para no comprometer al sistema con plazos optimistas.
_COMPLEXITY_BY_FEASIBILITY: dict[Feasibility, str] = {
    Feasibility.ENGINEERING: "horas a días",
    Feasibility.RESEARCH: "semanas a meses",
    Feasibility.OPEN_PROBLEM: "indefinido",
}

# Dependencias por defecto por feasibility — pueden ampliarse desde
# el resolvable_path del catálogo si éste menciona prerequisitos.
_DEFAULT_DEPENDENCIES: dict[Feasibility, list[str]] = {
    Feasibility.ENGINEERING: [],
    Feasibility.RESEARCH: ["definición ontológica del dominio meta"],
    Feasibility.OPEN_PROBLEM: [
        "avance filosófico/científico independiente del proyecto",
    ],
}


class ResearchPathProposer:
    """Convierte clasificaciones de gap en propuestas de investigación."""

    def propose(
        self,
        gap_result: GapClassificationResult,
    ) -> ResearchProposal:
        feasibility = self._feasibility_for(gap_result.gap_type)

        if feasibility == Feasibility.OPEN_PROBLEM:
            justification = (
                f"Este gap precede a cualquier solución técnica. "
                f"Resolverlo requiere primero resolver "
                f"'{gap_result.seed}' — que es el gap mismo. "
                f"({gap_result.justification})"
            )
            return ResearchProposal(
                gap_result=gap_result,
                feasibility=feasibility,
                proposed_action=None,
                justification=justification,
                dependencies=list(_DEFAULT_DEPENDENCIES[feasibility]),
                estimated_complexity=_COMPLEXITY_BY_FEASIBILITY[feasibility],
            )

        # ENGINEERING / RESEARCH — la acción se toma del catálogo.
        action = gap_result.resolvable_path
        if not action:
            # Salvaguarda: si por alguna razón el catálogo declaró un
            # tipo cerrable pero no aportó ruta, degradamos a RESEARCH
            # con dependencias declaradas. NO inventamos la ruta.
            return ResearchProposal(
                gap_result=gap_result,
                feasibility=Feasibility.RESEARCH,
                proposed_action=(
                    f"definir primero qué nodos modelarían '{gap_result.seed}' — "
                    f"el catálogo no aportó una ruta concreta."
                ),
                justification=(
                    f"el clasificador marcó el tipo como "
                    f"'{gap_result.gap_type.value}' pero no aportó ruta "
                    f"de cierre concreta. Se propone fase de diseño previa."
                ),
                dependencies=list(_DEFAULT_DEPENDENCIES[Feasibility.RESEARCH]),
                estimated_complexity=_COMPLEXITY_BY_FEASIBILITY[Feasibility.RESEARCH],
            )

        justification = (
            f"viable con esfuerzo de {feasibility.value}: "
            f"{gap_result.justification}"
        )
        return ResearchProposal(
            gap_result=gap_result,
            feasibility=feasibility,
            proposed_action=action,
            justification=justification,
            dependencies=list(_DEFAULT_DEPENDENCIES[feasibility]),
            estimated_complexity=_COMPLEXITY_BY_FEASIBILITY[feasibility],
        )

    def propose_all(
        self,
        gap_results: list[GapClassificationResult],
    ) -> list[ResearchProposal]:
        return [self.propose(g) for g in gap_results]

    # -- mapping table ---------------------------------------------------

    @staticmethod
    def _feasibility_for(gap_type: EpistemicGapType) -> Feasibility:
        if gap_type == EpistemicGapType.MISSING_CONCEPT:
            return Feasibility.ENGINEERING
        if gap_type == EpistemicGapType.FRONTIER_GAP:
            return Feasibility.RESEARCH
        if gap_type == EpistemicGapType.PHILOSOPHICAL_GAP:
            return Feasibility.OPEN_PROBLEM
        # Defensivo: tipo nuevo no contemplado.
        raise ValueError(f"EpistemicGapType no soportado: {gap_type!r}")

    # -- resúmenes auxiliares -------------------------------------------

    @staticmethod
    def feasibility_summary(
        proposals: list[ResearchProposal],
    ) -> dict[str, int]:
        out: dict[str, int] = {}
        for p in proposals:
            out[p.feasibility.value] = out.get(p.feasibility.value, 0) + 1
        return out

    @staticmethod
    def actionable_count(proposals: list[ResearchProposal]) -> int:
        return sum(1 for p in proposals if p.proposed_action is not None)
