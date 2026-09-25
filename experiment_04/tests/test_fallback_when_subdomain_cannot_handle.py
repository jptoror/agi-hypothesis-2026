"""Test: cuando el subdominio emergente NO puede resolver el problema
(p. ej. el target está fuera de sus outputs), el orchestrator cae
limpiamente al flujo inter-dominio original.

Esto verifica el 'fallback' de la política A: subdominios primero,
originales después.
"""
from __future__ import annotations

import unittest

from experiment_01.knowledge_graph import build_geometry_2d_graph
from experiment_01.specialist import DomainContext, Problem
from experiment_03.specialists.physics import build_physics_graph

from experiment_04.orchestrator import EmergentOrchestrator


def _p(pid: str, m: float, d: float) -> Problem:
    return Problem(
        statement=f"[{pid}]",
        target="Ec",
        context=DomainContext(kind="physics.object", known={"m": m, "d": d}),
        variable_bindings={"v": "l"},
        delegation_hints={"figure_kind": "square"},
    )


class FallbackWhenSubdomainCannotHandleTest(unittest.TestCase):
    def test_area_problem_falls_back_to_geometry_alone(self) -> None:
        orch = EmergentOrchestrator(
            source_graphs={
                "geometry": build_geometry_2d_graph(),
                "physics": build_physics_graph(),
            },
            min_pattern_count=3,
        )
        # Sintetizamos el subdominio 'geometry_physics' con 3 problemas.
        for i in (1, 2, 3):
            orch.solve(_p(f"P{i}", m=float(i), d=8.0),
                       initiating_domain="physics")
        self.assertIn("geometry_physics", orch.emergent_adapters)

        # Ahora un problema de geometría pura: area de cuadrado dado
        # el lado. El subdominio incluye thm.square.side_from_diagonal
        # pero NO thm.square.area_from_side (no fue ejercitado). Debe
        # caer al flujo inter-dominio donde Geometría lo resuelve.
        area_problem = Problem(
            statement="[AREA] área del cuadrado de lado 5",
            target="A",
            context=DomainContext(kind="square", known={"l": 5.0}),
        )
        report = orch.solve(area_problem, initiating_domain="geometry")

        self.assertTrue(report.success)
        self.assertAlmostEqual(report.value, 25.0, places=8)
        # La ruta NO debe ser el subdominio (A no está en sus outputs).
        self.assertEqual(report.route, "cross_domain")
        # Traza: se intentó el subdominio y se descartó.
        self.assertTrue(any(
            "intentando subdominio geometry_physics" in a or
            "subdominio geometry_physics no puede resolver" in a
            for a in report.attempts
        ))


if __name__ == "__main__":
    unittest.main()
