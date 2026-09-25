"""Tests del DefinitionHandler (exp_20)."""
from __future__ import annotations

import unittest

from experiment_01.knowledge_graph import (
    EpistemicStatus,
    KnowledgeGraph,
    KnowledgeNode,
    NodeKind,
)
from experiment_17.vocabulary import VocabularyRegistry
from experiment_19.conversation.session import Session
from experiment_20.conversation import (
    DefinitionAccepted,
    DefinitionConflict,
    DefinitionHandler,
    DefinitionRejected,
)
from experiment_20.patterns import DefinitionMatch


def _session_with_global(global_reg: VocabularyRegistry | None = None) -> Session:
    sess = Session(session_id="s1")
    sess.ensure_session_registry()
    sess.ensure_epistemic_state()
    return sess


def _make_global_registry(*, has_grafo: bool = False) -> VocabularyRegistry:
    reg = VocabularyRegistry()
    if has_grafo:
        g = KnowledgeGraph()
        g.add(KnowledgeNode(
            id="def.grafo",
            statement="un grafo es...",
            status=EpistemicStatus.DEFINITION,
            kind=NodeKind.CONCEPT,
            properties={"surface_forms": ["grafo"]},
        ))
        reg.register("alg_terms", g)
    return reg


def _match(symbol: str, body: str, pattern_id: str = "def_pat.llamemos") -> DefinitionMatch:
    return DefinitionMatch(
        symbol=symbol, body=body,
        pattern_id=pattern_id,
        raw_input=f"({pattern_id}) {symbol} → {body}",
    )


class AcceptedPathsTest(unittest.TestCase):
    def test_definition_with_grafo_in_body_gets_category(self) -> None:
        sess = _session_with_global()
        handler = DefinitionHandler(sess, VocabularyRegistry())
        result = handler.process(
            _match("G", "un grafo con vértices 1,2,3,4"),
            turn_id="turn_0001",
        )
        self.assertIsInstance(result, DefinitionAccepted)
        self.assertEqual(result.status, EpistemicStatus.HYPOTHESIS)
        # HYPOTHESIS porque no resuelve foundations (registry global vacío).
        self.assertEqual(result.local_foundations, [])
        self.assertEqual(result.external_foundations, [])
        self.assertEqual(
            sorted(result.surface_forms),
            sorted(["G", "el grafo G"]),
        )

    def test_definition_with_resolvable_global_body(self) -> None:
        sess = _session_with_global()
        global_reg = _make_global_registry(has_grafo=True)
        handler = DefinitionHandler(sess, global_reg)
        result = handler.process(
            _match("G", "un grafo de prueba"),
            turn_id="turn_0001",
        )
        self.assertIsInstance(result, DefinitionAccepted)
        # body resuelve "grafo" → def.grafo en alg_terms (cross-graph).
        self.assertEqual(result.status, EpistemicStatus.DEFINITION)
        self.assertEqual(result.local_foundations, [])
        self.assertEqual(
            result.external_foundations,
            ["alg_terms::def.grafo"],
        )

    def test_definition_with_local_foundation(self) -> None:
        sess = _session_with_global()
        # Pre-insertamos G en el conversation_graph.
        sess.conversation_graph.add(KnowledgeNode(
            id="conv:def.G",
            statement="grafo G",
            status=EpistemicStatus.DEFINITION,
            kind=NodeKind.CONCEPT,
            properties={"surface_forms": ["G", "el grafo G"]},
        ))
        sess.session_registry.rebuild_from_graph()
        handler = DefinitionHandler(sess, VocabularyRegistry())
        result = handler.process(
            _match("H", "G sin el vértice 4"),
            turn_id="turn_0002",
        )
        self.assertIsInstance(result, DefinitionAccepted)
        self.assertEqual(result.local_foundations, ["conv:def.G"])
        # Heredó la categoría "grafo" de G.
        self.assertIn("el grafo H", result.surface_forms)

    def test_session_registry_updated_after_accept(self) -> None:
        sess = _session_with_global()
        handler = DefinitionHandler(sess, VocabularyRegistry())
        handler.process(
            _match("G", "un grafo cualquiera"), turn_id="turn_0001",
        )
        # Tras aceptar, el registry de sesión indexa G.
        bindings = sess.session_registry.lookup("G")
        self.assertEqual(len(bindings), 1)
        self.assertEqual(bindings[0].node_id, "conv:def.G")

    def test_properties_carry_provenance(self) -> None:
        sess = _session_with_global()
        handler = DefinitionHandler(sess, VocabularyRegistry())
        handler.process(_match("X", "un grafo"), turn_id="turn_0007")
        node = sess.conversation_graph.get("conv:def.X")
        props = node.properties or {}
        self.assertEqual(props.get("defined_at_turn"), "turn_0007")
        self.assertEqual(props.get("definition_text"), "un grafo")
        self.assertEqual(props.get("pattern_id"), "def_pat.llamemos")
        # promotion_candidate reservado para exp_21/22.
        self.assertIn("promotion_candidate", props)
        self.assertFalse(props["promotion_candidate"])


class RedefinitionConflictTest(unittest.TestCase):
    def test_redefinition_emits_clarification(self) -> None:
        sess = _session_with_global()
        handler = DefinitionHandler(sess, VocabularyRegistry())
        handler.process(_match("G", "primer cuerpo"), turn_id="turn_0001")
        result = handler.process(
            _match("G", "segundo cuerpo"), turn_id="turn_0002",
        )
        self.assertIsInstance(result, DefinitionConflict)
        # conversation_graph NO modificado: G sigue con el primer cuerpo.
        self.assertEqual(
            sess.conversation_graph.get("conv:def.G").statement,
            "primer cuerpo",
        )
        # La clarificación lleva opciones explícitas.
        opts = result.clarification.options
        self.assertIn("mantener:conv:def.G", opts)
        self.assertIn("reemplazar:conv:def.G", opts)
        self.assertIn("cancelar", opts)


class RejectedPathsTest(unittest.TestCase):
    def test_empty_body_rejected(self) -> None:
        sess = _session_with_global()
        handler = DefinitionHandler(sess, VocabularyRegistry())
        result = handler.process(_match("G", ""), turn_id="turn_0001")
        self.assertIsInstance(result, DefinitionRejected)


class ConflictWithGlobalNotBlockedTest(unittest.TestCase):
    def test_local_shadows_global_without_clarification(self) -> None:
        """Si el símbolo conflicta con surface form del global,
        NO requiere clarification. Local gana (decisión 2 del
        experimento) y el handler procede normalmente."""
        sess = _session_with_global()
        global_reg = _make_global_registry()
        # Añadimos surface form 'G' al global apuntando a otro nodo.
        g = KnowledgeGraph()
        g.add(KnowledgeNode(
            id="other.G",
            statement="otro G",
            status=EpistemicStatus.DEFINITION,
            kind=NodeKind.CONCEPT,
            properties={"surface_forms": ["G"]},
        ))
        global_reg.register("other_spec", g)

        handler = DefinitionHandler(sess, global_reg)
        result = handler.process(
            _match("G", "mi propio G"), turn_id="turn_0001",
        )
        self.assertIsInstance(result, DefinitionAccepted)


if __name__ == "__main__":
    unittest.main()
