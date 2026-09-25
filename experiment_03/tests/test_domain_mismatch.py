"""Test: pedir una variable que ningún especialista registrado puede
producir resulta en un fallo limpio cuyo mensaje nombra la variable
faltante.

Fallar bien es tan importante como resolver bien: el sistema debe
delimitar exactamente qué no sabe.
"""
from __future__ import annotations

import unittest

from experiment_01.knowledge_graph import build_geometry_2d_graph
from experiment_01.specialist import DomainContext, Problem

from experiment_03.inter_specialist_protocol import (
    ResponseStatus,
    SpecialistRegistry,
)
from experiment_03.orchestrator import CrossDomainOrchestrator
from experiment_03.specialists.geometry import GeometryAdapter
from experiment_03.specialists.physics import PhysicsAdapter, build_physics_graph


class DomainMismatchTest(unittest.TestCase):
    def test_unknown_variable_yields_unresolvable_with_named_variable(self) -> None:
        registry = SpecialistRegistry()
        registry.register(GeometryAdapter(build_geometry_2d_graph()))
        registry.register(PhysicsAdapter(build_physics_graph()))
        orch = CrossDomainOrchestrator(registry=registry, max_depth=5)

        # 'Z' no aparece como output de ningún nodo en ningún grafo
        # registrado. Pero sí pedimos algo que dispara delegación: la
        # física necesita 'v' para Ec, y declaramos un binding de v→Z
        # para forzar al orchestrator a buscar a 'Z' por la registry.
        problem = Problem(
            statement="(test) pedir una variable que nadie produce",
            target="Ec",
            context=DomainContext(kind="physics.object", known={"m": 2.0}),
            variable_bindings={"v": "Z"},
        )
        result = orch.solve(problem, initiating_domain="physics")

        # No se resolvió.
        self.assertFalse(result.solve_result.success)
        self.assertIsNone(result.solve_result.value)

        # El gap final del especialista lleva el mensaje de la
        # delegación fallida. Verificamos que nombra 'Z'.
        gap = result.solve_result.gap
        self.assertIsNotNone(gap)
        # 'Z' aparece en el contexto del gap (orquestador devuelve
        # DOMAIN_MISMATCH con la variable faltante en el mensaje).
        self.assertIn("Z", gap.context)
        self.assertIn(
            ResponseStatus.DOMAIN_MISMATCH.value,
            gap.context,
            f"el gap debería mencionar el status DOMAIN_MISMATCH; fue: {gap.context!r}",
        )


if __name__ == "__main__":
    unittest.main()
