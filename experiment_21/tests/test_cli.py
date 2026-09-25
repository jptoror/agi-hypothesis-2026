"""Tests del CLI agi-author (exp_21).

Cubrimos códigos de salida, output de cada subcomando y mensajes
amigables. Para capturar stdout/stderr usamos `redirect_stdout`/
`redirect_stderr` del stdlib — sin libs nuevas.
"""
from __future__ import annotations

import io
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from experiment_21.authoring.cli import main


_SAMPLE = "experiment_21/data/sample_domain.md"


def _run(argv) -> tuple[int, str, str]:
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = main(argv)
    return rc, out.getvalue(), err.getvalue()


class _RootTmpMixin:
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="exp21_cli_"))

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)


class ValidateCmdTest(_RootTmpMixin, unittest.TestCase):
    def test_valid_document_exits_zero(self) -> None:
        rc, stdout, _ = _run([
            "--root", str(self.root), "validate", _SAMPLE,
        ])
        self.assertEqual(rc, 0)
        self.assertIn("Sin issues", stdout)

    def test_invalid_document_exits_one(self) -> None:
        broken = self.root / "broken.md"
        broken.write_text(
            "## 1.1\n**Teorema:**\n**Id:** thm.x\nSin fund.\n",
            encoding="utf-8",
        )
        rc, stdout, _ = _run([
            "--root", str(self.root), "validate", str(broken),
        ])
        self.assertEqual(rc, 1)
        self.assertIn("THEOREM_MISSING_FOUNDATIONS", stdout)

    def test_missing_document_exits_three(self) -> None:
        rc, _, stderr = _run([
            "--root", str(self.root), "validate", "nonexistent.md",
        ])
        self.assertEqual(rc, 3)
        self.assertIn("no existe", stderr)


class PreviewCmdTest(_RootTmpMixin, unittest.TestCase):
    def test_preview_shows_stats(self) -> None:
        rc, stdout, _ = _run([
            "--root", str(self.root), "preview", _SAMPLE,
            "--id", "poligonos",
        ])
        self.assertEqual(rc, 0)
        self.assertIn("Especialista propuesto: poligonos", stdout)
        self.assertIn("Nodos: 8", stdout)
        self.assertIn("cross-specialist", stdout)


class BuildAndListTest(_RootTmpMixin, unittest.TestCase):
    def test_build_yes_persists(self) -> None:
        rc, stdout, _ = _run([
            "--root", str(self.root), "build", _SAMPLE,
            "--id", "poligonos", "--yes",
        ])
        self.assertEqual(rc, 0)
        self.assertIn("Especialista listo", stdout)
        # list muestra el nuevo especialista.
        rc, stdout, _ = _run([
            "--root", str(self.root), "list",
        ])
        self.assertEqual(rc, 0)
        self.assertIn("poligonos", stdout)

    def test_build_overwrite_required_for_second_call(self) -> None:
        _run([
            "--root", str(self.root), "build", _SAMPLE,
            "--id", "poligonos", "--yes",
        ])
        rc, _, stderr = _run([
            "--root", str(self.root), "build", _SAMPLE,
            "--id", "poligonos", "--yes",
        ])
        self.assertEqual(rc, 1)
        self.assertIn("ya existe", stderr)
        # Con --overwrite tiene éxito.
        rc, _, _ = _run([
            "--root", str(self.root), "build", _SAMPLE,
            "--id", "poligonos", "--yes", "--overwrite",
        ])
        self.assertEqual(rc, 0)


class ShowAndRemoveTest(_RootTmpMixin, unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        _run([
            "--root", str(self.root), "build", _SAMPLE,
            "--id", "poligonos", "--yes",
        ])

    def test_show_existing(self) -> None:
        rc, stdout, _ = _run([
            "--root", str(self.root), "show", "poligonos",
        ])
        self.assertEqual(rc, 0)
        self.assertIn("specialist_id:    poligonos", stdout)
        self.assertIn("node_count:", stdout)

    def test_show_unknown_exits_three(self) -> None:
        rc, _, stderr = _run([
            "--root", str(self.root), "show", "ghost",
        ])
        self.assertEqual(rc, 3)
        self.assertIn("no existe", stderr)

    def test_remove_with_yes(self) -> None:
        rc, stdout, _ = _run([
            "--root", str(self.root), "remove", "poligonos", "--yes",
        ])
        self.assertEqual(rc, 0)
        self.assertIn("removido: poligonos", stdout)


if __name__ == "__main__":
    unittest.main()
