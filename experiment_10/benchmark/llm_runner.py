"""Runners para LLMs externos — Anthropic (Claude) y Google (Gemini).

Política común:
  - Sin API key → no se invoca al modelo. Se devuelve un LLMResponse
    con `model_used="(skipped: ...)"` y `provider="skipped"`. El
    benchmark sigue siendo válido para el lado del sistema.
  - Modelos solicitados por defecto declarados en constantes del
    módulo. Si están deprecados, se reintenta con un fallback
    declarado y se registra el modelo real usado.
  - Las preguntas se envían como mensajes de usuario sin system
    prompt — queremos la respuesta natural del modelo, sin sesgar
    hacia "muestra tu razonamiento" o "no inventes". El sesgo
    falsearía la comparación.

Dos runners disponibles:
  - LLMRunner   → Anthropic (Claude). Histórico del exp_10 inicial.
  - GeminiRunner → Google (Gemini). Añadido como alternativa.

El demo elige cuál usar según qué API key esté disponible. Ambos
implementan la misma interfaz mínima (`is_available`, `ask`) — el
Benchmark los consume sin distinguir el provider.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


# Modelos Anthropic.
_ANTHROPIC_REQUESTED = "claude-sonnet-4-20250514"
_ANTHROPIC_FALLBACK = "claude-sonnet-4-5"

# Modelos Gemini. La instrucción del exp_10 pedía gemini-1.5-flash,
# pero Google retiró esa familia del catálogo v1beta (404 al
# invocarla). Migramos a la familia 2.5 con fallback declarado.
# Documentado en experiment_10/FINDINGS.md #06.
_GEMINI_REQUESTED = "gemini-2.5-flash"
_GEMINI_FALLBACK = "gemini-flash-latest"

_MAX_TOKENS = 1024


@dataclass
class LLMResponse:
    answer_text: str
    explanation_text: str
    model_used: str           # id del modelo realmente consultado o "(skipped: ...)"
    error: str | None = None  # mensaje de error si la llamada falló
    provider: str = "anthropic"  # "anthropic" | "gemini" | "skipped"


# ---------------------------------------------------------------------
# Anthropic (Claude) — runner histórico del exp_10.
# ---------------------------------------------------------------------

class LLMRunner:
    """Runner Anthropic. Mantenido sin cambios funcionales del exp_10
    original — sólo se le añade `provider="anthropic"` al response.
    """

    provider_name = "anthropic"

    def __init__(
        self,
        requested_model: str = _ANTHROPIC_REQUESTED,
        fallback_model: str = _ANTHROPIC_FALLBACK,
    ) -> None:
        self.requested_model = requested_model
        self.fallback_model = fallback_model
        self._client = self._build_client()

    @staticmethod
    def _build_client():
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            return None
        try:
            import anthropic  # noqa: WPS433 — import dentro de fábrica
        except ImportError:
            return None
        return anthropic.Anthropic(api_key=key)

    @property
    def is_available(self) -> bool:
        return self._client is not None

    # -- API pública ---------------------------------------------------

    def ask(self, question_text: str) -> LLMResponse:
        if self._client is None:
            return LLMResponse(
                answer_text="(no API key — saltado)",
                explanation_text="(no API key — saltado)",
                model_used="(skipped: no ANTHROPIC_API_KEY)",
                provider="skipped",
            )

        # Primer intento: modelo solicitado.
        resp = self._call(self.requested_model, question_text)
        if resp.error is None:
            return resp

        # Fallback declarado.
        resp_fb = self._call(self.fallback_model, question_text)
        if resp_fb.error is None:
            resp_fb.model_used = (
                f"{self.fallback_model} (fallback de "
                f"{self.requested_model}: {resp.error})"
            )
            return resp_fb

        return LLMResponse(
            answer_text="(error consultando LLM)",
            explanation_text=f"requested: {resp.error} | fallback: {resp_fb.error}",
            model_used=f"(error: {self.requested_model}, {self.fallback_model})",
            error=resp.error,
            provider=self.provider_name,
        )

    # -- internals -----------------------------------------------------

    def _call(self, model_id: str, prompt: str) -> LLMResponse:
        try:
            message = self._client.messages.create(
                model=model_id,
                max_tokens=_MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as e:  # noqa: BLE001 — atrapamos cualquier fallo del API
            return LLMResponse(
                answer_text="",
                explanation_text="",
                model_used=model_id,
                error=f"{type(e).__name__}: {e}",
                provider=self.provider_name,
            )

        chunks: list[str] = []
        for block in (message.content or []):
            text = getattr(block, "text", None)
            if isinstance(text, str):
                chunks.append(text)
        full_text = "\n".join(chunks).strip()
        return LLMResponse(
            answer_text=full_text,
            explanation_text=full_text,
            model_used=model_id,
            provider=self.provider_name,
        )


# ---------------------------------------------------------------------
# Google (Gemini) — runner alternativo.
# ---------------------------------------------------------------------

class GeminiRunner:
    """Runner Google Gemini con el SDK `google-generativeai`.

    NOTA: el SDK `google-generativeai` está deprecado por Google
    (sucesor: `google-genai`). Se usa intencionalmente porque la
    instrucción del experimento lo declara así. Documentado en
    FINDINGS del exp_10.

    Recibe la API key como PARÁMETRO (no la lee del entorno desde
    aquí — el caller decide). Esto permite que el demo controle
    qué provider usar en función de qué key tenga disponible, sin
    construir clientes que no se van a usar.
    """

    provider_name = "gemini"

    def __init__(
        self,
        api_key: Optional[str] = None,
        requested_model: str = _GEMINI_REQUESTED,
        fallback_model: str = _GEMINI_FALLBACK,
    ) -> None:
        self.requested_model = requested_model
        self.fallback_model = fallback_model
        self._api_key = api_key
        self._client = self._build_client(api_key)

    @staticmethod
    def _build_client(api_key: Optional[str]):
        if not api_key:
            return None
        try:
            import google.generativeai as genai  # noqa: WPS433
        except ImportError:
            return None
        genai.configure(api_key=api_key)
        return genai

    @property
    def is_available(self) -> bool:
        return self._client is not None

    # -- API pública ---------------------------------------------------

    def ask(self, question_text: str) -> LLMResponse:
        if self._client is None:
            return LLMResponse(
                answer_text="(no API key — saltado)",
                explanation_text="(no API key — saltado)",
                model_used="(skipped: no GOOGLE_API_KEY)",
                provider="skipped",
            )

        # Primer intento: modelo solicitado.
        resp = self._call(self.requested_model, question_text)
        if resp.error is None:
            return resp

        # Fallback declarado.
        resp_fb = self._call(self.fallback_model, question_text)
        if resp_fb.error is None:
            resp_fb.model_used = (
                f"{self.fallback_model} (fallback de "
                f"{self.requested_model}: {resp.error})"
            )
            return resp_fb

        return LLMResponse(
            answer_text="(error consultando LLM)",
            explanation_text=f"requested: {resp.error} | fallback: {resp_fb.error}",
            model_used=f"(error: {self.requested_model}, {self.fallback_model})",
            error=resp.error,
            provider=self.provider_name,
        )

    # -- internals -----------------------------------------------------

    def _call(self, model_id: str, prompt: str) -> LLMResponse:
        try:
            model = self._client.GenerativeModel(model_id)
            response = model.generate_content(
                prompt,
                generation_config={"max_output_tokens": _MAX_TOKENS},
            )
        except Exception as e:  # noqa: BLE001
            return LLMResponse(
                answer_text="",
                explanation_text="",
                model_used=model_id,
                error=f"{type(e).__name__}: {e}",
                provider=self.provider_name,
            )

        text = (getattr(response, "text", None) or "").strip()
        return LLMResponse(
            answer_text=text,
            explanation_text=text,
            model_used=model_id,
            provider=self.provider_name,
        )
