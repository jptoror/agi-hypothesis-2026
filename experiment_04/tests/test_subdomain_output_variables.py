"""Test: el subgrafo sintetizado declara las salidas ejecutables
correctas, incluyendo `Ec` (del teorema físico) y `v` (del binding
consolidado)."""
from __future__ import annotations

import unittest

from experiment_01.knowledge_graph import EpistemicStatus, build_geometry_2d_graph
from experiment_01.specialist import DomainContext, Problem
from experiment_03.specialists.physics import build_physics_graph

from experiment_04.orchestrator import EmergentOrchestrator


class SubdomainOutputVariablesTest(unittest.TestCase):
    def test_subgraph_outputs_include_ec_and_v(self) -> None:
        orch = EmergentOrchestrator(
            source_graphs={
                "geometry": build_geometry_2d_graph(),
                "physics": build_physics_graph(),
            },
            min_pattern_count=3,
        )
        for pid, m, d in [("P1", 2.0, 8.0), ("P2", 1.0, 10.0), ("P3", 3.0, 6.0)]:
            orch.solve(
                Problem(
                    statement=f"[{pid}]",
                    target="Ec",
                    context=DomainContext(
                        kind="physics.object", known={"m": m, "d": d}
                    ),
                    variable_bindings={"v": "l"},
                    delegation_hints={"figure_kind": "square"},
                ),
                initiating_domain="physics",
            )
        adapter = orch.emergent_adapters["geometry_physics"]

        self.assertIn("Ec", adapter.output_variables)
        self.assertIn("v", adapter.output_variables)
        self.assertIn("l", adapter.output_variables)

        # El binding está como DEFINITION.
        binding = adapter.graph.get("binding.v_equals_l")
        self.assertEqual(binding.status, EpistemicStatus.DEFINITION)
        self.assertEqual(binding.foundations, [])

        # El subgrafo es autocontenido.
        self.assertEqual(adapter.graph.validate(), [])


if __name__ == "__main__":
    unittest.main()
