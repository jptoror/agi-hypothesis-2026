"""Benchmark comparativo antes/después de las optimizaciones del exp_12.

Mide en el MISMO RUN, sobre la MISMA MÁQUINA y CARGA, las tres
operaciones críticas del grafo:

  - find_relations_producing(variable)
  - backward chaining completo (specialist.solve)
  - transitive_foundations(node_id)

Para los 6 tamaños del exp_11 (10, 50, 100, 500, 1000, 5000) sobre:
  - LegacyKnowledgeGraph (snapshot pre-optimización)
  - KnowledgeGraph (versión optimizada del exp_12)

`sys.setrecursionlimit` se BAJA EXPLÍCITAMENTE a 1000 (default de
Python) para verificar que la versión optimizada NO necesita el
workaround de PROB-08.

Uso:
    python -m experiment_12.optimization.run_comparison
"""
from __future__ import annotations

import statistics
import sys
import time
from dataclasses import dataclass

from experiment_01.knowledge_graph import KnowledgeGraph
from experiment_01.specialist import (
    DomainContext,
    GeometrySpecialist,
    Problem,
)

# Reutilizamos generador y constantes del exp_11.
from experiment_11.scale_test.synth_graph import (
    TARGET_VAR,
    build_synthetic_graph,
)

from .legacy_graph import LegacyKnowledgeGraph
from .synth_graph_legacy import build_synthetic_legacy_graph


_SIZES = [10, 50, 100, 500, 1000, 5000]


def _reps_for(n: int) -> int:
    if n <= 100:
        return 200
    if n <= 500:
        return 50
    return 20


def _bench(fn, repetitions: int) -> float:
    fn()  # warm-up no contado
    samples: list[float] = []
    for _ in range(repetitions):
        t0 = time.perf_counter()
        fn()
        t1 = time.perf_counter()
        samples.append((t1 - t0) * 1000.0)
    return statistics.median(samples)


@dataclass
class Row:
    n: int
    legacy_find: float
    legacy_chain: float
    legacy_foundations: float
    optimized_find: float
    optimized_chain: float
    optimized_foundations: float
    legacy_failed: bool = False    # True si Legacy reventó (RecursionError)


def _measure_one(graph, repetitions: int) -> tuple[float, float, float]:
    """Mide find/chain/foundations sobre un grafo concreto."""
    specialist = GeometrySpecialist(graph)
    problem = Problem(
        statement="(comp) chain test",
        target=TARGET_VAR,
        context=DomainContext(kind="synth", known={}),
    )
    target_id = "thm.synth.target"

    def _do_find():
        graph.find_relations_producing(TARGET_VAR)

    def _do_chain():
        specialist.solve(problem)

    def _do_foundations():
        graph.transitive_foundations(target_id)

    return (
        _bench(_do_find, repetitions),
        _bench(_do_chain, repetitions),
        _bench(_do_foundations, repetitions),
    )


def main() -> None:
    # Forzamos el límite de recursión al default de Python para
    # verificar que la versión optimizada NO necesita el workaround
    # del exp_11 (sys.setrecursionlimit(20000)).
    sys.setrecursionlimit(1000)

    print("=" * 90)
    print("EXPERIMENT 12 — comparación antes/después de las optimizaciones")
    print("=" * 90)
    print(f"sys.recursionlimit = {sys.getrecursionlimit()} (default — sin workaround)")
    print(f"medición: time.perf_counter, mediana de N repeticiones, 1 warm-up")
    print()

    rows: list[Row] = []

    for n in _SIZES:
        reps = _reps_for(n)
        print(f"  n={n:5d} reps={reps:3d}", end=" ", flush=True)

        # Legacy.
        legacy_failed = False
        try:
            g_legacy = build_synthetic_legacy_graph(n)
            l_find, l_chain, l_found = _measure_one(g_legacy, reps)
        except RecursionError:
            legacy_failed = True
            l_find = l_chain = l_found = float("nan")

        # Optimized.
        g_opt = build_synthetic_graph(n)
        o_find, o_chain, o_found = _measure_one(g_opt, reps)

        rows.append(Row(
            n=n,
            legacy_find=l_find, legacy_chain=l_chain, legacy_foundations=l_found,
            optimized_find=o_find, optimized_chain=o_chain, optimized_foundations=o_found,
            legacy_failed=legacy_failed,
        ))

        if legacy_failed:
            print(f"LEGACY=RecursionError  OPT chain={o_chain:9.4f} ms")
        else:
            print(
                f"LEGACY chain={l_chain:9.4f} ms  "
                f"OPT chain={o_chain:9.4f} ms  "
                f"speedup={l_chain / o_chain:6.1f}x"
            )

    # ---------- Tabla principal: chain antes/después ----------
    print()
    print("=" * 90)
    print("TABLA COMPARATIVA — chain (backward chaining completo)")
    print("=" * 90)
    print(
        f"{'nodos':>6} | {'chain_antes_ms':>16} | "
        f"{'chain_despues_ms':>17} | {'mejora':>10}"
    )
    print("-" * 90)
    for r in rows:
        if r.legacy_failed:
            antes = "RecursionError"
            mejora = "n/a"
        else:
            antes = f"{r.legacy_chain:.4f}"
            mejora = f"{r.legacy_chain / r.optimized_chain:.1f}x"
        print(
            f"{r.n:>6} | {antes:>16} | "
            f"{r.optimized_chain:>17.4f} | {mejora:>10}"
        )

    # ---------- Tabla auxiliar: las otras dos operaciones ----------
    print()
    print("=" * 90)
    print("TABLA AUXILIAR — find_relations_producing y transitive_foundations")
    print("=" * 90)
    print(
        f"{'nodos':>6} | "
        f"{'find_antes':>10} | {'find_desp':>10} | {'find_×':>7} | "
        f"{'found_antes':>11} | {'found_desp':>10} | {'found_×':>8}"
    )
    print("-" * 90)
    for r in rows:
        if r.legacy_failed:
            print(
                f"{r.n:>6} | "
                f"{'n/a':>10} | {r.optimized_find:>10.4f} | {'n/a':>7} | "
                f"{'n/a':>11} | {r.optimized_foundations:>10.4f} | {'n/a':>8}"
            )
        else:
            f_speed = (r.legacy_find / r.optimized_find) if r.optimized_find > 0 else float("inf")
            d_speed = (r.legacy_foundations / r.optimized_foundations) if r.optimized_foundations > 0 else float("inf")
            print(
                f"{r.n:>6} | "
                f"{r.legacy_find:>10.4f} | {r.optimized_find:>10.4f} | "
                f"{f_speed:>6.1f}x | "
                f"{r.legacy_foundations:>11.4f} | {r.optimized_foundations:>10.4f} | "
                f"{d_speed:>7.1f}x"
            )


if __name__ == "__main__":
    main()
