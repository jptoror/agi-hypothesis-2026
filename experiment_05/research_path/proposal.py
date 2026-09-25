"""ResearchProposal — propuesta auditable de cierre de un gap.

Invariante crítico (defensa estructural):
    Si feasibility == OPEN_PROBLEM:
        proposed_action DEBE ser None
        estimated_complexity DEBE ser "indefinido"

Si el sistema intenta construir una proposal que viole estas reglas,
falla en `__post_init__` con ValueError. Esta defensa precede al
honesty_guard: el sistema no puede *intentar* afirmar algo accionable
para un problema abierto. El honesty_guard valida después; el invariante
estructural impide la alucinación de raíz.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from experiment_05.gap_classifier_v2 import GapClassificationResult

from .feasibility import Feasibility


@dataclass
class ResearchProposal:
    gap_result: GapClassificationResult
    feasibility: Feasibility
    proposed_action: str | None
    justification: str
    dependencies: list[str] = field(default_factory=list)
    estimated_complexity: str = ""

    def __post_init__(self) -> None:
        # Invariantes estructurales — el sistema no puede generar
        # proposals incoherentes. Estas reglas son las que el
        # honesty_guard volverá a verificar a posteriori.
        if self.feasibility == Feasibility.OPEN_PROBLEM:
            if self.proposed_action is not None:
                raise ValueError(
                    "OPEN_PROBLEM con proposed_action != None — "
                    "afirmación más allá de la frontera. Si la proposal "
                    "puede sugerir una acción, no es OPEN_PROBLEM."
                )
            if self.estimated_complexity != "indefinido":
                raise ValueError(
                    "OPEN_PROBLEM debe tener estimated_complexity="
                    "'indefinido'; valor recibido: "
                    f"{self.estimated_complexity!r}"
                )
        else:
            # ENGINEERING / RESEARCH requieren acción concreta y
            # justificación no vacía.
            if not self.proposed_action:
                raise ValueError(
                    f"feasibility={self.feasibility.value} requiere "
                    "proposed_action no vacío."
                )
            if not self.estimated_complexity:
                raise ValueError(
                    f"feasibility={self.feasibility.value} requiere "
                    "estimated_complexity no vacío."
                )
        if not self.justification:
            raise ValueError("toda proposal debe llevar justification.")

    def render(self) -> str:
        action = self.proposed_action or "(ninguna — más allá de la frontera)"
        deps = ", ".join(self.dependencies) or "(ninguna)"
        return (
            f"PROPOSAL para '{self.gap_result.seed}' "
            f"({self.gap_result.gap_type.value})\n"
            f"  feasibility: {self.feasibility.value}\n"
            f"  acción propuesta: {action}\n"
            f"  justificación: {self.justification}\n"
            f"  dependencias: {deps}\n"
            f"  complejidad estimada: {self.estimated_complexity}"
        )
