"""Test: una vez sintetizado un subdominio, resolver problemas
adicionales con la misma signature NO genera una segunda síntesis.

El sistema recuerda qué ha sintetizado — es otra dimensión de
persistencia del aprendizaje.
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


class SynthesisIsIdempotentTest(unittest.TestCase):
    def test_further_problems_do_not_resynthesize(self) -> None:
        orch = EmergentOrchestrator(
            source_graphs={
                "geometry": build_geometry_2d_graph(),
                "physics": build_physics_graph(),
            },
            min_pattern_count=3,
        )
        # Tres problemas que activan la síntesis en el tercero.
        reports = [
            orch.solve(_p(f"P{i}", m=float(i), d=8.0),
                       initiating_domain="physics")
            for i in (1, 2, 3)
        ]
        self.assertIsNotNone(reports[2].synthesized,
                             "P3 debería haber disparado la síntesis")

        # Un cuarto problema con la misma signature. Debería:
        #   - intentar primero el subdominio y ganar;
        #   - NO emitir una nueva SynthesisResult.
        r4 = orch.solve(_p("P4", m=5.0, d=4.0), initiating_domain="physics")
        self.assertEqual(r4.route, "subdomain:geometry_physics")
        self.assertIsNone(r4.synthesized,
                          "no debería re-sintetizar el mismo subdominio")
        # Sólo un adapter emergente registrado.
        self.assertEqual(list(orch.emergent_adapters), ["geometry_physics"])


if __name__ == "__main__":
    unittest.main()
