"""Tests del persister (exp_21)."""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from experiment_06.specialist_factory import PROCEDURES
from experiment_09.knowledge_graph import build_complexity_base_graph
from experiment_19.persistence import (
    ProcedureRefRegistry,
    load_system,
    register_procedures_from,
)
from experiment_21.authoring import (
    build_preview,
    list_specialists,
    persist_specialist,
    remove_specialist,
)


_SAMPLE = Path("experiment_21/data/sample_domain.md")


class PersistTest(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="exp21_persist_"))
        self.known = {
            "_complexity_base": build_complexity_base_graph(),
        }
        self.preview = build_preview(
            _SAMPLE, proposed_specialist_id="poligonos",
            known_specialists=self.known,
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def _proc_registry(self) -> ProcedureRefRegistry:
        reg = ProcedureRefRegistry()
        register_procedures_from(reg, PROCEDURES)
        return reg

    def test_persist_creates_expected_files(self) -> None:
        out = persist_specialist(
            _SAMPLE, self.preview, target_root=self.root,
            known_specialists=self.known,
        )
        self.assertTrue(out.graph_path.exists())
        self.assertTrue(out.document_path.exists())
        self.assertTrue((self.root / "manifest.json").exists())
        # manifest tiene la entry.
        entries = list_specialists(self.root)
        self.assertEqual([e.specialist_id for e in entries], ["poligonos"])

    def test_idempotent_with_overwrite(self) -> None:
        persist_specialist(
            _SAMPLE, self.preview, target_root=self.root,
            known_specialists=self.known,
        )
        graph_text_1 = (self.root / "graphs" / "poligonos.json").read_text()
        persist_specialist(
            _SAMPLE, self.preview, target_root=self.root,
            overwrite=True, known_specialists=self.known,
        )
        graph_text_2 = (self.root / "graphs" / "poligonos.json").read_text()
        self.assertEqual(graph_text_1, graph_text_2)

    def test_overwrite_false_blocks(self) -> None:
        persist_specialist(
            _SAMPLE, self.preview, target_root=self.root,
            known_specialists=self.known,
        )
        with self.assertRaises(FileExistsError):
            persist_specialist(
                _SAMPLE, self.preview, target_root=self.root,
                known_specialists=self.known,
            )

    def test_round_trip_with_load_system(self) -> None:
        out = persist_specialist(
            _SAMPLE, self.preview, target_root=self.root,
            known_specialists=self.known,
        )
        loaded = load_system(self.root, procedure_registry=self._proc_registry())
        self.assertEqual(
            sorted(loaded.graphs.keys()), ["poligonos"],
        )
        g = loaded.graphs["poligonos"]
        # Cross-spec import: el nodo def.complexity.On2 vino del base.
        self.assertTrue(g.has("def.complexity.On2"))
        # Procedure resuelta tras load.
        self.assertIsNotNone(
            g.get("alg.lado_desde_perimetro").compute,
        )
        # nodes_persisted reportado coincide con el grafo cargado.
        self.assertEqual(out.nodes_persisted, len(g))

    def test_remove_strips_manifest_and_files(self) -> None:
        persist_specialist(
            _SAMPLE, self.preview, target_root=self.root,
            known_specialists=self.known,
        )
        ok = remove_specialist(self.root, "poligonos")
        self.assertTrue(ok)
        self.assertEqual(list_specialists(self.root), [])
        self.assertFalse((self.root / "graphs" / "poligonos.json").exists())
        self.assertFalse((self.root / "sources" / "poligonos.md").exists())

    def test_remove_unknown_returns_false(self) -> None:
        # Manifest vacío.
        self.assertFalse(remove_specialist(self.root, "nope"))


if __name__ == "__main__":
    unittest.main()
