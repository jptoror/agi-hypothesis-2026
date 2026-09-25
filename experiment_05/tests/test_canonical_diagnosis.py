"""Test del diagnóstico canónico end-to-end del experimento 05.

Corre la pregunta canónica con las 8 semillas declaradas y verifica
las propiedades agregadas que el paper reportará:
  - VEREDICTO HONEST
  - 8 checks ejecutados, 0 violaciones
  - 4 PHILOSOPHICAL_GAPs sin acción
  - coverage_ratio = 0/8 (firma del 'sistema sin vocabulario sobre sí mismo')
  - autoría: 8 engineer / 0 system
"""
from __future__ import annotations

import unittest

from experiment_05.epistemic_mapper.demo import (
    CANONICAL_QUESTION,
    SEED_CONCEPTS,
    _bootstrap_graphs,
)
from experiment_05.gap_classifier_v2 import EpistemicGapType
from experiment_05.honesty_guard import Verdict
from experiment_05.orchestrator import EpistemicOrchestrator
from experiment_05.research_path import Feasibility


class CanonicalDiagnosisTest(unittest.TestCase):
    def setUp(self) -> None:
        self.graphs = _bootstrap_graphs()
        self.orch = EpistemicOrchestrator()
        self.diagnosis = self.orch.diagnose(
            question=CANONICAL_QUESTION,
            seed_concepts=SEED_CONCEPTS,
            graphs=self.graphs,
        )

    def test_inventory_coverage_is_zero(self) -> None:
        """El sistema no tiene vocabulario sobre sí mismo."""
        inv = self.diagnosis.inventory
        self.assertEqual(len(inv.unknown_concepts), len(SEED_CONCEPTS))
        self.assertEqual(inv.coverage_ratio(), 0.0)

    def test_classifications_all_engineer(self) -> None:
        """Todas las clasificaciones del catálogo son del ingeniero."""
        for c in self.diagnosis.classifications:
            self.assertEqual(c.classified_by, "engineer")

    def test_four_philosophical_gaps_have_no_action(self) -> None:
        """Los 4 PHILOSOPHICAL_GAPs no tienen acción propuesta."""
        philosophical = [
            p for p in self.diagnosis.proposals
            if p.gap_result.gap_type == EpistemicGapType.PHILOSOPHICAL_GAP
        ]
        self.assertEqual(len(philosophical), 4)
        for p in philosophical:
            self.assertIsNone(p.proposed_action)
            self.assertEqual(p.feasibility, Feasibility.OPEN_PROBLEM)
            self.assertEqual(p.estimated_complexity, "indefinido")

    def test_honesty_verdict_is_honest(self) -> None:
        """El veredicto del guardián sobre el diagnóstico canónico es HONEST."""
        report = self.diagnosis.honesty_report
        self.assertEqual(report.verdict, Verdict.HONEST)
        self.assertEqual(len(report.checks_executed), 8)
        self.assertEqual(len(report.violations), 0)


if __name__ == "__main__":
    unittest.main()
