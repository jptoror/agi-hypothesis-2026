"""Test del fix del NodeExtractor — la heurística de hermano previo
se omite para nodos AXIOM.

Verifica que la regla por status funciona en aislamiento, sobre un
documento minimal construido en el test (sin depender del documento
de colas):

  - DEFINITION/THEOREM sin `**Depende de:**` reciben hermanos
    previos como foundations (comportamiento original preservado).
  - AXIOM sin `**Depende de:**` recibe foundations=[] siempre,
    independientemente de qué nodos lo precedan en la sección.

Este test asegura que el fix se mantiene si alguien refactoriza el
extractor en el futuro.
"""
from __future__ import annotations

import unittest

from experiment_06.document_parser import (
    NodeExtractor,
    StructureExtractor,
)


_DOC = """\
# Test

## 1.1 Mixed section

**Definición:**
**Id:** def.alpha
La definición alpha es un concepto base.

**Definición:**
**Id:** def.beta
La definición beta apoya en alpha.

**Axioma:**
**Id:** ax.gamma
Un axioma sin marcador de dependencia. NO debe heredar
fundamentos de los nodos previos en la sección.

**Definición:**
**Id:** def.delta
La definición delta viene después del axioma.
"""


class ExtractorSkipsAxiomHeuristicTest(unittest.TestCase):
    def setUp(self) -> None:
        structure = StructureExtractor().extract_text(_DOC)
        self.report = NodeExtractor().extract(structure)
        self.by_id = {n.node_id: n for n in self.report.nodes_extracted}

    def test_parse_is_valid(self) -> None:
        self.assertTrue(self.report.is_valid)
        self.assertEqual(len(self.report.nodes_extracted), 4)

    def test_first_definition_has_no_foundations(self) -> None:
        # Es el primero de la sección; no hay hermanos previos.
        self.assertEqual(self.by_id["def.alpha"].foundations, [])

    def test_second_definition_inherits_previous(self) -> None:
        # def.beta hereda def.alpha (opción iii preservada para
        # DEFINITION).
        self.assertEqual(self.by_id["def.beta"].foundations, ["def.alpha"])

    def test_axiom_has_empty_foundations_despite_previous_siblings(self) -> None:
        """ax.gamma viene DESPUÉS de def.alpha y def.beta. La
        heurística antigua le habría asignado ambos como
        foundations. El fix lo evita: los axiomas siempre tienen
        foundations=[] sin marcador explícito."""
        self.assertEqual(self.by_id["ax.gamma"].foundations, [])

    def test_definition_after_axiom_still_inherits_all_previous(self) -> None:
        """El axioma SÍ cuenta como hermano previo para los nodos
        posteriores (sigue contribuyendo al historial de la
        sección). Eso preserva la coherencia del documento: las
        definiciones siguientes pueden depender estructuralmente
        del axioma."""
        self.assertEqual(
            self.by_id["def.delta"].foundations,
            ["def.alpha", "def.beta", "ax.gamma"],
        )


if __name__ == "__main__":
    unittest.main()
