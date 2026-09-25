"""Test crítico de PROB-01: un KnowledgeGraph serializado y
deserializado produce los mismos resultados que el original.

Usamos el grafo del subdominio emergente del exp_04 — 20 nodos
autocontenidos, con teoremas ejecutables (thm.kinetic_energy,
thm.square.side_from_diagonal). Tras dump → load, el grafo
reconstruido debe:
  1. Tener el mismo número de nodos.
  2. Tener los mismos ids, statuses, foundations.
  3. Pasar graph.validate() sin errores.
  4. Producir el mismo resultado numérico al ejecutar los
     compute reconectados desde la registry.
"""
from __future__ import annotations

import math
import tempfile
import unittest
from pathlib import Path

from experiment_01.knowledge_graph import build_geometry_2d_graph
from experiment_01.specialist import DomainContext, Problem
from experiment_03.specialists.physics import build_physics_graph
from experiment_04.orchestrator import EmergentOrchestrator

from experiment_02.persistence import (
    ComputeRegistry,
    DeserializationReport,
    SerializationReport,
    dump,
    load,
)


def _bootstrap_emergent_subgraph():
    """Reproduce el ciclo del exp_04 hasta producir el subdominio
    geometry_physics con 20 nodos."""
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
    return orch.emergent_adapters["geometry_physics"].graph


def _registry_for_subgraph() -> ComputeRegistry:
    """ComputeRegistry para el subgrafo emergente.

    Reproducimos los compute originales de los nodos ejecutables.
    En un proyecto real esta registry vive en un módulo central; la
    construimos in-test para no acoplar persistence a otros paquetes.
    """
    reg = ComputeRegistry()
    reg.register(
        "thm.kinetic_energy",
        lambda v: {"Ec": 0.5 * v["m"] * (v["v"] ** 2)},
    )
    reg.register(
        "thm.square.side_from_diagonal",
        lambda v: {"l": v["d"] / math.sqrt(2)},
    )
    reg.register(
        "binding.v_equals_l",
        lambda v: {"v": v["l"]},
    )
    # thm.pythagoras es fundamento transitivo del subgrafo emergente:
    # entró al sintetizar geometry_physics aunque no se ejercita en
    # los problemas canónicos del exp_04. Lo registramos por
    # completitud — un load del subgrafo debe poder reconstruirlo
    # también.
    reg.register(
        "thm.pythagoras",
        lambda v: {"c": math.sqrt(v["a"] ** 2 + v["b"] ** 2)},
    )
    return reg


class PersistenceRoundtripTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.original = _bootstrap_emergent_subgraph()
        cls.registry = _registry_for_subgraph()

    def test_node_count_is_twenty(self) -> None:
        """Sanity check: el subgrafo tiene 20 nodos como esperamos."""
        self.assertEqual(len(self.original), 20)

    def test_dump_writes_file(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "subgraph.json"
            report = dump(self.original, path)
            self.assertIsInstance(report, SerializationReport)
            self.assertEqual(report.node_count, 20)
            self.assertTrue(path.exists())
            self.assertGreater(path.stat().st_size, 0)

    def test_roundtrip_preserves_node_ids_and_statuses(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "subgraph.json"
            dump(self.original, path)
            result = load(path, self.registry)

            self.assertEqual(result.nodes_loaded, 20)
            original_ids = sorted(n.id for n in self.original)
            loaded_ids = sorted(n.id for n in result.graph)
            self.assertEqual(original_ids, loaded_ids)

            for orig in self.original:
                loaded = result.graph.get(orig.id)
                self.assertEqual(loaded.status, orig.status)
                self.assertEqual(loaded.kind, orig.kind)
                self.assertEqual(loaded.foundations, orig.foundations)
                self.assertEqual(loaded.statement, orig.statement)

    def test_roundtrip_graph_validates(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "subgraph.json"
            dump(self.original, path)
            result = load(path, self.registry)
            self.assertEqual(result.graph.validate(), [])

    def test_roundtrip_compute_produces_same_numeric_result(self) -> None:
        """El test más fuerte: ejecutar el mismo compute en original
        y reconstruido produce el mismo número.
        """
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "subgraph.json"
            dump(self.original, path)
            result = load(path, self.registry)

            # thm.kinetic_energy con m=2, v=4 → Ec = 0.5 * 2 * 16 = 16.0
            orig_thm = self.original.get("thm.kinetic_energy")
            load_thm = result.graph.get("thm.kinetic_energy")
            self.assertTrue(orig_thm.is_executable())
            self.assertTrue(load_thm.is_executable())
            inputs = {"m": 2.0, "v": 4.0}
            self.assertEqual(orig_thm.compute(inputs), load_thm.compute(inputs))

            # thm.square.side_from_diagonal con d=8 → l = 8/√2
            orig_sd = self.original.get("thm.square.side_from_diagonal")
            load_sd = result.graph.get("thm.square.side_from_diagonal")
            self.assertEqual(
                orig_sd.compute({"d": 8.0}),
                load_sd.compute({"d": 8.0}),
            )

            # binding.v_equals_l es trivial pero también ejecuta.
            orig_b = self.original.get("binding.v_equals_l")
            load_b = result.graph.get("binding.v_equals_l")
            self.assertEqual(
                orig_b.compute({"l": 7.5}),
                load_b.compute({"l": 7.5}),
            )

    def test_roundtrip_without_registry_marks_unresolved(self) -> None:
        """Sin registry, los nodos ejecutables se cargan sin compute
        y se reportan como unresolved — el sistema admite honestamente
        qué le falta."""
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "subgraph.json"
            dump(self.original, path)
            result: DeserializationReport = load(path, registry=None)

            self.assertEqual(result.nodes_loaded, 20)
            # Los 4 nodos ejecutables del subgrafo no se reconectaron.
            # (thm.pythagoras entra como fundamento transitivo aunque
            # no se ejercite en los problemas canónicos del exp_04.)
            self.assertEqual(set(result.unresolved_computes), {
                "thm.kinetic_energy",
                "thm.square.side_from_diagonal",
                "binding.v_equals_l",
                "thm.pythagoras",
            })
            self.assertFalse(result.is_complete)
            # Los compute están a None tras carga sin registry.
            for nid in result.unresolved_computes:
                self.assertIsNone(result.graph.get(nid).compute)


if __name__ == "__main__":
    unittest.main()
