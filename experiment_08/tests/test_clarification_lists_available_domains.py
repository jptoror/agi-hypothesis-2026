"""Test 4: las `options` de la ClarificationRequest son exactamente
los especialistas relevantes del bus, sin incluir al iniciador.

Verifica las dos formas de "options":
  - AMBIGUOUS → options son los candidatos que conocen el concepto.
  - UNKNOWN   → options son todos los elegibles (el caller debe
                declarar dónde encaja).

En ningún caso aparece el iniciador ('language' en este pipeline).
"""
from __future__ import annotations

import unittest

from experiment_08.clarification import ClarificationResolver

from experiment_08.tests._helpers import (
    registry_with_no_coefficient,
    registry_with_two_coefficient_specialists,
)


class ClarificationListsAvailableDomainsTest(unittest.TestCase):
    def test_ambiguous_options_match_candidates(self) -> None:
        registry = registry_with_two_coefficient_specialists()
        resolver = ClarificationResolver(
            registry=registry, initiating_specialist="language"
        )
        result = resolver.assess("coeficiente")
        options = result.clarification_request.options

        # Exactamente los candidatos que tienen "coeficiente" en sus
        # ids — sin el iniciador.
        self.assertEqual(set(options), {"algebra", "fisica"})
        self.assertNotIn("language", options)
        # Las opciones son un subconjunto de los nombres del bus.
        bus_names = {a.name for a in registry.all()}
        self.assertTrue(set(options).issubset(bus_names))

    def test_unknown_options_are_all_eligible(self) -> None:
        registry = registry_with_no_coefficient()
        resolver = ClarificationResolver(
            registry=registry, initiating_specialist="language"
        )
        result = resolver.assess("coeficiente")
        options = result.clarification_request.options

        # Como nadie conoce el concepto, las opciones son TODOS los
        # especialistas del bus excepto el iniciador.
        bus_names = {a.name for a in registry.all()}
        expected = bus_names - {"language"}
        self.assertEqual(set(options), expected)
        self.assertNotIn("language", options)


if __name__ == "__main__":
    unittest.main()
