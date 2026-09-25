"""Demo del consistency_validator.

Reproduce el flujo: gap → engine genera candidato → validator lo evalúa.
Luego ejercita los cuatro checks con escenarios adversariales para que
la traza muestre tanto éxitos como fallos.

Uso:
    python -m experiment_02.consistency_validator.demo
"""
from __future__ import annotations

from experiment_01.knowledge_graph import (
    EpistemicStatus,
    KnowledgeNode,
    NodeKind,
    build_geometry_2d_graph,
)
from experiment_01.specialist import DomainContext, Problem

from ..hypothesis_engine import HypothesisCandidate, HypothesisEngine
from .validator import ConsistencyValidator


def _make_perimeter_candidate() -> tuple[HypothesisCandidate, object]:
    graph = build_geometry_2d_graph()
    problem = Problem(
        statement="¿Cuál es el perímetro de un cuadrado de lado 5?",
        target="P",
        context=DomainContext(kind="square", known={"l": 5.0}),
    )
    engine = HypothesisEngine()
    candidates = engine.generate("P", problem, graph)
    return candidates[0], graph


def main() -> None:
    print("=" * 72)
    print("ESCENARIO 1 — candidato legítimo (perímetro del cuadrado)")
    print("=" * 72)
    candidate, graph = _make_perimeter_candidate()
    print(candidate.render())
    print()
    result = ConsistencyValidator().validate(candidate, graph)
    print(result.render())
    print()

    # Escenario 2: redundancia. Inyectamos un candidato que pretende
    # producir 'A' (área) — ya producida por thm.square.area_from_side
    # y otros. Debe fallar el check 2.
    print("=" * 72)
    print("ESCENARIO 2 — candidato redundante (propone producir A, ya existe)")
    print("=" * 72)
    redundant_node = KnowledgeNode(
        id="hyp.square.area_from_side_redundant",
        statement="(redundante) A = l * l",
        status=EpistemicStatus.HYPOTHESIS,
        kind=NodeKind.RELATION,
        foundations=["def.square", "ax.arithmetic.real_numbers"],
        validity_conditions=["la figura debe ser un square", "l >= 0"],
        inputs=["l"],
        outputs=["A"],
        compute=lambda v: {"A": v["l"] * v["l"]},
        rationale="duplicado deliberado para probar el check de necesidad.",
    )
    redundant_candidate = HypothesisCandidate(
        node=redundant_node,
        pattern_name="(manual)",
        source_nodes=["def.square"],
        justification="hipótesis manual — no debería pasar el check de necesidad.",
    )
    result2 = ConsistencyValidator().validate(redundant_candidate, graph)
    print(result2.render())
    print()

    # Escenario 3: fundamento inexistente.
    print("=" * 72)
    print("ESCENARIO 3 — candidato con fundamento inexistente")
    print("=" * 72)
    bad_foundation_node = KnowledgeNode(
        id="hyp.square.bogus",
        statement="(falso) algo que depende de un nodo inexistente",
        status=EpistemicStatus.HYPOTHESIS,
        kind=NodeKind.RELATION,
        foundations=["def.square", "thm.does_not_exist"],
        validity_conditions=[],
        inputs=["l"],
        outputs=["X"],
        compute=lambda v: {"X": v["l"]},
    )
    bad_candidate = HypothesisCandidate(
        node=bad_foundation_node,
        pattern_name="(manual)",
        source_nodes=["def.square"],
        justification="prueba el check 1.",
    )
    result3 = ConsistencyValidator().validate(bad_candidate, graph)
    print(result3.render())
    print()

    # Escenario 4: viola ax.length.nonnegative.
    print("=" * 72)
    print("ESCENARIO 4 — candidato que viola ax.length.nonnegative")
    print("=" * 72)
    violating_node = KnowledgeNode(
        id="hyp.square.negative_perimeter",
        statement="(falso) Y = -3 · l",
        status=EpistemicStatus.HYPOTHESIS,
        kind=NodeKind.RELATION,
        foundations=["def.square", "ax.arithmetic.real_numbers"],
        validity_conditions=["la figura debe ser un square"],
        inputs=["l"],
        outputs=["Y"],
        compute=lambda v: {"Y": -3 * v["l"]},
        rationale="produce salidas negativas para inputs >= 0.",
    )
    violating_candidate = HypothesisCandidate(
        node=violating_node,
        pattern_name="(manual)",
        source_nodes=["def.square"],
        justification="prueba el check 4.",
    )
    result4 = ConsistencyValidator().validate(violating_candidate, graph)
    print(result4.render())


if __name__ == "__main__":
    main()
