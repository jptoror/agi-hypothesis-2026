"""Demo del EpistemicMapper con la pregunta canónica del experimento 05.

Inventaría los grafos de geometría, física y el subdominio emergente
geometry_physics (sintetizado en el exp_04) contra 8 semillas
declaradas explícitamente por el caller.

Uso:
    python -m experiment_05.epistemic_mapper.demo
"""
from __future__ import annotations

from experiment_01.knowledge_graph import build_geometry_2d_graph
from experiment_01.specialist import DomainContext, Problem
from experiment_03.specialists.physics import build_physics_graph
from experiment_04.orchestrator import EmergentOrchestrator

from .concept_query import ConceptQuery
from .mapper import EpistemicMapper


CANONICAL_QUESTION = (
    "¿Cómo construirías un sistema que genuinamente entienda lo que procesa?"
)

SEED_CONCEPTS = [
    "sistema",
    "entendimiento",
    "comprensión",
    "procesamiento",
    "genuino",
    "razonamiento",
    "conocimiento",
    "consciencia",
]


def _bootstrap_graphs() -> dict:
    """Construye geometry + physics y, sintetizando el subdominio
    emergente del exp_04, geometry_physics. El mapper tratará los tres
    como grafos de primera clase."""
    geometry_graph = build_geometry_2d_graph()
    physics_graph = build_physics_graph()
    orch = EmergentOrchestrator(
        source_graphs={"geometry": geometry_graph, "physics": physics_graph},
        min_pattern_count=3,
    )
    for i, (m, d) in enumerate([(2.0, 8.0), (1.0, 10.0), (3.0, 6.0)], start=1):
        orch.solve(
            Problem(
                statement=f"[EP5-bootstrap-{i}]",
                target="Ec",
                context=DomainContext(kind="physics.object", known={"m": m, "d": d}),
                variable_bindings={"v": "l"},
                delegation_hints={"figure_kind": "square"},
            ),
            initiating_domain="physics",
        )
    graphs = {"geometry": geometry_graph, "physics": physics_graph}
    for name, adapter in orch.emergent_adapters.items():
        graphs[name] = adapter.graph
    return graphs


def main() -> None:
    graphs = _bootstrap_graphs()
    mapper = EpistemicMapper(max_related=5)
    query = ConceptQuery.of(
        question_text=CANONICAL_QUESTION,
        seed_concepts=SEED_CONCEPTS,
    )

    print(query.render())
    print()
    print(f"grafos disponibles: {list(graphs)}")
    for name, g in graphs.items():
        print(f"  · {name}: {len(g)} nodos")
    print()

    inventory = mapper.map(query, graphs)
    print(inventory.render())


if __name__ == "__main__":
    main()
