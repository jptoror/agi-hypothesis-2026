"""Tests del validator (exp_21).

Cada código de validación con al menos un test. El validador NUNCA
lanza excepciones — todo problema se reporta como issue tipado.
"""
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
from experiment_17.vocabulary import VocabularyRegistry
from experiment_21.authoring import (
    KNOWN_MARKERS,
    VALIDATION_CODES,
    validate_document,
)


def _write_doc(tmpdir: Path, body: str) -> Path:
    p = tmpdir / "doc.md"
    p.write_text(body, encoding="utf-8")
    return p


class _TmpDirMixin:
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="exp21_val_"))

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)


class HappyPathTest(_TmpDirMixin, unittest.TestCase):
    def test_clean_document_has_no_errors(self) -> None:
        body = """\
# Test
## 1.1
**Axioma:**
**Id:** ax.x
La x es base.

**Definición:**
**Id:** def.y
**Términos:** y
La y depende de x.
**Depende de:** ax.x
"""
        p = _write_doc(self.tmp, body)
        r = validate_document(p)
        self.assertTrue(r.is_valid, [i.code for i in r.errors])
        self.assertEqual(r.nodes_extracted, 2)


class StructuralTest(_TmpDirMixin, unittest.TestCase):
    def test_missing_id(self) -> None:
        body = """\
# Test
## 1.1
**Definición:**
La definición sin id.
"""
        p = _write_doc(self.tmp, body)
        r = validate_document(p)
        self.assertFalse(r.is_valid)
        codes = [i.code for i in r.errors]
        self.assertIn("MISSING_ID", codes)

    def test_duplicate_id(self) -> None:
        body = """\
# Test
## 1.1
**Definición:**
**Id:** def.x
La x.
## 1.2
**Definición:**
**Id:** def.x
Otra x.
"""
        p = _write_doc(self.tmp, body)
        r = validate_document(p)
        codes = [i.code for i in r.errors]
        self.assertIn("DUPLICATE_ID", codes)
        # Ambas líneas reportadas.
        dup_lines = sorted(
            i.line for i in r.errors if i.code == "DUPLICATE_ID"
        )
        self.assertEqual(len(dup_lines), 2)

    def test_unknown_marker(self) -> None:
        body = """\
# Test
## 1.1
**Definición:**
**Id:** def.x
**Magia:** algo
La x.
"""
        p = _write_doc(self.tmp, body)
        r = validate_document(p)
        codes = [i.code for i in r.errors]
        self.assertIn("UNKNOWN_MARKER", codes)
        # El mensaje debe listar los marcadores válidos.
        msg = next(i.message for i in r.errors if i.code == "UNKNOWN_MARKER")
        self.assertIn("**Definición:**", msg)


class EpistemicTest(_TmpDirMixin, unittest.TestCase):
    def test_axiom_with_foundations(self) -> None:
        body = """\
# Test
## 1.1
**Definición:**
**Id:** def.base
La base.

**Axioma:**
**Id:** ax.bad
Tiene fundamentos espurios.
**Depende de:** def.base
"""
        p = _write_doc(self.tmp, body)
        r = validate_document(p)
        codes = [i.code for i in r.errors]
        self.assertIn("AXIOM_HAS_FOUNDATIONS", codes)

    def test_theorem_missing_foundations(self) -> None:
        body = """\
# Test
## 1.1
**Teorema:**
**Id:** thm.solo
Un teorema sin foundations.
"""
        p = _write_doc(self.tmp, body)
        r = validate_document(p)
        codes = [i.code for i in r.errors]
        self.assertIn("THEOREM_MISSING_FOUNDATIONS", codes)

    def test_algorithm_missing_io(self) -> None:
        body = """\
# Test
## 1.1
**Definición:**
**Id:** def.b
Base.

**Algoritmo:**
**Id:** alg.x
Algoritmo sin entradas/salidas.
**Depende de:** def.b
"""
        p = _write_doc(self.tmp, body)
        r = validate_document(p)
        codes = [i.code for i in r.errors]
        self.assertIn("ALGORITHM_MISSING_IO", codes)


class ReferentialTest(_TmpDirMixin, unittest.TestCase):
    def test_foundation_not_found(self) -> None:
        body = """\
# Test
## 1.1
**Axioma:**
**Id:** ax.base
Base.

**Teorema:**
**Id:** thm.x
Depende de algo inexistente.
**Depende de:** ax.base, ghost.node
"""
        p = _write_doc(self.tmp, body)
        r = validate_document(p)
        codes = [i.code for i in r.errors]
        self.assertIn("FOUNDATION_NOT_FOUND", codes)

    def test_expression_ref_not_found(self) -> None:
        body = """\
# Test
## 1.1
**Definición:**
**Id:** def.a
**Expresión:** referencia a {node.def.ghost}
La a.
"""
        p = _write_doc(self.tmp, body)
        r = validate_document(p)
        codes = [i.code for i in r.errors]
        self.assertIn("EXPRESSION_REF_NOT_FOUND", codes)

    def test_expression_parse_error(self) -> None:
        body = """\
# Test
## 1.1
**Definición:**
**Id:** def.a
**Expresión:** llave sin cerrar {self.name
La a.
"""
        p = _write_doc(self.tmp, body)
        r = validate_document(p)
        codes = [i.code for i in r.errors]
        self.assertIn("EXPRESSION_PARSE_ERROR", codes)


