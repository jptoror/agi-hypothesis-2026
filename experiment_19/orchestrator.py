"""SessionOrchestrator — orquestador con persistencia de sesión
(exp_19).

NO reemplaza a los orquestadores per-experimento; los complementa.
Su responsabilidad única es:

  - Mantener la `LoadedSystem` (especialistas + vocabulary registry).
  - Gestionar sesiones (start/resume/process_turn/end).
  - Persistir cada turno automáticamente (resilencia a crashes).
  - Resolver referencias anafóricas DECLARATIVAS sobre el
    `ActiveContext`, sin estadística.

El orquestador NO posee conocimiento de dominio. Cualquier
verbalización de respuesta sale de `ExpressionRenderer` aplicado al
grafo del especialista correspondiente — la prosa es derivación
declarada, no generación.

Lo que NO hace exp_19 (queda para exp_20+):
  - Introducir vocabulario nuevo durante la conversación
    (`"llamemos H a este subgrafo"`).
  - Mantener estado epistémico de hipótesis discutidas.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from experiment_01.knowledge_graph import (
    EpistemicStatus,
    KnowledgeNode,
    NodeKind,
)
from experiment_07.specialist import LanguageSpecialist
from experiment_08.clarification import ClarificationRequest
from experiment_18.expression import ExpressionRenderer, UnresolvedReferenceError

from experiment_19.conversation.active_context import (
    ActiveContext,
    ContextResetReason,
)
from experiment_19.conversation.conversation_graph import (
    cross_graph_foundation,
    ensure_promotion_candidate_field,
    new_conversation_graph,
)
from experiment_19.conversation.session import (
    Session,
    Turn,
    load_session,
    save_session,
)
from experiment_19.persistence.manifest import (
    LoadedSystem,
    save_system,
)


# Patrones anafóricos DECLARADOS. El orquestador reconoce estas
# frases literalmente — no infiere. Cada entrada mapea
# `(pattern, category)` donde `pattern` es una regex case-insensitive
# y `category` es el prefijo de binding contra el que se resuelve en
# el ActiveContext.
_ANAPHORIC_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(?:el|al)\s+(grafo)\s+(?:de\s+antes|anterior)\b", re.IGNORECASE), "grafo"),
    (re.compile(r"\bdel?\s+(grafo)\s+(?:de\s+antes|anterior)\b", re.IGNORECASE), "grafo"),
    (re.compile(r"\b(?:la|su)\s+complejidad\b", re.IGNORECASE), "complejidad"),
    (re.compile(r"\b(?:aplica(?:lo)?|aplica)\s+(?:ahora|de\s+nuevo)\b", re.IGNORECASE), "algoritmo"),
]


class SessionOrchestrator:
    """Orquestador stateful con persistencia por turno.

    Construir directamente para un sistema nuevo, o vía
    `SessionOrchestrator.from_loaded_system(loaded, root_path)` para
    reconstruir tras un reinicio."""

    def __init__(
        self,
        loaded_system: LoadedSystem,
        root_path: str | Path,
    ) -> None:
        self.system = loaded_system
        self.root_path = Path(root_path)
        # Sesión activa en memoria. None hasta que se llame
        # `start_session` o `resume_session`.
        self.active_session: Session | None = None
        # Renderers por especialista, lazy.
        self._renderers: dict[str, ExpressionRenderer] = {}

    # -- API pública ---------------------------------------------------

    def start_session(self, user_id: str | None = None) -> Session:
        session = Session(
            session_id=f"session_{uuid.uuid4().hex[:12]}",
            user_id=user_id,
            conversation_graph=new_conversation_graph(),
            active_context=ActiveContext(),
        )
        self.active_session = session
        save_session(session, self.root_path)
        return session

    def resume_session(self, session_id: str) -> Session:
        session = load_session(self.root_path, session_id)
        self.active_session = session
        return session

    def end_session(self, session: Session | None = None) -> None:
        sess = session or self.active_session
        if sess is None:
            return
        save_session(sess, self.root_path)
        if self.active_session is sess:
            self.active_session = None

    def process_turn(
        self,
        user_input: str,
        session: Session | None = None,
    ) -> Turn:
        """Procesa un turno. Persistencia garantizada al final."""
        sess = session or self.active_session
        if sess is None:
            raise RuntimeError(
                "no hay sesión activa; usar start_session o resume_session"
            )

        # 1. Avanzar el reloj del contexto. Bindings caducados.
        expired = sess.active_context.tick()

        # 2. Parse del input con el LanguageSpecialist sobre el
        #    vocabulary_registry reconstruido.
        from experiment_01.knowledge_graph import KnowledgeGraph
        lang = LanguageSpecialist(
            graph=KnowledgeGraph(),  # no usamos grafo lingüístico aquí
            vocabulary_registry=self.system.vocabulary_registry,
        )
        # `domain_hint` derivado del último specialist (si lo hay).
        domain_hint = sess.active_context.last_specialist_id
        parse = lang.parse(user_input, domain_hint=domain_hint)

        # 3. Reconocimiento anafórico DECLARATIVO sobre el input
        #    crudo. Las categorías que matchean se resuelven contra
        #    `active_bindings`. Ambiguidades → ClarificationRequest.
        anaphoric, clarifications = self._resolve_anaphora(
            user_input=user_input,
            ctx=sess.active_context,
        )

        # 4. Construir el "parsed_problem" serializable. Incluye los
        #    términos resueltos por el registry y los anafóricos.
        resolved_dump = [
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
        ]
        parsed_problem = {
            "tokens": list(parse.steps[0].inputs.values()) if parse.steps else [],
            "resolved_terms": resolved_dump,
            "anaphoric": anaphoric,
            "unrecognized": list(parse.unrecognized_tokens),
        }

        # 5. Si hubo clarification_requests del parser O del
        #    resolver anafórico, el turno se cierra sin respuesta:
        #    el caller debe reformular.
        clarifications = list(parse.clarification_requests) + clarifications

        # 6. Registrar bindings nuevos a partir de los resolved_terms.
        #    Categoría = primera palabra del nodo después del último
        #    punto del node_id (heurística simple y declarada:
        #    `alg.greedy_coloring` → "alg", `def.grafo` → "def").
        #    El orquestador usa eso como "clase" para anáforas.
        new_bindings = []
        for rt in parse.resolved_terms:
            if not rt.bindings:
                continue
            b = rt.bindings[0]
            category = self._infer_category(b.node_id, rt.surface_form)
            binding_name = f"{category}_{len(sess.active_context.active_bindings)}"
            ref = cross_graph_foundation(b.specialist_id, b.node_id)
            sess.active_context.register_binding(binding_name, ref)
            sess.active_context.push_domain_hint(b.specialist_id)
            sess.active_context.last_specialist_id = b.specialist_id
            new_bindings.append((binding_name, ref))

        # 7. Construir un nodo episódico en el conversation_graph que
        #    represente este turno. Sus foundations apuntan a los
        #    nodos resueltos vía cross-graph refs. Eso conserva la
        #    trazabilidad estructural (no es prosa adicional).
        episode_node_id = sess.next_turn_id() + ".episode"
        episode = KnowledgeNode(
            id=episode_node_id,
            statement=user_input,
            status=EpistemicStatus.HYPOTHESIS,
            kind=NodeKind.CONCEPT,
            foundations=[ref for _, ref in new_bindings],
            properties={"turn_id": sess.next_turn_id()},
        )
        ensure_promotion_candidate_field(episode)
        # Importante: cross-graph foundations no están en el grafo
        # local. KnowledgeGraph.add() falla si una foundation no
        # existe en el mismo grafo. Para que la abstracción siga
        # siendo "un KnowledgeGraph normal", almacenamos las
        # cross-graph refs en `properties["external_foundations"]`
        # y dejamos `foundations` con solo refs locales (en este
        # turno, ninguno).
        episode.properties["external_foundations"] = list(episode.foundations)
        episode.foundations = []
        sess.conversation_graph.add(episode)

        # 8. Componer respuesta. Para cada nodo resuelto, renderear
        #    su expression_template (con bindings vacíos para evitar
        #    UnresolvedReferenceError; los nodos del demo doc sin
        #    bindings caen al statement por fallback).
        response_text, trace_dump = self._compose_response(
            parse=parse,
            anaphoric=anaphoric,
            ctx=sess.active_context,
        )

        # 9. Si hubo clarifications, prepend.
        if clarifications:
            cl_lines = "\n".join(f"  ? {c.render()}" for c in clarifications)
            response_text = (
                f"[clarification]\n{cl_lines}\n\n{response_text}"
                if response_text
                else f"[clarification]\n{cl_lines}"
            )

        turn = Turn(
            turn_id=sess.next_turn_id(),
            timestamp=datetime.now(timezone.utc).isoformat(),
            user_input=user_input,
            parsed_problem=parsed_problem,
            trace=trace_dump,
            response_text=response_text or None,
            error=None,
        )
        sess.add_turn(turn)

        # 10. Persistir SIEMPRE (contrato exp_19: cada turno escribe a
        #     disco para sobrevivir crashes).
        save_session(sess, self.root_path)
        return turn

    # -- Persistencia del sistema entero -----------------------------

    def save(self) -> None:
        """Persiste el manifest + grafos. La sesión activa ya se
        persiste turn-by-turn."""
        save_system(
            self.system.specialist_registry,
            self.root_path,
        )
        if self.active_session is not None:
            save_session(self.active_session, self.root_path)

    # -- helpers internos --------------------------------------------

    def _resolve_anaphora(
        self,
        user_input: str,
        ctx: ActiveContext,
    ) -> tuple[list[dict], list[ClarificationRequest]]:
        """Aplica patrones declarados. Cada match intenta resolver
        contra `ctx.resolve_anaphora(category)`. Si hay ambigüedad,
        emite ClarificationRequest con los candidatos."""
        results: list[dict] = []
        clarifications: list[ClarificationRequest] = []
        seen_categories: set[str] = set()

        for pattern, category in _ANAPHORIC_PATTERNS:
            if not pattern.search(user_input):
                continue
            if category in seen_categories:
                continue
            seen_categories.add(category)
            node_id, candidates = ctx.resolve_anaphora(category)
            if node_id is not None:
                results.append({
                    "category": category,
                    "resolved_to": node_id,
                })
                continue
            if candidates:
                clarifications.append(ClarificationRequest(
                    missing_concept=category,
                    available_context={
                        "active_bindings": dict(ctx.active_bindings),
                        "user_input": user_input,
                    },
                    options=candidates,
                    reason=(
                        f"referencia anafórica a '{category}' es "
                        f"ambigua: hay {len(candidates)} bindings activos"
                    ),
                ))
                continue
            # Patrón matcheó pero NO hay binding directo. Para
            # categorías derivables (complejidad → buscar
            # thm.{alg}.complejidad), el extension handler se
            # encarga. Para otras (grafo, algoritmo), sin binding
            # no hay forma de resolver — el caller verá
            # `resolved_to=None` y puede decidir.
            results.append({
                "category": category,
                "resolved_to": None,
            })
        return results, clarifications

    def _infer_category(self, node_id: str, surface_form: str) -> str:
        """Categoría conversacional declarada: usamos el prefijo
        antes del primer punto del node_id (`alg.greedy_coloring`
        → 'alg', `def.grafo` → 'def', `thm.x.complejidad` → 'thm').
        Si el id no tiene punto, usamos la surface_form sanitizada.

        Es DECLARATIVO — el caller que controla los node_ids
        controla las categorías. Sin embeddings."""
        if "." in node_id:
            return node_id.split(".", 1)[0]
        return re.sub(r"\W+", "_", surface_form.strip()) or "binding"

    def _compose_response(
        self,
        parse,
        anaphoric: list[dict],
        ctx: ActiveContext,
    ) -> tuple[str, dict]:
        """Render del texto de respuesta + serialización de traza.

        Para cada `ResolvedTerm`, intenta renderear su nodo vía
        `ExpressionRenderer`. Si el nodo tiene plantilla con
        `{input.X}` no satisfecho, cae al `statement` (NO
        propagamos `UnresolvedReferenceError` al usuario: la
        respuesta debe llegar; los errores duros son de plantilla,
        no de bindings)."""
        sentences: list[str] = []
        trace_steps: list[dict] = []

        for rt in parse.resolved_terms:
            if not rt.bindings:
                continue
            b = rt.bindings[0]
            renderer = self._renderer_for(b.specialist_id)
            if renderer is None:
                continue
            try:
                text = renderer.render_node(b.node_id, bindings={
                    # Permitir que la plantilla referencie su propio
                    # surface_form vía `{input.surface}` si el autor
                    # lo quiere — sin obligación.
                    "input": {"surface": rt.surface_form},
                })
            except UnresolvedReferenceError:
                # Fallback al statement si la plantilla pide
                # bindings que el orquestador no provee aún.
                text = renderer.graph.get(b.node_id).statement
            sentences.append(text)
            trace_steps.append({
                "specialist_id": b.specialist_id,
                "node_id": b.node_id,
                "surface_form": rt.surface_form,
                "rendered": text,
            })

        # Anafóricos: si el patrón matcheó y resolvió, añadimos al
        # final un nodo derivado relacionado. Para el caso canónico
        # "la complejidad" del demo, buscamos `thm.{algorithm}.complejidad`
        # en el especialista del último algoritmo binding.
        for ana in anaphoric:
            extra = self._render_anaphoric_extension(ana, ctx, trace_steps)
            if extra is not None:
                sentences.append(extra["rendered"])
                trace_steps.append(extra)

        return " ".join(sentences).strip(), {"steps": trace_steps}

    def _render_anaphoric_extension(
        self,
        ana: dict,
        ctx: ActiveContext,
        prior_steps: list[dict],
    ) -> dict | None:
        """Caso canónico: el anafórico `(la|su) complejidad` busca
        un teorema con sufijo `.complejidad` que dependa del
        algoritmo más reciente.

        Reconocimiento DECLARATIVO sobre el grafo: no inventa
        teoremas; si el nodo existe en el grafo, lo nombra. Si no,
        devuelve None."""
        if ana.get("category") != "complejidad":
            return None
        # Buscar el último algoritmo binding.
        target_ref = None
        for name, ref in reversed(list(ctx.active_bindings.items())):
            if name.startswith("alg_"):
                target_ref = ref
                break
        if target_ref is None:
            return None
        from experiment_19.conversation.conversation_graph import (
            parse_cross_graph_foundation,
        )
        spec_id, alg_id = parse_cross_graph_foundation(target_ref)
        thm_id = f"thm.{alg_id.split('.', 1)[1]}.complejidad" if "." in alg_id else None
        if thm_id is None:
            return None
        # Buscar el teorema across all loaded graphs — el binding del
        # algoritmo puede vivir en un especialista (vocabulario) y el
        # teorema de complejidad en otro (expresión). El cross-graph
        # foundation no obliga a que vivan en el mismo grafo; la
        # convención del proyecto es que cada nodo es estructura del
        # dominio sin importar qué especialista lo aloja.
        for candidate_spec, candidate_graph in self.system.graphs.items():
            if not candidate_graph.has(thm_id):
                continue
            renderer = self._renderer_for(candidate_spec)
            text = (renderer.render_node(thm_id)
                    if renderer else candidate_graph.get(thm_id).statement)
            ctx.register_binding(
                f"thm_{thm_id}",
                cross_graph_foundation(candidate_spec, thm_id),
            )
            return {
                "specialist_id": candidate_spec,
                "node_id": thm_id,
                "surface_form": "[anafórico: complejidad]",
                "rendered": text,
            }
        return None

    def _renderer_for(self, specialist_id: str) -> ExpressionRenderer | None:
        if specialist_id in self._renderers:
            return self._renderers[specialist_id]
        graph = self.system.graphs.get(specialist_id)
        if graph is None:
            return None
        r = ExpressionRenderer(graph)
        self._renderers[specialist_id] = r
        return r
