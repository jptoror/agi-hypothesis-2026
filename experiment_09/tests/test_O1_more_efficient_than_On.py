"""Test 3: el teorema de comparación del grafo base produce el
veredicto correcto al comparar O(1) con O(n).

La comparación se hace sobre el grafo base de complejidad — no
sobre el grafo del especialista de pilas, porque def.complexity.On
no entra al grafo del especialista (no lo referencia el documento).
Esa separación es honesta: el especialista de pilas razona sobre
pilas; las comparaciones generales viven en el grafo base.
"""
from __future__ import annotations

import unittest

from experiment_09.knowledge_graph import build_complexity_base_graph


class O1MoreEfficientThanOnTest(unittest.TestCase):
    def setUp(self) -> None:
        self.base = build_complexity_base_graph()
        self.thm = self.base.get("thm.complexity.comparison")

    def test_O1_more_efficient_than_On_returns_true(self) -> None:
        o1 = self.base.get("def.complexity.O1").properties["order"]
        on = self.base.get("def.complexity.On").properties["order"]
        result = self.thm.compute({"order_a": o1, "order_b": on})
        self.assertEqual(result, {"more_efficient": True})

    def test_On_more_efficient_than_O1_returns_false(self) -> None:
        # Simetría: la inversa debe ser False.
        on = self.base.get("def.complexity.On").properties["order"]
        o1 = self.base.get("def.complexity.O1").properties["order"]
        result = self.thm.compute({"order_a": on, "order_b": o1})
        self.assertEqual(result, {"more_efficient": False})

    def test_equal_complexities_return_false(self) -> None:
        # < estricto, no <=. Dos clases iguales NO son
        # "estrictamente más eficientes" entre sí.
        o1 = self.base.get("def.complexity.O1").properties["order"]
        result = self.thm.compute({"order_a": o1, "order_b": o1})
        self.assertEqual(result, {"more_efficient": False})

    def test_full_chain_of_efficiencies(self) -> None:
        # Cadena O(1) < O(log n) < O(n) < O(n log n) < O(n²).
        order_chain = [
            self.base.get(nid).properties["order"]
            for nid in [
                "def.complexity.O1",
                "def.complexity.Ologn",
                "def.complexity.On",
                "def.complexity.Onlogn",
                "def.complexity.On2",
            ]
        ]
        # Cada par consecutivo: el de la izquierda es más eficiente.
        for a, b in zip(order_chain, order_chain[1:]):
            result = self.thm.compute({"order_a": a, "order_b": b})
            self.assertTrue(
                result["more_efficient"],
                f"order_a={a} debería ser más eficiente que order_b={b}"
            )


if __name__ == "__main__":
    unittest.main()
