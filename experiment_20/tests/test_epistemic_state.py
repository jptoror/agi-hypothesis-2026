"""Tests del EpistemicState (exp_20)."""
from __future__ import annotations

import unittest

from experiment_20.epistemic import (
    Affirmation,
    Agreement,
    ClarificationRecord,
    DeclaredGap,
    EpistemicState,
    Hypothesis,
    Inconsistency,
)


def _affirm(aid: str, turn: str, entities: dict[str, str]) -> Affirmation:
    return Affirmation(
        affirmation_id=aid, turn_id=turn,
        timestamp="2026-05-11T00:00:00+00:00",
        statement_summary=f"affirmation {aid}",
        trace_ref="trace",
        asserted_entities=dict(entities),
    )


class RecordTest(unittest.TestCase):
    def test_append_only_recording(self) -> None:
        es = EpistemicState()
        es.record_affirmation(_affirm("a1", "turn_1", {"x": "1"}))
        es.record_hypothesis(Hypothesis(
            hypothesis_id="h1", turn_id="turn_1", statement="?",
        ))
        es.record_gap(DeclaredGap(
            gap_id="g1", turn_id="turn_1", concept="bipartito",
        ))
        es.record_clarification(ClarificationRecord(
            clarification_id="c1", turn_id="turn_1",
            question="?", options=["a", "b"],
        ))
        es.record_agreement(Agreement(
            agreement_id="ag1", turn_id="turn_1",
            convention="usar notación (u,v)", scope="session",
        ))
        self.assertEqual(len(es.affirmations), 1)
        self.assertEqual(len(es.hypotheses), 1)
        self.assertEqual(len(es.gaps), 1)
        self.assertEqual(len(es.clarifications), 1)
        self.assertEqual(len(es.agreements), 1)


class HypothesisTransitionTest(unittest.TestCase):
    def test_pending_to_confirmed(self) -> None:
        es = EpistemicState()
        es.record_hypothesis(Hypothesis(
            hypothesis_id="h1", turn_id="turn_1", statement="X?",
            missing_foundations=["dep_a"],
        ))
        self.assertTrue(es.confirm_hypothesis("h1", "turn_3"))
        self.assertEqual(es.hypotheses[0].status, "confirmed")
        self.assertEqual(es.hypotheses[0].resolved_at_turn, "turn_3")

    def test_already_resolved_not_reconfirmed(self) -> None:
        es = EpistemicState()
        es.record_hypothesis(Hypothesis(
            hypothesis_id="h1", turn_id="turn_1", statement="?",
            status="confirmed", resolved_at_turn="turn_2",
        ))
        self.assertFalse(es.confirm_hypothesis("h1", "turn_5"))

    def test_pending_to_refuted(self) -> None:
        es = EpistemicState()
        es.record_hypothesis(Hypothesis(
            hypothesis_id="h1", turn_id="turn_1", statement="?",
        ))
        self.assertTrue(es.refute_hypothesis("h1", "turn_4"))
        self.assertEqual(es.hypotheses[0].status, "refuted")


class InconsistencyTest(unittest.TestCase):
    def test_contradictory_keys_detected(self) -> None:
        es = EpistemicState()
        es.record_affirmation(_affirm("a1", "turn_1", {"G.vertices": "4"}))
        inc = es.detect_inconsistency({
            "affirmation_id": "a2",
            "turn_id": "turn_5",
            "asserted_entities": {"G.vertices": "6"},
        })
        self.assertIsInstance(inc, Inconsistency)
        self.assertEqual(inc.previous_turn_id, "turn_1")
        self.assertEqual(inc.new_turn_id, "turn_5")
        self.assertEqual(
            inc.conflicting_keys,
            {"G.vertices": ("4", "6")},
        )

    def test_disjoint_keys_no_inconsistency(self) -> None:
        # Comparación EXACTA: si no hay clave compartida, NO se
        # infieren consecuencias. Devuelve None.
        es = EpistemicState()
        es.record_affirmation(_affirm("a1", "turn_1", {"G.vertices": "4"}))
        inc = es.detect_inconsistency({
            "affirmation_id": "a2",
            "turn_id": "turn_5",
            "asserted_entities": {"H.edges": "3"},
        })
        self.assertIsNone(inc)

    def test_matching_values_no_inconsistency(self) -> None:
        es = EpistemicState()
        es.record_affirmation(_affirm("a1", "turn_1", {"G.vertices": "4"}))
        inc = es.detect_inconsistency({
            "affirmation_id": "a2",
            "turn_id": "turn_5",
            "asserted_entities": {"G.vertices": "4"},
        })
        self.assertIsNone(inc)

    def test_detects_against_most_recent_conflict(self) -> None:
        # Hay 3 affirmations previas; la inconsistencia debe
        # apuntar a la MÁS RECIENTE que tenga conflicto.
        es = EpistemicState()
        es.record_affirmation(_affirm("a1", "turn_1", {"x": "1"}))
        es.record_affirmation(_affirm("a2", "turn_2", {"x": "1"}))
        es.record_affirmation(_affirm("a3", "turn_3", {"x": "1"}))
        inc = es.detect_inconsistency({
            "affirmation_id": "a4",
            "turn_id": "turn_4",
            "asserted_entities": {"x": "2"},
        })
        self.assertIsNotNone(inc)
        self.assertEqual(inc.previous_turn_id, "turn_3")


