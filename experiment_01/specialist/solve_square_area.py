"""Resuelve el primer problema del experimento:
"¿Cuál es el área de un cuadrado cuya diagonal mide 8?"

Uso:
    python -m experiment_01.specialist.solve_square_area
"""
from __future__ import annotations

from ..knowledge_graph import build_geometry_2d_graph
from .problem import DomainContext, Problem
from .specialist import GeometrySpecialist


def main() -> None:
    graph = build_geometry_2d_graph()
    specialist = GeometrySpecialist(graph)

    problem = Problem(
        statement="¿Cuál es el área de un cuadrado cuya diagonal mide 8?",
        target="A",
        context=DomainContext(kind="square", known={"d": 8.0}),
    )

    result = specialist.solve(problem)
    print(result.render())


if __name__ == "__main__":
    main()
