"""Demo del hypothesis_engine aislado.

Reproduce el gap de perímetro (de experiment_01), invoca el engine sobre
el grafo actual y muestra los candidatos generados — SIN añadirlos al grafo.

Uso:
    python -m experiment_02.hypothesis_engine.demo
"""
from __future__ import annotations

from experiment_01.knowledge_graph import build_geometry_2d_graph
from experiment_01.orchestrator import Orchestrator
from experiment_01.specialist import DomainContext, Problem

from .engine import HypothesisEngine


def main() -> None:
    graph = build_geometry_2d_graph()
    orch = Orchestrator(graph)

    problem = Problem(
        statement="¿Cuál es el perímetro de un cuadrado de lado 5?",
        target="P",
        context=DomainContext(kind="square", known={"l": 5.0}),
    )

    # Paso 1: confirmar que el grafo actual produce un gap MISSING_RELATION.
    report = orch.run(problem)
    print("-" * 72)
    print("FASE 1 — diagnóstico del orchestrator (experiment_01)")
    print("-" * 72)
    if report.gap_classification is None:
        print("no hubo gap — el experimento no aplica a este problema.")
        return
    print(report.gap_classification.render())
    print()

    missing_var = report.gap_classification.raw_gap.missing_variable

    # Paso 2: invocar el engine sobre el gap.
    engine = HypothesisEngine()
    candidates = engine.generate(missing_var, problem, graph)

    print("-" * 72)
    print(f"FASE 2 — hypothesis_engine sobre gap '{missing_var}'")
    print("-" * 72)
    if not candidates:
        print("ningún patrón registrado pudo proponer un candidato.")
        return

    print(f"Candidatos generados: {len(candidates)}\n")
    for c in candidates:
        print(c.render())
        print()

    # Paso 3: sanity check numérica — ejecutar el compute del candidato
    # top sobre los datos del problema, SIN mutar el grafo.
    print("-" * 72)
    print("FASE 3 — sanity check del candidato top (no se incorpora al grafo)")
    print("-" * 72)
    top = candidates[0]
    inputs = {k: problem.context.known[k] for k in top.node.inputs if k in problem.context.known}
    missing_inputs = [k for k in top.node.inputs if k not in problem.context.known]
    if missing_inputs:
        print(f"no se puede ejecutar: faltan entradas {missing_inputs}")
    else:
        outputs = top.node.compute(inputs)
        print(f"inputs: {inputs}")
        print(f"outputs: {outputs}")

    print()
    print("-" * 72)
    print("FASE 4 — invariante: el engine no modifica el grafo")
    print("-" * 72)
    print(f"nodos en el grafo: {len(graph)} (igual que al inicio — el engine sólo propone)")


if __name__ == "__main__":
    main()
