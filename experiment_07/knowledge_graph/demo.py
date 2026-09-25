"""Inspección del grafo base del especialista de lenguaje español.

Uso:
    python -m experiment_07.knowledge_graph.demo
"""
from __future__ import annotations

from experiment_01.knowledge_graph import EpistemicStatus

from .spanish_base import build_spanish_base_graph


def main() -> None:
    g = build_spanish_base_graph()

    errors = g.validate()
    if errors:
        print("ERRORES DE INTEGRIDAD:")
        for e in errors:
            print(f"  - {e}")
        return

    print(f"Grafo lingüístico construido con {len(g)} nodos.\n")

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
            role = props.get("linguistic_role")
            if role:
                print(f"  rol lingüístico: {role}")
                strat = props.get("match_strategy")
                print(f"  estrategia: {strat}")
                if strat == "tokens":
                    print(f"  tokens: {props.get('tokens')}")
                elif strat == "pattern":
                    print(f"  pattern: {props.get('pattern')!r}")
                elif strat == "inference":
                    print(f"  requiere: {props.get('inference_requires')}")
                    print(f"  constraints: {props.get('inference_constraints')}")
                print(f"  produces: {props.get('produces')}")
            print()


if __name__ == "__main__":
    main()
