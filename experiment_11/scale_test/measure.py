"""Mediciones de las 3 operaciones críticas del grafo.

Política de medición:
  - `time.perf_counter` (alta resolución, monotónico).
  - Cada operación se ejecuta `repetitions` veces (default 100) y se
    reporta el TIEMPO MEDIANO en milisegundos. La mediana es robusta
    a picos por GC o switch de proceso.
  - Antes de medir cada operación se hace 1 warm-up para que el
    primer hit no contamine. El warm-up no se cuenta.
  - Sólo se mide el tiempo de la operación bajo prueba — la
    construcción del grafo y del especialista quedan fuera.
"""
from __future__ import annotations

import statistics
import time
from dataclasses import dataclass

from experiment_01.knowledge_graph import KnowledgeGraph
from experiment_01.specialist import (
    DomainContext,
    GeometrySpecialist,
    Problem,
)

from .synth_graph import TARGET_VAR


@dataclass
class Measurement:
    n_nodes: int
    find_time_ms: float
    chain_time_ms: float
    foundations_time_ms: float
    repetitions: int


def _bench(fn, repetitions: int) -> float:
    """Devuelve la mediana en milisegundos de N ejecuciones de fn().
    Hace 1 warm-up no contado.
    """
    fn()  # warm-up
    samples: list[float] = []
    for _ in range(repetitions):
        t0 = time.perf_counter()
        fn()
        t1 = time.perf_counter()
        samples.append((t1 - t0) * 1000.0)
    return statistics.median(samples)


def measure_graph(
    graph: KnowledgeGraph,
    repetitions: int = 100,
) -> Measurement:
    """Mide las 3 operaciones críticas sobre el grafo dado."""
    # 1. find_relations_producing(TARGET_VAR) — busca el productor
    #    del objetivo. O(N) en la implementación actual (itera).
    def _do_find():
        graph.find_relations_producing(TARGET_VAR)

    # 2. backward chaining completo — pide TARGET_VAR a un especialista
    #    arrancando con un Problem vacío. El especialista buscará el
    #    productor, recurrirá a sus inputs (las variables de las
    #    últimas K defs), y para cada input encontrará un productor
    #    sin inputs (las defs son ejecutables sin inputs).
    specialist = GeometrySpecialist(graph)
    problem = Problem(
        statement="(synth) chain test",
        target=TARGET_VAR,
        context=DomainContext(kind="synth", known={}),
    )

    def _do_chain():
        specialist.solve(problem)

    # 3. transitive_foundations(thm.synth.target) — recorre
    #    recursivamente todos los fundamentos. Crece con la
    #    profundidad de la cadena (que es ~N por construcción del
    #    grafo sintético).
    target_id = "thm.synth.target"

    def _do_foundations():
        graph.transitive_foundations(target_id)

    return Measurement(
        n_nodes=len(graph),
        find_time_ms=_bench(_do_find, repetitions),
        chain_time_ms=_bench(_do_chain, repetitions),
        foundations_time_ms=_bench(_do_foundations, repetitions),
        repetitions=repetitions,
    )
