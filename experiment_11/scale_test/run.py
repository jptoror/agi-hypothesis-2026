"""Corre el scale test sobre los 6 tamaños del enunciado.

Política de repeticiones:
  - Tamaños pequeños (≤ 100): 200 repeticiones — los tiempos son
    sub-milisegundo y necesitan más muestras para reducir ruido.
  - Tamaños medios (500): 50 repeticiones.
  - Tamaños grandes (≥ 1000): 20 repeticiones — el backward chaining
    crece con N y queremos que el script termine en tiempo razonable.

Las repeticiones por tamaño se reportan en la tabla para auditoría.

Uso:
    python -m experiment_11.scale_test.run
"""
from __future__ import annotations

import sys
import time

from .measure import measure_graph
from .synth_graph import build_synthetic_graph

# La implementación actual de `KnowledgeGraph.transitive_foundations`
# es recursiva (graph.py:88-94). Para grafos con cadenas lineales de
# profundidad > 1000 (default sys.recursionlimit), Python lanza
# RecursionError. Subimos el límite para esta corrida; el fix
# definitivo (reescribir como iterativo) queda anotado como PROB-08.
sys.setrecursionlimit(20000)


_SIZES = [10, 50, 100, 500, 1000, 5000]


def _reps_for(n: int) -> int:
    if n <= 100:
        return 200
    if n <= 500:
        return 50
    return 20


def main() -> None:
    print("=" * 78)
    print("EXPERIMENT 11 — scale test")
    print("=" * 78)
    print(f"medición: time.perf_counter, mediana de N repeticiones, 1 warm-up")
    print()

    rows: list[tuple[int, int, float, float, float, float]] = []
    for n in _SIZES:
        t_build0 = time.perf_counter()
        graph = build_synthetic_graph(n)
        t_build_ms = (time.perf_counter() - t_build0) * 1000.0
        reps = _reps_for(n)
        m = measure_graph(graph, repetitions=reps)
        rows.append((
            n, reps, t_build_ms,
            m.find_time_ms, m.chain_time_ms, m.foundations_time_ms,
        ))
        print(
            f"  n={n:5d}  reps={reps:3d}  "
            f"build={t_build_ms:8.2f} ms  "
            f"find={m.find_time_ms:9.4f} ms  "
            f"chain={m.chain_time_ms:9.4f} ms  "
            f"foundations={m.foundations_time_ms:9.4f} ms"
        )

    print()
    print("=" * 78)
    print("TABLA DE RESULTADOS")
    print("=" * 78)
    print(
        f"{'nodos':>6} | {'find_time_ms':>13} | "
        f"{'chain_time_ms':>14} | {'foundations_time_ms':>19}"
    )
    print("-" * 78)
    for n, _reps, _build, find, chain, found in rows:
        print(
            f"{n:>6} | {find:>13.4f} | {chain:>14.4f} | {found:>19.4f}"
        )

    # Tasa de crecimiento aproximada entre extremos.
    if rows:
        first = rows[0]
        last = rows[-1]
        size_ratio = last[0] / first[0]
        print()
        print("=" * 78)
        print("CRECIMIENTO ENTRE EXTREMOS")
        print("=" * 78)
        print(
            f"  tamaño:        {first[0]:5d} → {last[0]:5d}  (×{size_ratio:.0f})"
        )
        for label, idx in (("find", 3), ("chain", 4), ("foundations", 5)):
            t0 = first[idx]
            t1 = last[idx]
            ratio = t1 / t0 if t0 > 0 else float("inf")
            print(
                f"  {label:<14}{t0:9.4f} ms → {t1:9.4f} ms  (×{ratio:.1f})"
            )


if __name__ == "__main__":
    main()
