"""Test del invariante estructural del ResearchProposal.

Verifica que el dataclass rechaza en construcción cualquier proposal
incoherente — la primera línea de defensa contra alucinación, antes
de que el guardián tenga que verificar a posteriori.
"""
from __future__ import annotations

import unittest

from experiment_05.gap_classifier_v2 import (
    EpistemicGapType,
    GapClassificationResult,
)
from experiment_05.research_path import (
    Feasibility,
    ResearchProposal,
)


def _gap(gtype: EpistemicGapType) -> GapClassificationResult:
    return GapClassificationResult(
        seed="x",
        gap_type=gtype,
        justification="ignored in this test",
        classified_by="engineer",
        resolvable_path=None,
    )


class ProposalInvariantTest(unittest.TestCase):
    def test_open_problem_with_action_raises(self) -> None:
        with self.assertRaises(ValueError):
            ResearchProposal(
                gap_result=_gap(EpistemicGapType.PHILOSOPHICAL_GAP),
                feasibility=Feasibility.OPEN_PROBLEM,
                proposed_action="hacer algo",
                justification="x",
                estimated_complexity="indefinido",
            )

    def test_open_problem_with_finite_complexity_raises(self) -> None:
        with self.assertRaises(ValueError):
            ResearchProposal(
                gap_result=_gap(EpistemicGapType.PHILOSOPHICAL_GAP),
                feasibility=Feasibility.OPEN_PROBLEM,
                proposed_action=None,
                justification="x",
                estimated_complexity="1 hora",
            )

    def test_engineering_without_action_raises(self) -> None:
        with self.assertRaises(ValueError):
            ResearchProposal(
                gap_result=_gap(EpistemicGapType.MISSING_CONCEPT),
                feasibility=Feasibility.ENGINEERING,
                proposed_action=None,
                justification="x",
                estimated_complexity="horas",
            )

    def test_well_formed_proposals_succeed(self) -> None:
        # OPEN_PROBLEM coherente.
        p1 = ResearchProposal(
            gap_result=_gap(EpistemicGapType.PHILOSOPHICAL_GAP),
            feasibility=Feasibility.OPEN_PROBLEM,
            proposed_action=None,
            justification="ok",
            estimated_complexity="indefinido",
        )
        self.assertIsNone(p1.proposed_action)

        # ENGINEERING coherente.
        p2 = ResearchProposal(
            gap_result=_gap(EpistemicGapType.MISSING_CONCEPT),
            feasibility=Feasibility.ENGINEERING,
            proposed_action="añadir def.x",
            justification="ok",
            estimated_complexity="horas",
        )
        self.assertEqual(p2.proposed_action, "añadir def.x")


if __name__ == "__main__":
    unittest.main()
