"""Unit tests del VocabularyRegistry (exp_17).

Cubren los invariantes del contrato: idempotencia, longest match,
conflictos, normalización mínima, robustez ante entradas
malformadas.
"""
from __future__ import annotations

import unittest

from experiment_01.knowledge_graph import (
    EpistemicStatus,
    KnowledgeGraph,
    KnowledgeNode,
    NodeKind,
)

from experiment_17.vocabulary import VocabularyRegistry, normalize


def _node(node_id: str, surface_forms) -> KnowledgeNode:
    """Helper: nodo definicional con surface_forms en properties.

    Usamos DEFINITION + CONCEPT para que graph.add() acepte el nodo
    sin necesidad de fundamentos ni compute. surface_forms se pasa
    tal cual — los tests prueban formas válidas y no-string para
    ejercitar la robustez.
    """
    return KnowledgeNode(
        id=node_id,
        statement=f"nodo de prueba {node_id}",
        status=EpistemicStatus.DEFINITION,
        kind=NodeKind.CONCEPT,
        properties={"surface_forms": surface_forms},
    )


def _graph(*nodes) -> KnowledgeGraph:
    g = KnowledgeGraph()
    for n in nodes:
        g.add(n)
    return g


class NormalizeTest(unittest.TestCase):
    def test_lowercase(self) -> None:
        self.assertEqual(normalize("Coloreado Voraz"), "coloreado voraz")

    def test_collapses_internal_whitespace(self) -> None:
        self.assertEqual(normalize("a   b\tc"), "a b c")

    def test_strip(self) -> None:
        self.assertEqual(normalize("   foo   "), "foo")

    def test_preserves_accents(self) -> None:
        self.assertEqual(normalize("Vóraz"), "vóraz")
        self.assertNotEqual(normalize("vóraz"), normalize("voraz"))

    def test_non_string_returns_empty(self) -> None:
        self.assertEqual(normalize(123), "")
        self.assertEqual(normalize(None), "")


class RegistryBasicsTest(unittest.TestCase):
    def test_register_indexes_all_forms(self) -> None:
        g = _graph(
            _node("n1", ["alfa", "beta"]),
            _node("n2", ["gamma"]),
        )
        r = VocabularyRegistry()
        added = r.register("specA", g)
        self.assertEqual(added, 3)
        self.assertEqual(len(r), 3)

    def test_lookup_exact_returns_binding(self) -> None:
        g = _graph(_node("n1", ["coloreado voraz"]))
        r = VocabularyRegistry()
        r.register("specA", g, source_document="doc.md")
        bindings = r.lookup("coloreado voraz")
        self.assertEqual(len(bindings), 1)
        self.assertEqual(bindings[0].specialist_id, "specA")
        self.assertEqual(bindings[0].node_id, "n1")
        self.assertEqual(bindings[0].source_document, "doc.md")

    def test_lookup_is_case_insensitive(self) -> None:
        g = _graph(_node("n1", ["Coloreado Voraz"]))
        r = VocabularyRegistry()
        r.register("specA", g)
        self.assertEqual(len(r.lookup("coloreado voraz")), 1)
        self.assertEqual(len(r.lookup("COLOREADO VORAZ")), 1)

    def test_lookup_collapses_internal_whitespace(self) -> None:
        g = _graph(_node("n1", ["coloreado voraz"]))
        r = VocabularyRegistry()
        r.register("specA", g)
        self.assertEqual(len(r.lookup("coloreado    voraz")), 1)
        self.assertEqual(len(r.lookup("  coloreado voraz  ")), 1)

    def test_lookup_unknown_returns_empty(self) -> None:
        g = _graph(_node("n1", ["alfa"]))
        r = VocabularyRegistry()
        r.register("specA", g)
        self.assertEqual(r.lookup("xxx"), [])

    def test_lookup_empty_or_whitespace_returns_empty(self) -> None:
        g = _graph(_node("n1", ["alfa"]))
        r = VocabularyRegistry()
        r.register("specA", g)
        self.assertEqual(r.lookup(""), [])
        self.assertEqual(r.lookup("   "), [])
        self.assertEqual(r.lookup("\t\n"), [])


class IdempotenceTest(unittest.TestCase):
    def test_re_register_replaces_not_duplicates(self) -> None:
        g1 = _graph(_node("n1", ["alfa", "beta"]))
        g2 = _graph(_node("n9", ["gamma"]))
        r = VocabularyRegistry()
        r.register("specA", g1)
        self.assertEqual(len(r), 2)
        # Re-register con un grafo diferente para el mismo
        # specialist_id → reemplaza, no acumula.
        r.register("specA", g2)
        self.assertEqual(len(r), 1)
        self.assertEqual(r.lookup("alfa"), [])
        self.assertEqual(len(r.lookup("gamma")), 1)

    def test_unregister_removes_only_target(self) -> None:
        g_a = _graph(_node("n1", ["alfa"]))
        g_b = _graph(_node("n2", ["beta"]))
        r = VocabularyRegistry()
        r.register("specA", g_a)
        r.register("specB", g_b)
        n = r.unregister("specA")
        self.assertEqual(n, 1)
        self.assertEqual(r.lookup("alfa"), [])
        self.assertEqual(len(r.lookup("beta")), 1)
        self.assertNotIn("specA", r.specialists())
        self.assertIn("specB", r.specialists())

    def test_unregister_unknown_specialist_is_noop(self) -> None:
        r = VocabularyRegistry()
        self.assertEqual(r.unregister("nope"), 0)


