"""Inspección del grafo de Física.

Uso:
    python -m experiment_03.specialists.physics.knowledge_graph.demo
"""
from __future__ import annotations

from experiment_01.knowledge_graph import EpistemicStatus

from .physics_1d import build_physics_graph


def main() -> None:
    g = build_physics_graph()

    errors = g.validate()
    if errors:
        print("ERRORES DE INTEGRIDAD:")
        for e in errors:
            print(f"  - {e}")
        return

    print(f"Grafo de Física construido con {len(g)} nodos.\n")

    for status in (
        EpistemicStatus.AXIOM,
        EpistemicStatus.DEFINITION,
        EpistemicStatus.THEOREM,
    ):
        nodes = g.by_status(status)
        if not nodes:
            continue
        print(f"=== {status.value.upper()} ({len(nodes)}) ===")
        for n in nodes:
            print(n.describe())
            print()

    print("=== CIERRE TRANSITIVO de thm.kinetic_energy ===")
    for dep in g.transitive_foundations("thm.kinetic_energy"):
        print(f"  - {dep.id}: {dep.statement}")

    print("\n=== EJECUCIÓN NUMÉRICA: m=2, v=5.656854 ===")
    thm = g.get("thm.kinetic_energy")
    result = thm.compute({"m": 2.0, "v": 5.656854})
    print(f"  compute → {result}")


if __name__ == "__main__":
    main()
