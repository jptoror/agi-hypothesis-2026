"""BenchmarkResult — registro estructurado de una pregunta evaluada.

Métrica dual:

  - `correct: bool | None` — coincidencia LITERAL con ground truth
    declarado en BenchmarkQuestion. None cuando no aplica (p. ej.
    sistema en categoría B: el sistema NO debe responder, así que
    evaluar `correct` sería injusto).

  - `system_behavior_correct: bool` — el sistema HIZO LO CORRECTO
    según la categoría de la pregunta (no si la respuesta numérica
    coincide con el LLM o con ground truth). Reglas exactas según
    confirmación del enunciado:
        Categoría A: True si hay respuesta + traza no vacía.
        Categoría B: True SOLO si declaró gap explícito.
        Categoría C: True si la traza tiene ≥1 ReasoningStep con
                     node_id verificable.

`llm_has_trace` es siempre False — el LLM no expone trazas
estructuradas. Lo dejamos como campo explícito para que la asimetría
sea visible en el output.

`llm_explanation_text` lleva la prosa generada del LLM (si hay).
Distinta de una traza: prosa explicativa NO ejecutable ni
verificable contra ningún grafo.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .question import BenchmarkQuestion, Category


@dataclass
class BenchmarkResult:
    question: BenchmarkQuestion

    # Lado del sistema.
    system_answer: str
    system_trace: list[str] | None       # ids de nodos usados; None si no hay
    system_gap: str | None               # texto del gap declarado; None si no hay
    system_behavior_correct: bool

    # Lado del LLM.
    llm_answer: str
    llm_explanation_text: str            # prosa del LLM (puede ser igual a llm_answer)
    llm_has_trace: bool                  # siempre False — invariante del LLM
    llm_model_used: str                  # id real del modelo consultado o "(skipped)"

    # Comparación con ground truth literal — None cuando no aplica.
    correct: bool | None

    # Provider del LLM consultado: "anthropic" | "gemini" | "skipped".
    llm_provider: str = "skipped"

    # Notas auditables del evaluador (qué regla aplicó, advertencias).
    evaluator_notes: list[str] = field(default_factory=list)

    # -- render -------------------------------------------------------

    def render(self) -> str:
        q = self.question
        lines = [
            f"── {q.qid} ({q.category.value}) ──",
            f"Pregunta: {q.natural_language}",
            "",
            "[SISTEMA]",
            f"  respuesta: {self.system_answer}",
            f"  traza: {self.system_trace if self.system_trace else '(sin traza)'}",
            f"  gap: {self.system_gap if self.system_gap else '(no declarado)'}",
            f"  system_behavior_correct: {self.system_behavior_correct}",
            "",
            "[LLM]",
            f"  provider: {self.llm_provider}",
            f"  modelo: {self.llm_model_used}",
            f"  respuesta: {self.llm_answer}",
            f"  has_trace: {self.llm_has_trace}",
            "",
            f"correct (vs ground truth literal): {self.correct}",
        ]
        if self.evaluator_notes:
            lines.append("notas:")
            for n in self.evaluator_notes:
                lines.append(f"  · {n}")
        return "\n".join(lines)
