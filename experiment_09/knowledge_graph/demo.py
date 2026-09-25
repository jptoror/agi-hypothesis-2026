"""Inspección del grafo base de complejidad.

Uso:
    python -m experiment_09.knowledge_graph.demo
"""
from __future__ import annotations

from experiment_01.knowledge_graph import EpistemicStatus

from .complexity_base import build_complexity_base_graph


def main() -> None:
    g = build_complexity_base_graph()

    errors = g.validate()
    if errors:
        print("ERRORES DE INTEGRIDAD:")
        for e in errors:
            print(f"  - {e}")
        return

    print(f"Grafo de complejidad construido con {len(g)} nodos.\n")

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
            props = n.properties or {}
            if props:
                print(f"  properties: {props}")
            print()

    # Sanity numérica del teorema de comparación.
    thm = g.get("thm.complexity.comparison")
    print("=== EJECUCIÓN: O(1) vs O(n) ===")
    o1 = g.get("def.complexity.O1").properties["order"]
    on = g.get("def.complexity.On").properties["order"]
    result = thm.compute({"order_a": o1, "order_b": on})
    print(f"  compute(order_a={o1}, order_b={on}) → {result}")
    assert result == {"more_efficient": True}

    print()
    print("=== EJECUCIÓN: O(n²) vs O(log n) ===")
    on2 = g.get("def.complexity.On2").properties["order"]
    olog = g.get("def.complexity.Ologn").properties["order"]
    result = thm.compute({"order_a": on2, "order_b": olog})
    print(f"  compute(order_a={on2}, order_b={olog}) → {result}")
    assert result == {"more_efficient": False}

    print()
    print("validate() OK ✓")


if __name__ == "__main__":
    main()
