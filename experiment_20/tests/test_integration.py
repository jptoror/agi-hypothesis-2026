"""Integration test del flujo completo de exp_20.

Escenario:

  T1. "definamos G como un grafo con vértices {1,2,3,4} y aristas
       {(1,2),(2,3),(3,4),(4,1)}"
  T2. "llamemos H a G sin el vértice 4"
  --- SHUTDOWN + RESTART ---
  T3. "cuál es el coloreado voraz de H"

Aserciones:
  - conv:def.G y conv:def.H se crean con foundations correctas y
    surface_forms heredadas estructuralmente.
  - session_registry se reconstruye tras restart desde el
    conversation_graph persistido.
  - T3 resuelve "H" via session_registry y "coloreado voraz" via
    el global_registry — local gana, global aporta lo que falta.

Nota: el spec menciona "sea G un grafo con vértices..." pero el
patrón `def_pat.sea_igual` exige `=` o `igual a`. Usamos
`definamos G como ...` (patrón `def_pat.definamos`) que sí está
declarado, sin extender silenciosamente los patrones.
"""
from __future__ import annotations

import gc
import shutil
import tempfile
import unittest
from pathlib import Path

from experiment_03.inter_specialist_protocol import SpecialistRegistry
from experiment_06.specialist_factory import PROCEDURES, SpecialistFactory
from experiment_09.knowledge_graph import build_complexity_base_graph
from experiment_17.vocabulary import VocabularyRegistry
from experiment_19.persistence import (
    ProcedureRefRegistry,
    load_system,
    register_procedures_from,
    save_system,
)
from experiment_20.orchestrator import EpistemicSessionOrchestrator


class FullCycleTest(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="exp20_int_"))
        # Bootstrap: 2 especialistas (alg_terms con vocabulario,
        # alg_expr con plantillas).
        vreg = VocabularyRegistry()
        sreg = SpecialistRegistry()
        factory = SpecialistFactory(
            registry=sreg, vocabulary_registry=vreg,
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
        save_system(sreg, self.root, source_documents={
            "alg_terms": "experiment_17/data/demo_algorithms.md",
            "alg_expr":  "experiment_18/data/algorithms_with_expression.md",
        })

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def _proc_registry(self) -> ProcedureRefRegistry:
        reg = ProcedureRefRegistry()
        register_procedures_from(reg, PROCEDURES)
        return reg

    def test_three_turn_cycle_with_restart(self) -> None:
        # ===== Fase 1: bootstrap + T1 + T2 =====
        loaded = load_system(self.root, procedure_registry=self._proc_registry())
        orch = EpistemicSessionOrchestrator(loaded, root_path=self.root)
        sess = orch.start_session(user_id="user_001")
        saved_id = sess.session_id

        t1 = orch.process_turn(
            "definamos G como un grafo con vértices 1,2,3,4 y "
            "aristas (1,2),(2,3),(3,4),(4,1)"
        )
        # T1 produjo un nodo conv:def.G en el conversation_graph.
        self.assertTrue(sess.conversation_graph.has("conv:def.G"))
        node_g = sess.conversation_graph.get("conv:def.G")
        sfs = (node_g.properties or {}).get("surface_forms", [])
        self.assertIn("G", sfs)
        self.assertIn("el grafo G", sfs)
        # Patrón usado quedó registrado.
        self.assertEqual(t1.parsed_problem.get("pattern_id"),
                         "def_pat.definamos")

        t2 = orch.process_turn("llamemos H a G sin el vértice 4")
        self.assertTrue(sess.conversation_graph.has("conv:def.H"))
        node_h = sess.conversation_graph.get("conv:def.H")
        # foundations locales: H depende de G (mismo conv graph).
        self.assertIn("conv:def.G", node_h.foundations)
        # Categoría heredada: el grafo H.
        h_sfs = (node_h.properties or {}).get("surface_forms", [])
        self.assertIn("H", h_sfs)
        self.assertIn("el grafo H", h_sfs)

        # ===== Fase 2: SHUTDOWN =====
        del orch, loaded, sess, t1, t2
        gc.collect()

        # ===== Fase 3: cold boot =====
        loaded2 = load_system(
            self.root, procedure_registry=self._proc_registry(),
        )
        orch2 = EpistemicSessionOrchestrator(loaded2, root_path=self.root)
        sess2 = orch2.resume_session(saved_id)
        self.assertTrue(sess2.conversation_graph.has("conv:def.H"))
        # session_registry reindexado automáticamente tras resume.
        bindings = sess2.session_registry.lookup("H")
        self.assertEqual(len(bindings), 1)
        self.assertEqual(bindings[0].node_id, "conv:def.H")

        # ===== Fase 4: T3 con "H" resolviendo a session graph =====
        t3 = orch2.process_turn("cuál es el coloreado voraz de H")
        resolved = {
            (rt["surface_form"], rt["bindings"][0]["specialist_id"])
            for rt in t3.parsed_problem.get("resolved_terms", [])
        }
        # "coloreado voraz" → global; "h" → session (post-restart).
        self.assertIn(("coloreado voraz", "alg_terms"), resolved)
        self.assertIn(("h", "session"), resolved)
        self.assertIsNotNone(t3.response_text)


if __name__ == "__main__":
    unittest.main()
