"""Session + Turn — memoria episódica persistente (exp_19).

Política:

  - Una sesión tiene `session_id` único, lista ordenada de turnos,
    un `conversation_graph` (KnowledgeGraph normal con convención
    del módulo `conversation_graph`) y un `ActiveContext`
    serializable.

  - Cada turno conserva el input del usuario, una representación
    serializable del parse (`parsed_problem`), una serialización de
    la traza si la hubo (`trace`), el texto de respuesta y
    opcionalmente un `error`. Los campos son JSON-nativos para que
    el round-trip sea idéntico al de los grafos.

  - La persistencia es por archivo: `sessions/{session_id}.json`.
    El caller (orquestador) decide cuándo escribir; el contrato
    canónico es "después de cada turno" para que un crash no
    pierda datos.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from experiment_01.knowledge_graph import KnowledgeGraph
from experiment_19.persistence.serialization import (
    FORMAT_VERSION,
    ProcedureRefRegistry,
    UnsupportedSchemaError,
    deserialize_graph,
    serialize_graph,
)
from experiment_19.persistence.manifest import _atomic_write

from .active_context import ActiveContext


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Turn:
    turn_id: str
    timestamp: str
    user_input: str
    parsed_problem: dict | None = None
    trace: dict | None = None
    response_text: str | None = None
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "turn_id": self.turn_id,
            "timestamp": self.timestamp,
            "user_input": self.user_input,
            "parsed_problem": self.parsed_problem,
            "trace": self.trace,
            "response_text": self.response_text,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Turn":
        return cls(
            turn_id=d["turn_id"],
            timestamp=d["timestamp"],
            user_input=d["user_input"],
            parsed_problem=d.get("parsed_problem"),
            trace=d.get("trace"),
            response_text=d.get("response_text"),
            error=d.get("error"),
        )


@dataclass
class Session:
    session_id: str
    user_id: str | None = None
    created_at: str = field(default_factory=_utcnow_iso)
    turns: list[Turn] = field(default_factory=list)
    conversation_graph: KnowledgeGraph = field(
        default_factory=KnowledgeGraph,
    )
    active_context: ActiveContext = field(default_factory=ActiveContext)
    # Campos añadidos en experiment_20. Default-vacíos para que
    # cargar una sesión persistida con exp_19 sin estos campos siga
    # funcionando. `session_registry` NO se persiste — se
    # reconstruye desde `conversation_graph` cuando el caller lo
    # solicita. `epistemic_state` SÍ se persiste; default vacío.
    epistemic_state: object | None = None
    session_registry: object | None = None

    def next_turn_id(self) -> str:
        return f"turn_{len(self.turns) + 1:04d}"

    def add_turn(self, turn: Turn) -> None:
        self.turns.append(turn)

    def ensure_session_registry(self):
        """Inicializa (o reusa) el `SessionVocabularyRegistry` ligado
        al conversation_graph. Lazy import para no acoplar el módulo
        del exp_19 al exp_20 si la sesión nunca usa vocabulario."""
        if self.session_registry is None:
            from experiment_20.vocabulary import SessionVocabularyRegistry
            self.session_registry = SessionVocabularyRegistry(
                self.conversation_graph,
            )
        else:
            # Tras un load, el conversation_graph es una instancia
            # nueva; el registry debe re-anclarse y reindexar.
            from experiment_20.vocabulary import SessionVocabularyRegistry
            if isinstance(self.session_registry, SessionVocabularyRegistry):
                self.session_registry.attach_graph(self.conversation_graph)
        return self.session_registry

    def ensure_epistemic_state(self):
        """Lazy: una sesión que nunca toque estado epistémico no
        paga por el import. La primera consulta lo materializa."""
        if self.epistemic_state is None:
            from experiment_20.epistemic import EpistemicState
            self.epistemic_state = EpistemicState()
        return self.epistemic_state

    # -- Serialización -----------------------------------------------

    def to_dict(self) -> dict:
        epi = None
        if self.epistemic_state is not None:
            # `to_dict()` exigido por el tipo. Si el caller usó otra
            # estructura (improbable), preferimos un error explícito a
            # serializar basura.
            epi = self.epistemic_state.to_dict()
        return {
            "format_version": FORMAT_VERSION,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "created_at": self.created_at,
            "turns": [t.to_dict() for t in self.turns],
            "conversation_graph": serialize_graph(self.conversation_graph),
            "active_context": self.active_context.to_dict(),
            "epistemic_state": epi,
        }

    @classmethod
    def from_dict(
        cls,
        data: dict,
        *,
        procedure_registry: ProcedureRefRegistry | None = None,
    ) -> "Session":
        fv = data.get("format_version")
        if fv != FORMAT_VERSION:
            raise UnsupportedSchemaError(
                f"session.format_version {fv!r} no soportado "
                f"(esperado {FORMAT_VERSION!r})"
            )
        sess = cls(
            session_id=data["session_id"],
            user_id=data.get("user_id"),
            created_at=data.get("created_at", _utcnow_iso()),
            turns=[Turn.from_dict(t) for t in data.get("turns", [])],
            conversation_graph=deserialize_graph(
                data.get("conversation_graph") or {
                    "format_version": FORMAT_VERSION,
                    "node_count": 0,
                    "nodes": [],
                },
                procedure_registry=procedure_registry,
            ),
            active_context=ActiveContext.from_dict(
                data.get("active_context") or {},
            ),
        )
        # epistemic_state: cargar sólo si el JSON lo trae. Una sesión
        # de exp_19 que no tenía el campo se carga con estado vacío
        # (semántica "no se conoce nada", indistinguible de "no se
        # afirmó nada"). Tolerante: si EpistemicState no está
        # disponible en el path de import, dejamos None y el caller
        # decide.
        epi = data.get("epistemic_state")
        if epi is not None:
            try:
                from experiment_20.epistemic import EpistemicState
                sess.epistemic_state = EpistemicState.from_dict(epi)
            except ImportError:
                # exp_20 no disponible — preservar el dict crudo
                # para que un componente compatible pueda reconstruir.
                sess.epistemic_state = epi
        return sess


# ---------------------------------------------------------------------
# IO
# ---------------------------------------------------------------------

def session_path(root_path: str | Path, session_id: str) -> Path:
    return Path(root_path) / "sessions" / f"{session_id}.json"


def save_session(session: Session, root_path: str | Path) -> Path:
    """Persiste la sesión a `root/sessions/{session_id}.json`.
    Atómico (escritura a `.tmp` + `os.replace`)."""
    p = session_path(root_path, session.session_id)
    _atomic_write(
        p,
        json.dumps(session.to_dict(), indent=2, ensure_ascii=False),
    )
    return p


def load_session(
    root_path: str | Path,
    session_id: str,
    *,
    procedure_registry: ProcedureRefRegistry | None = None,
) -> Session:
    p = session_path(root_path, session_id)
    if not p.exists():
        raise FileNotFoundError(f"no existe sesión en {p}")
    data = json.loads(p.read_text(encoding="utf-8"))
    return Session.from_dict(data, procedure_registry=procedure_registry)
