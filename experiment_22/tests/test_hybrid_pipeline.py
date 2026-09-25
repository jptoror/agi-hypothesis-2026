"""Tests del pipeline híbrido con un LLM guionizado.

El guion decide qué "dice" el LLM en cada rol; los tests fijan qué
hace el sistema con eso: qué nivel asigna, qué rechaza y por qué.
"""
from __future__ import annotations

import json
import unittest

from experiment_22.gateway import EngineGateway
from experiment_22.hypothesis import Verdict
from experiment_22.llm import LLMError, ScriptedLLM
from experiment_22.pipeline import HybridPipeline, Tier


def _translation(domain, kind, target, known, quantity="", status="ok"):
    return {
        "status": status, "reason": "scripted", "domain": domain, "context_kind": kind,
        "target": target, "target_quantity": quantity,
        "known": [{"name": k, "value": v} for k, v in known.items()],
        "variable_bindings": [], "partner_context_kind": "",
    }


def _proposal(output, expression, inputs, foundations, dim=(0, 1, 0)):
    return {
        "status": "proposed", "reason": "", "statement": f"{output} = {expression}",
        "output": output, "inputs": inputs, "expression": expression,
        "foundations": foundations, "output_dimension": dict(zip("MLT", dim)),
    }


class HybridPipelineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.gateway = EngineGateway()

    def pipeline(self, translate=None, hypothesize=None, answer=None, fallback=True):
        def handler(task, user):
            fn = {"translate": translate, "hypothesize": hypothesize, "answer": answer}[task]
            if fn is None:
                raise AssertionError(f"llamada inesperada al LLM: {task}")
            return fn(json.loads(user)) if callable(fn) else fn
        return HybridPipeline(ScriptedLLM(handler), gateway=self.gateway, fallback_to_llm=fallback)

    # -- VERIFIED ------------------------------------------------------------

    def test_in_domain_question_is_verified_without_hypothesis(self) -> None:
        p = self.pipeline(translate=_translation("geometry", "square", "A", {"d": 8}))
        answer = p.answer("What is the area of a square whose diagonal is 8?")
        self.assertEqual(answer.tier, Tier.VERIFIED)
        self.assertEqual(answer.value, 32.0)
        self.assertEqual(answer.trace_node_ids, ["thm.square.area_from_diagonal"])

    # -- hipótesis --------------------------------------------------------------

    def perimeter(self, expression, dim=(0, 1, 0)):
        return self.pipeline(
            translate=_translation("geometry", "square", "P", {"l": 5}, quantity="perimeter"),
            hypothesize=_proposal("P", expression, ["l"], ["def.square"], dim),
        ).answer("What is the perimeter of a square with side 5?")

    def test_hypothesis_matching_own_pattern_is_corroborated(self) -> None:
        answer = self.perimeter("4 * l")
        self.assertEqual(answer.tier, Tier.CORROBORATED)
        self.assertEqual(answer.value, 20.0)
        self.assertIn("hyp.llm.geometry.P_from_l", answer.trace_node_ids)

    def test_hypothesis_contradicting_own_pattern_is_rejected(self) -> None:
        answer = self.perimeter("3 * l")
        self.assertEqual(answer.tier, Tier.ABSTAINED)
        self.assertEqual(answer.hypothesis.verdict, Verdict.REJECTED)
        self.assertIn("contradicción", answer.reason)

    def test_dimension_is_checked_against_the_quantity_not_the_llm(self) -> None:
        # El LLM declara L² para ser coherente consigo mismo; la tabla dice que
        # un perímetro es L. Gana la tabla.
        answer = self.perimeter("l ** 2", dim=(0, 2, 0))
        self.assertEqual(answer.tier, Tier.ABSTAINED)
        self.assertIn("dimensión", answer.reason)

    def test_uncorroborated_hypothesis_is_conditional(self) -> None:
        p = self.pipeline(
            translate=_translation("geometry", "square", "d", {"l": 5}),
            hypothesize=_proposal("d", "l * sqrt(2)", ["l"], ["def.square"]),
        )
        answer = p.answer("How long is the diagonal of a square with side 5?")
        self.assertEqual(answer.tier, Tier.CONDITIONAL)
        self.assertAlmostEqual(answer.value, 7.0710678118654755)

    def test_hypothesis_can_cover_an_intermediate_gap(self) -> None:
        seen = {}

        def hypothesize(payload):
            seen["missing"] = payload["missing_variable"]
            return _proposal("d", "sqrt(2 * A)", ["A"], ["def.square"])

        p = self.pipeline(
            translate=_translation("geometry", "square", "l", {"A": 49}),
            hypothesize=hypothesize,
        )
        answer = p.answer("A square has an area of 49. How long is its side?")
        self.assertEqual(seen["missing"], "d")
        self.assertEqual(answer.tier, Tier.CONDITIONAL)
        self.assertAlmostEqual(answer.value, 7.0)

    def test_hypothesis_without_foundations_is_rejected(self) -> None:
        p = self.pipeline(
            translate=_translation("physics", "physics.object", "p", {"m": 3, "v": 4},
                                   quantity="momentum"),
            hypothesize=_proposal("p", "m * v", ["m", "v"], [], dim=(1, 1, -1)),
        )
        answer = p.answer("Momentum of a 3 kg object at 4 m/s?")
        self.assertEqual(answer.tier, Tier.ABSTAINED)
        self.assertIn("fundamento", answer.reason)

    def test_unsafe_expression_is_rejected(self) -> None:
        answer = self.perimeter("__import__('os').getcwd()")
        self.assertEqual(answer.tier, Tier.ABSTAINED)
        self.assertIn("no permitida", answer.reason)

    def test_llm_declining_to_propose_means_abstention(self) -> None:
        p = self.pipeline(
            translate=_translation("geometry", "square", "P", {"l": 5}, quantity="perimeter"),
            hypothesize=dict(_proposal("P", "", [], []), status="cannot_propose"),
        )
        answer = p.answer("What is the perimeter of a square with side 5?")
        self.assertEqual(answer.tier, Tier.ABSTAINED)
        self.assertEqual(answer.hypothesis.verdict, Verdict.NOT_PROPOSED)

    # -- abstenciones y fallback ------------------------------------------------

    def test_insufficient_data_abstains_without_asking_for_an_answer(self) -> None:
        p = self.pipeline(translate=_translation("", "", "", {}, status="insufficient_data"))
        answer = p.answer("What is the area of a square?")
        self.assertEqual(answer.tier, Tier.ABSTAINED)

    def test_hallucinated_input_is_caught_by_grounding(self) -> None:
        p = self.pipeline(translate=_translation("geometry", "square", "A", {"l": 1}))
        answer = p.answer("What is the area of a square?")
        self.assertEqual(answer.tier, Tier.ABSTAINED)
        self.assertIn("grounding", answer.reason)

    def test_precondition_violation_abstains(self) -> None:
        p = self.pipeline(translate=_translation("algebra", "linear_equation", "x", {"a": 0, "b": 5}))
        answer = p.answer("Solve for x: 0x + 5 = 0")
        self.assertEqual(answer.tier, Tier.ABSTAINED)
        self.assertIn("a ≠ 0", answer.reason)

    def test_out_of_scope_falls_back_to_unverified_llm_answer(self) -> None:
        p = self.pipeline(
            translate=_translation("", "", "", {}, status="out_of_scope"),
            answer={"status": "answered", "value": 36, "explanation": "15% of 240"},
        )
        answer = p.answer("What is 15% of 240?")
        self.assertEqual(answer.tier, Tier.UNVERIFIED)
        self.assertEqual(answer.value, 36.0)

    def test_out_of_scope_without_fallback_abstains(self) -> None:
        p = self.pipeline(translate=_translation("", "", "", {}, status="out_of_scope"),
                          fallback=False)
        self.assertEqual(p.answer("What is 15% of 240?").tier, Tier.ABSTAINED)

    def test_llm_failure_is_an_abstention(self) -> None:
        p = self.pipeline(translate=lambda _: LLMError("boom"))
        answer = p.answer("anything")
        self.assertEqual(answer.tier, Tier.ABSTAINED)
        self.assertIn("llm_failed", answer.reason)


if __name__ == "__main__":
    unittest.main()
