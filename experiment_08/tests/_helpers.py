"""Helpers compartidos por los tests del experimento 08.

Construye registries mock con especialistas que tienen 'coeficiente'
en distintos números de dominios — necesario para ejercitar los
caminos AMBIGUOUS y UNKNOWN, que con el bus realista (un solo
especialista de álgebra) NO se disparan.

Es honesto declarar que estos mocks son setup de test: simulan
escenarios donde el bus tiene varios o ningún especialista
relevante para el concepto bajo prueba.
"""
from __future__ import annotations

from experiment_01.knowledge_graph import (
    EpistemicStatus,
    KnowledgeGraph,
    KnowledgeNode,
    NodeKind,
)
from experiment_03.inter_specialist_protocol import (
    GapRequest,
    GapResponse,
    ResponseStatus,
    SpecialistAdapter,
    SpecialistRegistry,
)
from experiment_07.knowledge_graph import build_spanish_base_graph


class MockBusAdapter(SpecialistAdapter):
    """Adapter mínimo para tests — sólo necesita `name` y `graph`."""
    output_variables = frozenset()

    def __init__(self, name: str, graph: KnowledgeGraph) -> None:
        self.name = name
        self.graph = graph

    def handle(self, request: GapRequest, delegate=None) -> GapResponse:
        return GapResponse(
            request_id=request.request_id,
            responder=self.name,
            status=ResponseStatus.UNRESOLVABLE,
        )


def _graph_with_node(node_id: str) -> KnowledgeGraph:
    g = KnowledgeGraph()
    g.add(KnowledgeNode(
        id=node_id,
        statement=f"(test) {node_id}",
        status=EpistemicStatus.DEFINITION,
        kind=NodeKind.CONCEPT,
    ))
    return g


def registry_with_two_coefficient_specialists() -> SpecialistRegistry:
    """language + algebra (con def.coeficiente_algebraico) +
    fisica (con def.coeficiente_friccion). 'coeficiente' es
    AMBIGUO entre algebra y fisica.
    """
    reg = SpecialistRegistry()
    reg.register(MockBusAdapter("language", build_spanish_base_graph()))
    reg.register(MockBusAdapter("algebra",
                                _graph_with_node("def.coeficiente_algebraico")))
    reg.register(MockBusAdapter("fisica",
                                _graph_with_node("def.coeficiente_friccion")))
    return reg


def registry_with_no_coefficient() -> SpecialistRegistry:
    """language + dos especialistas que NO conocen 'coeficiente'.
    'coeficiente' es UNKNOWN — ningún dominio lo tiene.
    """
    reg = SpecialistRegistry()
    reg.register(MockBusAdapter("language", build_spanish_base_graph()))
    reg.register(MockBusAdapter("matematicas",
                                _graph_with_node("def.numero_real")))
    reg.register(MockBusAdapter("logica",
                                _graph_with_node("def.implicacion")))
    return reg
