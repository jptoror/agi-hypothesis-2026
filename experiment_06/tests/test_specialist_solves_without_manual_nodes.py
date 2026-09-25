"""Test crítico del experimento 06.

Verifica las cuatro propiedades centrales:

  1. nodes_built == 5
  2. nodes_constructed_manually == 0  ← el invariante más importante
  3. result.value == -2.0
  4. len(result.trace.steps) > 0

El segundo assert es el corazón del experimento: ningún KnowledgeNode
del grafo del especialista fue construido fuera del pipeline de
parsing. Si alguien añadiera un nodo a mano (p. ej. para 'arreglar'
algo durante una iteración), ese nodo no llevaría
`properties['extracted_from_document'] = True` y este test fallaría.
"""
from __future__ import annotations

import unittest
from pathlib import Path

from experiment_01.specialist import DomainContext, Problem
from experiment_03.inter_specialist_protocol import SpecialistRegistry

from experiment_06.specialist_factory import SpecialistFactory


_DOC = (
    Path(__file__).resolve().parent.parent
    / "sample_documents" / "algebra_ch3.md"
)


class SpecialistSolvesWithoutManualNodesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = SpecialistRegistry()
        self.factory = SpecialistFactory(
            registry=self.registry,
            implicit_figure_kind="linear_equation",
        )
        self.result = self.factory.from_document(_DOC)

    # -- propiedades del build ------------------------------------------

    def test_build_produced_five_nodes(self) -> None:
        self.assertTrue(self.result.registered)
        self.assertEqual(self.result.build_report.nodes_built, 5)
        self.assertTrue(self.result.build_report.graph_valid)

    def test_no_manual_nodes_in_graph(self) -> None:
        """El assert más importante del experimento.

        Cuenta cuántos nodos del grafo del especialista NO llevan la
        marca `extracted_from_document=True`. Esa marca la asigna
        sólo el GraphBuilder al construir nodos a partir del
        ParseReport. Cualquier nodo sin la marca habría sido añadido
        fuera del pipeline — exactamente lo que el experimento dice
        que NO ocurre.
        """
        graph = self.result.build_report.graph
        self.assertIsNotNone(graph)
        manual = SpecialistFactory.count_manual_nodes(graph)
        self.assertEqual(
            manual, 0,
            f"se esperaba 0 nodos manuales; se encontraron {manual}",
        )

    # -- propiedades de la resolución -----------------------------------

    def test_specialist_solves_linear_equation(self) -> None:
        problem = Problem(
            statement="3x + 6 = 0",
            target="x",
            context=DomainContext(kind="linear_equation", known={"a": 3.0, "b": 6.0}),
        )
        result = self.result.specialist.solve(problem)

        self.assertTrue(result.success)
        self.assertEqual(result.value, -2.0)
        self.assertGreater(len(result.trace.steps), 0)

        # Además: el paso usado debe ser un nodo extraído del documento.
        first_step = result.trace.steps[0]
        graph = self.result.build_report.graph
        node_used = graph.get(first_step.node_id)
        self.assertTrue(
            (node_used.properties or {}).get("extracted_from_document"),
            f"el nodo usado en la derivación '{first_step.node_id}' debería "
            f"estar marcado como extraído del documento."
        )


if __name__ == "__main__":
    unittest.main()
