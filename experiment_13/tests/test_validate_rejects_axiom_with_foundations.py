"""Test del fix de PROB-10: graph.validate() detecta axiomas con
fundamentos no vacíos.

El bug original: un AXIOM podía tener foundations sin que validate
lo reportara. La regla canónica es:
  - Un axioma se acepta sin demostración → foundations debe estar vacío.
  - Un teorema necesita demostración → foundations debe ser no vacío.

Antes del fix, sólo se controlaba el segundo caso. Ahora ambos.
"""
from __future__ import annotations

import unittest

from experiment_01.knowledge_graph import (
    EpistemicStatus,
    KnowledgeGraph,
    KnowledgeNode,
    NodeKind,
)


class ValidateRejectsAxiomWithFoundationsTest(unittest.TestCase):
    def test_axiom_without_foundations_is_valid(self) -> None:
        g = KnowledgeGraph()
        g.add(KnowledgeNode(
            id="ax.ok",
            statement="(test) axioma sin fundamentos — caso correcto",
            status=EpistemicStatus.AXIOM,
            kind=NodeKind.RELATION,
        ))
        self.assertEqual(g.validate(), [])

    def test_axiom_with_foundations_is_rejected(self) -> None:
        g = KnowledgeGraph()
        # Axioma base válido para que el fundamento exista.
        g.add(KnowledgeNode(
            id="ax.base",
            statement="(test) axioma raíz",
            status=EpistemicStatus.AXIOM,
            kind=NodeKind.RELATION,
        ))
        # Axioma INVÁLIDO — declara fundamentos.
        g.add(KnowledgeNode(
            id="ax.bad",
            statement="(test) axioma con fundamentos espurios",
            status=EpistemicStatus.AXIOM,
            kind=NodeKind.RELATION,
            foundations=["ax.base"],
        ))
        errors = g.validate()
        self.assertEqual(len(errors), 1)
        msg = errors[0]
        self.assertIn("ax.bad", msg)
        self.assertIn("AXIOMA", msg)
        self.assertIn("ax.base", msg)

    def test_theorem_with_foundations_remains_valid(self) -> None:
        # Sanity: el otro check (teorema sin foundations) sigue
        # funcionando — no rompemos al añadir el nuevo.
        g = KnowledgeGraph()
        g.add(KnowledgeNode(
            id="ax.ok",
            statement="(test)",
            status=EpistemicStatus.AXIOM,
            kind=NodeKind.RELATION,
        ))
        g.add(KnowledgeNode(
            id="thm.ok",
            statement="(test)",
            status=EpistemicStatus.THEOREM,
            kind=NodeKind.RELATION,
            foundations=["ax.ok"],
        ))
        self.assertEqual(g.validate(), [])

    def test_theorem_without_foundations_is_still_rejected(self) -> None:
        g = KnowledgeGraph()
        g.add(KnowledgeNode(
            id="thm.bad",
            statement="(test)",
            status=EpistemicStatus.THEOREM,
            kind=NodeKind.RELATION,
        ))
        errors = g.validate()
        self.assertEqual(len(errors), 1)
        self.assertIn("thm.bad", errors[0])
        self.assertIn("TEOREMA", errors[0])


if __name__ == "__main__":
    unittest.main()
