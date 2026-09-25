"""Tests del SystemManifest y save_system/load_system (exp_19)."""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from experiment_03.inter_specialist_protocol import SpecialistRegistry
from experiment_06.specialist_factory import PROCEDURES, SpecialistFactory
from experiment_09.knowledge_graph import build_complexity_base_graph
from experiment_17.vocabulary import VocabularyRegistry
from experiment_19.persistence import (
    ManifestError,
    ProcedureRefRegistry,
    SystemManifest,
    UnsupportedSchemaError,
    load_system,
    register_procedures_from,
    save_system,
)


class ManifestRoundTripTest(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="exp19_test_"))
        self.vreg = VocabularyRegistry()
        self.sreg = SpecialistRegistry()
        factory = SpecialistFactory(
            registry=self.sreg, vocabulary_registry=self.vreg,
        )
        factory.from_document(
            "experiment_17/data/demo_algorithms.md",
            specialist_name="alg_terms",
        )
        factory.from_document(
            "experiment_18/data/algorithms_with_expression.md",
            specialist_name="alg_expr",
            base_graph=build_complexity_base_graph(),
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def _new_proc_registry(self) -> ProcedureRefRegistry:
        reg = ProcedureRefRegistry()
        register_procedures_from(reg, PROCEDURES)
        return reg

    def test_save_creates_expected_files(self) -> None:
        save_system(self.sreg, self.root)
        self.assertTrue((self.root / "manifest.json").exists())
        self.assertTrue((self.root / "graphs" / "alg_terms.json").exists())
        self.assertTrue((self.root / "graphs" / "alg_expr.json").exists())
        # sessions dir creado vacío (lo usará el SessionOrchestrator).
        self.assertTrue((self.root / "sessions").is_dir())

    def test_load_restores_both_specialists(self) -> None:
        save_system(self.sreg, self.root)
        loaded = load_system(
            self.root, procedure_registry=self._new_proc_registry(),
        )
        names = {a.name for a in loaded.specialist_registry.all()}
        self.assertEqual(names, {"alg_terms", "alg_expr"})

    def test_load_reconstructs_vocabulary_registry(self) -> None:
        save_system(self.sreg, self.root)
        loaded = load_system(
            self.root, procedure_registry=self._new_proc_registry(),
        )
        forms = loaded.vocabulary_registry.surface_forms("alg_terms")
        self.assertIn("coloreado voraz", forms)
        self.assertIn("greedy coloring", forms)

    def test_save_with_source_documents_persists_paths(self) -> None:
        save_system(self.sreg, self.root, source_documents={
            "alg_terms": "experiment_17/data/demo_algorithms.md",
        })
        data = json.loads((self.root / "manifest.json").read_text())
        entry = next(
            e for e in data["specialists"]
            if e["specialist_id"] == "alg_terms"
        )
        self.assertEqual(
            entry["source_document"],
            "experiment_17/data/demo_algorithms.md",
        )

    def test_save_is_idempotent(self) -> None:
        m1 = save_system(self.sreg, self.root)
        # `last_modified` cambia pero los archivos quedan equivalentes.
        m2 = save_system(self.sreg, self.root)
        self.assertEqual(m1.created_at, m2.created_at)
        g1 = (self.root / "graphs" / "alg_terms.json").read_text()
        save_system(self.sreg, self.root)
        g2 = (self.root / "graphs" / "alg_terms.json").read_text()
        # El contenido del grafo no cambia entre saves idénticos.
        self.assertEqual(g1, g2)


class ErrorPathsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="exp19_test_err_"))

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def test_load_without_manifest(self) -> None:
        with self.assertRaises(ManifestError):
            load_system(self.root)

    def test_load_with_missing_graph_file(self) -> None:
        # Manifest válido pero graph_path apunta a archivo inexistente.
        (self.root / "graphs").mkdir()
        manifest = {
            "format_version": "1.0",
            "specialists": [{
                "specialist_id": "ghost",
                "specialist_class": "experiment_04.subdomain_specialist.SubdomainAdapter",
                "graph_path": "graphs/ghost.json",
                "source_document": None,
                "init_kwargs": {},
            }],
            "created_at": "2026-05-11T00:00:00+00:00",
            "last_modified": "2026-05-11T00:00:00+00:00",
        }
        (self.root / "manifest.json").write_text(json.dumps(manifest))
        with self.assertRaises(ManifestError):
            load_system(self.root)

    def test_load_with_unimportable_class(self) -> None:
        # Manifest declara una clase que no existe.
        (self.root / "graphs").mkdir()
        (self.root / "graphs" / "x.json").write_text(json.dumps({
            "format_version": "1.0",
            "node_count": 0,
            "nodes": [],
        }))
        manifest = {
            "format_version": "1.0",
            "specialists": [{
                "specialist_id": "x",
                "specialist_class": "non.existent.module.Ghost",
                "graph_path": "graphs/x.json",
                "source_document": None,
                "init_kwargs": {},
            }],
            "created_at": "2026-05-11T00:00:00+00:00",
            "last_modified": "2026-05-11T00:00:00+00:00",
        }
        (self.root / "manifest.json").write_text(json.dumps(manifest))
        with self.assertRaises(ManifestError):
            load_system(self.root)

    def test_load_with_unsupported_format_version(self) -> None:
        (self.root / "manifest.json").write_text(json.dumps({
            "format_version": "0.9",
            "specialists": [],
            "created_at": "", "last_modified": "",
        }))
        with self.assertRaises(UnsupportedSchemaError):
            load_system(self.root)


class AtomicWriteTest(unittest.TestCase):
    """El save escribe a `.tmp` + `os.replace`. Si el destino ya
    existe, el contenido nuevo lo reemplaza atómicamente: no hay
    estado intermedio observable."""

    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="exp19_atomic_"))
        self.vreg = VocabularyRegistry()
        self.sreg = SpecialistRegistry()
        factory = SpecialistFactory(
            registry=self.sreg, vocabulary_registry=self.vreg,
        )
        factory.from_document(
            "experiment_17/data/demo_algorithms.md",
            specialist_name="alg_terms",
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def test_overwrite_preserves_consistency(self) -> None:
        # Primer save.
        save_system(self.sreg, self.root)
        original_graph = (self.root / "graphs" / "alg_terms.json").read_text()
        # Segundo save sin cambios — debe quedar idéntico el grafo.
        save_system(self.sreg, self.root)
        again = (self.root / "graphs" / "alg_terms.json").read_text()
        self.assertEqual(original_graph, again)
        # No quedan archivos `.tmp` huérfanos.
        leftovers = [p for p in self.root.rglob(".*.tmp")]
        self.assertEqual(leftovers, [])


if __name__ == "__main__":
    unittest.main()
