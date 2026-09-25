"""Tests críticos del especialista C++ mínimo (exp_16).

Tres aserciones que distinguen este experimento del resto:

  1. test_cpp_specialist_registers
     El especialista se registra y NO se construyó ningún nodo a
     mano — todo viene del documento C++ o del grafo del especialista
     ch1 (exp_15).

  2. test_derives_greedy_in_cpp
     La traza de ancestros del nodo de mapping atraviesa nodos de
     AMBOS especialistas: cpp + ch1. Sin la fusión de los dos
     dominios, la pregunta no se podría responder.

  3. test_output_is_structured_text
     La salida del procedimiento es código C++ COMPUESTO a partir
     de las plantillas declaradas en `cpp_templates.CPP_TEMPLATES`
     — no es predicción del siguiente token. Cada fragmento del
     output es trazable a una plantilla concreta.
"""
from __future__ import annotations

import unittest

from experiment_01.knowledge_graph import EpistemicStatus
from experiment_15.specialist_factory import (
    AlgorithmsCh1SpecialistFactory,
)

from experiment_16.specialist_factory import (
    CPP_TEMPLATES,
    CppMinimalSpecialistFactory,
)


class CppMinimalSpecialistTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = CppMinimalSpecialistFactory().build()
        cls.graph = cls.result.graph
        cls.ch1_ids = {
            n.id for n in AlgorithmsCh1SpecialistFactory().build().graph
        }
        cls.cpp_doc_ids = {
            n.node_id
            for n in cls.result.underlying.parse_report.nodes_extracted
        }

    # -- 1. registers + 0 manual nodes -----------------------------

    def test_cpp_specialist_registers(self) -> None:
        """Se registra limpio y SIN nodos construidos a mano. Todo
        nodo del grafo final pertenece a {cpp_doc} ∪ {ch1_base}."""
        self.assertTrue(self.result.registered)
        self.assertEqual(self.result.errors, [])

        errors, warnings = self.graph.validate_with_warnings()
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

        manual = [
            n.id for n in self.graph
            if n.id not in self.cpp_doc_ids
            and n.id not in self.ch1_ids
        ]
        self.assertEqual(
            manual, [],
            f"se esperaba 0 nodos manuales; se encontraron {manual}"
        )

    # -- 2. cross-specialist trace ---------------------------------

    def test_derives_greedy_in_cpp(self) -> None:
        """La traza del nodo de mapping atraviesa AMBOS especialistas
        — al menos un ancestro del C++ y al menos uno del ch1. Sin
        la importación del base_graph esto sería imposible."""
        impl_id = "alg.cpp.greedy_coloring_impl"
        self.assertTrue(self.graph.has(impl_id))
        impl = self.graph.get(impl_id)
        self.assertEqual(impl.status, EpistemicStatus.ALGORITHM)

        ancestors = list(self.graph.transitive_foundations(impl_id))
        ancestor_ids = {n.id for n in ancestors}

        from_cpp = ancestor_ids & self.cpp_doc_ids
        from_ch1 = ancestor_ids & self.ch1_ids
        self.assertGreater(
            len(from_cpp), 0,
            "se esperaba al menos un ancestro del especialista cpp"
        )
        self.assertGreater(
            len(from_ch1), 0,
            "se esperaba al menos un ancestro del especialista ch1"
        )

        # En particular, el algoritmo abstracto del ch1 debe estar
        # entre los ancestros — es la justificación semántica del
        # mapping.
        self.assertIn("alg.greedy_coloring", from_ch1)
        # Y al menos un constructo C++ definicional debe estar entre
        # los ancestros — es la justificación sintáctica.
        cpp_def_ancestors = {
            nid for nid in from_cpp if nid.startswith("def.cpp.")
        }
        self.assertGreater(
            len(cpp_def_ancestors), 0,
            "se esperaba al menos un def.cpp.* entre los ancestros"
        )

    # -- 3. structured output (composición, no predicción) ---------

    def test_output_is_structured_text(self) -> None:
        """El cpp_code producido es composición determinista de
        plantillas declaradas — no inferencia. Verificamos:
          a) cada llamada con los mismos inputs produce exactamente
             el mismo output (determinismo).
          b) el output contiene los fragmentos literales que cada
             plantilla del CPP_TEMPLATES rinde con los inputs
             dados — la salida es trazable token a token a la
             biblioteca."""
        impl = self.graph.get("alg.cpp.greedy_coloring_impl")
        self.assertIsNotNone(impl.compute)

        inputs = {
            "abstract_node": "alg.greedy_coloring",
            "target_container": "no_col",
        }
        out1 = impl.compute(inputs)
        out2 = impl.compute(inputs)

        # a) determinismo: misma entrada → misma salida exacta.
        self.assertEqual(out1, out2)
        self.assertIn("cpp_code", out1)
        code = out1["cpp_code"]
        self.assertIsInstance(code, str)

        # b) trazabilidad a plantillas concretas. Cada fragmento
        # esperado proviene de una plantilla del CPP_TEMPLATES
        # rinden con los slots correctos.
        iter_fragment = CPP_TEMPLATES["def.cpp.iterator"].render(
            T="set<int>", name="q",
        )
        self.assertIn(iter_fragment, code)

        for_fragment_head = "for (q = no_col.begin(); q != no_col.end(); q++)"
        self.assertIn(for_fragment_head, code)

        # El output nombra explícitamente el nodo abstracto y el
        # constructor C++ — la auditoría apunta al grafo de origen.
        self.assertIn("alg.greedy_coloring", code)
        self.assertIn("def.cpp.set", code)

    # -- diagnósticos extra (no críticos) --------------------------

    def test_mapping_node_resolves_procedure(self) -> None:
        """`alg.cpp.greedy_coloring_impl` lleva compute resuelto y
        properties con inputs/outputs declarados (contrato exp_14
        para nodos ALGORITHM)."""
        impl = self.graph.get("alg.cpp.greedy_coloring_impl")
        self.assertIsNotNone(impl.compute)
        props = impl.properties or {}
        self.assertEqual(props.get("procedure_name"),
                         "cpp_greedy_coloring_compose")
        self.assertTrue(props.get("procedure_resolved"))
        self.assertEqual(
            props.get("inputs"),
            ["abstract_node", "target_container"],
        )
        self.assertEqual(props.get("outputs"), ["cpp_code"])


if __name__ == "__main__":
    unittest.main()
