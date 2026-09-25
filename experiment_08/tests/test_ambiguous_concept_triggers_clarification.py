"""Test 1: cuando dos o más especialistas conocen el mismo concepto,
el resolver emite una ClarificationRequest con razón AMBIGUOUS y
las opciones que el caller puede elegir.
"""
from __future__ import annotations

import unittest

from experiment_08.clarification import (
    ClarificationResolver,
    SufficiencyVerdict,
)

from experiment_08.tests._helpers import registry_with_two_coefficient_specialists


class AmbiguousConceptTriggersClarificationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = registry_with_two_coefficient_specialists()
        self.resolver = ClarificationResolver(
            registry=self.registry,
            initiating_specialist="language",
        )

    def test_emits_clarification_request(self) -> None:
        result = self.resolver.assess("coeficiente")
        self.assertIsNotNone(result.clarification_request)
        self.assertEqual(result.verdict, SufficiencyVerdict.AMBIGUOUS)

    def test_reason_mentions_ambiguity(self) -> None:
        result = self.resolver.assess("coeficiente")
        self.assertIsNotNone(result.clarification_request)
        # 'AMBIGUOUS' como concepto epistémico aparece en el reason
        # como "varios especialistas reconocen ...". Verificamos los
        # marcadores semánticos sin acoplarnos a redacción exacta.
        reason = result.clarification_request.reason.lower()
        self.assertIn("varios", reason)
        self.assertIn("coeficiente", reason)

    def test_options_count_matches_candidates(self) -> None:
        result = self.resolver.assess("coeficiente")
        self.assertIsNotNone(result.clarification_request)
        self.assertEqual(len(result.clarification_request.options), 2)
        self.assertEqual(set(result.clarification_request.options),
                         {"algebra", "fisica"})

    def test_initiator_excluded_from_options(self) -> None:
        result = self.resolver.assess("coeficiente")
        self.assertNotIn("language", result.clarification_request.options)


if __name__ == "__main__":
    unittest.main()
