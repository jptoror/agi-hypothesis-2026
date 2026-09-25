"""HybridPipeline: el LLM como interfaz, el motor como juez.

    pregunta ──► Translator (LLM) ──► TranslationChecker ──► EngineGateway
                                                               │
                                        gap ◄──────────────────┘
                                         │
                                         ▼
                              HypothesisBroker (LLM propone,
                              el sistema verifica) ──► re-solve

Cada respuesta sale con un NIVEL que dice cuánto hay que creerle:

  VERIFIED      derivada sólo con nodos establecidos del grafo.
  CORROBORATED  usa una hipótesis del LLM que el sistema derivó por
                su cuenta de forma independiente.
  CONDITIONAL   usa una hipótesis del LLM que pasó todos los checks
                pero que nada corrobora. Correcta SI la hipótesis lo es.
  UNVERIFIED    la pregunta está fuera de los dominios del sistema;
                respondió el LLM directamente, sin verificación.
  ABSTAINED     el sistema declara por qué no responde (datos
                insuficientes, precondición violada, traducción o
                hipótesis rechazadas).

El nivel es la interfaz honesta: un consumidor puede aceptar sólo
VERIFIED/CORROBORATED en un contexto crítico y todo lo demás en uno
exploratorio.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum

from .catalog import DomainCatalog
from .gateway import EngineGateway, EngineResult
from .hypothesis import HypothesisBroker, HypothesisVerdict, Verdict
from .llm import JsonLLM, LLMError
from .translator import Translation, TranslationStatus, Translator


class Tier(str, Enum):
    VERIFIED = "verified"
    CORROBORATED = "corroborated"
    CONDITIONAL = "conditional"
    UNVERIFIED = "unverified"
    ABSTAINED = "abstained"


@dataclass
class HybridAnswer:
    question: str
    tier: Tier
    value: float | None = None
    reason: str = ""
    translation: Translation | None = None
    engine: EngineResult | None = None
    hypothesis: HypothesisVerdict | None = None
    trace_node_ids: list[str] = field(default_factory=list)

    @property
    def answered(self) -> bool:
        return self.tier != Tier.ABSTAINED and self.value is not None

    def render(self) -> str:
        lines = [f"Pregunta: {self.question}", f"Nivel: {self.tier.value.upper()}"]
        if self.value is not None:
            lines.append(f"Valor: {self.value}")
        if self.reason:
            lines.append(f"Motivo: {self.reason}")
        if self.translation and self.translation.query:
            q = self.translation.query
            lines.append(
                f"Traducción: {q.domain}/{q.context_kind} target={q.target} known={q.known}"
                + (f" bindings={q.variable_bindings}" if q.variable_bindings else "")
            )
            for c in self.translation.checks:
                lines.append(f"  · {c}")
        if self.hypothesis:
            lines.append(f"Hipótesis: {self.hypothesis.verdict.value} — {self.hypothesis.expression}")
            for c in self.hypothesis.checks:
                lines.append(f"  · {c}")
        if self.trace_node_ids:
            lines.append(f"Traza: {' → '.join(self.trace_node_ids)}")
        return "\n".join(lines)


DIRECT_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": ["answered", "insufficient_data", "cannot_answer"]},
        "value": {"anyOf": [{"type": "number"}, {"type": "null"}]},
        "explanation": {"type": "string"},
    },
    "required": ["status", "value", "explanation"],
    "additionalProperties": False,
}

_DIRECT_SYSTEM = (
    "Answer the question with a single number in 'value'. If the question does not "
    "give enough information to compute a unique numeric answer, use status "
    "'insufficient_data' and value null. If it cannot be answered numerically, use "
    "'cannot_answer'. Keep the explanation to one or two sentences."
)


@dataclass
class DirectAnswer:
    status: str
    value: float | None
    explanation: str = ""


def ask_directly(llm: JsonLLM, question: str) -> DirectAnswer:
    """Pregunta al LLM sin sistema de por medio (línea base y fallback)."""
    try:
        raw = llm.complete_json(
            "answer", _DIRECT_SYSTEM, json.dumps({"question": question}), DIRECT_SCHEMA,
        )
    except LLMError as e:
        return DirectAnswer("error", None, str(e))
    value = raw.get("value")
    return DirectAnswer(
        status=raw.get("status", "cannot_answer"),
        value=float(value) if isinstance(value, (int, float)) else None,
        explanation=raw.get("explanation", ""),
    )


class HybridPipeline:
    def __init__(
        self,
        llm: JsonLLM,
        gateway: EngineGateway | None = None,
        fallback_to_llm: bool = True,
    ) -> None:
        self.llm = llm
        self.gateway = gateway or EngineGateway()
        self.catalog = DomainCatalog(self.gateway.graphs)
        self.translator = Translator(llm, self.catalog)
        self.broker = HypothesisBroker(llm)
        self.fallback_to_llm = fallback_to_llm

    def answer(self, question: str) -> HybridAnswer:
        translation = self.translator.translate(question)

        if translation.status == TranslationStatus.OUT_OF_SCOPE:
            return self._fallback(question, translation)
        if translation.status != TranslationStatus.OK:
            return HybridAnswer(
                question, Tier.ABSTAINED,
                reason=f"traducción {translation.status.value}: {translation.reason}",
                translation=translation,
            )

        query = translation.query
        result = self.gateway.solve(query)
        if result.success:
            return HybridAnswer(
                question, Tier.VERIFIED, value=result.value,
                reason="derivado con nodos establecidos del grafo",
                translation=translation, engine=result,
                trace_node_ids=result.trace_node_ids,
            )

        if result.precondition_violation or query.variable_bindings or not result.missing_variable:
            return HybridAnswer(
                question, Tier.ABSTAINED, reason=f"gap del motor: {result.gap_text}",
                translation=translation, engine=result,
            )

        # Gap de conocimiento: el LLM propone, el sistema juzga.
        missing = result.missing_variable
        verdict = self.broker.propose_and_verify(
            query,
            missing,
            translation.target_quantity if missing == query.target else "",
            self.catalog.get(query.domain),
            self.gateway.graph(query.domain),
        )
        if not verdict.accepted:
            return HybridAnswer(
                question, Tier.ABSTAINED,
                reason=f"gap '{missing}' sin cubrir — hipótesis {verdict.verdict.value}: {verdict.reason}",
                translation=translation, engine=result, hypothesis=verdict,
            )

        retry = self.gateway.solve(query, extra_nodes=[verdict.node])
        if not retry.success:
            return HybridAnswer(
                question, Tier.ABSTAINED,
                reason=f"con la hipótesis aceptada, el motor sigue sin derivar: {retry.gap_text}",
                translation=translation, engine=retry, hypothesis=verdict,
            )
        tier = Tier.CORROBORATED if verdict.verdict == Verdict.CORROBORATED else Tier.CONDITIONAL
        return HybridAnswer(
            question, tier, value=retry.value,
            reason=f"derivado usando la hipótesis {verdict.node.id} ({verdict.verdict.value})",
            translation=translation, engine=retry, hypothesis=verdict,
            trace_node_ids=retry.trace_node_ids,
        )

    def _fallback(self, question: str, translation: Translation) -> HybridAnswer:
        if not self.fallback_to_llm:
            return HybridAnswer(
                question, Tier.ABSTAINED,
                reason=f"fuera de los dominios del sistema: {translation.reason}",
                translation=translation,
            )
        direct = ask_directly(self.llm, question)
        if direct.status == "answered" and direct.value is not None:
            return HybridAnswer(
                question, Tier.UNVERIFIED, value=direct.value,
                reason=f"fuera de dominio — respuesta directa del LLM, no verificada: {direct.explanation}",
                translation=translation,
            )
        return HybridAnswer(
            question, Tier.ABSTAINED,
            reason=f"fuera de dominio y el LLM no dio valor ({direct.status}): {direct.explanation}",
            translation=translation,
        )
