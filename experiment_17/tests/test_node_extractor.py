"""Unit tests del cambio en NodeExtractor para `**Términos:**`
(exp_17).

Verifican que:
  - Las formas se extraen normalizadas (lowercase + colapso de
    espacios) y aterrizan en `properties["surface_forms"]` después
    de pasar por GraphBuilder.
  - Documentos sin el marcador siguen funcionando — la propiedad
    queda como `[]`, no faltante.
  - Casos límite (espacios, duplicados) se manejan deterministamente.

Decisión de diseño documentada: las duplicadas DENTRO de la misma
declaración del nodo se preservan tal cual aparecen en el documento;
el VocabularyRegistry deduplica internamente porque indexa por forma.
Mantener la lista textual aquí preserva auditabilidad.
"""
from __future__ import annotations

import unittest

from experiment_06.document_parser import (
    GraphBuilder,
    NodeExtractor,
    StructureExtractor,
)


def _parse(doc: str):
    structure = StructureExtractor().extract_text(doc)
    report = NodeExtractor().extract(structure)
    return report


def _build(doc: str):
    parse = _parse(doc)
    build = GraphBuilder().build(parse)
    return parse, build


class TerminosMarkerTest(unittest.TestCase):
    def test_marker_populates_surface_forms(self) -> None:
        doc = """\
# Test
## 1.1
**Definición:**
**Id:** def.alfa
**Términos:** alfa, beta, gamma
Definición simple con tres formas.
"""
        report = _parse(doc)
        self.assertTrue(report.is_valid)
        node = report.nodes_extracted[0]
        self.assertEqual(
            node.extra_properties["surface_forms"],
            ["alfa", "beta", "gamma"],
        )

    def test_marker_normalizes_whitespace_and_case(self) -> None:
        doc = """\
# Test
## 1.1
**Definición:**
**Id:** def.alfa
**Términos:**   Coloreado  Voraz  ,  Greedy   Coloring  ,GREEDY
Definición.
"""
        report = _parse(doc)
        node = report.nodes_extracted[0]
        self.assertEqual(
            node.extra_properties["surface_forms"],
            ["coloreado voraz", "greedy coloring", "greedy"],
        )

    def test_duplicates_inside_marker_are_preserved(self) -> None:
        # Decisión: la deduplicación es responsabilidad del registry
        # (que indexa por forma); el extractor preserva la lista
        # textual del documento para auditabilidad.
        doc = """\
# Test
## 1.1
**Definición:**
**Id:** def.alfa
**Términos:** alfa, alfa, beta
Definición.
"""
        report = _parse(doc)
        node = report.nodes_extracted[0]
        self.assertEqual(
            node.extra_properties["surface_forms"],
            ["alfa", "alfa", "beta"],
        )

    def test_multiple_marker_lines_are_concatenated(self) -> None:
        doc = """\
# Test
## 1.1
**Definición:**
**Id:** def.alfa
**Términos:** alfa, beta
**Términos:** gamma
Definición.
"""
        report = _parse(doc)
        node = report.nodes_extracted[0]
        self.assertEqual(
            node.extra_properties["surface_forms"],
            ["alfa", "beta", "gamma"],
        )

    def test_empty_marker_yields_empty_list(self) -> None:
        # `**Términos:**` solo (sin valor) → lista vacía. Mismo
        # resultado que ausencia del marcador, pero el caso debe
        # tolerarse sin error.
        doc = """\
# Test
## 1.1
**Definición:**
**Id:** def.alfa
**Términos:**
Definición.
"""
        report = _parse(doc)
        node = report.nodes_extracted[0]
        self.assertEqual(node.extra_properties["surface_forms"], [])


class BackwardCompatibilityTest(unittest.TestCase):
    def test_no_marker_yields_empty_list(self) -> None:
        # CRÍTICO: documentos existentes (los 142 tests anteriores)
        # NO tienen `**Términos:**`. El campo debe estar como []
        # no faltante — eso simplifica la lógica del registry.
        doc = """\
# Test
## 1.1
**Definición:**
**Id:** def.alfa
Definición sin marcador de términos.
"""
        report = _parse(doc)
        node = report.nodes_extracted[0]
        self.assertIn("surface_forms", node.extra_properties)
        self.assertEqual(node.extra_properties["surface_forms"], [])

    def test_property_propagates_to_knowledge_node(self) -> None:
        # Verificamos end-to-end: extracción → graph_builder →
        # KnowledgeNode.properties["surface_forms"].
        doc = """\
# Test
## 1.1
**Definición:**
**Id:** def.alfa
**Términos:** alfa, beta
Definición.
"""
        parse, build = _build(doc)
        self.assertTrue(build.is_valid)
        kn = build.graph.get("def.alfa")
        self.assertEqual(
            kn.properties.get("surface_forms"),
            ["alfa", "beta"],
        )

    def test_no_marker_propagates_empty_list_to_knowledge_node(self) -> None:
        doc = """\
# Test
## 1.1
**Definición:**
**Id:** def.alfa
Sin marcador.
"""
        parse, build = _build(doc)
        kn = build.graph.get("def.alfa")
        self.assertEqual(kn.properties.get("surface_forms"), [])


if __name__ == "__main__":
    unittest.main()
