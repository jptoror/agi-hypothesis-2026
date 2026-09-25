"""SessionVocabularyRegistry — vocabulario con scope de sesión
(exp_20).

Estructuralmente idéntico al `VocabularyRegistry` del exp_17, pero
anclado a un `conversation_graph` específico. Cuando el usuario
introduce un símbolo en la conversación ("llamemos H a..."), el
nodo `conv:def.H` aterriza en el conversation_graph con
`surface_forms = ["H", "el grafo H"]` y este registry lo indexa
bajo el id de especialista `"session"`.

`FallbackVocabularyView` es la fachada que el LanguageSpecialist
consume: expone la misma API (`lookup`, `lookup_longest_match`)
pero consulta primero el registry de sesión y delega al global
sólo si la forma no aparece localmente. Local SIEMPRE gana cuando
hay match — eso refleja la decisión de diseño 2 del experimento.
"""
from __future__ import annotations

from experiment_01.knowledge_graph import KnowledgeGraph
from experiment_17.vocabulary import VocabularyBinding, VocabularyRegistry


SESSION_SPECIALIST_ID = "session"


class SessionVocabularyRegistry(VocabularyRegistry):
    """Registry anclado a un conversation_graph. Idempotente bajo
    `rebuild_from_graph`."""

    def __init__(self, conversation_graph: KnowledgeGraph) -> None:
        super().__init__()
        self._conversation_graph = conversation_graph
        self.rebuild_from_graph()

    @property
    def conversation_graph(self) -> KnowledgeGraph:
        return self._conversation_graph

    def attach_graph(self, conversation_graph: KnowledgeGraph) -> None:
        """Sustituye el grafo asociado y reindexa. Lo usa el loader
        de sesión cuando el conversation_graph se reconstruye desde
        JSON antes que el registry."""
        self._conversation_graph = conversation_graph
        self.rebuild_from_graph()

    def rebuild_from_graph(self) -> None:
        """Re-indexa todos los nodos del conversation_graph que
        lleven `properties["surface_forms"]`. Como `register` del
        padre es idempotente por specialist_id, llamar dos veces
        produce el mismo estado."""
        self.register(
            specialist_id=SESSION_SPECIALIST_ID,
            graph=self._conversation_graph,
            source_document=None,
        )

    # `lookup_with_fallback` se ofrece como método de conveniencia,
    # pero el consumo canónico en el orquestador pasa por
    # `FallbackVocabularyView` que ya envuelve la lógica entera.
    def lookup_with_fallback(
        self,
        phrase: str,
        global_registry: VocabularyRegistry,
    ) -> list[VocabularyBinding]:
        local = self.lookup(phrase)
        if local:
            return local
        return global_registry.lookup(phrase)


class FallbackVocabularyView:
    """Fachada que el LanguageSpecialist consume sin saber que hay
    dos registries por debajo.

    Implementa los dos métodos que el speech path usa: `lookup` y
    `lookup_longest_match`. Para `lookup_longest_match`, calcula el
    rango más largo combinando los `_max_token_len` de ambos
    registries — sin esa unión podríamos perder un span largo que
    sólo vive en uno de los dos índices.
    """

    def __init__(
        self,
        session_registry: SessionVocabularyRegistry,
        global_registry: VocabularyRegistry,
    ) -> None:
        self.session = session_registry
        self.global_ = global_registry

    def lookup(self, phrase: str) -> list[VocabularyBinding]:
        return self.session.lookup_with_fallback(phrase, self.global_)

    def lookup_longest_match(
        self,
        tokens: list[str],
        start: int = 0,
    ) -> tuple[list[VocabularyBinding], int] | None:
        """Itera desde la ventana más larga posible (max de ambos
        registries) hacia 1. Para cada longitud, prueba primero el
        local; si no hay hit, prueba el global. Esto preserva el
        invariante "el span más informativo gana" Y el invariante
        "local gana en empates de longitud"."""
        n = len(tokens)
        if start < 0 or start >= n:
            return None
        max_len = max(
            self.session._max_token_len,
            self.global_._max_token_len,
        )
        if max_len == 0:
            return None
        max_len = min(max_len, n - start)
        for span in range(max_len, 0, -1):
            phrase = " ".join(tokens[start:start + span])
            bindings = self.session.lookup(phrase)
            if bindings:
                return (bindings, span)
            bindings = self.global_.lookup(phrase)
            if bindings:
                return (bindings, span)
        return None
