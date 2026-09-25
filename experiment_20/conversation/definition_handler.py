"""DefinitionHandler — procesa `DefinitionMatch` y produce nodos
del conversation_graph (exp_20).

Reglas:

  - El node_id sigue la convención `conv:def.{symbol}`. El prefijo
    `conv:` marca scope de sesión y diferencia de ids del grafo
    semántico.

  - Si el símbolo ya está definido en la sesión → emite
    `ClarificationRequest` (mecanismo del exp_08) y devuelve
    `DefinitionConflict`. El conversation_graph NO se modifica
    hasta que el usuario decida.

  - Si el body referencia surface forms resolubles (en el
    SessionVocabularyRegistry o en el global), esos node_ids
    pasan a ser `foundations` cuando viven en el
    conversation_graph mismo, o entran a
    `properties["external_foundations"]` cuando viven en grafos
    de especialistas externos. Esta convención sigue lo declarado
    en `experiment_19/conversation/conversation_graph.py`.

  - Si NO se resuelve ninguna referencia y el body parece
    sustantivo → el nodo entra como `HYPOTHESIS` en lugar de
    `DEFINITION`. Esto refleja la honestidad epistémica: una
    definición sin fundamentos verificables es una afirmación
    propuesta, no un acuerdo derivado.

  - `surface_forms` se popula con `[symbol]` siempre; si el body
    contiene una palabra-categoría reconocida (por ahora sólo
    `"grafo"`), se añade `"el {category} {symbol}"`. La lista de
    categorías es DECLARATIVA — extenderla es un cambio explícito.

  - El nodo SIEMPRE lleva `properties["promotion_candidate"] =
    False` (reservado para exp_21/22, vía
    `ensure_promotion_candidate_field` del exp_19).

Conflicto con surface form del registry global: NO requiere
clarificación. Local gana en la sesión; ese es el contrato del
`FallbackVocabularyView`. El conflicto sólo se reporta cuando el
mismo símbolo ya está definido en la MISMA sesión.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Union

from experiment_01.knowledge_graph import (
    EpistemicStatus,
    KnowledgeNode,
    NodeKind,
)
from experiment_08.clarification import ClarificationRequest
from experiment_17.vocabulary import VocabularyBinding, VocabularyRegistry
from experiment_19.conversation.conversation_graph import (
    cross_graph_foundation,
    ensure_promotion_candidate_field,
)
from experiment_19.conversation.session import Session
from experiment_20.patterns import DefinitionMatch


# ---------------------------------------------------------------------
# Resultados
# ---------------------------------------------------------------------

@dataclass(frozen=True)
class DefinitionAccepted:
    """El nodo se añadió al conversation_graph; el registry de
    sesión queda actualizado tras `rebuild_from_graph`."""

    node_id: str
    status: EpistemicStatus
    surface_forms: list[str]
    local_foundations: list[str]
    external_foundations: list[str]


@dataclass(frozen=True)
class DefinitionConflict:
    """El símbolo ya estaba definido en la sesión."""

    existing_node_id: str
    new_match: DefinitionMatch
    clarification: ClarificationRequest


@dataclass(frozen=True)
class DefinitionRejected:
    """Caso degenerado (symbol vacío, body vacío, etc.)."""

    reason: str
    match: DefinitionMatch


ProcessResult = Union[
    DefinitionAccepted, DefinitionConflict, DefinitionRejected,
]


# ---------------------------------------------------------------------
# Heurística DECLARATIVA de categoría
# ---------------------------------------------------------------------

# Mapa palabra-categoría → string que se usa en la surface form
# adicional `"el {categoria} {symbol}"`. Cualquier extensión requiere
# editar este dict (cambio de política explícito).
_CATEGORY_TRIGGERS: dict[str, str] = {
    "grafo": "grafo",
    "conjunto": "conjunto",
    "función": "función",
    "funcion": "función",
}


def _detect_category(body: str) -> str | None:
    """Detección DECLARATIVA: primer token-palabra del body que
    aparezca en `_CATEGORY_TRIGGERS`. Si no aparece ninguno,
    None."""
    tokens = re.findall(r"\w+", body.lower())
    for tok in tokens:
        if tok in _CATEGORY_TRIGGERS:
            return _CATEGORY_TRIGGERS[tok]
    return None


def _inherit_category_from_foundation(
    foundation_node,
) -> str | None:
    """Si una foundation ya declarada lleva surface_forms del tipo
    `"el {categoria} {symbol}"`, heredamos esa categoria. Esto
    refleja la propiedad estructural "H se llamó a G sin un
    vértice → H sigue siendo un grafo". Es DECLARATIVO: la
    inferencia viene de surface_forms ya escritas, no de un
    parser semántico.
    """
    surface_forms = (foundation_node.properties or {}).get(
        "surface_forms", []
    )
    if not isinstance(surface_forms, list):
        return None
    for sf in surface_forms:
        if not isinstance(sf, str):
            continue
        m = re.match(r"^el\s+(\w+)\s+\S+$", sf.strip().lower())
        if m and m.group(1) in _CATEGORY_TRIGGERS.values():
            return m.group(1)
    return None


# ---------------------------------------------------------------------
# Resolución de referencias del body
# ---------------------------------------------------------------------

def _resolve_body_references(
    body: str,
    session_graph_ids: set[str],
    session_lookup,
    global_lookup,
) -> tuple[list[str], list[str], list[VocabularyBinding]]:
    """Detecta surface forms en el body y devuelve:

      (local_foundations, external_foundations_refs, raw_bindings)

    `local_foundations` son node_ids que VIVEN en el
    conversation_graph (ids con prefijo `conv:`). Pueden entrar a
    `KnowledgeNode.foundations` porque el contenedor es el mismo.

    `external_foundations_refs` son refs cross-graph
    (`spec::node_id`) — entran a `properties["external_foundations"]`
    porque el `KnowledgeGraph` exige que las foundations existan
    localmente.

    El recorrido es token-by-token con longest match izquierda→
    derecha. Sin estadística: cada match es lookup exacto contra
    los dos registries (local prioritario).
    """
    tokens = _tokenize(body)
    local: list[str] = []
    external: list[str] = []
    raw_bindings: list[VocabularyBinding] = []

    i = 0
    n = len(tokens)
    while i < n:
        # Probar longest-match con local primero, luego global.
        consumed = 0
        chosen: list[VocabularyBinding] = []
        for span in range(min(n - i, 6), 0, -1):
            phrase = " ".join(tokens[i:i + span])
            chosen = session_lookup(phrase)
            if chosen:
                consumed = span
                break
            chosen = global_lookup(phrase)
            if chosen:
                consumed = span
                break
        if not chosen:
            i += 1
            continue
        # Tomamos la primera binding (orden de registro). Conflicto
        # de bindings se reportaría arriba en otro flujo —
        # `DefinitionHandler` aquí no decide ambiguidad; toma la
        # más antigua.
        b = chosen[0]
        raw_bindings.append(b)
        if b.node_id in session_graph_ids:
            if b.node_id not in local:
                local.append(b.node_id)
        else:
            ref = cross_graph_foundation(b.specialist_id, b.node_id)
            if ref not in external:
                external.append(ref)
        i += consumed

    return local, external, raw_bindings


_TOKEN_SPLIT = re.compile(r"[\s,;:.!?()¿¡{}\[\]]+")


def _tokenize(s: str) -> list[str]:
    return [t for t in _TOKEN_SPLIT.split(s) if t]


# ---------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------

class DefinitionHandler:
    """Stateless. Recibe el session + el registry global en cada
    `process()` y no guarda estado propio."""

    def __init__(
        self,
        session: Session,
        global_registry: VocabularyRegistry,
    ) -> None:
        self.session = session
        self.global_registry = global_registry

    def process(
        self,
        match: DefinitionMatch,
        turn_id: str,
    ) -> ProcessResult:
        if not match.symbol or not match.body:
            return DefinitionRejected(
                reason="symbol o body vacíos", match=match,
            )

        node_id = f"conv:def.{match.symbol}"
        graph = self.session.conversation_graph

        # 1. Redefinición en la misma sesión → ClarificationRequest.
        if graph.has(node_id):
            existing = graph.get(node_id)
            previous_body = (
                (existing.properties or {}).get("definition_text")
                or existing.statement
            )
            clarification = ClarificationRequest(
                missing_concept=match.symbol,
                available_context={
                    "existing_node_id": node_id,
                    "existing_body": previous_body,
                    "new_body": match.body,
                    "turn_id": turn_id,
                    "raw_input": match.raw_input,
                },
                options=[
                    f"mantener:{node_id}",
                    f"reemplazar:{node_id}",
                    "cancelar",
                ],
                reason=(
                    f"'{match.symbol}' ya está definido en esta sesión. "
                    f"Redefinir requiere confirmación explícita."
                ),
            )
            return DefinitionConflict(
                existing_node_id=node_id,
                new_match=match,
                clarification=clarification,
            )

        # 2. Resolver referencias en el body.
        session_graph_ids = {n.id for n in graph}
        session_reg = self._get_session_registry()
        local_foundations, external_foundations, raw_bindings = (
            _resolve_body_references(
                body=match.body,
                session_graph_ids=session_graph_ids,
                session_lookup=session_reg.lookup if session_reg else (lambda _: []),
                global_lookup=self.global_registry.lookup,
            )
        )

        # 3. Determinar status del nodo.
        if local_foundations or external_foundations:
            status = EpistemicStatus.DEFINITION
        else:
            # Sin fundamentos resueltos → es una afirmación propuesta.
            # El sistema NO la convierte en DEFINITION silenciosamente.
            status = EpistemicStatus.HYPOTHESIS

        # 4. Surface forms.
        category = _detect_category(match.body)
        if category is None:
            # Fallback DECLARATIVO: heredar categoría de la primera
            # foundation local que la lleve. Si H se definió a
            # partir de G y G es un "grafo", H también lo es.
            for fid in local_foundations:
                if not graph.has(fid):
                    continue
                cat = _inherit_category_from_foundation(graph.get(fid))
                if cat is not None:
                    category = cat
                    break
        surface_forms = [match.symbol]
        if category is not None:
            surface_forms.append(f"el {category} {match.symbol}")
        else:
            # Cuando no se reconoce categoría, añadimos solamente
            # "el {symbol}" como atajo común — DECLARADO en spec.
            surface_forms.append(f"el {match.symbol}")

        # 5. Construir y agregar el nodo. `foundations` sólo
        # local; `external_foundations` viven en properties.
        node = KnowledgeNode(
            id=node_id,
            statement=match.body,
            status=status,
            kind=NodeKind.CONCEPT,
            foundations=list(local_foundations),
            properties={
                "surface_forms": list(surface_forms),
                "defined_at_turn": turn_id,
                "definition_text": match.body,
                "pattern_id": match.pattern_id,
                "external_foundations": list(external_foundations),
            },
        )
        ensure_promotion_candidate_field(node)
        graph.add(node)

        # 6. Re-indexar el SessionVocabularyRegistry para que el
        # próximo turno pueda resolver el símbolo. El propio
        # registro lo expone via `rebuild_from_graph()`.
        if session_reg is not None:
            session_reg.rebuild_from_graph()

        return DefinitionAccepted(
            node_id=node_id,
            status=status,
            surface_forms=list(surface_forms),
            local_foundations=list(local_foundations),
            external_foundations=list(external_foundations),
        )

    # -- helpers internos -------------------------------------------

    def _get_session_registry(self):
        """El `SessionVocabularyRegistry` vive en `Session` tras la
        extensión que hace exp_20. Lo accedemos por atributo para
        que esta clase NO conozca el constructor (loose coupling)."""
        return getattr(self.session, "session_registry", None)
