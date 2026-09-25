"""Traductor LLM: lenguaje natural → StructuredQuery verificada.

El LLM hace lo que hace bien — leer lenguaje natural — y NADA más.
No calcula, no decide la respuesta. Su salida es una consulta
estructurada que el motor puede ejecutar o rechazar.

Lo que el LLM dice NO se cree por defecto. Antes de que la consulta
llegue al motor, `TranslationChecker` verifica de forma determinista:

  1. Contrato: el dominio, el tipo de contexto y las variables
     existen en el catálogo (o el target se declara explícitamente
     como magnitud NUEVA, que abre la vía de hipótesis).
  2. Grounding: cada valor numérico extraído aparece literalmente en
     el enunciado (en valor absoluto — "7x = 21" se traduce a b = -21).
     Un número que el LLM "completó" por su cuenta es la forma más
     común de alucinación en extracción, y se rechaza.
  3. Coherencia: el target no puede venir como dato conocido; los
     bindings sólo pueden unir variables de dominios distintos.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from enum import Enum

from .catalog import DomainCatalog
from .gateway import StructuredQuery
from .llm import JsonLLM, LLMError


class TranslationStatus(str, Enum):
    OK = "ok"
    OUT_OF_SCOPE = "out_of_scope"
    INSUFFICIENT_DATA = "insufficient_data"
    REJECTED = "rejected"          # el LLM tradujo, pero la verificación falló
    LLM_FAILED = "llm_failed"


@dataclass
class Translation:
    status: TranslationStatus
    query: StructuredQuery | None = None
    reason: str = ""
    new_target: bool = False
    target_quantity: str = ""
    checks: list[str] = field(default_factory=list)
    raw: dict | None = None


TRANSLATION_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": ["ok", "out_of_scope", "insufficient_data"]},
        "reason": {"type": "string"},
        "domain": {"type": "string"},
        "context_kind": {"type": "string"},
        "target": {"type": "string"},
        "target_quantity": {"type": "string"},
        "known": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"name": {"type": "string"}, "value": {"type": "number"}},
                "required": ["name", "value"],
                "additionalProperties": False,
            },
        },
        "variable_bindings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"from": {"type": "string"}, "to": {"type": "string"}},
                "required": ["from", "to"],
                "additionalProperties": False,
            },
        },
        "partner_context_kind": {"type": "string"},
    },
    "required": [
        "status", "reason", "domain", "context_kind", "target", "target_quantity",
        "known", "variable_bindings", "partner_context_kind",
    ],
    "additionalProperties": False,
}

_SYSTEM = """You translate a natural-language question into a structured query for a \
symbolic reasoning engine. You never solve the problem yourself.

The engine knows these domains:
{catalog}

