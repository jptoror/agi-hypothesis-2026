"""Test que codifica el COMPORTAMIENTO ACTUAL del especialista de
colas tras los DOS fixes de PROB-10:

  1. graph.validate() detecta axiomas con foundations no vacíos.
  2. NodeExtractor NO aplica la heurística "hermano previo" a
     nodos AXIOM — un axioma sin marcador `**Depende de:**`
     queda con foundations=[].

Tras AMBOS fixes:
  - El especialista de colas SE REGISTRA correctamente (validate
    pasa porque ax.fifo tiene foundations=[]).
  - ax.fifo queda con foundations=[] sin necesidad de modificar
    el documento.

Este archivo reemplaza al test previo que congelaba el estado
INTERMEDIO (sólo fix 1 aplicado, especialista NO registrado). Esa
iteración intermedia ya no es el estado actual del sistema.
"""
from __future__ import annotations

import unittest

from experiment_13.specialist_factory import QueueSpecialistFactory


class QueueSpecialistAxiomCorrectlyHandledTest(unittest.TestCase):
    def setUp(self) -> None:
        self.result = QueueSpecialistFactory().build()

    def test_queue_specialist_registers_correctly(self) -> None:
        """Tras el fix completo de PROB-10 (validate + NodeExtractor),
        el especialista de colas se registra sin errores."""
        self.assertTrue(self.result.registered)
        self.assertEqual(self.result.errors, [])

    def test_axiom_has_empty_foundations(self) -> None:
        """El axioma ax.fifo del documento NO declara
        `**Depende de:**`. El NodeExtractor le asigna
        foundations=[] por status — sin pasar por la heurística
        de hermano previo."""
        ax = self.result.graph.get("ax.fifo")
        self.assertEqual(ax.foundations, [])

    def test_graph_validates_clean(self) -> None:
        """Tras los fixes, el grafo entero pasa validate."""
        self.assertEqual(self.result.graph.validate(), [])

    def test_theorems_still_reference_axiom_explicitly(self) -> None:
        """Los teoremas que SÍ dependen de ax.fifo lo declaran con
        `**Depende de:**` en el documento — esa referencia se
        preserva intacta. El fix sólo afecta a la heurística por
        defecto, no al marcador explícito."""
        push_thm = self.result.graph.get("thm.cola.complejidad.push")
        self.assertIn("ax.fifo", push_thm.foundations)
        pop_thm = self.result.graph.get("thm.cola.complejidad.pop")
        self.assertIn("ax.fifo", pop_thm.foundations)
        front_thm = self.result.graph.get("thm.cola.complejidad.front")
        self.assertIn("ax.fifo", front_thm.foundations)

    def test_document_extracted_correctly(self) -> None:
        """El parse del documento sigue produciendo los 17 nodos
        esperados — el fix no afecta a la fase de extracción de
        bloques, sólo a la resolución de fundamentos por defecto."""
        parse = self.result.underlying.parse_report
        self.assertTrue(parse.is_valid)
        self.assertEqual(len(parse.nodes_extracted), 17)

    def test_final_graph_has_20_nodes(self) -> None:
        """17 del documento + 3 importados del grafo base de
        complejidad (def.complexity.O1, def.complexity.On y
        ax.complexity.total_order)."""
        self.assertEqual(len(self.result.graph), 20)


if __name__ == "__main__":
    unittest.main()
