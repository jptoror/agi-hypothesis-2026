"""Test del CrossSpecialistRenderer (exp_18).

Construye dos grafos pequeños — uno "geometría" y otro "física" —
con plantillas distintas. Una traza atraviesa los dos especialistas
mediante `delegated_trace` (mismo mecanismo del exp_03/04). El
renderer cruzado debe:

  - particionar la traza por especialista,
  - delegar cada segmento al renderer correspondiente,
  - concatenar con un conector de transición agnóstico al dominio.

Eso satisface el criterio: "prosa con voces distintas por
segmento, cada segmento anclado a su grafo".

El orquestador NO aporta conocimiento de dominio — sólo etiqueta
qué especialista resuelve cada delegación (atributo `delegated_to`
en el step) y declara el conector de transición.
"""
from __future__ import annotations

import unittest

from experiment_01.knowledge_graph import (
    EpistemicStatus,
    KnowledgeGraph,
    KnowledgeNode,
    NodeKind,
)
from experiment_01.specialist import ReasoningStep, ReasoningTrace
from experiment_18.expression import (
    CrossSpecialistRenderer,
    ExpressionRenderer,
)


def _node(node_id, statement, template):
    return KnowledgeNode(
        id=node_id,
        statement=statement,
        status=EpistemicStatus.DEFINITION,
        kind=NodeKind.CONCEPT,
        properties={"expression_template": template},
    )


def _graph(*nodes):
    g = KnowledgeGraph()
    for n in nodes:
        g.add(n)
    return g


def _step(idx, node_id, *, delegated=None, delegated_to=None):
    s = ReasoningStep(
        index=idx,
        node_id=node_id,
        node_statement="(no usado)",
        purpose="(no usado)",
        delegated_trace=delegated,
    )
    if delegated_to is not None:
        # Atributo añadido por convención del orquestador: indica al
        # CrossSpecialistRenderer cuál renderer aplicar a la subtraza.
        s.delegated_to = delegated_to
    return s


class CrossSpecialistRendererTest(unittest.TestCase):
    def setUp(self) -> None:
        self.geom_graph = _graph(
            _node("def.lado", "el lado",
                  template="el lado del cuadrado mide {self.name}"),
            _node("def.diagonal", "la diagonal",
                  template="la diagonal es la línea entre vértices opuestos"),
        )
        self.phys_graph = _graph(
            _node("def.energia", "energía",
                  template="la energía cinética es ½ m v²"),
            _node("def.masa", "masa",
                  template="la masa es una propiedad inercial"),
        )
        self.r_geom = ExpressionRenderer(self.geom_graph)
        self.r_phys = ExpressionRenderer(self.phys_graph)

    def test_segment_is_routed_to_correct_renderer(self) -> None:
        # Traza: paso 1 (geom) → paso 2 delega a physics → paso 3 (geom).
        sub = ReasoningTrace(steps=[
            _step(1, "def.energia"),
            _step(2, "def.masa"),
        ])
        trace = ReasoningTrace(steps=[
            _step(1, "def.lado"),
            _step(2, "def.diagonal", delegated=sub, delegated_to="physics"),
        ])
        cross = CrossSpecialistRenderer(
            renderers={"geometry": self.r_geom, "physics": self.r_phys},
            default_specialist="geometry",
            transition_connector=". Por su parte, ",
        )
        text = cross.render(trace)

        # La voz geom aparece (def.lado).
        self.assertIn("el lado del cuadrado", text)
        # La voz física aparece (def.energia + def.masa).
        self.assertIn("la energía cinética", text)
        self.assertIn("la masa es una propiedad inercial", text)
        # El conector de transición separa los segmentos.
        self.assertIn(". Por su parte, ", text)

    def test_unknown_specialist_raises(self) -> None:
        sub = ReasoningTrace(steps=[_step(1, "def.energia")])
        trace = ReasoningTrace(steps=[
            _step(1, "def.lado"),
            _step(2, "def.diagonal", delegated=sub, delegated_to="cosmos"),
        ])
        cross = CrossSpecialistRenderer(
            renderers={"geometry": self.r_geom, "physics": self.r_phys},
            default_specialist="geometry",
        )
        with self.assertRaises(KeyError):
            cross.render(trace)

    def test_default_specialist_is_required_in_renderers(self) -> None:
        with self.assertRaises(ValueError):
            CrossSpecialistRenderer(
                renderers={"geom": self.r_geom},
                default_specialist="phys",  # no está
            )

    def test_only_default_specialist_renders_consecutively(self) -> None:
        # Sin delegaciones, el render cruzado equivale al render
        # del especialista por defecto.
        trace = ReasoningTrace(steps=[
            _step(1, "def.lado"),
            _step(2, "def.diagonal"),
        ])
        cross = CrossSpecialistRenderer(
            renderers={"geometry": self.r_geom, "physics": self.r_phys},
            default_specialist="geometry",
        )
        cross_text = cross.render(trace)
        baseline = self.r_geom.render_trace(trace)
        self.assertEqual(cross_text, baseline)

    def test_segments_keep_internal_connectors(self) -> None:
        # Dentro de un segmento, el especialista usa SUS conectores
        # rotativos. El conector de transición sólo aparece entre
        # segmentos de distinto especialista.
        sub = ReasoningTrace(steps=[
            _step(1, "def.energia"),
            _step(2, "def.masa"),
        ])
        trace = ReasoningTrace(steps=[
            _step(1, "def.lado"),
            _step(2, "def.diagonal", delegated=sub, delegated_to="physics"),
        ])
        cross = CrossSpecialistRenderer(
            renderers={"geometry": self.r_geom, "physics": self.r_phys},
            default_specialist="geometry",
            transition_connector=" || ",
        )
        text = cross.render(trace)
        # Estructura esperada:
        #   <geom: def.lado> || <physics: def.energia +
        #     conector_default + def.masa>
        # El conector " Luego, " (default del exp_18) debe aparecer
        # entre los dos pasos de física.
        self.assertIn(" Luego, ", text)
        # Y el conector de transición separa los grupos.
        self.assertIn(" || ", text)


if __name__ == "__main__":
    unittest.main()
