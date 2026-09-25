"""Test del flujo de conflicto + clarificación (exp_17).

Dos especialistas declaran la misma forma de superficie ('set').
Sin hint del caller, el sistema NO adivina — emite
ClarificationRequest con la lista de candidatos. Con hint que
identifica al especialista, resuelve sin clarificación.

Esto reusa el mecanismo del exp_08 (ClarificationRequest) sin
introducir lógica nueva de resolución — el contrato es: el sistema
delega ambigüedad al caller, no la resuelve por mayoría ni
heurística.
"""
from __future__ import annotations

import unittest

from experiment_01.knowledge_graph import (
    EpistemicStatus,
    KnowledgeGraph,
    KnowledgeNode,
    NodeKind,
)
from experiment_07.specialist import LanguageSpecialist
from experiment_08.clarification import ClarificationRequest
from experiment_17.vocabulary import VocabularyRegistry


def _graph_with(node_id: str, surface_form: str) -> KnowledgeGraph:
    g = KnowledgeGraph()
    g.add(KnowledgeNode(
        id=node_id,
        statement=f"nodo {node_id}",
        status=EpistemicStatus.DEFINITION,
        kind=NodeKind.CONCEPT,
        properties={"surface_forms": [surface_form]},
    ))
    return g


class ConflictTest(unittest.TestCase):
    def setUp(self) -> None:
        self.vreg = VocabularyRegistry()
        self.vreg.register("cpp", _graph_with("def.cpp.set", "set"))
        self.vreg.register("math", _graph_with("def.math.set", "set"))
        self.ls = LanguageSpecialist(
            graph=KnowledgeGraph(),
            vocabulary_registry=self.vreg,
        )

    def test_conflict_without_hint_emits_clarification(self) -> None:
        res = self.ls.parse("set")
        # Sin resolución exitosa.
        self.assertEqual(res.resolved_terms, [])
        # Una ClarificationRequest con ambos candidatos.
        self.assertEqual(len(res.clarification_requests), 1)
        cr = res.clarification_requests[0]
        self.assertIsInstance(cr, ClarificationRequest)
        self.assertEqual(cr.missing_concept, "set")
        self.assertEqual(
            sorted(cr.options),
            ["cpp:def.cpp.set", "math:def.math.set"],
        )

    def test_conflict_with_matching_hint_resolves(self) -> None:
        res = self.ls.parse("set", domain_hint="cpp")
        # Resolución exitosa, sin clarificación.
        self.assertEqual(res.clarification_requests, [])
        self.assertEqual(len(res.resolved_terms), 1)
        rt = res.resolved_terms[0]
        # `bindings` mantiene los DOS candidatos para auditabilidad,
        # pero el step trace registra el elegido.
        self.assertEqual(len(rt.bindings), 2)
        chosen_step = next(
            s for s in res.steps
            if s.node_id == "def.cpp.set"
        )
        self.assertEqual(chosen_step.outputs["specialist_id"], "cpp")

    def test_hint_that_does_not_match_emits_clarification(self) -> None:
        res = self.ls.parse("set", domain_hint="phys")  # no existe
        self.assertEqual(res.resolved_terms, [])
        self.assertEqual(len(res.clarification_requests), 1)
        cr = res.clarification_requests[0]
        # El motivo debe mencionar el motivo (varios especialistas).
        self.assertIn("2 especialistas", cr.reason)
        # Y el contexto incluye el hint que no resolvió.
        self.assertEqual(cr.available_context["domain_hint"], "phys")

    def test_no_conflict_resolves_directly(self) -> None:
        # Una sola binding → no necesita hint, no emite clarificación.
        vreg = VocabularyRegistry()
        vreg.register("only", _graph_with("def.only", "alfa"))
        ls = LanguageSpecialist(
            graph=KnowledgeGraph(), vocabulary_registry=vreg,
        )
        res = ls.parse("alfa")
        self.assertEqual(len(res.resolved_terms), 1)
        self.assertEqual(res.clarification_requests, [])


if __name__ == "__main__":
    unittest.main()
