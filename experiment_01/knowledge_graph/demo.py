"""Inspección manual del grafo — ayuda a auditar los nodos fundamentales.

Uso:
    python -m experiment_01.knowledge_graph.demo
"""
from __future__ import annotations

from .geometry_2d import build_geometry_2d_graph
from .node import EpistemicStatus


def main() -> None:
    g = build_geometry_2d_graph()

    errors = g.validate()
    if errors:
        print("ERRORES DE INTEGRIDAD:")
        for e in errors:
            print(f"  - {e}")
        return

    print(f"Grafo construido con {len(g)} nodos.\n")

    for status in (
        EpistemicStatus.AXIOM,
        EpistemicStatus.DEFINITION,
        EpistemicStatus.THEOREM,
        EpistemicStatus.HYPOTHESIS,
    ):
        nodes = g.by_status(status)
        if not nodes:
            continue
        print(f"=== {status.value.upper()} ({len(nodes)}) ===")
        for n in nodes:
            print(n.describe())
            print()

    print("\n=== CIERRE DE FUNDAMENTOS de thm.square.area_from_diagonal ===")
    for dep in g.transitive_foundations("thm.square.area_from_diagonal"):
        print(f"  - {dep.id}: {dep.statement}")


if __name__ == "__main__":
    main()
