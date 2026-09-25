"""Resultado de clasificar un gap epistémico."""
from __future__ import annotations

from dataclasses import dataclass

from .gap_type import EpistemicGapType


@dataclass(frozen=True)
class GapClassificationResult:
    """Clasificación auditable de un gap.

    El campo `classified_by` es el invariante de honestidad: cuando el
    paper diga "el sistema clasificó N gaps", deberá poder
    distinguirse exactamente cuántos los clasificó el sistema y
    cuántos dependieron de un agente externo.

    Para todas las semillas del catálogo canónico de este experimento,
    `classified_by == "engineer"` — eso refleja un límite estructural
    descrito en FINDINGS.md #02.
    """

    seed: str
    gap_type: EpistemicGapType
    justification: str
    classified_by: str           # "system" | "engineer"
    resolvable_path: str | None  # None para PHILOSOPHICAL_GAP

    def render(self) -> str:
        path = self.resolvable_path or "(no cerrable desde ingeniería)"
        return (
            f"[{self.gap_type.value:18}] '{self.seed}'\n"
            f"  classified_by: {self.classified_by}\n"
            f"  justificación: {self.justification}\n"
            f"  ruta de cierre: {path}"
        )
