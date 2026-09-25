"""Integration test del flujo completo (exp_18).

Construye el especialista de algoritmos desde el documento enriquecido
y verifica:

  1. La factory parsea el documento, registra el especialista, y los
     5 nodos clave llevan `expression_template` en sus properties.
  2. `specialist.express(trace)` produce prosa que contiene las
     afirmaciones fundamentadas en cada paso de la traza, sin
     inventos ni omisiones.
  3. La correspondencia oración↔nodo es trazable: cada paso aporta
     una oración rendereada por la plantilla del nodo declarado en
     `step.node_id`.
  4. Mismo input → mismo output (reproducibilidad).

La traza se construye a mano en el test porque el flujo de
backward-chaining del GeometrySpecialist no incluye nodos
ALGORITHM/THEOREM directamente — el caso canónico de exp_18 es
verbalizar una traza que YA existe (sea producida por solve(), por
otro especialista, o construida explícitamente como aquí). Eso
mantiene la responsabilidad bien separada: el solver razona, el
renderer verbaliza.
"""
from __future__ import annotations

import unittest
from pathlib import Path

from experiment_01.specialist import ReasoningStep, ReasoningTrace
from experiment_03.inter_specialist_protocol import SpecialistRegistry
from experiment_06.specialist_factory import SpecialistFactory
from experiment_09.knowledge_graph import build_complexity_base_graph
from experiment_17.vocabulary import VocabularyRegistry


_DEMO_DOC = (
    Path(__file__).resolve().parent.parent
    / "data" / "algorithms_with_expression.md"
)


def _step(idx, node_id, inputs=None, outputs=None) -> ReasoningStep:
    return ReasoningStep(
        index=idx,
        node_id=node_id,
        node_statement="(no usado en render)",
        purpose="(no usado en render)",
        inputs=dict(inputs or {}),
        outputs=dict(outputs or {}),
    )


class IntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # Aislar registries para no interferir con otros tests.
        cls.vreg = VocabularyRegistry()
        cls.sreg = SpecialistRegistry()
        factory = SpecialistFactory(
            registry=cls.sreg,
            vocabulary_registry=cls.vreg,
        )
        cls.result = factory.from_document(
            _DEMO_DOC,
            specialist_name="alg_demo",
            base_graph=build_complexity_base_graph(),
        )
        cls.specialist = cls.result.adapter.specialist
        cls.graph = cls.result.build_report.graph

    # -- 1. Parser propaga la plantilla -----------------------------

    def test_specialist_registers_cleanly(self) -> None:
        self.assertTrue(self.result.registered, self.result.errors)

    def test_each_authored_node_has_expression_template(self) -> None:
        expected = {
            "def.grafo",
            "def.vertice",
            "def.adyacencia",
            "alg.greedy_coloring",
            "thm.greedy_coloring.complejidad",
        }
        for nid in expected:
            with self.subTest(nid=nid):
                self.assertTrue(self.graph.has(nid))
                node = self.graph.get(nid)
                template = (node.properties or {}).get("expression_template")
                self.assertIsInstance(template, str)
                self.assertGreater(len(template), 0)

    # -- 2. Verbalización de la derivación canónica ------------------

    def test_express_renders_canonical_derivation(self) -> None:
        """La traza atraviesa los 5 nodos clave en orden dependencial.
        El texto resultante debe contener fragmentos que provienen
        EXACTAMENTE de las plantillas declaradas — no de los
        statements ni de un LLM."""
        trace = ReasoningTrace(steps=[
            _step(1, "def.grafo"),
            _step(2, "def.vertice"),
            _step(3, "def.adyacencia"),
            _step(4, "alg.greedy_coloring", inputs={"grafo G": "G"}),
            _step(5, "thm.greedy_coloring.complejidad"),
        ])
        text = self.specialist.express(trace)

        # Fragmentos literales que vienen de las plantillas.
        for fragment in (
            "un grafo es una estructura de vértices",
            "los vértices son los puntos del grafo",
            "dos vértices son adyacentes",
            "para colorear G aplicamos el algoritmo greedy",
            "la complejidad del coloreo greedy es a lo sumo m³",
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, text)

    def test_each_sentence_maps_to_its_step_node(self) -> None:
        """La correspondencia oración↔nodo se preserva: rendereando
        cada paso por separado, su texto está contenido en el render
        completo. Esto satisface el criterio de auditabilidad: para
        cualquier afirmación de la prosa, hay un node_id que la
        fundamenta."""
        steps = [
            _step(1, "def.grafo"),
            _step(2, "def.vertice"),
            _step(3, "def.adyacencia"),
        ]
        trace = ReasoningTrace(steps=steps)
        full_text = self.specialist.express(trace)
        for s in steps:
            sentence = self.specialist.renderer.render_node(s.node_id)
            with self.subTest(node_id=s.node_id):
                self.assertIn(sentence, full_text)

    def test_express_is_reproducible(self) -> None:
        trace = ReasoningTrace(steps=[
            _step(1, "def.grafo"),
            _step(2, "alg.greedy_coloring", inputs={"grafo G": "G"}),
        ])
        a = self.specialist.express(trace)
        b = self.specialist.express(trace)
        self.assertEqual(a, b)

    def test_unbound_input_raises_explicit_error(self) -> None:
        # Sin libertad creativa: si la plantilla pide `{input.X}` y
        # el caller no lo provee, el render FALLA — no inventa.
        from experiment_18.expression import UnresolvedReferenceError
        trace = ReasoningTrace(steps=[_step(1, "alg.greedy_coloring")])
        with self.assertRaises(UnresolvedReferenceError):
            self.specialist.express(trace)


if __name__ == "__main__":
    unittest.main()
