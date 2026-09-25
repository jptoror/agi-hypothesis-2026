"""Mensajes estructurados del protocolo inter-especialista.

Principios de diseño:

  1. Mensajes tipados — nunca strings interpretables por NLP.
  2. Request y response están correlacionados por `request_id`.
  3. La respuesta lleva su traza — auditabilidad transitiva.
  4. El protocolo admite gap-en-gap: un especialista consultado
     puede responder UNRESOLVABLE con su propio KnowledgeGap.
  5. `depth` permite al orchestrator abortar cadenas demasiado largas
     — análogo a la fatiga cognitiva humana; el sistema sabe cuándo
     abandonar y buscar otra ruta.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum

from experiment_01.specialist import KnowledgeGap, ReasoningStep, ReasoningTrace


class ResponseStatus(str, Enum):
    """Estados posibles de una respuesta inter-especialista.

    RESOLVED              — el responder produjo los valores pedidos.
    UNRESOLVABLE          — el responder tenía la capacidad pero no
                            pudo derivar el resultado (gap en su grafo).
    DOMAIN_MISMATCH       — el responder no es competente para esta
                            consulta (no debería recibirla, pero el
                            estado existe para fallar explícitamente).
    DELEGATION_DEPTH_EXCEEDED
                          — la cadena de delegaciones superó el umbral
                            de profundidad configurado.
    CYCLE_DETECTED        — se detectó una delegación circular:
                            (requester, target_variable) ya estaba en
                            la pila activa.
    NEEDS_MORE_CONTEXT    — reservado para futuras rondas de
                            negociación; no se usa en el experimento 03.
    """

    RESOLVED = "resolved"
    UNRESOLVABLE = "unresolvable"
    DOMAIN_MISMATCH = "domain_mismatch"
    DELEGATION_DEPTH_EXCEEDED = "delegation_depth_exceeded"
    CYCLE_DETECTED = "cycle_detected"
    NEEDS_MORE_CONTEXT = "needs_more_context"


class DelegationError(Exception):
    """Fallo fatal del protocolo — distinto de una respuesta UNRESOLVABLE.

    Se lanza cuando hay un error estructural: mensajes malformados,
    especialista no registrado, etc. Un responder que simplemente no
    puede resolver devuelve `GapResponse(status=UNRESOLVABLE)`, no lanza.
    """


def _new_request_id() -> str:
    return str(uuid.uuid4())


@dataclass
class GapRequest:
    """Consulta enviada por un especialista al orchestrator.

    El requester NUNCA nombra al responder — sólo dice qué necesita.
    El orchestrator decide a qué especialista reenviarla en función de
    la registry. Esto preserva la propiedad 'el requester no conoce los
    otros dominios' y 'el orchestrator no conoce ningún dominio — sólo
    enruta'.

    `domain_context` es el contexto que el requester aporta desde SU
    dominio (p. ej. Física aporta `{"figure": DomainContext(kind="square", ...)}`
    porque el enunciado habla de un cuadrado). Es información que el
    responder puede necesitar; no es conocimiento del dominio del
    responder inyectado por el requester.
    """

    requester: str
    target_variable: str
    domain_context: dict = field(default_factory=dict)
    rationale: str = ""
    depth: int = 0
    request_id: str = field(default_factory=_new_request_id)

    def child(self, new_requester: str, new_target: str, **kw) -> "GapRequest":
        """Deriva una sub-consulta incrementando depth.

        Uso típico: un responder que, al intentar resolver, descubre que
        él mismo necesita delegar. Preserva la profundidad acumulada.
        """
        return GapRequest(
            requester=new_requester,
            target_variable=new_target,
            domain_context=kw.get("domain_context", dict(self.domain_context)),
            rationale=kw.get("rationale", ""),
            depth=self.depth + 1,
        )

    def render(self) -> str:
        ctx = ", ".join(f"{k}={v!r}" for k, v in self.domain_context.items())
        return (
            f"GapRequest[{self.request_id[:8]}] "
            f"{self.requester} pide '{self.target_variable}' "
            f"(depth={self.depth}) | contexto: {ctx or '(vacío)'} | "
            f"motivo: {self.rationale or '(sin motivo)'}"
        )


@dataclass
class GapResponse:
    """Respuesta a una GapRequest.

    `value` es un dict porque un especialista puede devolver varias
    variables derivadas juntas (p. ej. Geometría devolviendo `v` y de
    paso `l`). Esto preserva trabajo ya hecho.

    `trace` lleva la derivación que el responder hizo. El requester la
    incorporará como `delegated_trace` en su propio paso.

    `failure` se rellena si status ∈ {UNRESOLVABLE, CYCLE_DETECTED,
    DELEGATION_DEPTH_EXCEEDED} y aporta un KnowledgeGap explicando por
    qué. Para DOMAIN_MISMATCH es None — no hay 'gap', simplemente no
    procede.
    """

    request_id: str
    responder: str
    status: ResponseStatus
    value: dict | None = None
    trace: ReasoningTrace | None = None
    failure: KnowledgeGap | None = None
    # Pasos que el orchestrator quiere que aparezcan en la TRAZA
    # PRINCIPAL del requester, insertados ANTES del delegated_step.
    # Uso canónico: el 'binding:<src>→<dst>' que el orchestrator emite
    # cuando respeta una equivalencia ontológica declarada en el problema.
    # Los especialistas consumen esta lista en `_try_delegate`.
    pre_steps: list[ReasoningStep] = field(default_factory=list)

    def is_success(self) -> bool:
        return self.status == ResponseStatus.RESOLVED and self.value is not None

    def render(self) -> str:
        head = (
            f"GapResponse[{self.request_id[:8]}] "
            f"de {self.responder} → {self.status.value}"
        )
        if self.is_success():
            vals = ", ".join(f"{k}={v}" for k, v in self.value.items())
            return f"{head} | {vals}"
        if self.failure is not None:
            return f"{head} | {self.failure.context}"
        return head
