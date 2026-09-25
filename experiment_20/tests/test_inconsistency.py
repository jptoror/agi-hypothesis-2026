"""Test de la detección de inconsistencia turno-a-turno (exp_20).

El sistema NO autocorrige. Cuando una nueva affirmation contradice
una previa en `asserted_entities`, el orquestador añade una nota
al `response_text` mencionando el turn_id de la primera. El turno
se procesa normalmente.
"""
from __future__ import annotations

import unittest

from experiment_20.epistemic import Affirmation, EpistemicState


def _affirm(aid: str, turn: str, entities: dict[str, str]) -> Affirmation:
    return Affirmation(
        affirmation_id=aid, turn_id=turn,
        timestamp="ts", statement_summary="", trace_ref="",
        asserted_entities=dict(entities),
    )


class InconsistencyNoteTest(unittest.TestCase):
    def test_orchestrator_does_not_block_on_inconsistency(self) -> None:
        """Aserción declarativa: detect_inconsistency reporta el
        conflicto y deja al caller decidir. El test verifica el
        contrato del detector, que es la unidad observable."""
        es = EpistemicState()
        es.record_affirmation(_affirm(
            "a1", "turn_1", {"G.vertices": "4"},
        ))
        inc = es.detect_inconsistency({
            "affirmation_id": "a5",
            "turn_id": "turn_5",
            "asserted_entities": {"G.vertices": "6"},
        })
        self.assertIsNotNone(inc)
        self.assertEqual(inc.previous_turn_id, "turn_1")
        # El detector NO mutó las affirmations; quedan en estado
        # append-only.
        self.assertEqual(len(es.affirmations), 1)
        self.assertEqual(
            es.affirmations[0].asserted_entities["G.vertices"], "4",
        )

    def test_inconsistency_message_includes_previous_turn(self) -> None:
        es = EpistemicState()
        es.record_affirmation(_affirm(
            "a1", "turn_1", {"G.vertices": "4"},
        ))
        inc = es.detect_inconsistency({
            "affirmation_id": "a5",
            "turn_id": "turn_5",
            "asserted_entities": {"G.vertices": "6"},
        })
        # Forma del payload: clave → (valor_previo, valor_nuevo).
        self.assertEqual(
            inc.conflicting_keys["G.vertices"], ("4", "6"),
        )


if __name__ == "__main__":
    unittest.main()
