"""Tests del preview (exp_21)."""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from experiment_01.knowledge_graph import (
    EpistemicStatus,
    KnowledgeGraph,
    KnowledgeNode,
    NodeKind,
)
from experiment_09.knowledge_graph import build_complexity_base_graph
from experiment_17.vocabulary import VocabularyRegistry
from experiment_21.authoring import build_preview, validate_document


_SAMPLE = Path("experiment_21/data/sample_domain.md")


class SamplePreviewTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.known = {"_complexity_base": build_complexity_base_graph()}
        cls.preview = build_preview(
            _SAMPLE, proposed_specialist_id="poligonos",
            known_specialists=cls.known,
        )

    def test_specialist_id(self) -> None:
        self.assertEqual(self.preview.proposed_specialist_id, "poligonos")

    def test_node_count(self) -> None:
        # 1 axiom + 4 def + 2 thm + 1 alg = 8 nodos.
        self.assertEqual(self.preview.statistics.total_nodes, 8)
        self.assertEqual(
            self.preview.statistics.by_status,
            {"axiom": 1, "definition": 4, "theorem": 2, "algorithm": 1},
        )

    def test_cross_references_identified(self) -> None:
        refs = self.preview.cross_specialist_references
        self.assertEqual(len(refs), 1)
        ref = refs[0]
        self.assertEqual(ref.foundation_ref,
                         "_complexity_base::def.complexity.On2")
        self.assertEqual(ref.target_specialist, "_complexity_base")
        self.assertEqual(ref.target_node, "def.complexity.On2")

    def test_surface_forms_present(self) -> None:
        forms = {sf.form for sf in self.preview.surface_forms}
        self.assertIn("polígono", forms)
        self.assertIn("perímetro", forms)

    def test_expression_templates_listed(self) -> None:
        ids = {e.node_id for e in self.preview.expression_templates}
        self.assertIn("thm.perimetro", ids)
        self.assertIn("alg.lado_desde_perimetro", ids)

    def test_node_lines_present(self) -> None:
        # Cada NodePreview lleva la línea absoluta del **Id:**.
        for n in self.preview.nodes:
            self.assertGreater(n.line_in_document, 0)


class PreviewRequiresValidDocumentTest(unittest.TestCase):
    def test_invalid_document_raises(self) -> None:
        tmp = Path(tempfile.mkdtemp(prefix="exp21_pv_"))
        try:
            broken = tmp / "broken.md"
            broken.write_text(
                "## 1.1\n**Teorema:**\n**Id:** thm.x\nSin fund.\n",
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                build_preview(broken)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class ConflictingSurfaceFormsInPreviewTest(unittest.TestCase):
    def test_conflicts_listed_in_preview(self) -> None:
        tmp = Path(tempfile.mkdtemp(prefix="exp21_pv2_"))
        try:
            doc = tmp / "doc.md"
            doc.write_text(
                "# T\n## 1.1\n**Definición:**\n"
                "**Id:** def.x\n**Términos:** alfa\nLa x.\n",
                encoding="utf-8",
            )
            other = KnowledgeGraph()
            other.add(KnowledgeNode(
                id="other.alfa", statement="otro alfa",
                status=EpistemicStatus.DEFINITION, kind=NodeKind.CONCEPT,
                properties={"surface_forms": ["alfa"]},
            ))
            global_reg = VocabularyRegistry()
            global_reg.register("other_spec", other)

            pv = build_preview(
                doc, proposed_specialist_id="my_spec",
                global_registry=global_reg,
            )
            sf = next(s for s in pv.surface_forms if s.form == "alfa")
            self.assertIn("other_spec", sf.conflicts_with)
            self.assertEqual(pv.statistics.surface_forms_in_conflict, 1)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
