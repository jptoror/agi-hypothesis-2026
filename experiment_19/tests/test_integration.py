"""Integration test del flujo completo de exp_19.

La aserción central del experimento: un proceso muere a mitad de
conversación, se levanta de cero, y aún resuelve correctamente una
referencia anafórica al turno previo. Esto demuestra:

  1. Persistencia perfecta de capa 1 (grafos serializados).
  2. Persistencia de capa 2 (manifest + vocabulary registry
     reconstruido).
  3. Persistencia de capa 3 (sesión + active_context + bindings).
  4. Trazabilidad: el trace del turno posterior al restart apunta
     a nodos cuya existencia depende del trabajo del turno previo.
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
from experiment_19.orchestrator import SessionOrchestrator
from experiment_19.persistence import (
    ProcedureRefRegistry,
    load_system,
    register_procedures_from,
    save_system,
)


class FullCycleTest(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="exp19_int_"))

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def _proc_registry(self) -> ProcedureRefRegistry:
        reg = ProcedureRefRegistry()
        register_procedures_from(reg, PROCEDURES)
        return reg

    def _bootstrap(self) -> None:
        """Crea dos especialistas y persiste el sistema. Dos
        especialistas son necesarios para ejercitar el flujo
        cross-graph: `alg_terms` aporta vocabulario (`coloreado
        voraz`, `grafo G`), `alg_expr` aporta plantillas
        `**Expresión:**` y el teorema de complejidad."""
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

    def test_full_session_survives_restart(self) -> None:
        self._bootstrap()

        # === Fase 1: carga, turno 1, persistencia automática. ===
        loaded = load_system(self.root, procedure_registry=self._proc_registry())
        orch = SessionOrchestrator(loaded, root_path=self.root)
        session = orch.start_session(user_id="user_001")
        session_id = session.session_id

        turn1 = orch.process_turn("calculá el coloreado voraz del grafo G")
        # El turno 1 resuelve "coloreado voraz" → alg.greedy_coloring
        # y "grafo g" → def.grafo. Ambos vía VocabularyRegistry.
        surface_forms = {
            rt["surface_form"]
            for rt in turn1.parsed_problem["resolved_terms"]
        }
        self.assertIn("coloreado voraz", surface_forms)
        self.assertIn("grafo g", surface_forms)
        # Y registra bindings cross-graph.
        bindings = session.active_context.active_bindings
        self.assertTrue(any(
            v.endswith("::alg.greedy_coloring") for v in bindings.values()
        ))

        # === Fase 2: shutdown simulado. ===
        del orch, loaded, session, turn1
        gc.collect()

        # === Fase 3: cold boot. ===
        loaded2 = load_system(
            self.root, procedure_registry=self._proc_registry(),
        )
        orch2 = SessionOrchestrator(loaded2, root_path=self.root)
        session2 = orch2.resume_session(session_id)
        # Estado preservado: 1 turno, bindings activos.
        self.assertEqual(len(session2.turns), 1)
        self.assertTrue(any(
            v.endswith("::alg.greedy_coloring")
            for v in session2.active_context.active_bindings.values()
        ))

        # === Fase 4: turno 2 con referencia anafórica. ===
        turn2 = orch2.process_turn("ahora calculá la complejidad")
        # Reconoció el patrón anafórico "(la|su) complejidad".
        categories = [a["category"] for a in turn2.parsed_problem["anaphoric"]]
        self.assertIn("complejidad", categories)
        # La respuesta proviene del thm.greedy_coloring.complejidad
        # del especialista alg_expr — atravesando bindings del turno
        # previo, que fueron cargados desde disco.
        self.assertIsNotNone(turn2.response_text)
        self.assertIn("complejidad", turn2.response_text.lower())
        # La traza apunta explícitamente al nodo del teorema.
        nodes_in_trace = {s["node_id"] for s in turn2.trace["steps"]}
        self.assertIn(
            "thm.greedy_coloring.complejidad", nodes_in_trace,
        )

    def test_session_persistence_is_per_turn(self) -> None:
        """Verifica el contrato: cada turno escribe a disco antes de
        retornar. Sin esperar end_session ni un commit explícito."""
        self._bootstrap()
        loaded = load_system(self.root, procedure_registry=self._proc_registry())
        orch = SessionOrchestrator(loaded, root_path=self.root)
        session = orch.start_session()
        orch.process_turn("calculá el coloreado voraz del grafo G")

        # Sin llamar a end_session: el archivo ya debe existir.
        path = self.root / "sessions" / f"{session.session_id}.json"
        self.assertTrue(path.exists())
        # Y debe contener al menos el turno procesado.
        loaded2 = load_system(self.root, procedure_registry=self._proc_registry())
        orch2 = SessionOrchestrator(loaded2, root_path=self.root)
        sess2 = orch2.resume_session(session.session_id)
        self.assertEqual(len(sess2.turns), 1)

    def test_vocabulary_registry_reconstructed_after_load(self) -> None:
        """Aserción explícita del criterio 4: el VocabularyRegistry
        no se persiste como tal — se reconstruye de los grafos. Tras
        load, las surface_forms de cada nodo están indexadas."""
        self._bootstrap()
        loaded = load_system(self.root, procedure_registry=self._proc_registry())
        forms = loaded.vocabulary_registry.lookup("coloreado voraz")
        self.assertEqual(len(forms), 1)
        self.assertEqual(forms[0].specialist_id, "alg_terms")
        self.assertEqual(forms[0].node_id, "alg.greedy_coloring")


if __name__ == "__main__":
    unittest.main()
