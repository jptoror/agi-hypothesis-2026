"""Integration test del flujo completo (exp_17).

Construye el especialista de algoritmos desde el documento demo,
verifica registro automático en VocabularyRegistry, parsea una
consulta en lenguaje natural y verifica que la surface form
'coloreado voraz' se resuelve a `alg.greedy_coloring` SIN trabajo
manual de propagación. Verifica además la trazabilidad
end-to-end: surface_form → documento origen → nodo declarante.
"""
from __future__ import annotations

import unittest
from pathlib import Path

from experiment_01.knowledge_graph import KnowledgeGraph
from experiment_03.inter_specialist_protocol import SpecialistRegistry
from experiment_06.specialist_factory import SpecialistFactory
from experiment_07.specialist import LanguageSpecialist
from experiment_17.vocabulary import VocabularyRegistry


_DEMO_DOC = (
    Path(__file__).resolve().parent.parent
    / "data" / "demo_algorithms.md"
)


class IntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # Inyectamos un VocabularyRegistry aislado — no contaminamos
        # el DEFAULT_REGISTRY que pueden usar otros tests.
        cls.vreg = VocabularyRegistry()
        cls.sreg = SpecialistRegistry()
        factory = SpecialistFactory(
            registry=cls.sreg,
            vocabulary_registry=cls.vreg,
        )
        cls.result = factory.from_document(
            _DEMO_DOC, specialist_name="algorithms_demo",
        )

    # -- 1. Especialista se registra y publica vocabulario ----------

    def test_specialist_registers_cleanly(self) -> None:
        self.assertTrue(self.result.registered, self.result.errors)
        self.assertIn("algorithms_demo", {a.name for a in self.sreg.all()})

    def test_vocabulary_propagated_automatically(self) -> None:
        # Sin trabajo manual: las 7 formas declaradas en el documento
        # están indexadas tras la registración.
        self.assertIn("algorithms_demo", self.vreg.specialists())
        forms = self.vreg.surface_forms("algorithms_demo")
        self.assertIn("coloreado voraz", forms)
        self.assertIn("algoritmo greedy de coloración", forms)
        self.assertIn("greedy coloring", forms)

    def test_each_form_resolves_to_expected_node(self) -> None:
        for form in (
            "coloreado voraz",
            "algoritmo greedy de coloración",
            "greedy coloring",
        ):
            with self.subTest(form=form):
                bindings = self.vreg.lookup(form)
                self.assertEqual(len(bindings), 1)
                self.assertEqual(bindings[0].node_id, "alg.greedy_coloring")
                self.assertEqual(bindings[0].specialist_id, "algorithms_demo")

    # -- 2. LanguageSpecialist consulta el registry ------------------

    def test_language_specialist_resolves_surface_form(self) -> None:
        ls = LanguageSpecialist(
            graph=KnowledgeGraph(),
            vocabulary_registry=self.vreg,
        )
        res = ls.parse("calculá el coloreado voraz del grafo G")
        # Span largo gana sobre tokens sueltos: 'coloreado voraz'
        # debe consumirse como uno solo, no como dos.
        forms = [rt.surface_form for rt in res.resolved_terms]
        self.assertIn("coloreado voraz", forms)
        # Y el grafo G (segunda forma de 2 tokens declarada para
        # def.grafo) debe resolver al nodo correcto.
        self.assertIn("grafo g", forms)
        # Sin clarificaciones — no hay conflicto.
        self.assertEqual(res.clarification_requests, [])

    def test_resolution_carries_provenance(self) -> None:
        """Trazabilidad surface_form → documento origen → nodo. La
        binding lleva el path del documento; el step lo expone."""
        ls = LanguageSpecialist(
            graph=KnowledgeGraph(),
            vocabulary_registry=self.vreg,
        )
        res = ls.parse("coloreado voraz")
        rt = next(r for r in res.resolved_terms
                  if r.surface_form == "coloreado voraz")
        b = rt.bindings[0]
        self.assertEqual(b.node_id, "alg.greedy_coloring")
        self.assertEqual(b.specialist_id, "algorithms_demo")
        self.assertIsNotNone(b.source_document)
        self.assertTrue(str(b.source_document).endswith("demo_algorithms.md"))
        # El step del lenguaje también registra la provenance.
        step = next(s for s in res.steps
                    if s.node_id == "alg.greedy_coloring")
        self.assertIn("source_document", step.outputs)
        self.assertEqual(
            step.outputs["specialist_id"], "algorithms_demo"
        )

    # -- 3. Routing al especialista ----------------------------------

    def test_resolved_term_identifies_target_specialist(self) -> None:
        """El orquestador no se ejercita aquí (cada exp tiene el
        suyo), pero la binding lleva `specialist_id` — único dato
        que el orquestador necesita para enrutar. Eso satisface el
        criterio: el sistema enruta a `algorithms_demo` SIN
        consultar al lenguaje sobre el dominio."""
        ls = LanguageSpecialist(
            graph=KnowledgeGraph(),
            vocabulary_registry=self.vreg,
        )
        res = ls.parse("greedy coloring")
        target = res.resolved_terms[0].bindings[0]
        self.assertEqual(target.specialist_id, "algorithms_demo")
        # El especialista existe en la SpecialistRegistry — el
        # orquestador puede recuperarlo por nombre.
        self.assertIn(target.specialist_id, {a.name for a in self.sreg.all()})

    # -- 4. Idempotencia del registro ------------------------------

    def test_re_registering_does_not_duplicate(self) -> None:
        # Reconstruir el especialista (hot-reload) NO debe duplicar
        # bindings — la segunda registración reemplaza.
        before = len(self.vreg)
        factory = SpecialistFactory(
            registry=SpecialistRegistry(),
            vocabulary_registry=self.vreg,
        )
        factory.from_document(_DEMO_DOC, specialist_name="algorithms_demo")
        after = len(self.vreg)
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
