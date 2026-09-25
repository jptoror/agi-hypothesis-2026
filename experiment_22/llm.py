"""Clientes LLM con salida JSON.

Todo el exp_22 habla con el LLM a través de UNA operación:

    complete_json(task, system, user, schema) -> dict

`task` identifica el rol de la llamada ("translate", "hypothesize",
"answer") — los clientes reales lo ignoran; los clientes de prueba lo
usan para despachar respuestas guionizadas sin parsear prompts.

Proveedores:
  - ClaudeJsonLLM  — Anthropic SDK (`pip install anthropic`), structured
                     outputs vía `output_config.format`.
  - GeminiJsonLLM  — Google GenAI SDK (`pip install google-genai`),
                     `response_mime_type="application/json"`.
  - ScriptedLLM    — respuestas deterministas para tests y demos
                     offline. No es un modelo: es un guion.

Los SDKs se importan dentro de los constructores: el núcleo del
proyecto sigue sin dependencias y los tests corren sin red.
"""
from __future__ import annotations

import json
import os
from typing import Callable, Protocol


class LLMUnavailable(RuntimeError):
    """No hay SDK instalado o no hay credenciales."""


class LLMError(RuntimeError):
    """La llamada falló o devolvió algo que no es JSON utilizable."""


class JsonLLM(Protocol):
    name: str

    def complete_json(self, task: str, system: str, user: str, schema: dict) -> dict:
        ...


def _parse_json(text: str) -> dict:
    """Parsea JSON tolerando fences ```json ...``` que algunos modelos añaden."""
    body = (text or "").strip()
    if body.startswith("```"):
        body = body.strip("`")
        body = body[4:] if body.lower().startswith("json") else body
    try:
        data = json.loads(body)
    except json.JSONDecodeError as e:
        raise LLMError(f"respuesta no es JSON válido: {e}: {text[:200]!r}") from e
    if not isinstance(data, dict):
        raise LLMError(f"se esperaba un objeto JSON, llegó {type(data).__name__}")
    return data


class ClaudeJsonLLM:
    """Claude vía Anthropic SDK con structured outputs.

    Por defecto usa `claude-opus-5`. Los fallbacks del lado del
    servidor están activados: si el modelo declina por política, la
    API reintenta en otro modelo dentro de la misma llamada. Si toda
    la cadena declina (`stop_reason == "refusal"`) se lanza LLMError
    y el pipeline lo trata como abstención.
    """

    def __init__(
        self,
        model: str = "claude-opus-5",
        max_tokens: int = 16000,
        use_fallbacks: bool = True,
    ) -> None:
        try:
            import anthropic  # noqa: PLC0415 — dependencia opcional
        except ImportError as e:
            raise LLMUnavailable("instala el SDK: pip install anthropic") from e
        self._anthropic = anthropic
        self.client = anthropic.Anthropic()
        self.model = model
        self.max_tokens = max_tokens
        self.use_fallbacks = use_fallbacks
        self.name = f"claude:{model}"

    def complete_json(self, task: str, system: str, user: str, schema: dict) -> dict:
        params = dict(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config={"format": {"type": "json_schema", "schema": schema}},
        )
        try:
            if self.use_fallbacks:
                response = self.client.beta.messages.create(
                    betas=["server-side-fallback-2026-07-01"],
                    fallbacks="default",
                    **params,
                )
            else:
                response = self.client.messages.create(**params)
        except self._anthropic.APIStatusError as e:
            raise LLMError(f"{task}: API error {e.status_code}: {e.message}") from e
        except self._anthropic.APIConnectionError as e:
            raise LLMError(f"{task}: error de conexión: {e}") from e

        if response.stop_reason == "refusal":
            raise LLMError(f"{task}: el modelo declinó la solicitud")
        if response.stop_reason == "max_tokens":
            raise LLMError(f"{task}: respuesta truncada por max_tokens")
        text = next((b.text for b in response.content if b.type == "text"), "")
        return _parse_json(text)


class GeminiJsonLLM:
    """Gemini vía Google GenAI SDK. Lee GOOGLE_API_KEY o GEMINI_API_KEY."""

    def __init__(self, model: str = "gemini-2.5-flash") -> None:
        key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
        if not key:
            raise LLMUnavailable("define GOOGLE_API_KEY o GEMINI_API_KEY")
        try:
            from google import genai  # noqa: PLC0415 — dependencia opcional
        except ImportError as e:
            raise LLMUnavailable("instala el SDK: pip install google-genai") from e
        self.client = genai.Client(api_key=key)
        self.model = model
        self.name = f"gemini:{model}"

    def complete_json(self, task: str, system: str, user: str, schema: dict) -> dict:
        prompt = (
            f"{user}\n\nRespond ONLY with a JSON object that validates against "
            f"this JSON schema:\n{json.dumps(schema)}"
        )
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config={
                    "system_instruction": system,
                    "response_mime_type": "application/json",
                },
            )
        except Exception as e:  # noqa: BLE001 — el SDK no expone una jerarquía estable
            raise LLMError(f"{task}: error de Gemini: {e}") from e
        return _parse_json(response.text or "")


class ScriptedLLM:
    """Guion determinista: `handler(task, user) -> dict`.

    Útil para tests (cada test declara exactamente qué "dice" el LLM)
    y para el modo `oracle` del benchmark, que mide el techo del
    pipeline con traducciones perfectas.
    """

    def __init__(self, handler: Callable[[str, str], dict], name: str = "scripted") -> None:
        self.handler = handler
        self.name = name
        self.calls: list[tuple[str, str]] = []

    def complete_json(self, task: str, system: str, user: str, schema: dict) -> dict:
        self.calls.append((task, user))
        result = self.handler(task, user)
        if isinstance(result, Exception):
            raise result
        return result


def build_llm(provider: str, model: str | None = None) -> JsonLLM:
    provider = provider.lower()
    if provider == "claude":
        return ClaudeJsonLLM(model=model or "claude-opus-5")
    if provider == "gemini":
        return GeminiJsonLLM(model=model or "gemini-2.5-flash")
    raise ValueError(f"proveedor desconocido: {provider!r} (usa claude o gemini)")
