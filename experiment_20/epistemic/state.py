"""EpistemicState — estado epistémico de la sesión (exp_20).

Append-only durante la sesión: cada entrada lleva su `turn_id` y
las transiciones de estado (hipótesis pending → confirmed) se
marcan, NO se reescriben.

`detect_inconsistency` es COMPARACIÓN DIRECTA entre
`asserted_entities` — sin inferencia, sin similitud. Si una
afirmación previa dijo `G.vertices = "4"` y una nueva dice
`G.vertices = "6"` para la misma clave, hay inconsistencia. Si las
claves no se solapan, el sistema no infiere consecuencias y
devuelve None.

Todo el estado es JSON-nativo para que la serialización dentro de
`Session` sea trivial.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional


# ---------------------------------------------------------------------
# Tipos
# ---------------------------------------------------------------------

HypothesisStatus = Literal["pending", "confirmed", "refuted"]
AgreementScope = Literal["session"]  # reservado para "user" en futuro


@dataclass
class Affirmation:
    affirmation_id: str
    turn_id: str
    timestamp: str
    statement_summary: str
    trace_ref: str
    asserted_entities: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "affirmation_id": self.affirmation_id,
            "turn_id": self.turn_id,
            "timestamp": self.timestamp,
            "statement_summary": self.statement_summary,
            "trace_ref": self.trace_ref,
            "asserted_entities": dict(self.asserted_entities),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Affirmation":
        return cls(
            affirmation_id=d["affirmation_id"],
            turn_id=d["turn_id"],
            timestamp=d.get("timestamp", ""),
            statement_summary=d.get("statement_summary", ""),
            trace_ref=d.get("trace_ref", ""),
            asserted_entities=dict(d.get("asserted_entities") or {}),
        )


@dataclass
class Hypothesis:
    hypothesis_id: str
    turn_id: str
    statement: str
    missing_foundations: list[str] = field(default_factory=list)
    status: HypothesisStatus = "pending"
    resolved_at_turn: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "hypothesis_id": self.hypothesis_id,
            "turn_id": self.turn_id,
            "statement": self.statement,
            "missing_foundations": list(self.missing_foundations),
            "status": self.status,
            "resolved_at_turn": self.resolved_at_turn,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Hypothesis":
        return cls(
            hypothesis_id=d["hypothesis_id"],
            turn_id=d["turn_id"],
            statement=d.get("statement", ""),
            missing_foundations=list(d.get("missing_foundations") or []),
            status=d.get("status", "pending"),  # type: ignore[arg-type]
            resolved_at_turn=d.get("resolved_at_turn"),
        )


@dataclass
class DeclaredGap:
    gap_id: str
    turn_id: str
    concept: str
    resolved_at_turn: Optional[str] = None
    resolved_by_specialist: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "gap_id": self.gap_id,
            "turn_id": self.turn_id,
            "concept": self.concept,
            "resolved_at_turn": self.resolved_at_turn,
            "resolved_by_specialist": self.resolved_by_specialist,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "DeclaredGap":
        return cls(
            gap_id=d["gap_id"],
            turn_id=d["turn_id"],
            concept=d.get("concept", ""),
            resolved_at_turn=d.get("resolved_at_turn"),
            resolved_by_specialist=d.get("resolved_by_specialist"),
        )


@dataclass
class ClarificationRecord:
    clarification_id: str
    turn_id: str
    question: str
    options: list[str] = field(default_factory=list)
    user_response: Optional[str] = None
    resolved_at_turn: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "clarification_id": self.clarification_id,
            "turn_id": self.turn_id,
            "question": self.question,
            "options": list(self.options),
            "user_response": self.user_response,
            "resolved_at_turn": self.resolved_at_turn,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ClarificationRecord":
        return cls(
            clarification_id=d["clarification_id"],
            turn_id=d["turn_id"],
            question=d.get("question", ""),
            options=list(d.get("options") or []),
            user_response=d.get("user_response"),
            resolved_at_turn=d.get("resolved_at_turn"),
        )


@dataclass
class Agreement:
    agreement_id: str
    turn_id: str
    convention: str
    scope: AgreementScope = "session"

    def to_dict(self) -> dict:
        return {
            "agreement_id": self.agreement_id,
            "turn_id": self.turn_id,
            "convention": self.convention,
            "scope": self.scope,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Agreement":
        return cls(
            agreement_id=d["agreement_id"],
            turn_id=d["turn_id"],
            convention=d.get("convention", ""),
            scope=d.get("scope", "session"),  # type: ignore[arg-type]
        )


# ---------------------------------------------------------------------
# Inconsistencia detectada
# ---------------------------------------------------------------------

@dataclass(frozen=True)
class Inconsistency:
    """Reporte declarativo: la `new_affirmation_id` contradice a
    `previous_affirmation_id` en `conflicting_keys`. El orquestador
    decide si notificar al usuario; el detector NO autocorrige."""

    previous_affirmation_id: str
    previous_turn_id: str
    new_affirmation_id: str
    new_turn_id: str
    conflicting_keys: dict[str, tuple[str, str]]  # key → (prev_val, new_val)


# ---------------------------------------------------------------------
# EpistemicState (contenedor)
# ---------------------------------------------------------------------

@dataclass
class EpistemicState:
    affirmations: list[Affirmation] = field(default_factory=list)
    hypotheses: list[Hypothesis] = field(default_factory=list)
    gaps: list[DeclaredGap] = field(default_factory=list)
    clarifications: list[ClarificationRecord] = field(default_factory=list)
    agreements: list[Agreement] = field(default_factory=list)

    # -- Constructores semánticos -----------------------------------

    def record_affirmation(self, a: Affirmation) -> None:
        self.affirmations.append(a)

    def record_hypothesis(self, h: Hypothesis) -> None:
        self.hypotheses.append(h)

    def record_gap(self, g: DeclaredGap) -> None:
        self.gaps.append(g)

    def record_clarification(self, c: ClarificationRecord) -> None:
        self.clarifications.append(c)

    def record_agreement(self, a: Agreement) -> None:
        self.agreements.append(a)

    def confirm_hypothesis(
        self,
        hypothesis_id: str,
        resolved_at_turn: str,
    ) -> bool:
        for h in self.hypotheses:
            if h.hypothesis_id == hypothesis_id and h.status == "pending":
                h.status = "confirmed"
                h.resolved_at_turn = resolved_at_turn
                return True
        return False

    def refute_hypothesis(
        self,
        hypothesis_id: str,
        resolved_at_turn: str,
    ) -> bool:
        for h in self.hypotheses:
            if h.hypothesis_id == hypothesis_id and h.status == "pending":
                h.status = "refuted"
                h.resolved_at_turn = resolved_at_turn
                return True
        return False

    # -- Detección de inconsistencia (DECLARATIVA) ------------------

    def detect_inconsistency(
        self,
        new_assertion: dict,
    ) -> Inconsistency | None:
        """`new_assertion` es un dict con la misma forma que
        `Affirmation.asserted_entities` + dos metadatos:

          {
            "affirmation_id": "...",
            "turn_id": "...",
            "asserted_entities": {clave: valor_str, ...},
          }

        El detector recorre `self.affirmations` desde la más reciente
        a la más vieja. Para cada par (previa, nueva), busca claves
        COMPARTIDAS con valores DISTINTOS (comparación de strings).
        Si hay al menos una clave conflictiva → `Inconsistency`. Si
        no, None — NO inferimos consecuencias.

        La búsqueda se detiene al encontrar la primera previa
        inconsistente (la más reciente). Eso refleja la semántica
        "la última afirmación pisa a las más viejas si no hay
        conflicto, pero si HAY conflicto, el orquestador es
        notificado contra la previa más cercana"."""
        new_id = new_assertion.get("affirmation_id", "")
        new_turn = new_assertion.get("turn_id", "")
        new_entities: dict = dict(new_assertion.get("asserted_entities") or {})
        if not new_entities:
            return None

        # Iterar desde la última hacia la primera.
        for prev in reversed(self.affirmations):
            conflicting: dict[str, tuple[str, str]] = {}
            for key, val in new_entities.items():
                if key in prev.asserted_entities:
                    prev_val = prev.asserted_entities[key]
                    if prev_val != val:
                        conflicting[key] = (prev_val, val)
            if conflicting:
                return Inconsistency(
                    previous_affirmation_id=prev.affirmation_id,
                    previous_turn_id=prev.turn_id,
                    new_affirmation_id=new_id,
                    new_turn_id=new_turn,
                    conflicting_keys=conflicting,
                )
        return None

    # -- Resolución de gaps por carga de especialistas --------------

    def find_resolved_gap(
        self,
        loaded_specialist_id: str,
        specialist_concepts: set[str],
    ) -> list[DeclaredGap]:
        """Busca `gaps` pendientes cuyo `concept` coincida con algún
        elemento de `specialist_concepts` (comparación exacta).
        Marca los gaps resueltos in-place (`resolved_at_turn` se
        deja en None — el orquestador lo setea cuando despacha la
        nota; eso permite registrar el turno real, no un
        timestamp lateral)."""
        if not specialist_concepts:
            return []
        out: list[DeclaredGap] = []
        for g in self.gaps:
            if g.resolved_at_turn is not None:
                continue
            if g.concept in specialist_concepts:
                g.resolved_by_specialist = loaded_specialist_id
                out.append(g)
        return out

    # -- Serialización ----------------------------------------------

    def to_dict(self) -> dict:
        return {
            "affirmations": [a.to_dict() for a in self.affirmations],
            "hypotheses": [h.to_dict() for h in self.hypotheses],
            "gaps": [g.to_dict() for g in self.gaps],
            "clarifications": [c.to_dict() for c in self.clarifications],
            "agreements": [a.to_dict() for a in self.agreements],
        }

    @classmethod
    def from_dict(cls, d: dict | None) -> "EpistemicState":
        """Tolerante a `None` y a campos faltantes: una sesión
        antigua (sin epistemic_state) se carga como state vacío."""
        if not d:
            return cls()
        return cls(
            affirmations=[
                Affirmation.from_dict(a) for a in d.get("affirmations") or []
            ],
            hypotheses=[
                Hypothesis.from_dict(h) for h in d.get("hypotheses") or []
            ],
            gaps=[
                DeclaredGap.from_dict(g) for g in d.get("gaps") or []
            ],
            clarifications=[
                ClarificationRecord.from_dict(c)
                for c in d.get("clarifications") or []
            ],
            agreements=[
                Agreement.from_dict(a) for a in d.get("agreements") or []
            ],
        )
