"""Demo del PatternDetector.

Corre 3 problemas physics+geometry con la misma forma estructural
(deben constituir un patrón READY con umbral=3) y 1 problema con
hint distinto (que queda como EMERGING con count=1).

Uso:
    python -m experiment_04.pattern_detector.demo
"""
from __future__ import annotations

from experiment_01.knowledge_graph import build_geometry_2d_graph
from experiment_01.specialist import DomainContext, Problem
from experiment_03.inter_specialist_protocol import SpecialistRegistry
from experiment_03.orchestrator import CrossDomainOrchestrator
from experiment_03.specialists.geometry import GeometryAdapter
from experiment_03.specialists.physics import PhysicsAdapter, build_physics_graph
from experiment_04.collaboration_monitor import CollaborationMonitor

from .detector import PatternDetector


def _square_problem(pid: str, m: float, d: float) -> Problem:
    return Problem(
        statement=f"[{pid}] Ec con m={m} y v=lado del cuadrado de diagonal {d}",
        target="Ec",
        context=DomainContext(kind="physics.object", known={"m": m, "d": d}),
        variable_bindings={"v": "l"},
        delegation_hints={"figure_kind": "square"},
    )


def _square_from_side_problem(pid: str, m: float, l: float) -> Problem:
    return Problem(
        statement=f"[{pid}] Ec con m={m} y v=lado del cuadrado de lado {l}",
        target="Ec",
        context=DomainContext(kind="physics.object", known={"m": m, "l": l}),
        variable_bindings={"v": "l"},
        delegation_hints={"figure_kind": "square"},
    )


def main() -> None:
    monitor = CollaborationMonitor()

    registry = SpecialistRegistry()
    registry.register(GeometryAdapter(build_geometry_2d_graph()))
    registry.register(PhysicsAdapter(build_physics_graph()))
    orch = CrossDomainOrchestrator(
        registry=registry, max_depth=5,
        on_solve_complete=lambda p, r: monitor.observe(p, r, problem_id=p.statement.split("]")[0][1:]),
    )

    # Dos problemas con misma FORMA (misma signature): suficientes
    # para ilustrar EMERGING con umbral N=3 (count=2 < 3).
    emerging_problems = [
        _square_problem("E1", m=2.0, d=8.0),
        _square_problem("E2", m=1.0, d=10.0),
    ]
    for p in emerging_problems:
        orch.solve(p, initiating_domain="physics")

    print("=== Tras 2 problemas (umbral N=3) ===")
    print(PatternDetector(monitor=monitor, min_count=3).render())

    # Tercer problema de la misma familia: el patrón pasa a READY.
    orch.solve(_square_from_side_problem("R3", m=3.0, l=6.0),
               initiating_domain="physics")

    print("=== Tras 3 problemas (umbral N=3) ===")

    print(PatternDetector(monitor=monitor, min_count=3).render())


if __name__ == "__main__":
    main()