class GapResolutionTest(unittest.TestCase):
    def test_gap_concept_matches_specialist_concept(self) -> None:
        es = EpistemicState()
        es.record_gap(DeclaredGap(
            gap_id="g1", turn_id="turn_1", concept="bipartito",
        ))
        resolved = es.find_resolved_gap(
            loaded_specialist_id="bipartite_spec",
            specialist_concepts={"bipartito", "k-partito"},
        )
        self.assertEqual(len(resolved), 1)
        self.assertEqual(resolved[0].gap_id, "g1")
        # El gap quedó marcado con el especialista, pero
        # resolved_at_turn sigue None (lo setea el orquestador).
        self.assertEqual(resolved[0].resolved_by_specialist, "bipartite_spec")
        self.assertIsNone(resolved[0].resolved_at_turn)

    def test_no_match_returns_empty(self) -> None:
        es = EpistemicState()
        es.record_gap(DeclaredGap(
            gap_id="g1", turn_id="turn_1", concept="bipartito",
        ))
        resolved = es.find_resolved_gap(
            loaded_specialist_id="alg",
            specialist_concepts={"coloreo", "greedy"},
        )
        self.assertEqual(resolved, [])

    def test_already_resolved_gap_skipped(self) -> None:
        es = EpistemicState()
        es.record_gap(DeclaredGap(
            gap_id="g1", turn_id="turn_1", concept="bipartito",
            resolved_at_turn="turn_3",
            resolved_by_specialist="bipartite",
        ))
        resolved = es.find_resolved_gap(
            loaded_specialist_id="bipartite",
            specialist_concepts={"bipartito"},
        )
        self.assertEqual(resolved, [])


class RoundTripTest(unittest.TestCase):
    def test_full_round_trip(self) -> None:
        es = EpistemicState()
        es.record_affirmation(_affirm("a1", "turn_1", {"x": "1"}))
        es.record_hypothesis(Hypothesis(
            hypothesis_id="h1", turn_id="turn_1", statement="X?",
            missing_foundations=["dep_a"],
        ))
        es.record_gap(DeclaredGap(
            gap_id="g1", turn_id="turn_1", concept="bipartito",
        ))
        es.record_clarification(ClarificationRecord(
            clarification_id="c1", turn_id="turn_1",
            question="?", options=["a", "b"],
        ))
        es.record_agreement(Agreement(
            agreement_id="ag1", turn_id="turn_1",
            convention="usar (u,v)", scope="session",
        ))
        d = es.to_dict()
        es2 = EpistemicState.from_dict(d)
        self.assertEqual(es2.affirmations[0].asserted_entities, {"x": "1"})
        self.assertEqual(es2.hypotheses[0].missing_foundations, ["dep_a"])
        self.assertEqual(es2.gaps[0].concept, "bipartito")
        self.assertEqual(es2.clarifications[0].options, ["a", "b"])
        self.assertEqual(es2.agreements[0].convention, "usar (u,v)")

    def test_empty_from_dict_is_safe(self) -> None:
        es = EpistemicState.from_dict(None)
        self.assertEqual(es.affirmations, [])
        es = EpistemicState.from_dict({})
        self.assertEqual(es.affirmations, [])


if __name__ == "__main__":
    unittest.main()
