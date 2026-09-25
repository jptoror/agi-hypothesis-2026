"""Helpers para los tests del benchmark."""
from __future__ import annotations

from experiment_10.benchmark.llm_runner import LLMResponse


class _MockLLMRunner:
    """LLMRunner mock — devuelve respuestas fijas declaradas por el
    test, sin tocar la red. Permite ejercitar la evaluación
    `correct` sin depender del API."""

    def __init__(self, responses_by_question: dict[str, str]) -> None:
        # Mapping pregunta-natural-language → respuesta del LLM.
        self._responses = responses_by_question
        self.is_available = True

    def ask(self, question_text: str) -> LLMResponse:
        text = self._responses.get(question_text, "")
        return LLMResponse(
            answer_text=text,
            explanation_text=text,
            model_used="mock-model",
            error=None,
        )