class VocabularyTest(_TmpDirMixin, unittest.TestCase):
    def test_empty_surface_form(self) -> None:
        body = """\
# Test
## 1.1
**Definición:**
**Id:** def.a
**Términos:** alfa, , beta
La a.
"""
        p = _write_doc(self.tmp, body)
        r = validate_document(p)
        codes = [i.code for i in r.errors]
        self.assertIn("EMPTY_SURFACE_FORM", codes)

    def test_duplicate_surface_form_in_document(self) -> None:
        body = """\
# Test
## 1.1
**Definición:**
**Id:** def.a
**Términos:** compartido
La a.

**Definición:**
**Id:** def.b
**Términos:** compartido
La b.
"""
        p = _write_doc(self.tmp, body)
        r = validate_document(p)
        codes = [i.code for i in r.errors]
        self.assertIn("DUPLICATE_SURFACE_FORM_IN_DOCUMENT", codes)

    def test_surface_form_conflict_with_registry_is_warning(self) -> None:
        body = """\
# Test
## 1.1
**Definición:**
**Id:** def.a
**Términos:** existing_term
La a.
"""
        p = _write_doc(self.tmp, body)
        # Construimos un registry global con el mismo término.
        ext_g = KnowledgeGraph()
        ext_g.add(KnowledgeNode(
            id="other.x", statement="otro",
            status=EpistemicStatus.DEFINITION, kind=NodeKind.CONCEPT,
            properties={"surface_forms": ["existing_term"]},
        ))
        global_reg = VocabularyRegistry()
        global_reg.register("other_spec", ext_g)

        r = validate_document(p, global_registry=global_reg)
        codes_warning = [i.code for i in r.warnings]
        self.assertIn("SURFACE_FORM_CONFLICT_WITH_REGISTRY", codes_warning)
        # No es error → is_valid sigue True.
        self.assertTrue(r.is_valid)


class CoherenceTest(_TmpDirMixin, unittest.TestCase):
    def test_empty_document(self) -> None:
        p = _write_doc(self.tmp, "# Vacío\n")
        r = validate_document(p)
        codes = [i.code for i in r.errors]
        self.assertIn("EMPTY_DOCUMENT", codes)

    def test_no_axioms_no_foundations_warning(self) -> None:
        body = """\
# Test
## 1.1
**Definición:**
**Id:** def.x
Solo una definición sin más.
"""
        p = _write_doc(self.tmp, body)
        r = validate_document(p)
        codes_w = [i.code for i in r.warnings]
        self.assertIn("NO_AXIOMS_NO_FOUNDATIONS", codes_w)


class MultipleIssuesTest(_TmpDirMixin, unittest.TestCase):
    def test_all_issues_reported_not_just_first(self) -> None:
        body = """\
# Test
## 1.1
**Axioma:**
**Id:** ax.bad
Foundations espurias.
**Depende de:** def.base

**Teorema:**
**Id:** thm.solo
Sin foundations.
"""
        p = _write_doc(self.tmp, body)
        r = validate_document(p)
        codes = [i.code for i in r.errors]
        self.assertIn("AXIOM_HAS_FOUNDATIONS", codes)
        self.assertIn("THEOREM_MISSING_FOUNDATIONS", codes)


class CodesCatalogTest(unittest.TestCase):
    def test_known_markers_listed(self) -> None:
        # Sanity: la lista pública incluye los marcadores que el
        # mensaje de UNKNOWN_MARKER cita.
        for needed in (
            "**Definición:**", "**Teorema:**", "**Axioma:**",
            "**Algoritmo:**", "**Términos:**", "**Expresión:**",
        ):
            self.assertIn(needed, KNOWN_MARKERS)

    def test_codes_catalog_present(self) -> None:
        for code in (
            "MISSING_ID", "DUPLICATE_ID", "MALFORMED_MARKER",
            "UNKNOWN_MARKER", "AXIOM_HAS_FOUNDATIONS",
            "THEOREM_MISSING_FOUNDATIONS", "ALGORITHM_MISSING_IO",
            "HYPOTHESIS_WITH_COMPLETE_FOUNDATIONS",
            "FOUNDATION_NOT_FOUND", "EXPRESSION_REF_NOT_FOUND",
            "EXPRESSION_PARSE_ERROR",
            "EMPTY_SURFACE_FORM", "DUPLICATE_SURFACE_FORM_IN_DOCUMENT",
            "SURFACE_FORM_CONFLICT_WITH_REGISTRY",
            "EMPTY_DOCUMENT", "NO_AXIOMS_NO_FOUNDATIONS",
        ):
            self.assertIn(code, VALIDATION_CODES)


if __name__ == "__main__":
    unittest.main()
