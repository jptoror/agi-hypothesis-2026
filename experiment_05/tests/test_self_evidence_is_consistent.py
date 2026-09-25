"""Test específico de SelfEvidence.

Verifica los dos invariantes pedidos para la auto-evidencia:

  1. Cada propiedad en `properties_demonstrated` tiene una evidencia
     string no vacía.
  2. Cada gap en `actionable_gaps_addressable` está en
     `unknown_concepts` del inventario, NO en `known_concepts`.
     El sistema no puede reclamar que cerrará gaps que ya tiene.
"""
from __future__ import annotations

import unittest

from experiment_05.epistemic_mapper.demo import (
    CANONICAL_QUESTION,
    SEED_CONCEPTS,
    _bootstrap_graphs,
)
from experiment_05.orchestrator import EpistemicOrchestrator
from experiment_05.research_path import Feasibility


class SelfEvidenceIsConsistentTest(unittest.TestCase):
    def setUp(self) -> None:
        self.graphs = _bootstrap_graphs()
        self.orch = EpistemicOrchestrator()
        self.diagnosis = self.orch.diagnose(
            question=CANONICAL_QUESTION,
            seed_concepts=SEED_CONCEPTS,
            graphs=self.graphs,
        )
        self.evidence = self.diagnosis.self_evidence

    # ---- Invariante 1 ---------------------------------------------------

    def test_properties_demonstrated_have_non_empty_evidence(self) -> None:
        self.assertTrue(self.evidence.properties_demonstrated,
                        "properties_demonstrated no debe estar vacío")
        for prop, evidence in self.evidence.properties_demonstrated.items():
            self.assertIsInstance(prop, str)
            self.assertIsInstance(evidence, str)
            self.assertTrue(prop.strip(),
                            f"propiedad vacía: {prop!r}")
            self.assertTrue(evidence.strip(),
                            f"evidencia vacía para '{prop}'")

    # ---- Invariante 2 ---------------------------------------------------

    def test_actionable_gaps_must_be_unknown_in_inventory(self) -> None:
        unknown = set(self.diagnosis.inventory.unknown_concepts)
        known = set(self.diagnosis.inventory.known_concepts)
        for seed in self.evidence.actionable_gaps_addressable:
            self.assertIn(
                seed, unknown,
                f"el sistema reclama '{seed}' como accionable pero no aparece "
                f"en unknown_concepts del inventario."
            )
            self.assertNotIn(
                seed, known,
                f"el sistema reclama '{seed}' como accionable pero ya lo "
                f"conoce — no puede 'cerrar' un gap que no tiene."
            )

    def test_actionable_gaps_correspond_to_actionable_proposals(self) -> None:
        """Cada actionable_gaps_addressable debe corresponder a una
        proposal con feasibility ENGINEERING o RESEARCH (no OPEN_PROBLEM)."""
        actionable_seeds_in_proposals = {
            p.gap_result.seed
            for p in self.diagnosis.proposals
            if p.feasibility in (Feasibility.ENGINEERING, Feasibility.RESEARCH)
        }
        for seed in self.evidence.actionable_gaps_addressable:
            self.assertIn(
                seed, actionable_seeds_in_proposals,
                f"'{seed}' está en actionable_gaps_addressable pero no "
                f"corresponde a una proposal ENGINEERING/RESEARCH."
            )

    # ---- Invariantes de cierre ----------------------------------------

    def test_experiments_completed_lists_five_experiments(self) -> None:
        """El proyecto tiene 5 experimentos; la SelfEvidence los cita."""
        self.assertEqual(len(self.evidence.experiments_completed), 5)
        expected_prefixes = ("exp_01", "exp_02", "exp_03", "exp_04", "exp_05")
        for prefix, line in zip(expected_prefixes, self.evidence.experiments_completed):
            self.assertTrue(
                line.startswith(prefix),
                f"se esperaba que la línea comenzara con {prefix!r}, "
                f"fue: {line!r}"
            )

    def test_conclusion_is_non_empty(self) -> None:
        self.assertTrue(self.evidence.conclusion.strip())


if __name__ == "__main__":
    unittest.main()
