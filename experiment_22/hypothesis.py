"""HypothesisBroker: el LLM propone, el sistema juzga.

Cuando el motor declara un gap (ningún nodo produce la variable
pedida), el broker pide al LLM UNA fórmula candidata en la gramática
de `expression.py`. La propuesta pasa por un veredicto determinista:

  1. Forma: expresión segura; sus variables son exactamente los
     inputs declarados; todos pertenecen al dominio.
  2. Consistencia (exp_02): fundamentos existentes, cómputo
     ejecutable/determinista/finito, compatible con los axiomas
     verificables del grafo. El check de redundancia del exp_02 se
     redefine (ver `_input_aware_redundancy`).
  3. Dimensión: la dimensión inferida de la expresión debe coincidir
     con la de la magnitud pedida. La dimensión esperada sale del
     catálogo o de la tabla de magnitudes — no de lo que declare el
     propio LLM, salvo que la magnitud sea desconocida (queda anotado).
  4. Corroboración: si los patrones propios del sistema (exp_02)
     derivan de forma independiente una relación para la misma
     variable y con los mismos inputs, ambas deben coincidir
     numéricamente. Coinciden → CORROBORATED. Discrepan → REJECTED
     (el LLM contradice una derivación del sistema). No hay patrón →
     CONSISTENT: pasó todos los checks, pero nada la confirma.

La distinción CORROBORATED / CONSISTENT es el corazón honesto del
experimento: "no la puedo refutar" no es lo mismo que "la sé".
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from enum import Enum

from experiment_01.knowledge_graph import (
    EpistemicStatus,
    KnowledgeGraph,
    KnowledgeNode,
    NodeKind,
)
from experiment_01.specialist import DomainContext, Problem
from experiment_02.consistency_validator import ConsistencyValidator
from experiment_02.consistency_validator.result import CheckOutcome
from experiment_02.hypothesis_engine import HypothesisCandidate, HypothesisEngine

from .catalog import DomainSpec, quantity_dimension
from .expression import Dimension, DimensionError, SafeExpression, UnsafeExpression
from .gateway import StructuredQuery
from .llm import JsonLLM, LLMError


class Verdict(str, Enum):
    CORROBORATED = "corroborated"
    CONSISTENT = "consistent"
    REJECTED = "rejected"
    NOT_PROPOSED = "not_proposed"


@dataclass
class HypothesisVerdict:
    verdict: Verdict
    node: KnowledgeNode | None = None
    expression: str = ""
    reason: str = ""
    checks: list[str] = field(default_factory=list)

    @property
    def accepted(self) -> bool:
        return self.verdict in (Verdict.CORROBORATED, Verdict.CONSISTENT)


HYPOTHESIS_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": ["proposed", "cannot_propose"]},
        "reason": {"type": "string"},
        "statement": {"type": "string"},
        "output": {"type": "string"},
        "inputs": {"type": "array", "items": {"type": "string"}},
        "expression": {"type": "string"},
        "foundations": {"type": "array", "items": {"type": "string"}},
        "output_dimension": {
            "type": "object",
            "properties": {
                "M": {"type": "number"}, "L": {"type": "number"}, "T": {"type": "number"},
            },
            "required": ["M", "L", "T"],
            "additionalProperties": False,
        },
    },
    "required": [
        "status", "reason", "statement", "output", "inputs", "expression",
        "foundations", "output_dimension",
    ],
    "additionalProperties": False,
}

_SYSTEM = """A symbolic reasoning engine could not derive a quantity because no relation \
in its knowledge graph produces it. Propose ONE general formula (a relation, not a \
numeric answer) that produces the missing variable from the available variables.

