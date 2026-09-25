"""Tests del SessionVocabularyRegistry + FallbackVocabularyView."""
from __future__ import annotations

import unittest

from experiment_01.knowledge_graph import (
    EpistemicStatus,
    KnowledgeGraph,
    KnowledgeNode,
    NodeKind,
)
from experiment_17.vocabulary import VocabularyRegistry
from experiment_19.conversation import save_session, load_session
from experiment_19.conversation.session import Session
from experiment_20.vocabulary import (
    FallbackVocabularyView,
    SessionVocabularyRegistry,
)


def _node(node_id: str, surface_forms: list[str]) -> KnowledgeNode:
    return KnowledgeNode(
        id=node_id,
        statement=f"nodo {node_id}",
        status=EpistemicStatus.DEFINITION,
        kind=NodeKind.CONCEPT,
        properties={"surface_forms": list(surface_forms)},
    )


class BuildAndLookupTest(unittest.TestCase):
    def test_empty_graph_yields_empty_registry(self) -> None:
        reg = SessionVocabularyRegistry(KnowledgeGraph())
        self.assertEqual(len(reg), 0)

    def test_indexes_session_nodes(self) -> None:
        cg = KnowledgeGraph()
        cg.add(_node("conv:def.G", ["G", "el grafo G"]))
        cg.add(_node("conv:def.H", ["H"]))
        reg = SessionVocabularyRegistry(cg)
        self.assertEqual(
            sorted(reg.surface_forms()),
            ["el grafo g", "g", "h"],
        )

    def test_rebuild_is_idempotent(self) -> None:
        cg = KnowledgeGraph()
        cg.add(_node("conv:def.G", ["G"]))
        reg = SessionVocabularyRegistry(cg)
        forms_a = reg.surface_forms()
        reg.rebuild_from_graph()
        reg.rebuild_from_graph()
        self.assertEqual(reg.surface_forms(), forms_a)

    def test_attach_graph_replaces_state(self) -> None:
        cg1 = KnowledgeGraph()
        cg1.add(_node("conv:def.G", ["G"]))
        reg = SessionVocabularyRegistry(cg1)
        cg2 = KnowledgeGraph()
        cg2.add(_node("conv:def.H", ["H"]))
        reg.attach_graph(cg2)
        self.assertEqual(reg.lookup("g"), [])
        self.assertEqual(len(reg.lookup("h")), 1)


class FallbackTest(unittest.TestCase):
    def setUp(self) -> None:
        # Global: 'coloreado voraz' → alg_terms:alg.greedy_coloring.
        gg = KnowledgeGraph()
        gg.add(_node("alg.greedy_coloring", ["coloreado voraz"]))
        self.global_reg = VocabularyRegistry()
        self.global_reg.register("alg_terms", gg)

        # Local: 'H' y 'el grafo H' → session:conv:def.H.
        cg = KnowledgeGraph()
        cg.add(_node("conv:def.H", ["H", "el grafo H"]))
        self.session_reg = SessionVocabularyRegistry(cg)

        self.view = FallbackVocabularyView(self.session_reg, self.global_reg)

    def test_local_hit_does_not_consult_global(self) -> None:
        bindings = self.view.lookup("H")
        self.assertEqual(len(bindings), 1)
        self.assertEqual(bindings[0].specialist_id, "session")

    def test_local_miss_falls_to_global(self) -> None:
        bindings = self.view.lookup("coloreado voraz")
        self.assertEqual(len(bindings), 1)
        self.assertEqual(bindings[0].specialist_id, "alg_terms")

    def test_local_wins_in_conflict(self) -> None:
        # Reusar la surface form "coloreado voraz" en la sesión.
        cg = self.session_reg.conversation_graph
        cg.add(_node("conv:def.MISC", ["coloreado voraz"]))
        self.session_reg.rebuild_from_graph()
        bindings = self.view.lookup("coloreado voraz")
        self.assertEqual(len(bindings), 1)
        self.assertEqual(bindings[0].specialist_id, "session")
        self.assertEqual(bindings[0].node_id, "conv:def.MISC")

    def test_longest_match_prefers_longer_span(self) -> None:
        # "el grafo H" (3 tokens) gana sobre "H" (1 token).
        toks = "aplica el grafo H ahora".split()
        hit = self.view.lookup_longest_match(toks, start=1)
        self.assertIsNotNone(hit)
        bindings, span = hit
        self.assertEqual(span, 3)
        self.assertEqual(bindings[0].node_id, "conv:def.H")

    def test_longest_match_finds_global_at_higher_index(self) -> None:
        toks = "el coloreado voraz".split()
        hit = self.view.lookup_longest_match(toks, start=1)
        self.assertIsNotNone(hit)
        bindings, span = hit
        self.assertEqual(span, 2)
        self.assertEqual(bindings[0].specialist_id, "alg_terms")


class RoundTripTest(unittest.TestCase):
    def test_session_round_trip_rebuilds_registry(self, tmp_root: str = None) -> None:
        import tempfile
        import shutil
        from pathlib import Path

        root = Path(tempfile.mkdtemp(prefix="exp20_reg_"))
        try:
            sess = Session(session_id="s1")
            sess.conversation_graph.add(_node("conv:def.H", ["H", "el grafo H"]))
            sess.ensure_session_registry()
            self.assertEqual(len(sess.session_registry.lookup("H")), 1)
            save_session(sess, root)

            loaded = load_session(root, "s1")
            loaded.ensure_session_registry()
            self.assertEqual(len(loaded.session_registry.lookup("H")), 1)
            self.assertEqual(
                loaded.session_registry.lookup("H")[0].node_id,
                "conv:def.H",
            )
        finally:
            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
