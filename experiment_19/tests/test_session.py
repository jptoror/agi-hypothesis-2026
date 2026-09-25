"""Tests de Session + Turn + conversation_graph (exp_19).

Cubren persistencia de sesión, preservación de orden de turnos,
preservación de `conversation_graph` con `promotion_candidate`, y
helpers de cross-graph foundations.
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from experiment_01.knowledge_graph import (
    EpistemicStatus,
    KnowledgeNode,
    NodeKind,
)
from experiment_19.conversation import (
    Session,
    Turn,
    cross_graph_foundation,
    ensure_promotion_candidate_field,
    is_cross_graph_foundation,
    load_session,
    new_conversation_graph,
    parse_cross_graph_foundation,
    save_session,
    set_promotion_candidate,
)
from experiment_19.conversation.conversation_graph import (
    is_promotion_candidate,
)


def _episode(turn_id: str, statement: str = "x") -> KnowledgeNode:
    n = KnowledgeNode(
        id=f"{turn_id}.episode",
        statement=statement,
        status=EpistemicStatus.HYPOTHESIS,
        kind=NodeKind.CONCEPT,
        properties={"turn_id": turn_id},
    )
    ensure_promotion_candidate_field(n)
    return n


class CrossGraphFoundationTest(unittest.TestCase):
    def test_encode_decode_roundtrip(self) -> None:
        ref = cross_graph_foundation("alg_demo", "alg.greedy_coloring")
        self.assertTrue(is_cross_graph_foundation(ref))
        spec, nid = parse_cross_graph_foundation(ref)
        self.assertEqual(spec, "alg_demo")
        self.assertEqual(nid, "alg.greedy_coloring")

    def test_local_id_not_treated_as_cross(self) -> None:
        self.assertFalse(is_cross_graph_foundation("def.alfa"))

    def test_rejects_separator_in_specialist_id(self) -> None:
        with self.assertRaises(ValueError):
            cross_graph_foundation("a::b", "node")

    def test_parse_rejects_local_id(self) -> None:
        with self.assertRaises(ValueError):
            parse_cross_graph_foundation("def.local")


class PromotionCandidateTest(unittest.TestCase):
    def test_default_is_false_when_field_ensured(self) -> None:
        n = KnowledgeNode(
            id="x", statement="x",
            status=EpistemicStatus.HYPOTHESIS, kind=NodeKind.CONCEPT,
        )
        ensure_promotion_candidate_field(n)
        self.assertFalse(is_promotion_candidate(n))
        self.assertIn("promotion_candidate", n.properties)

    def test_set_and_query(self) -> None:
        n = KnowledgeNode(
            id="x", statement="x",
            status=EpistemicStatus.HYPOTHESIS, kind=NodeKind.CONCEPT,
        )
        set_promotion_candidate(n, True)
        self.assertTrue(is_promotion_candidate(n))


class SessionRoundTripTest(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="exp19_session_"))

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def test_save_and_load_simple_session(self) -> None:
        sess = Session(
            session_id="test_001", user_id="juanpa",
            conversation_graph=new_conversation_graph(),
        )
        sess.add_turn(Turn(
            turn_id="turn_0001", timestamp="2026-05-11T00:00:00+00:00",
            user_input="hola", response_text="hola",
        ))
        save_session(sess, self.root)
        s2 = load_session(self.root, "test_001")
        self.assertEqual(s2.session_id, "test_001")
        self.assertEqual(s2.user_id, "juanpa")
        self.assertEqual(len(s2.turns), 1)
        self.assertEqual(s2.turns[0].user_input, "hola")

    def test_turn_order_preserved(self) -> None:
        sess = Session(session_id="ord", user_id=None)
        for i in range(1, 6):
            sess.add_turn(Turn(
                turn_id=f"turn_{i:04d}",
                timestamp=f"2026-05-11T00:00:0{i}+00:00",
                user_input=f"q{i}",
            ))
        save_session(sess, self.root)
        s2 = load_session(self.root, "ord")
        self.assertEqual([t.turn_id for t in s2.turns],
                         [f"turn_{i:04d}" for i in range(1, 6)])

    def test_conversation_graph_persists(self) -> None:
        sess = Session(session_id="cg", user_id=None)
        sess.conversation_graph.add(_episode("turn_0001", "primera pregunta"))
        save_session(sess, self.root)
        s2 = load_session(self.root, "cg")
        self.assertEqual(len(s2.conversation_graph), 1)
        node = s2.conversation_graph.get("turn_0001.episode")
        self.assertEqual(node.properties["turn_id"], "turn_0001")

    def test_promotion_candidate_survives_round_trip(self) -> None:
        sess = Session(session_id="pc", user_id=None)
        n = _episode("turn_0001")
        set_promotion_candidate(n, True)
        sess.conversation_graph.add(n)
        save_session(sess, self.root)
        s2 = load_session(self.root, "pc")
        recovered = s2.conversation_graph.get("turn_0001.episode")
        self.assertTrue(is_promotion_candidate(recovered))

    def test_resume_and_add_turn(self) -> None:
        sess = Session(session_id="resume", user_id=None)
        sess.add_turn(Turn(
            turn_id="turn_0001", timestamp="t1", user_input="A",
        ))
        save_session(sess, self.root)

        s2 = load_session(self.root, "resume")
        s2.add_turn(Turn(
            turn_id=s2.next_turn_id(), timestamp="t2", user_input="B",
        ))
        save_session(s2, self.root)

        s3 = load_session(self.root, "resume")
        self.assertEqual([t.user_input for t in s3.turns], ["A", "B"])

    def test_load_missing_session_raises(self) -> None:
        with self.assertRaises(FileNotFoundError):
            load_session(self.root, "nope")


if __name__ == "__main__":
    unittest.main()
