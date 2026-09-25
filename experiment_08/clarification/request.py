"""ClarificationRequest — el sistema reconoce que no tiene contexto
suficiente y pide al caller que lo aporte, en lugar de adivinar.

Es la pieza central del exp_08: un sistema honesto admite cuando no
sabe en qué dominio operar y delega esa decisión al usuario, con
opciones explícitas. NO infiere por mayoría, NO elige el dominio
'más probable', NO inventa.

`SufficiencyAssessment` es la salida del resolver — distingue tres
casos:

  SUFFICIENT             → puede continuar; `domain` rellena el dominio
                           determinado (declarado por el caller o el
                           único candidato del bus)
  AMBIGUOUS              → varios especialistas conocen el concepto;
                           el caller debe elegir
  UNKNOWN                → ningún especialista conoce el concepto;
                           el caller debe declarar dónde encaja o
                           reformular

Ambos AMBIGUOUS y UNKNOWN llevan un `clarification_request` con
`options` apropiadas y un `reason` que distingue ambos casos.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class SufficiencyVerdict(str, Enum):
    SUFFICIENT = "sufficient"
    AMBIGUOUS = "ambiguous"
    UNKNOWN = "unknown"


@dataclass
class ClarificationRequest:
    """Solicitud explícita de aclaración del caller."""

    missing_concept: str
    available_context: dict
    options: list[str]
    reason: str

    def render(self) -> str:
        opts = ", ".join(self.options) if self.options else "(ninguna)"
        return (
            f"CLARIFICATION_REQUEST\n"
            f"  concepto: '{self.missing_concept}'\n"
            f"  motivo: {self.reason}\n"
            f"  opciones: {opts}\n"
            f"  contexto disponible: {self.available_context}"
        )


@dataclass
class SufficiencyAssessment:
    """Veredicto del resolver sobre si el contexto basta para
    continuar el pipeline.

    Si `verdict == SUFFICIENT`, `domain` lleva el dominio
    determinado (puede venir del hint del caller o del único
    candidato encontrado). En los otros dos casos, `domain` es None
    y `clarification_request` no es None — el caller debe
    procesarlo.
    """

    concept: str
    verdict: SufficiencyVerdict
    domain: str | None = None
    clarification_request: ClarificationRequest | None = None
    candidates: list[str] = field(default_factory=list)

    @property
    def is_sufficient(self) -> bool:
        return self.verdict == SufficiencyVerdict.SUFFICIENT

    def render(self) -> str:
        head = f"SUFFICIENCY: {self.verdict.value} | concepto='{self.concept}'"
        if self.is_sufficient:
            return f"{head} | domain={self.domain}"
        if self.clarification_request is not None:
            return f"{head}\n{self.clarification_request.render()}"
        return head
