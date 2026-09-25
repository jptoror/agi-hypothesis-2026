"""Test: el especialista de lenguaje reporta como
`unrecognized_tokens` cualquier token que ningún nodo procesó.

El sistema es selectivo POR DISEÑO: 'para' aparece en la instrucción
canónica pero no está en ningún `tokens` declarado y tampoco
matchea el patrón de asignación. Debe verse en la lista de no
reconocidos — el sistema no calla lo que no entiende.
"""
from __future__ import annotations

import unittest

from experiment_07.orchestrator import LanguageToAlgebraOrchestrator


class UnrecognizedTokensReportedTest(unittest.TestCase):
    def setUp(self) -> None:
        self.orch = LanguageToAlgebraOrchestrator()

    def test_para_appears_in_unrecognized_for_canonical(self) -> None:
        result = self.orch.run("resuelve x para a=3, b=6")
        self.assertIn("para", result.parse_result.unrecognized_tokens)

    def test_unknown_words_dont_block_resolution(self) -> None:
        """Tokens no reconocidos no bloquean la resolución mientras
        los nodos necesarios sí matcheen."""
        result = self.orch.run(
            "por favor, resuelve x para a=3, b=6, gracias"
        )
        self.assertTrue(result.success)
        self.assertEqual(result.final_value, -2.0)
        # Las palabras nuevas también caen en unrecognized.
        unrecognized_set = {t.lower() for t in result.parse_result.unrecognized_tokens}
        self.assertIn("para", unrecognized_set)
        self.assertIn("gracias", unrecognized_set)
        self.assertIn("favor", unrecognized_set)
        self.assertIn("por", unrecognized_set)

    def test_invented_words_are_reported_not_silently_dropped(self) -> None:
        """Palabras totalmente inventadas (que ningún humano usaría)
        van a unrecognized_tokens — el sistema no las inventa ni las
        ignora silenciosamente."""
        result = self.orch.run("resuelve x para a=3, b=6 zxqwerty")
        self.assertIn("zxqwerty", result.parse_result.unrecognized_tokens)


if __name__ == "__main__":
    unittest.main()
