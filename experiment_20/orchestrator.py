"""EpistemicSessionOrchestrator — extiende el SessionOrchestrator
del exp_19 con:

  - Reconocimiento de definiciones del usuario (4 patrones
    declarados). Cuando matchea, hand-off a `DefinitionHandler` y
    el turno es de tipo "definition" (no se invocan especialistas
    de dominio).

  - Consulta de vocabulario CON FALLBACK: el `LanguageSpecialist`
    recibe un `FallbackVocabularyView` que consulta primero el
    `SessionVocabularyRegistry` y, si no hay match, delega al
    global. Local SIEMPRE gana en empates.

  - Registro de `Affirmation` por respuesta (granularidad de una
    afirmación por turno respondido). Inconsistencia con
    afirmaciones previas → nota explícita en la respuesta, sin
    bloquear.

  - Registro de `DeclaredGap` cuando el parser no resuelve ningún
    término. El orquestador NO autoescribe el concepto; toma la
    surface form más larga del input no reconocido como el
    concepto pendiente. Es DECLARATIVO — el caller que quiera
    granularidad fina, agrega gaps a mano.

NO mutamos al orquestador del exp_19 — extendemos. Los tests del
exp_19 siguen verde.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from experiment_01.knowledge_graph import (
    EpistemicStatus,
    KnowledgeGraph,
    KnowledgeNode,
    NodeKind,
)
from experiment_07.specialist import LanguageSpecialist
from experiment_18.expression import (
    ExpressionRenderer,
    UnresolvedReferenceError,
)
from experiment_19.conversation.active_context import ActiveContext
from experiment_19.conversation.conversation_graph import (
    cross_graph_foundation,
    ensure_promotion_candidate_field,
)
from experiment_19.conversation.session import (
    Session,
    Turn,
    save_session,
)
from experiment_19.orchestrator import SessionOrchestrator
from experiment_19.persistence.manifest import LoadedSystem

from experiment_20.conversation import (
    DefinitionAccepted,
    DefinitionConflict,
    DefinitionHandler,
    DefinitionRejected,
)
from experiment_20.epistemic import (
    Affirmation,
    DeclaredGap,
    EpistemicState,
    Hypothesis,
)
from experiment_20.patterns import DefinitionMatch, match_definition
from experiment_20.vocabulary import (
    FallbackVocabularyView,
    SessionVocabularyRegistry,
)


class EpistemicSessionOrchestrator(SessionOrchestrator):
    """Orquestador con vocabulario conversacional + estado epistémico
    persistente."""

    def __init__(
        self,
        loaded_system: LoadedSystem,
        root_path: str | Path,
    ) -> None:
        super().__init__(loaded_system, root_path)

    # -- start/resume — inicializan los componentes exp_20 ---------

    def start_session(self, user_id: str | None = None) -> Session:
        session = super().start_session(user_id=user_id)
        # Inicializar el registry de sesión y el estado epistémico.
        session.ensure_session_registry()
        session.ensure_epistemic_state()
        save_session(session, self.root_path)
        return session

    def resume_session(self, session_id: str) -> Session:
        session = super().resume_session(session_id)
        # Tras un load, el conversation_graph es una instancia nueva;
        # forzamos el rebuild del registry y reidratamos el estado
        # epistémico (que `Session.from_dict` ya intentó cargar).
        session.ensure_session_registry()
        session.ensure_epistemic_state()
        return session

    # -- process_turn — entrada principal ---------------------------

    def process_turn(
        self,
        user_input: str,
        session: Session | None = None,
    ) -> Turn:
        sess = session or self.active_session
        if sess is None:
            raise RuntimeError(
                "no hay sesión activa; usar start_session o resume_session"
            )
        sess.ensure_session_registry()
        sess.ensure_epistemic_state()

        # 1. Intentar matchear como definición. Si matchea, la ruta
        #    es completamente distinta: no se invocan especialistas
        #    de dominio.
        defn = match_definition(user_input)
        if defn is not None:
            return self._process_definition_turn(sess, user_input, defn)

        # 2. Flujo normal extendido con FallbackVocabularyView.
        return self._process_query_turn(sess, user_input)

    # -- Ruta: definición -------------------------------------------

    def _process_definition_turn(
        self,
        sess: Session,
        user_input: str,
        match: DefinitionMatch,
    ) -> Turn:
        handler = DefinitionHandler(
            session=sess, global_registry=self.system.vocabulary_registry,
        )
        turn_id = sess.next_turn_id()
        result = handler.process(match, turn_id=turn_id)

        if isinstance(result, DefinitionRejected):
            response = (
                f"No pude registrar la definición ({result.reason}). "
                f"Reformula el enunciado."
            )
            parsed = {
                "type": "definition_rejected",
                "reason": result.reason,
                "pattern_id": match.pattern_id,
            }
            trace = None
            error = None
        elif isinstance(result, DefinitionConflict):
            response = self._render_clarification(result.clarification)
            parsed = {
                "type": "definition_conflict",
                "pattern_id": match.pattern_id,
                "existing_node_id": result.existing_node_id,
                "new_body": match.body,
            }
            # Registrar la clarificación en el estado epistémico.
            from experiment_20.epistemic import ClarificationRecord
            sess.epistemic_state.record_clarification(ClarificationRecord(
                clarification_id=f"clar_{uuid.uuid4().hex[:8]}",
                turn_id=turn_id,
                question=result.clarification.reason,
                options=list(result.clarification.options),
            ))
            trace = None
            error = None
        else:
            # DefinitionAccepted.
            response = self._render_definition_accepted(match, result)
            parsed = {
                "type": "definition_accepted",
                "pattern_id": match.pattern_id,
                "node_id": result.node_id,
                "status": result.status.value,
                "surface_forms": list(result.surface_forms),
                "local_foundations": list(result.local_foundations),
                "external_foundations": list(result.external_foundations),
            }
            trace = {
                "steps": [{
                    "node_id": result.node_id,
                    "rendered": match.body,
                    "specialist_id": "session",
                    "surface_form": match.symbol,
                }]
            }
            error = None
            # NO registramos `Affirmation` para definiciones — el
            # contrato del exp_20 es "una afirmación por respuesta
            # del sistema con derivación de dominio". Una definición
            # es un acuerdo conversacional, no una derivación. Se
            # registra como `Agreement`.
            from experiment_20.epistemic import Agreement
            sess.epistemic_state.record_agreement(Agreement(
                agreement_id=f"agr_{uuid.uuid4().hex[:8]}",
                turn_id=turn_id,
                convention=(
                    f"{match.symbol} = {match.body}"
                ),
                scope="session",
            ))

        turn = Turn(
            turn_id=turn_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            user_input=user_input,
            parsed_problem=parsed,
            trace=trace,
            response_text=response or None,
            error=error,
        )
        sess.add_turn(turn)
        save_session(sess, self.root_path)
        return turn

    # -- Ruta: consulta normal --------------------------------------

    def _process_query_turn(
        self,
        sess: Session,
        user_input: str,
    ) -> Turn:
        sess.active_context.tick()

        view = FallbackVocabularyView(
            session_registry=sess.session_registry,
            global_registry=self.system.vocabulary_registry,
        )
        lang = LanguageSpecialist(
            graph=KnowledgeGraph(), vocabulary_registry=view,
        )
        domain_hint = sess.active_context.last_specialist_id
        parse = lang.parse(user_input, domain_hint=domain_hint)

        anaphoric, clarifications = self._resolve_anaphora(
            user_input=user_input, ctx=sess.active_context,
        )
        clarifications = list(parse.clarification_requests) + clarifications

        # Registrar bindings + episode (lógica del exp_19).
        new_bindings: list[tuple[str, str]] = []
        asserted_entities: dict[str, str] = {}
        for rt in parse.resolved_terms:
            if not rt.bindings:
                continue
            b = rt.bindings[0]
            category = self._infer_category(b.node_id, rt.surface_form)
            binding_name = (
                f"{category}_{len(sess.active_context.active_bindings)}"
            )
            ref = cross_graph_foundation(b.specialist_id, b.node_id)
            sess.active_context.register_binding(binding_name, ref)
            sess.active_context.push_domain_hint(b.specialist_id)
            sess.active_context.last_specialist_id = b.specialist_id
            new_bindings.append((binding_name, ref))
            # asserted_entities: forma declarativa "{category}={node_id}".
            # Permite detectar inconsistencia turno a turno cuando un
            # mismo concepto se asocia a un node_id distinto.
            asserted_entities[f"{category}.bound_node"] = b.node_id

        episode_node_id = sess.next_turn_id() + ".episode"
        episode = KnowledgeNode(
            id=episode_node_id, statement=user_input,
            status=EpistemicStatus.HYPOTHESIS, kind=NodeKind.CONCEPT,
            foundations=[],
            properties={
                "turn_id": sess.next_turn_id(),
                "external_foundations": [ref for _, ref in new_bindings],
            },
        )
        ensure_promotion_candidate_field(episode)
        sess.conversation_graph.add(episode)

        response_text, trace_dump = self._compose_response(
            parse=parse, anaphoric=anaphoric, ctx=sess.active_context,
        )

        # Registrar Affirmation/Gap/Hypothesis según el resultado.
        turn_id = sess.next_turn_id()
        notes: list[str] = []

        if response_text and asserted_entities:
            aff = Affirmation(
                affirmation_id=f"aff_{uuid.uuid4().hex[:8]}",
                turn_id=turn_id,
                timestamp=datetime.now(timezone.utc).isoformat(),
                statement_summary=response_text[:120],
                trace_ref=episode_node_id,
                asserted_entities=dict(asserted_entities),
            )
            # Detectar inconsistencia ANTES de registrar.
            inc = sess.epistemic_state.detect_inconsistency({
                "affirmation_id": aff.affirmation_id,
                "turn_id": aff.turn_id,
                "asserted_entities": aff.asserted_entities,
            })
            sess.epistemic_state.record_affirmation(aff)
            if inc is not None:
                # NO bloquear; añadir nota explícita al texto.
                detail = "; ".join(
                    f"{k}: antes='{v[0]}' ahora='{v[1]}'"
                    for k, v in inc.conflicting_keys.items()
                )
                notes.append(
                    f"Esta afirmación contradice lo dicho en el "
                    f"{inc.previous_turn_id}: {detail}."
                )

        # Si el input no resolvió ningún término, registrar gap
        # con el concepto = el input completo trimmed (forma
        # declarativa mínima).
        if not parse.resolved_terms and not anaphoric and user_input.strip():
            gap = DeclaredGap(
                gap_id=f"gap_{uuid.uuid4().hex[:8]}",
                turn_id=turn_id,
                concept=user_input.strip(),
            )
            sess.epistemic_state.record_gap(gap)

        # Si el episodio nodo es HYPOTHESIS (siempre lo es por
        # convención), registrar Hypothesis explícita SÓLO si el
        # turno introdujo refs externas pero NO produjo affirmation
        # (caso "no llegamos a una conclusión").
        if not response_text and new_bindings:
            sess.epistemic_state.record_hypothesis(Hypothesis(
                hypothesis_id=f"hyp_{uuid.uuid4().hex[:8]}",
                turn_id=turn_id,
                statement=user_input,
                missing_foundations=[ref for _, ref in new_bindings],
                status="pending",
            ))

        if notes:
            response_text = (response_text or "") + "\n" + "\n".join(
                f"⚠ {n}" for n in notes
            )

        if clarifications:
            cl_lines = "\n".join(f"  ? {c.render()}" for c in clarifications)
            response_text = (
                f"[clarification]\n{cl_lines}\n\n{response_text}"
                if response_text
                else f"[clarification]\n{cl_lines}"
            )

        turn = Turn(
            turn_id=turn_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            user_input=user_input,
            parsed_problem={
                "type": "query",
                "resolved_terms": [
                    {
                        "surface_form": rt.surface_form,
                        "span_tokens": list(rt.span_tokens),
                        "start_index": rt.start_index,
                        "bindings": [
                            {
                                "specialist_id": b.specialist_id,
                                "node_id": b.node_id,
                                "source_document": b.source_document,
                            }
                            for b in rt.bindings
                        ],
                    }
                    for rt in parse.resolved_terms
                ],
                "anaphoric": anaphoric,
                "unrecognized": list(parse.unrecognized_tokens),
            },
            trace=trace_dump,
            response_text=response_text or None,
            error=None,
        )
        sess.add_turn(turn)
        save_session(sess, self.root_path)
        return turn

    # -- helpers de respuesta ---------------------------------------

    def _render_definition_accepted(
        self,
        match: DefinitionMatch,
        result: DefinitionAccepted,
    ) -> str:
        status_word = (
            "definido" if result.status == EpistemicStatus.DEFINITION
            else "registrado como hipótesis"
        )
        forms = ", ".join(f"\"{f}\"" for f in result.surface_forms)
        return (
            f"{status_word.capitalize()} {match.symbol} como {match.body}. "
            f"Vocabulario de sesión: {forms}."
        )

    def _render_clarification(self, clar) -> str:
        return clar.render()

    # -- compatibilidad con tests: detectar resolución de gaps -----

    def notify_loaded_specialist(
        self,
        specialist_id: str,
        concepts: set[str],
    ) -> list[DeclaredGap]:
        """Hook para experimentos futuros (on-demand load): cuando
        un especialista se carga, busca gaps previos que ahora
        podrían resolverse y los marca. Devuelve los resueltos."""
        if self.active_session is None:
            return []
        epi = self.active_session.ensure_epistemic_state()
        resolved = epi.find_resolved_gap(specialist_id, concepts)
        # `find_resolved_gap` ya marca `resolved_by_specialist`. El
        # turn_id de resolución se setea al siguiente process_turn
        # — aquí preservamos None hasta que ocurra una nueva
        # interacción.
        return resolved
