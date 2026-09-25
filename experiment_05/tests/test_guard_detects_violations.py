"""Test forense: el guardián detecta violaciones inyectadas.

Si todas las corridas del guardián fueran HONEST, no podríamos
distinguirlo de un guardián que siempre dice OK. Este test inyecta
violaciones de h1, h2, h5 y h6 deliberadamente y verifica que cada
una se reporta.
"""
from __future__ import annotations

import unittest

from experiment_05.epistemic_mapper.demo import (
    CANONICAL_QUESTION,
    SEED_CONCEPTS,
    _bootstrap_graphs,
)
from experiment_05.epistemic_mapper import (
    ConceptQuery,
    EpistemicMapper,
)
from experiment_05.gap_classifier_v2 import (
    EpistemicGapType,
    GapClassificationResult,
    GapClassifierV2,
)
from experiment_05.honesty_guard import HonestyGuard, Verdict
from experiment_05.research_path import (
    Feasibility,
    ResearchPathProposer,
    ResearchProposal,
)


class GuardDetectsViolationsTest(unittest.TestCase):
    def test_injected_violations_are_detected(self) -> None:
        graphs = _bootstrap_graphs()
        mapper = EpistemicMapper(max_related=5)
        classifier = GapClassifierV2()
        proposer = ResearchPathProposer()
        guard = HonestyGuard()

        inventory = mapper.map(
            ConceptQuery.of(CANONICAL_QUESTION, SEED_CONCEPTS), graphs
        )
        classifications = classifier.classify(inventory)
        proposals = proposer.propose_all(classifications)

        # Inyectamos 4 violaciones independientes:

        # (h1) seed con entrada en hits_per_seed pero lista vacía.
        inventory.hits_per_seed["fake_known"] = []

        # (h2) clasificación para seed que no está en unknown_concepts.
        bad_classification_unknown = GapClassificationResult(
            seed="seed_no_inventario",
            gap_type=EpistemicGapType.MISSING_CONCEPT,
            justification="inyectado",
            classified_by="engineer",
            resolvable_path="x",
        )

        # (h5) classified_by='system' para semilla del catálogo.
        bad_classification_authorship = GapClassificationResult(
            seed="consciencia",
            gap_type=EpistemicGapType.MISSING_CONCEPT,
            justification="mal etiquetado",
            classified_by="system",
            resolvable_path="x",
        )

        classifications_bad = list(classifications) + [
            bad_classification_unknown,
            bad_classification_authorship,
        ]

        # (h6) proposal para seed que no está en unknown_concepts.
        bad_proposal = ResearchProposal(
            gap_result=GapClassificationResult(
                seed="seed_no_inventario_2",
                gap_type=EpistemicGapType.MISSING_CONCEPT,
                justification="x",
                classified_by="engineer",
                resolvable_path="x",
            ),
            feasibility=Feasibility.ENGINEERING,
            proposed_action="x",
            justification="x",
            estimated_complexity="horas",
        )
        proposals_bad = list(proposals) + [bad_proposal]

        report = guard.audit(
            inventory=inventory,
            classifications=classifications_bad,
            proposals=proposals_bad,
            catalogue_keys=set(classifier.catalogue),
        )

        self.assertEqual(report.verdict, Verdict.VIOLATIONS_FOUND)
        violation_ids = {v.check_id for v in report.violations}
        self.assertIn("h1", violation_ids)
        self.assertIn("h2", violation_ids)
        self.assertIn("h5", violation_ids)
        self.assertIn("h6", violation_ids)


if __name__ == "__main__":
    unittest.main()
