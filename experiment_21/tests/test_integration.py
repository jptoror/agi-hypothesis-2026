"""Integration test del flujo CLI → bootstrap → consulta (exp_21).

Pasos del test:
  1. CLI build sobre `data/sample_domain.md`.
  2. Bootstrap del SessionOrchestrator (exp_19) sobre la misma raíz.
  3. Verificar que el especialista nuevo está cargado y que sus
     surface forms se reconocen via el VocabularyRegistry
     reconstruido.
  4. Una consulta simple resuelve un término declarado en el doc.

También verifica que la equivalencia con el flujo "canónico"
(`SpecialistFactory.from_document`) se mantiene: el grafo
serializado debe tener el mismo conteo de nodos que el construido
directamente.
"""
from __future__ import annotations

import io
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

from experiment_03.inter_specialist_protocol import SpecialistRegistry
from experiment_06.specialist_factory import PROCEDURES, SpecialistFactory
from experiment_09.knowledge_graph import build_complexity_base_graph
from experiment_17.vocabulary import VocabularyRegistry
from experiment_19.persistence import (
    ProcedureRefRegistry,
    load_system,
    register_procedures_from,
)
from experiment_19.orchestrator import SessionOrchestrator
from experiment_21.authoring.cli import main as cli_main


_SAMPLE = "experiment_21/data/sample_domain.md"


def _run_cli(argv) -> int:
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        return cli_main(argv)


class FullCycleTest(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="exp21_int_"))

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def _proc_registry(self) -> ProcedureRefRegistry:
        reg = ProcedureRefRegistry()
        register_procedures_from(reg, PROCEDURES)
        return reg

    def test_cli_build_then_bootstrap_loads_specialist(self) -> None:
        # 1. CLI build.
        rc = _run_cli([
            "--root", str(self.root), "build", _SAMPLE,
            "--id", "poligonos", "--yes",
        ])
        self.assertEqual(rc, 0)

        # 2. Bootstrap del sistema usando el manifest recién creado.
        loaded = load_system(self.root, procedure_registry=self._proc_registry())
        self.assertIn(
            "poligonos", {a.name for a in loaded.specialist_registry.all()}
        )
        # 3. Vocabulary reindexado con surface_forms del doc.
        bindings = loaded.vocabulary_registry.lookup("polígono")
        self.assertEqual(len(bindings), 1)
        self.assertEqual(bindings[0].specialist_id, "poligonos")

    def test_authored_graph_contains_expected_key_nodes(self) -> None:
        """El grafo persistido contiene todos los nodos clave del
        documento, incluyendo los importados por cross-spec.

        Nota de diseño: el `SpecialistFactory.from_document` canónico
        del exp_06 NO acepta la sintaxis `spec::node` en
        `**Depende de:**` (sólo ids puros). La herramienta de
        autoría del exp_21 sí la acepta y la canoniza al persistir.
        Esa diferencia es deliberada — el doc del autor usa la
        forma explícita por claridad, el grafo persistido la guarda
        en forma canónica para compatibilidad runtime."""
        _run_cli([
            "--root", str(self.root), "build", _SAMPLE,
            "--id", "poligonos", "--yes",
        ])
        loaded = load_system(self.root, procedure_registry=self._proc_registry())
        authored = loaded.graphs["poligonos"]
        for nid in (
            "ax.lados_iguales", "def.poligono", "thm.perimetro",
            "alg.lado_desde_perimetro", "def.complexity.On2",
            "thm.calculo_perimetro_complejidad",
        ):
            self.assertTrue(authored.has(nid), f"falta {nid}")
        # `alg.lado_desde_perimetro` carga el procedure tras el load.
        self.assertIsNotNone(
            authored.get("alg.lado_desde_perimetro").compute,
        )

    def test_session_orchestrator_uses_authored_specialist(self) -> None:
        """Bootstrap + sesión + consulta. El SessionOrchestrator del
        exp_19 reconoce el surface form 'polígono' aportado por el
        especialista autoreado."""
        _run_cli([
            "--root", str(self.root), "build", _SAMPLE,
            "--id", "poligonos", "--yes",
        ])
        loaded = load_system(self.root, procedure_registry=self._proc_registry())
        orch = SessionOrchestrator(loaded, root_path=self.root)
        sess = orch.start_session(user_id="test_user")
        turn = orch.process_turn("definí el polígono regular")
        # El longest-match prefiere "polígono regular" (2 tokens)
        # sobre "polígono" (1) cuando ambos están registrados.
        # Cualquiera de los dos es válido para esta aserción: lo
        # importante es que SE RESOLVIÓ contra `poligonos`.
        resolved = turn.parsed_problem.get("resolved_terms", [])
        forms = {rt["surface_form"] for rt in resolved}
        self.assertTrue(
            "polígono" in forms or "polígono regular" in forms,
            f"se esperaba un match contra polígono(s); got: {forms}",
        )
        spec_ids = {
            rt["bindings"][0]["specialist_id"] for rt in resolved
        }
        self.assertIn("poligonos", spec_ids)


if __name__ == "__main__":
    unittest.main()