class LongestMatchTest(unittest.TestCase):
    def test_prefers_longest_span(self) -> None:
        g = _graph(
            _node("n1", ["coloreado"]),
            _node("n2", ["coloreado voraz"]),
        )
        r = VocabularyRegistry()
        r.register("specA", g)
        tokens = ["calculá", "el", "coloreado", "voraz", "del", "grafo"]
        hit = r.lookup_longest_match(tokens, start=2)
        self.assertIsNotNone(hit)
        bindings, span = hit
        self.assertEqual(span, 2)
        self.assertEqual(bindings[0].node_id, "n2")

    def test_works_with_nonzero_start(self) -> None:
        g = _graph(_node("n1", ["greedy coloring"]))
        r = VocabularyRegistry()
        r.register("specA", g)
        tokens = ["the", "greedy", "coloring", "algorithm"]
        hit = r.lookup_longest_match(tokens, start=1)
        self.assertIsNotNone(hit)
        bindings, span = hit
        self.assertEqual(span, 2)
        self.assertEqual(bindings[0].node_id, "n1")

    def test_returns_none_when_no_match(self) -> None:
        g = _graph(_node("n1", ["alfa"]))
        r = VocabularyRegistry()
        r.register("specA", g)
        tokens = ["beta", "gamma", "delta"]
        self.assertIsNone(r.lookup_longest_match(tokens, start=0))

    def test_returns_none_on_invalid_start(self) -> None:
        g = _graph(_node("n1", ["alfa"]))
        r = VocabularyRegistry()
        r.register("specA", g)
        self.assertIsNone(r.lookup_longest_match(["alfa"], start=5))
        self.assertIsNone(r.lookup_longest_match(["alfa"], start=-1))


class ConflictTest(unittest.TestCase):
    def test_conflict_returns_all_bindings(self) -> None:
        g_a = _graph(_node("def.cpp.set", ["set"]))
        g_b = _graph(_node("def.math.set", ["set"]))
        r = VocabularyRegistry()
        r.register("specCpp", g_a)
        r.register("specMath", g_b)
        bindings = r.lookup("set")
        self.assertEqual(len(bindings), 2)
        ids = {b.specialist_id for b in bindings}
        self.assertEqual(ids, {"specCpp", "specMath"})

    def test_accents_are_distinct_entries(self) -> None:
        g = _graph(
            _node("n1", ["voraz"]),
            _node("n2", ["vóraz"]),
        )
        r = VocabularyRegistry()
        r.register("specA", g)
        self.assertEqual(len(r.lookup("voraz")), 1)
        self.assertEqual(r.lookup("voraz")[0].node_id, "n1")
        self.assertEqual(r.lookup("vóraz")[0].node_id, "n2")


class RobustnessTest(unittest.TestCase):
    def test_non_string_surface_forms_are_ignored(self) -> None:
        # Mezcla de strings válidos, no-strings, vacíos.
        g = _graph(_node("n1", ["alfa", 123, None, "", "  ", "beta"]))
        r = VocabularyRegistry()
        added = r.register("specA", g)
        self.assertEqual(added, 2)
        self.assertEqual(len(r.lookup("alfa")), 1)
        self.assertEqual(len(r.lookup("beta")), 1)

    def test_surface_forms_field_must_be_list(self) -> None:
        # Si alguien pone un string suelto u otra forma no-list,
        # ignorar sin lanzar.
        g = _graph(_node("n1", "alfa"))  # no-list
        r = VocabularyRegistry()
        added = r.register("specA", g)
        self.assertEqual(added, 0)
        self.assertEqual(len(r), 0)

    def test_node_without_surface_forms_property_is_skipped(self) -> None:
        g = KnowledgeGraph()
        g.add(KnowledgeNode(
            id="n1",
            statement="sin marcador",
            status=EpistemicStatus.DEFINITION,
            kind=NodeKind.CONCEPT,
        ))
        r = VocabularyRegistry()
        added = r.register("specA", g)
        self.assertEqual(added, 0)


class SurfaceFormsAccessorTest(unittest.TestCase):
    def test_global_listing(self) -> None:
        g = _graph(_node("n1", ["alfa", "beta"]))
        r = VocabularyRegistry()
        r.register("specA", g)
        self.assertEqual(r.surface_forms(), ["alfa", "beta"])

    def test_per_specialist_filter(self) -> None:
        g_a = _graph(_node("n1", ["alfa"]))
        g_b = _graph(_node("n2", ["beta"]))
        r = VocabularyRegistry()
        r.register("specA", g_a)
        r.register("specB", g_b)
        self.assertEqual(r.surface_forms("specA"), ["alfa"])
        self.assertEqual(r.surface_forms("specB"), ["beta"])
        self.assertEqual(r.surface_forms("ghost"), [])


if __name__ == "__main__":
    unittest.main()
