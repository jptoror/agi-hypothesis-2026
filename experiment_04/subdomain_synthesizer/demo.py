"""Demo del SubdomainSynthesizer.

Corre 3 problemas physics+geometry con la misma forma (misma
signature). El pattern_detector los promueve a READY. El sintetizador
construye el subgrafo emergente 'geometry_physics' y mostramos:

  - qué nodos vinieron de qué grafo fuente;
  - qué binding se consolidó como nodo permanente;
  - el grafo resultante es autocontenido (validate() == []).

Uso:
    python -m experiment_04.subdomain_synthesizer.demo
"""
from __future__ import annotations

from experiment_01.knowledge_graph import build_geometry_2d_graph
from experiment_01.specialist import DomainContext, Problem
from experiment_03.inter_specialist_protocol import SpecialistRegistry
from experiment_03.orchestrator import CrossDomainOrchestrator
from experiment_03.specialists.geometry import GeometryAdapter
from experiment_03.specialists.physics import PhysicsAdapter, build_physics_graph

from experiment_04.collaboration_monitor import CollaborationMonitor
from experiment_04.pattern_detector import PatternDetector

from .synthesizer import SubdomainSynthesizer


def _square_problem(pid: str, m: float, d: float) -> Problem:
    return Problem(
        statement=f"[{pid}] Ec con m={m} sobre cuadrado de diagonal {d}",
        target="Ec",
        context=DomainContext(kind="physics.object", known={"m": m, "d": d}),
        variable_bindings={"v": "l"},
        delegation_hints={"figure_kind": "square"},
    )


def main() -> None:
    geometry_graph = build_geometry_2d_graph()
    physics_graph = build_physics_graph()

    monitor = CollaborationMonitor()
    registry = SpecialistRegistry()
    registry.register(GeometryAdapter(geometry_graph))
    registry.register(PhysicsAdapter(physics_graph))
    orch = CrossDomainOrchestrator(
        registry=registry, max_depth=5,
        on_solve_complete=lambda p, r: monitor.observe(
            p, r, problem_id=p.statement.split("]")[0][1:]
        ),
    )

    # Tres problemas con misma forma estructural.
    for p in [
        _square_problem("P1", m=2.0, d=8.0),
        _square_problem("P2", m=1.0, d=10.0),
        _square_problem("P3", m=3.0, d=6.0),
    ]:
        orch.solve(p, initiating_domain="physics")

    # Detectar patrones listos.
    detector = PatternDetector(monitor=monitor, min_count=3)
    ready = detector.detect_ready()

    print("=" * 72)
    print("PATRONES DETECTADOS")
    print("=" * 72)
    for p in ready:
        print(p.render())
        print()

    if not ready:
        print("(sin patrones ready — nada que sintetizar)")
        return

    # Sintetizar el subdominio del primer patrón listo.
    synthesizer = SubdomainSynthesizer(source_graphs={
        "geometry": geometry_graph,
        "physics": physics_graph,
    })
    result = synthesizer.synthesize(ready[0])

    print("=" * 72)
    print("SÍNTESIS DEL SUBDOMINIO EMERGENTE")
    print("=" * 72)
    print(result.render())
    print()

    # Validar estructural del subgrafo.
    errors = result.subgraph.validate()
    print(f"validate() del subgrafo: {'OK' if not errors else errors}")
    print()

    # Mostrar cada nodo del subgrafo con su origen auditable.
    print("=" * 72)
    print("INVENTARIO DEL SUBGRAFO (nodos con procedencia)")
    print("=" * 72)
    for node in result.subgraph:
        origin: list[str] = []
        if node.id in result.binding_nodes:
            origin.append("BINDING consolidado")
        if node.id in result.nodes_from_initiator:
            origin.append(f"heredado de {ready[0].sample_record.initiator} (ejercitado)")
        if node.id in result.nodes_from_responder:
            origin.append(f"heredado de {ready[0].sample_record.responder} (ejercitado)")
        if not origin:
            origin.append("fundamento transitivo")
        print(f"  [{node.status.value:11}] {node.id}  ← {', '.join(origin)}")


if __name__ == "__main__":
    main()
