"""Tests del soporte EpistemicStatus.ALGORITHM (exp_14).

Cinco tests pedidos:
  1. test_algorithm_status_exists
  2. test_algorithm_without_inputs_fails_validate
  3. test_algorithm_without_foundations_produces_warning
  4. test_parser_extracts_algorithm_node
  5. test_parser_extracts_entrada_salida

Verifican el contrato extremo a extremo: enum → validate →
parser. Cada test es independiente y construye su propio fixture
mínimo (no comparte estado).
"""
from __future__ import annotations

import unittest

from experiment_01.knowledge_graph import (
    EpistemicStatus,
    KnowledgeGraph,
    KnowledgeNode,
    NodeKind,
)
from experiment_06.document_parser import (
    NodeExtractor,
    StructureExtractor,
)


# ---------------------------------------------------------------------
# 1. EpistemicStatus.ALGORITHM existe
# ---------------------------------------------------------------------

class AlgorithmStatusExistsTest(unittest.TestCase):
    def test_algorithm_status_exists(self) -> None:
        # Existe como miembro del enum.
        self.assertTrue(hasattr(EpistemicStatus, "ALGORITHM"))
        # Y su valor es el string esperado (coherente con la
        # convención del enum: lowercase del nombre).
        self.assertEqual(EpistemicStatus.ALGORITHM.value, "algorithm")
        # Y es UN MIEMBRO MÁS — los previos siguen ahí intactos.
        for name in ("AXIOM", "DEFINITION", "THEOREM", "HYPOTHESIS"):
            self.assertTrue(hasattr(EpistemicStatus, name))


# ---------------------------------------------------------------------
# 2. ALGORITHM sin properties["inputs"] (o "outputs") → validate error
# ---------------------------------------------------------------------

class AlgorithmWithoutInputsFailsValidateTest(unittest.TestCase):
    def _make_graph(self, properties: dict) -> KnowledgeGraph:
        g = KnowledgeGraph()
        g.add(KnowledgeNode(
            id="alg.test",
            statement="(test) algoritmo bajo prueba",
            status=EpistemicStatus.ALGORITHM,
            kind=NodeKind.RELATION,
            properties=properties,
        ))
        return g

    def test_missing_inputs_produces_error(self) -> None:
        g = self._make_graph(properties={"outputs": ["x"]})
        errors = g.validate()
        self.assertEqual(len(errors), 1)
        msg = errors[0]
        self.assertIn("alg.test", msg)
        self.assertIn("ALGORITHM", msg)
        self.assertIn("inputs", msg)

    def test_missing_outputs_produces_error(self) -> None:
        g = self._make_graph(properties={"inputs": ["a"]})
        errors = g.validate()
        self.assertEqual(len(errors), 1)
        self.assertIn("outputs", errors[0])

    def test_empty_inputs_list_produces_error(self) -> None:
        # Lista vacía cuenta como "no declarado" — la regla exige
        # lista NO vacía.
        g = self._make_graph(properties={"inputs": [], "outputs": ["x"]})
        errors = g.validate()
        self.assertEqual(len(errors), 1)
        self.assertIn("inputs", errors[0])

    def test_both_present_passes(self) -> None:
        g = self._make_graph(
            properties={"inputs": ["a"], "outputs": ["x"]}
        )
        # validate() sólo controla errores; no debe haber ninguno
        # por las reglas de ALGORITHM.
        self.assertEqual(g.validate(), [])


# ---------------------------------------------------------------------
# 3. ALGORITHM sin foundations → warning (no error)
# ---------------------------------------------------------------------

class AlgorithmWithoutFoundationsProducesWarningTest(unittest.TestCase):
    def setUp(self) -> None:
        self.graph = KnowledgeGraph()
        self.graph.add(KnowledgeNode(
            id="alg.autonomous",
            statement="(test) algoritmo autónomo sin foundations",
            status=EpistemicStatus.ALGORITHM,
            kind=NodeKind.RELATION,
            properties={"inputs": ["a"], "outputs": ["x"]},
        ))

    def test_validate_returns_no_error(self) -> None:
        # validate() (sólo errors) debe estar vacío — no es error.
        self.assertEqual(self.graph.validate(), [])

    def test_validate_with_warnings_emits_warning(self) -> None:
        errors, warnings = self.graph.validate_with_warnings()
        self.assertEqual(errors, [])
        self.assertEqual(len(warnings), 1)
        msg = warnings[0]
        self.assertIn("alg.autonomous", msg)
        self.assertIn("ALGORITHM", msg)
        self.assertIn("foundations", msg)

    def test_warning_disappears_when_foundations_declared(self) -> None:
        # Añadimos un axioma base y un algoritmo con foundations
        # apuntando a él. El warning desaparece.
        g = KnowledgeGraph()
        g.add(KnowledgeNode(
            id="ax.base",
            statement="(test) axioma raíz",
            status=EpistemicStatus.AXIOM,
            kind=NodeKind.RELATION,
        ))
        g.add(KnowledgeNode(
            id="alg.with_foundations",
            statement="(test)",
            status=EpistemicStatus.ALGORITHM,
            kind=NodeKind.RELATION,
            foundations=["ax.base"],
            properties={"inputs": ["a"], "outputs": ["x"]},
        ))
        errors, warnings = g.validate_with_warnings()
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])


