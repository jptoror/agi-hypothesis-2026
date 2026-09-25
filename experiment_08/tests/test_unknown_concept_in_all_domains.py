"""Test 3: cuando ningún especialista del bus conoce el concepto,
el resolver emite ClarificationRequest con razón UNKNOWN y opciones
= todos los especialistas elegibles (el caller debe declarar dónde
encaja).
"""
from __future__ import annotations

import unittest

from experiment_08.clarification import (
    ClarificationResolver,
    SufficiencyVerdict,
)

from experiment_08.tests._helpers import registry_with_no_coefficient


class UnknownConceptInAllDomainsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = registry_with_no_coefficient()
        self.resolver = ClarificationResolver(
            registry=self.registry,
            initiating_specialist="language",
        )

    def test_emits_clarification_request(self) -> None:
        result = self.resolver.assess("coeficiente")
        self.assertIsNotNone(result.clarification_request)
        self.assertEqual(result.verdict, SufficiencyVerdict.UNKNOWN)

    def test_reason_mentions_unknown(self) -> None:
        result = self.resolver.assess("coeficiente")
        reason = result.clarification_request.reason.lower()
        # Marcador semántico del caso UNKNOWN: el reason dice
        # "ningún especialista" reconoce el concepto.
        self.assertIn("ningún", reason)
        self.assertIn("coeficiente", reason)

    def test_options_are_all_eligible_specialists(self) -> None:
        result = self.resolver.assess("coeficiente")
        # Opciones = todos menos el iniciador.
        self.assertEqual(set(result.clarification_request.options),
                         {"matematicas", "logica"})

    def test_initiator_excluded(self) -> None:
        result = self.resolver.assess("coeficiente")
        self.assertNotIn("language", result.clarification_request.options)


if __name__ == "__main__":
    unittest.main()
