"""Consulta epistémica: el caller declara qué conceptos considera
centrales en una pregunta. El mapper no extrae conceptos por NLP —
recibe la lista explícita del caller.

Declarar las semillas fuera del mapper es decisión epistemológica:
la 'extracción de conceptos' sería un eslabón no auditable si la
hiciera el sistema. Aquí el límite es claro — 'estos son los
conceptos que pido que busques'.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ConceptQuery:
    question_text: str        # la pregunta completa en NL — sólo trazabilidad
    seed_concepts: tuple[str, ...]  # conceptos declarados explícitamente por el caller

    @classmethod
    def of(cls, question_text: str, seed_concepts: list[str]) -> "ConceptQuery":
        return cls(question_text=question_text, seed_concepts=tuple(seed_concepts))

    def render(self) -> str:
        lines = [
            f"pregunta: {self.question_text}",
            f"semillas declaradas ({len(self.seed_concepts)}):",
        ]
        for s in self.seed_concepts:
            lines.append(f"  · {s}")
        return "\n".join(lines)