Rules:
- status "ok": the question asks for one numeric quantity about an object of one of \
these domains, and every value needed is stated in the question.
- Use ONLY variable names listed above for "known". Extract ONLY numbers that appear \
in the question; never invent, assume or convert values. Rewrite equations into the \
form a·x + b = 0 when needed (e.g. "7x = 21" gives a=7, b=-21).
- "target" is the variable asked for. If the asked quantity is about a domain object \
but has no listed variable (e.g. the perimeter of a square), invent a short symbol \
for it (e.g. "P") and name the quantity in "target_quantity".
- Cross-domain questions (e.g. a speed equal to the side of a square): set "domain" to \
the domain of the asked quantity, put the other object's values in "known", add a \
binding {{"from": <variable of the asked domain>, "to": <variable of the other domain>}}, \
and set "partner_context_kind" to the other object's context kind. Otherwise leave \
"variable_bindings" empty and "partner_context_kind" "".
- status "insufficient_data": the question is about these domains but a needed value \
is missing or the problem is ill-posed.
- status "out_of_scope": the question is not about these domains' objects.
- For non-"ok" statuses, fill string fields with "" and arrays with [], and explain in "reason".
"""

_NUMBER = re.compile(r"\d+(?:\.\d+)?")


def numbers_in(text: str) -> list[float]:
    """Números que aparecen literalmente en el enunciado."""
    clean = re.sub(r"(?<=\d),(?=\d{3}\b)", "", text)   # 1,289.7 → 1289.7
    return [float(n) for n in _NUMBER.findall(clean)]


def is_grounded(value: float, text_numbers: list[float]) -> bool:
    return any(
        math.isclose(abs(value), n, rel_tol=1e-9, abs_tol=1e-12) for n in text_numbers
    )


class TranslationChecker:
    def __init__(self, catalog: DomainCatalog) -> None:
        self.catalog = catalog

    def check(self, question: str, raw: dict) -> Translation:
        status = raw.get("status")
        if status == "out_of_scope":
            return Translation(TranslationStatus.OUT_OF_SCOPE, reason=raw.get("reason", ""), raw=raw)
        if status == "insufficient_data":
            return Translation(TranslationStatus.INSUFFICIENT_DATA, reason=raw.get("reason", ""), raw=raw)
        if status != "ok":
            return self._reject(raw, f"status desconocido: {status!r}")

        checks: list[str] = []
        spec = self.catalog.get(raw.get("domain", ""))
        if spec is None:
            return self._reject(raw, f"dominio fuera del catálogo: {raw.get('domain')!r}")
        kind = raw.get("context_kind", "")
        if kind not in spec.context_kinds:
            return self._reject(raw, f"context_kind '{kind}' no existe en '{spec.name}'")
        checks.append(f"contrato: dominio '{spec.name}', contexto '{kind}'")

        bindings = {b["from"]: b["to"] for b in raw.get("variable_bindings", [])}
        partner_kind = raw.get("partner_context_kind", "") or ""
        allowed = set(spec.variables)
        if bindings:
            for src, dst in bindings.items():
                if src not in spec.variables:
                    return self._reject(raw, f"binding desde variable desconocida '{src}'")
                partner = [
                    d for d in self.catalog.domains.values()
                    if d.name != spec.name and dst in d.variables
                ]
                if not partner:
                    return self._reject(raw, f"binding hacia variable desconocida '{dst}'")
                allowed |= set(partner[0].variables)
                if partner_kind not in partner[0].context_kinds:
                    return self._reject(raw, f"partner_context_kind '{partner_kind}' inválido")
            checks.append(f"bindings: {bindings} → contexto socio '{partner_kind}'")

        target = raw.get("target", "")
        if not target.isidentifier():
            return self._reject(raw, f"target inválido: {target!r}")
        new_target = target not in spec.variables
        if new_target:
            checks.append(
                f"target '{target}' ({raw.get('target_quantity', '')}) NO está en el "
                f"catálogo — se tratará como magnitud nueva"
            )

        known: dict[str, float] = {}
        text_numbers = numbers_in(question)
        for item in raw.get("known", []):
            name, value = item["name"], float(item["value"])
            if name not in allowed:
                return self._reject(raw, f"variable '{name}' fuera del contrato")
            if name == target:
                return self._reject(raw, f"el target '{target}' viene como dato conocido")
            if not is_grounded(value, text_numbers):
                return self._reject(
                    raw,
                    f"grounding: {name}={value} no aparece en el enunciado "
                    f"(números presentes: {text_numbers})",
                )
            known[name] = value
        checks.append(f"grounding: {len(known)} valores presentes literalmente en el enunciado")

        query = StructuredQuery(
            domain=spec.name,
            context_kind=kind,
            target=target,
            known=known,
            statement=question,
            variable_bindings=bindings,
            partner_context_kind=partner_kind if bindings else "",
        )
        return Translation(
            TranslationStatus.OK, query=query, new_target=new_target,
            target_quantity=raw.get("target_quantity", ""), checks=checks, raw=raw,
        )

    @staticmethod
    def _reject(raw: dict, reason: str) -> Translation:
        return Translation(TranslationStatus.REJECTED, reason=reason, raw=raw)


class Translator:
    def __init__(self, llm: JsonLLM, catalog: DomainCatalog) -> None:
        self.llm = llm
        self.checker = TranslationChecker(catalog)
        self.system = _SYSTEM.format(catalog=catalog.describe())

    def translate(self, question: str) -> Translation:
        try:
            raw = self.llm.complete_json(
                "translate", self.system, json.dumps({"question": question}), TRANSLATION_SCHEMA,
            )
        except LLMError as e:
            return Translation(TranslationStatus.LLM_FAILED, reason=str(e))
        return self.checker.check(question, raw)
