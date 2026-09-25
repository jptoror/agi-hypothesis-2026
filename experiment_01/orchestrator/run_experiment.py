"""Ejecuta el experimento 01 completo sobre varios problemas.

Uso:
    python -m experiment_01.orchestrator.run_experiment
"""
from __future__ import annotations

from ..knowledge_graph import build_geometry_2d_graph
from ..specialist import DomainContext, Problem
from .orchestrator import Orchestrator


def main() -> None:
    graph = build_geometry_2d_graph()
    orch = Orchestrator(graph)

    problems = [
        # Caso 1: el problema del enunciado. Debe resolverlo.
        Problem(
            statement="¿Cuál es el área de un cuadrado cuya diagonal mide 8?",
            target="A",
            context=DomainContext(kind="square", known={"d": 8.0}),
        ),
        # Caso 2: el lado dado, área como objetivo. Debe resolverlo en un paso.
        Problem(
            statement="¿Cuál es el área de un cuadrado de lado 5?",
            target="A",
            context=DomainContext(kind="square", known={"l": 5.0}),
        ),
        # Caso 3: gap intencionado. Perímetro no está en el grafo.
        Problem(
            statement="¿Cuál es el perímetro de un cuadrado de lado 5?",
            target="P",
            context=DomainContext(kind="square", known={"l": 5.0}),
        ),
        # Caso 4: gap por input faltante. Pedimos área sin dar ni lado ni diagonal.
        Problem(
            statement="¿Cuál es el área de un cuadrado?",
            target="A",
            context=DomainContext(kind="square", known={}),
        ),
    ]

    for p in problems:
        report = orch.run(p)
        print(report.render())
        print("\n")


if __name__ == "__main__":
    main()
