"""Demo del CollaborationMonitor.

Resuelve dos problemas distintos que comparten forma estructural
(physics+geometry, binding v=l, hint figure_kind=square) y verifica
que el monitor:
  1. Registra una colaboración por problema.
  2. Las dos colaboraciones tienen la misma signature().
  3. Los nodos ejercitados se capturan correctamente.

Uso:
    python -m experiment_04.collaboration_monitor.demo
"""
from __future__ import annotations

from experiment_01.knowledge_graph import build_geometry_2d_graph
from experiment_01.specialist import DomainContext, Problem
from experiment_03.inter_specialist_protocol import SpecialistRegistry
from experiment_03.orchestrator import CrossDomainOrchestrator
from experiment_03.specialists.geometry import GeometryAdapter
from experiment_03.specialists.physics import PhysicsAdapter, build_physics_graph

from .monitor import CollaborationMonitor


def main() -> None:
    monitor = CollaborationMonitor()

    registry = SpecialistRegistry()
    registry.register(GeometryAdapter(build_geometry_2d_graph()))
    registry.register(PhysicsAdapter(build_physics_graph()))
    orch = CrossDomainOrchestrator(
        registry=registry, max_depth=5,
        on_solve_complete=lambda p, r: monitor.observe(p, r, problem_id=p.statement[:32]),
    )

    p1 = Problem(
        statement="Ec con m=2 y v=lado del cuadrado de diagonal 8",
        target="Ec",
        context=DomainContext(kind="physics.object", known={"m": 2.0, "d": 8.0}),
        variable_bindings={"v": "l"},
        delegation_hints={"figure_kind": "square"},
    )
    p2 = Problem(
        statement="Ec con m=1 y v=lado del cuadrado de diagonal 10",
        target="Ec",
        context=DomainContext(kind="physics.object", known={"m": 1.0, "d": 10.0}),
        variable_bindings={"v": "l"},
        delegation_hints={"figure_kind": "square"},
    )

    r1 = orch.solve(p1, initiating_domain="physics")
    r2 = orch.solve(p2, initiating_domain="physics")

    print("=" * 72)
    print("RESULTADOS DE LOS PROBLEMAS")
    print("=" * 72)
    print(f"P1: success={r1.solve_result.success} → Ec = {r1.solve_result.value}")
    print(f"P2: success={r2.solve_result.success} → Ec = {r2.solve_result.value}")
    print()

    print("=" * 72)
    print("RECORDS REGISTRADOS")
    print("=" * 72)
    for rec in monitor.all_records():
        print(rec.render())
        print(f"  signature: {rec.signature()}")
        print()

    print("=" * 72)
    print("AGRUPACIÓN POR SIGNATURE")
    print("=" * 72)
    groups = monitor.records_by_signature()
    print(f"Grupos distintos: {len(groups)}")
    for sig, recs in groups.items():
        print(f"  · {len(recs)} record(s) con signature compartida:")
        for r in recs:
            print(f"      - {r.problem_id}")

    print()
    print("=" * 72)
    print("COLABORACIONES POR PAR")
    print("=" * 72)
    pair_recs = monitor.records_for_pair("physics", "geometry")
    print(f"physics ↔ geometry: {len(pair_recs)} colaboración(es)")


if __name__ == "__main__":
    main()
