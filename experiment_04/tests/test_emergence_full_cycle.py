"""Test central del experimento 04: la narrativa de los 4 problemas.

Demuestra que tras 3 problemas con la misma forma estructural
(physics+geometry, binding v=l, figure_kind=square), el sistema
sintetiza el subdominio emergente 'geometry_physics' y resuelve un
cuarto problema SIN delegación ni bindings declarados.
"""
from __future__ import annotations

import unittest

from experiment_01.knowledge_graph import build_geometry_2d_graph
from experiment_01.specialist import DomainContext, Problem
from experiment_03.specialists.physics import build_physics_graph

from experiment_04.orchestrator import EmergentOrchestrator


def _p(pid: str, m: float, d: float) -> Problem:
    return Problem(
        statement=f"[{pid}] Ec con m={m}, cuadrado de diagonal {d}",
        target="Ec",
        context=DomainContext(kind="physics.object", known={"m": m, "d": d}),
        variable_bindings={"v": "l"},
        delegation_hints={"figure_kind": "square"},
    )


class EmergenceFullCycleTest(unittest.TestCase):
    def test_four_problem_narrative(self) -> None:
        orch = EmergentOrchestrator(
            source_graphs={
                "geometry": build_geometry_2d_graph(),
                "physics": build_physics_graph(),
            },
            min_pattern_count=3,
        )

        # P1, P2, P3: ruta cross_domain esperada.
        for pid, m, d, expected in [
            ("P1", 2.0, 8.0, 32.0),
            ("P2", 1.0, 10.0, 25.0),
            ("P3", 3.0, 6.0, 27.0),
        ]:
            report = orch.solve(_p(pid, m, d), initiating_domain="physics")
            self.assertTrue(report.success, f"{pid} debería resolverse")
            self.assertEqual(report.route, "cross_domain")
            self.assertAlmostEqual(report.value, expected, places=8)

        # Tras P3, el subdominio 'geometry_physics' debe existir.
        self.assertIn("geometry_physics", orch.emergent_adapters)
        adapter = orch.emergent_adapters["geometry_physics"]
        self.assertIn("Ec", adapter.output_variables)

        # P4: problema sin bindings declarados, figura = square.
        p4 = Problem(
            statement="[P4] Ec sin binding declarado",
            target="Ec",
            context=DomainContext(kind="square", known={"m": 4.0, "d": 6.0}),
            variable_bindings={},
            delegation_hints={},
        )
        report4 = orch.solve(p4, initiating_domain="physics")

        # Evidencia central.
        self.assertTrue(report4.success)
        self.assertEqual(report4.route, "subdomain:geometry_physics")
        self.assertAlmostEqual(report4.value, 36.0, places=8)

        # El problema NO declaró variable_bindings.
        self.assertEqual(p4.variable_bindings, {})
        # La traza del orchestrator muestra que se intentó el subdominio
        # antes que el fallback.
        self.assertTrue(any(
            "intentando subdominio geometry_physics" in a
            for a in report4.attempts
        ))
        self.assertTrue(any(
            "resuelto por subdominio geometry_physics" in a
            for a in report4.attempts
        ))


if __name__ == "__main__":
    unittest.main()