Constraints:
- "expression" uses only numbers, the listed variable names, pi, + - * / **, and sqrt().
- "inputs" lists exactly the variables used in the expression.
- "foundations" lists ids of existing nodes (definitions, axioms, theorems) the formula \
relies on, chosen from the list provided.
- "output_dimension" gives exponents of mass M, length L and time T of the output.
- If no formula over the available variables is correct, answer status "cannot_propose".
"""


class HypothesisBroker:
    SAMPLE_POINTS = (1.0, 2.5, 7.0)

    def __init__(self, llm: JsonLLM) -> None:
        self.llm = llm
        self.validator = ConsistencyValidator()
        self.engine = HypothesisEngine()

    # -- API -------------------------------------------------------------

    def propose_and_verify(
        self,
        query: StructuredQuery,
        missing_variable: str,
        target_quantity: str,
        spec: DomainSpec,
        graph: KnowledgeGraph,
    ) -> HypothesisVerdict:
        try:
            raw = self.llm.complete_json(
                "hypothesize",
                _SYSTEM,
                self._user_message(query, missing_variable, target_quantity, spec, graph),
                HYPOTHESIS_SCHEMA,
            )
        except LLMError as e:
            return HypothesisVerdict(Verdict.NOT_PROPOSED, reason=str(e))
        if raw.get("status") != "proposed":
            return HypothesisVerdict(Verdict.NOT_PROPOSED, reason=raw.get("reason", ""))
        return self.verify(raw, query, missing_variable, target_quantity, spec, graph)

    def verify(
        self,
        raw: dict,
        query: StructuredQuery,
        missing_variable: str,
        target_quantity: str,
        spec: DomainSpec,
        graph: KnowledgeGraph,
    ) -> HypothesisVerdict:
        checks: list[str] = []
        expr_text = raw.get("expression", "")

        def reject(reason: str) -> HypothesisVerdict:
            return HypothesisVerdict(
                Verdict.REJECTED, expression=expr_text, reason=reason, checks=checks,
            )

        # 1. Forma --------------------------------------------------------
        if raw.get("output") != missing_variable:
            return reject(
                f"la fórmula produce '{raw.get('output')}', se pidió '{missing_variable}'"
            )
        try:
            expr = SafeExpression.parse(expr_text)
        except UnsafeExpression as e:
            return reject(f"expresión no permitida: {e}")
        declared_inputs = set(raw.get("inputs", []))
        if declared_inputs != set(expr.variables):
            return reject(
                f"inputs declarados {sorted(declared_inputs)} ≠ variables de la "
                f"expresión {sorted(expr.variables)}"
            )
        if missing_variable in expr.variables:
            return reject("la fórmula usa la propia variable que pretende producir")
        unknown = [v for v in expr.variables if v not in spec.variables]
        if unknown:
            return reject(f"variables fuera del dominio '{spec.name}': {unknown}")
        checks.append(f"forma: {missing_variable} = {expr.source}")

        # 2. Dimensión ------------------------------------------------------
        dims = {name: v.dimension for name, v in spec.variables.items()}
        try:
            got = expr.dimension(dims)
        except DimensionError as e:
            return reject(f"dimensión inválida: {e}")
        expected, source = self._expected_dimension(
            missing_variable, target_quantity, spec, raw,
        )
        if got != expected:
            return reject(
                f"dimensión: la expresión es {got.render()}, se esperaba "
                f"{expected.render()} ({source})"
            )
        checks.append(f"dimensión: {got.render()} coincide con la esperada ({source})")

        # 3. Consistencia exp_02 --------------------------------------------
        node = self._build_node(raw, expr, missing_variable, spec)
        candidate = HypothesisCandidate(
            node=node,
            pattern_name="llm_proposal",
            source_nodes=list(node.foundations),
            justification=raw.get("statement", ""),
        )
        result = self.validator.validate(candidate, graph)
        outcomes = [
            self._input_aware_redundancy(candidate, graph) if c.name == "not_redundant" else c
            for c in result.checks
        ]
        if not node.foundations:
            outcomes.append(CheckOutcome(
                name="has_foundations", passed=False,
                detail="la hipótesis no declara ningún fundamento",
            ))
        failed = [c for c in outcomes if not c.passed]
        for c in outcomes:
            checks.append(f"{'✓' if c.passed else '✗'} {c.name}: {c.detail}")
        if failed:
            return reject("; ".join(f"{c.name}: {c.detail}" for c in failed))

        # 4. Corroboración independiente -------------------------------------
        verdict, detail = self._corroborate(node, expr, query, missing_variable, graph)
        checks.append(detail)
        if verdict == Verdict.REJECTED:
            return reject(detail)
        return HypothesisVerdict(
            verdict, node=node, expression=expr.source, reason=detail, checks=checks,
        )

    # -- piezas ------------------------------------------------------------

    @staticmethod
    def _user_message(query, missing, target_quantity, spec, graph) -> str:
        foundations = [
            f"{n.id}: {n.statement}"
            for n in graph
            if n.status in (EpistemicStatus.AXIOM, EpistemicStatus.DEFINITION,
                            EpistemicStatus.THEOREM)
        ]
        variables = {
            name: f"{v.meaning} [{v.dimension.render()}]" for name, v in spec.variables.items()
        }
        return json.dumps({
            "question": query.statement,
            "missing_variable": missing,
            "missing_quantity": target_quantity or variables.get(missing, ""),
            "context_kind": query.context_kind,
            "known_values": query.known,
            "available_variables": variables,
            "available_foundations": foundations,
        }, ensure_ascii=False)

    @staticmethod
    def _expected_dimension(missing, target_quantity, spec, raw) -> tuple[Dimension, str]:
        if missing in spec.variables:
            return spec.variables[missing].dimension, "catálogo"
        from_table = quantity_dimension(target_quantity)
        if from_table is not None:
            return from_table, f"tabla de magnitudes: '{target_quantity}'"
        declared = Dimension.from_mapping(raw.get("output_dimension", {}))
        return declared, "declarada por el LLM — sin comprobación independiente"

    @staticmethod
    def _build_node(raw, expr: SafeExpression, output: str, spec: DomainSpec) -> KnowledgeNode:
        inputs = sorted(expr.variables)

        def compute(values: dict) -> dict:
            return {output: expr.evaluate(values)}

        return KnowledgeNode(
            id=f"hyp.llm.{spec.name}.{output}_from_{'_'.join(inputs) or 'const'}",
            statement=raw.get("statement") or f"{output} = {expr.source}",
            status=EpistemicStatus.HYPOTHESIS,
            kind=NodeKind.RELATION,
            foundations=list(dict.fromkeys(raw.get("foundations", []))),
            compute=compute,
            inputs=inputs,
            outputs=[output],
            rationale=f"propuesta por LLM, verificada por exp_22: {output} = {expr.source}",
        )

    @staticmethod
    def _input_aware_redundancy(candidate: HypothesisCandidate, graph: KnowledgeGraph) -> CheckOutcome:
        """Redefinición del check `not_redundant` del exp_02.

        El exp_02 declara redundante cualquier hipótesis cuya OUTPUT ya
        tenga un productor. Eso rechaza conocimiento necesario: `l = P/4`
        es "redundante" porque existe `l = d/√2`, aunque sin la diagonal
        ese nodo no sirve. Aquí es redundante sólo si ya existe un
        productor de la misma output con el MISMO conjunto de inputs.
        """
        node = candidate.node
        same = [
            n.id for n in graph.find_relations_producing(node.outputs[0])
            if set(n.inputs) == set(node.inputs) and n.id != node.id
        ]
        if same:
            return CheckOutcome(
                name="not_redundant", passed=False,
                detail=f"ya existe un productor con los mismos inputs: {', '.join(same)}",
            )
        return CheckOutcome(
            name="not_redundant", passed=True,
            detail=(
                f"ningún nodo produce {node.outputs} a partir de {node.inputs} "
                f"(criterio por inputs, redefinido en exp_22)"
            ),
        )

    def _corroborate(self, node, expr, query, missing, graph) -> tuple[Verdict, str]:
        problem = Problem(
            statement=query.statement,
            target=missing,
            context=DomainContext(kind=query.context_kind, known=dict(query.known)),
        )
        own = [
            c for c in self.engine.generate(missing, problem, graph)
            if set(c.node.inputs) == set(node.inputs)
        ]
        if not own:
            return (
                Verdict.CONSISTENT,
                "corroboración: ningún patrón propio del sistema deriva esta relación — "
                "queda como hipótesis CONSISTENTE, no corroborada",
            )
        for cand in own:
            for t in self.SAMPLE_POINTS:
                values = {k: t for k in node.inputs}
                mine = cand.node.compute(values)[missing]
                theirs = expr.evaluate(values)
                if not math.isclose(mine, theirs, rel_tol=1e-9, abs_tol=1e-12):
                    return (
                        Verdict.REJECTED,
                        f"contradicción: el patrón propio {cand.pattern_name} "
                        f"({cand.node.id}) da {mine} en {values}, el LLM propone {theirs}",
                    )
        names = ", ".join(c.node.id for c in own)
        return (
            Verdict.CORROBORATED,
            f"corroboración: coincide con la derivación propia del sistema ({names}) "
            f"en {len(self.SAMPLE_POINTS)} puntos de prueba",
        )