# ---------------------------------------------------------------------
# 4. **Algoritmo:** produce nodo con status=ALGORITHM
# ---------------------------------------------------------------------

_DOC_ALGORITHM = """\
# Test

## 1.1 Búsqueda

**Algoritmo:**
**Id:** alg.simple
La búsqueda lineal recorre la colección hasta encontrar el valor.
**Entrada:** coleccion, valor
**Salida:** posicion
"""


class ParserExtractsAlgorithmNodeTest(unittest.TestCase):
    def setUp(self) -> None:
        structure = StructureExtractor().extract_text(_DOC_ALGORITHM)
        self.report = NodeExtractor().extract(structure)

    def test_parse_is_valid(self) -> None:
        self.assertTrue(self.report.is_valid)
        self.assertEqual(self.report.errors, [])

    def test_one_node_extracted(self) -> None:
        self.assertEqual(len(self.report.nodes_extracted), 1)

    def test_node_has_algorithm_status(self) -> None:
        node = self.report.nodes_extracted[0]
        self.assertEqual(node.node_id, "alg.simple")
        self.assertEqual(node.status, EpistemicStatus.ALGORITHM)


# ---------------------------------------------------------------------
# 5. **Entrada:** y **Salida:** rellenan inputs/outputs
# ---------------------------------------------------------------------

class ParserExtractsEntradaSalidaTest(unittest.TestCase):
    def setUp(self) -> None:
        structure = StructureExtractor().extract_text(_DOC_ALGORITHM)
        self.report = NodeExtractor().extract(structure)
        self.node = self.report.nodes_extracted[0]

    def test_inputs_top_level_field_filled(self) -> None:
        # **Entrada:** rellena el atributo top-level `inputs`
        # del ExtractedNode (sinónimo de **Inputs:**).
        self.assertEqual(self.node.inputs, ["coleccion", "valor"])

    def test_outputs_top_level_field_filled(self) -> None:
        self.assertEqual(self.node.outputs, ["posicion"])

    def test_extra_properties_inputs_outputs_for_algorithm(self) -> None:
        # P literal: para nodos ALGORITHM, el extractor también
        # rellena extra_properties con las mismas listas — eso
        # garantiza que el KnowledgeNode resultante tenga
        # properties['inputs'] y properties['outputs'] tras pasar
        # por el GraphBuilder, satisfaciendo el contrato del
        # validate() para ALGORITHM.
        self.assertEqual(
            self.node.extra_properties.get("inputs"),
            ["coleccion", "valor"],
        )
        self.assertEqual(
            self.node.extra_properties.get("outputs"),
            ["posicion"],
        )

    def test_inputs_synonym_works_for_non_algorithm_blocks(self) -> None:
        """**Entrada:** es sinónimo (S1) — funciona también en bloques
        no ALGORITHM cuando se quiera. Para no-ALGORITHM, NO se
        rellena extra_properties (eso es exclusivo del status
        ALGORITHM por la regla literal del enunciado)."""
        doc = """\
# Test
## 1.1
**Teorema:**
**Id:** thm.uses_entrada
Un teorema con entrada/salida en castellano.
**Procedimiento:** dummy
**Entrada:** a, b
**Salida:** c
**Depende de:** ax.x

**Axioma:**
**Id:** ax.x
Axioma base.
"""
        structure = StructureExtractor().extract_text(doc)
        report = NodeExtractor().extract(structure)
        thm = next(
            n for n in report.nodes_extracted
            if n.node_id == "thm.uses_entrada"
        )
        # Sinónimo funciona: inputs/outputs top-level rellenos.
        self.assertEqual(thm.inputs, ["a", "b"])
        self.assertEqual(thm.outputs, ["c"])
        # Pero extra_properties NO contiene inputs/outputs para
        # no-ALGORITHM — los I/O de un teorema son atributos
        # top-level, no metadata. (`surface_forms` se añade siempre
        # con default [] desde exp_17 — verificado abajo.)
        self.assertNotIn("inputs", thm.extra_properties)
        self.assertNotIn("outputs", thm.extra_properties)
        self.assertEqual(thm.extra_properties.get("surface_forms"), [])


if __name__ == "__main__":
    unittest.main()
