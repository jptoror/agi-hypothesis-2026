"""Test de resolución de gaps por carga on-demand de especialistas
(exp_20).

Cuando un especialista nuevo se registra (en una sesión activa),
el orquestador puede notificar al estado epistémico vía
`notify_loaded_specialist(specialist_id, concepts)`. Los gaps
cuyos `concept` coincidan con alguno de los `concepts` quedan
marcados con `resolved_by_specialist`. El `resolved_at_turn` se
setea cuando el orquestador procese el siguiente turno.
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from experiment_03.inter_specialist_protocol import SpecialistRegistry
from experiment_06.specialist_factory import PROCEDURES
from experiment_17.vocabulary import VocabularyRegistry
from experiment_19.persistence import (
    ProcedureRefRegistry,
    load_system,
    register_procedures_from,
    save_system,
)
from experiment_20.epistemic import DeclaredGap
from experiment_20.orchestrator import EpistemicSessionOrchestrator


class GapResolutionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="exp20_gap_"))
        # Sistema vacío — sin especialistas. Eso fuerza al T1 a
        # NO resolver términos y registrar un gap.
        save_system(SpecialistRegistry(), self.root)

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def _orch(self) -> EpistemicSessionOrchestrator:
        preg = ProcedureRefRegistry()
        register_procedures_from(preg, PROCEDURES)
        loaded = load_system(self.root, procedure_registry=preg)
        return EpistemicSessionOrchestrator(loaded, root_path=self.root)

    def test_gap_recorded_when_no_term_resolves(self) -> None:
        orch = self._orch()
        sess = orch.start_session()
        orch.process_turn("qué es un grafo bipartito")
        gaps = sess.epistemic_state.gaps
        # T1 no resolvió ningún término → quedó un gap.
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0].concept, "qué es un grafo bipartito")
        self.assertIsNone(gaps[0].resolved_by_specialist)

    def test_loaded_specialist_resolves_previous_gap(self) -> None:
        orch = self._orch()
        sess = orch.start_session()
        orch.process_turn("qué es un grafo bipartito")
        # Simular carga on-demand de un especialista que cubre el
        # concepto. El concept de un gap es el input crudo, así
        # que pasamos exactamente esa cadena al set de concepts.
        resolved = orch.notify_loaded_specialist(
            specialist_id="bipartite_spec",
            concepts={"qué es un grafo bipartito"},
        )
        self.assertEqual(len(resolved), 1)
        self.assertEqual(resolved[0].resolved_by_specialist, "bipartite_spec")

    def test_unrelated_specialist_does_not_resolve(self) -> None:
        orch = self._orch()
        sess = orch.start_session()
        orch.process_turn("qué es un grafo bipartito")
        resolved = orch.notify_loaded_specialist(
            specialist_id="alg_terms",
            concepts={"coloreo greedy"},
        )
        self.assertEqual(resolved, [])
        self.assertIsNone(
            sess.epistemic_state.gaps[0].resolved_by_specialist,
        )


if __name__ == "__main__":
    unittest.main()
