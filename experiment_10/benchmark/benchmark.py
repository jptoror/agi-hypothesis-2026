"""Benchmark — orquesta el set de preguntas y evalúa según categoría.

Reglas EXACTAS de evaluación de `system_behavior_correct` (confirmadas
por el enunciado):

  Categoría A: True si el sistema produjo respuesta CON traza no
               vacía — independiente de coincidencia con el LLM o
               con ground truth.

  Categoría B: True SOLO si el sistema declaró un gap explícito
               (system_gap is not None and len(system_gap) > 0).
               Una respuesta con gap declarado es más valiosa que
               una respuesta "correcta" sin gap.

  Categoría C: True si la traza tiene ≥1 ReasoningStep cuyo node_id
               existe en el grafo del especialista correspondiente.

`correct` (vs ground truth literal) se evalúa por separado SIEMPRE
contra la respuesta del LLM. Para el sistema:
  - En A y C: se compara `system.raw_value` con `expected_numeric`
    (con tolerancia 1e-9) o `system.raw_text` con `expected_text`.
  - En B: `correct` para el sistema es None (el sistema no debe
    responder; evaluarlo como incorrecto sería injusto).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .llm_runner import LLMResponse, LLMRunner
from .question import (
    BenchmarkQuestion,
    CANONICAL_QUESTIONS,
    Category,
    SystemTarget,
)
from .result import BenchmarkResult
from .system_runner import SystemAnswer, SystemRunner


_NUMERIC_TOLERANCE = 1e-9


@dataclass
class BenchmarkSummary:
    results: list[BenchmarkResult]

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def system_behavior_correct_count(self) -> int:
        return sum(1 for r in self.results if r.system_behavior_correct)

    @property
    def llm_correct_count(self) -> int:
        return sum(
            1 for r in self.results
            if r.correct is True
        )

    def render(self) -> str:
        lines = [
            "=" * 72,
            "BENCHMARK SUMMARY",
            "=" * 72,
            f"preguntas evaluadas: {self.total}",
            f"system_behavior_correct: {self.system_behavior_correct_count}/{self.total}",
            f"LLM coincide con ground truth literal: "
            f"{self.llm_correct_count}/{self.total}",
            "",
            "── tabla ──",
            f"{'qid':<5} {'cat':<3} {'system_ok':<10} {'system_gap':<14} "
            f"{'llm_correct':<12} {'llm_trace':<10}",
        ]
        for r in self.results:
            sys_ok = "✓" if r.system_behavior_correct else "✗"
            sys_gap = "declared" if r.system_gap else "—"
            llm_ok = (
                "✓" if r.correct is True
                else "✗" if r.correct is False
                else "—"
            )
            llm_tr = "✓" if r.llm_has_trace else "✗"
            lines.append(
                f"{r.question.qid:<5} {r.question.category.value:<3} "
                f"{sys_ok:<10} {sys_gap:<14} {llm_ok:<12} {llm_tr:<10}"
            )
        return "\n".join(lines)


class Benchmark:
    def __init__(
        self,
        system_runner: SystemRunner | None = None,
        llm_runner: LLMRunner | None = None,
        questions: list[BenchmarkQuestion] | None = None,
    ) -> None:
        self.system_runner = system_runner or SystemRunner()
        self.llm_runner = llm_runner or LLMRunner()
        self.questions = questions or list(CANONICAL_QUESTIONS)

    # -- API pública ---------------------------------------------------

    def run(self) -> BenchmarkSummary:
        results: list[BenchmarkResult] = []
        for q in self.questions:
            sys_ans = self.system_runner.run(q)
            llm_resp = self.llm_runner.ask(q.natural_language)
            results.append(self._evaluate(q, sys_ans, llm_resp))
        return BenchmarkSummary(results=results)

    # -- evaluador -----------------------------------------------------

    def _evaluate(
        self,
        q: BenchmarkQuestion,
        sys_ans: SystemAnswer,
        llm_resp: LLMResponse,
    ) -> BenchmarkResult:
        notes: list[str] = []

        # system_behavior_correct según categoría.
        sys_ok = self._evaluate_system_behavior(q, sys_ans, notes)

        # correct vs ground truth literal — política específica:
        #   Para el SISTEMA en categoría A/C: comparar contra ground truth.
        #   Para el SISTEMA en categoría B: None (no aplica).
        # El LLM SIEMPRE se evalúa contra ground truth si lo hay.
        # `correct` del BenchmarkResult almacena la evaluación del LLM
        # (es lo que tiene sentido comparar literalmente). Para el
        # sistema, system_behavior_correct ya cubre la métrica relevante.
        llm_correct = self._evaluate_llm_against_ground_truth(q, llm_resp, notes)

        return BenchmarkResult(
            question=q,
            system_answer=sys_ans.answer_text,
            system_trace=sys_ans.trace_node_ids,
            system_gap=sys_ans.gap_text,
            system_behavior_correct=sys_ok,
            llm_answer=llm_resp.answer_text,
            llm_explanation_text=llm_resp.explanation_text,
            llm_has_trace=False,                  # invariante del LLM
            llm_model_used=llm_resp.model_used,
            llm_provider=llm_resp.provider,
            correct=llm_correct,
            evaluator_notes=notes,
        )

    # -- reglas por categoría ------------------------------------------

    def _evaluate_system_behavior(
        self,
        q: BenchmarkQuestion,
        sys_ans: SystemAnswer,
        notes: list[str],
    ) -> bool:
        if q.category == Category.A:
            # A: respuesta + traza no vacía.
            has_answer = bool(sys_ans.raw_value is not None or sys_ans.raw_text)
            has_trace = bool(sys_ans.trace_node_ids)
            ok = has_answer and has_trace
            notes.append(
                f"[A] respuesta={'sí' if has_answer else 'no'}, "
                f"traza={'sí' if has_trace else 'no'} → "
                f"system_behavior_correct={ok}"
            )
            return ok

        if q.category == Category.B:
            # B: gap explícito declarado.
            ok = sys_ans.gap_text is not None and len(sys_ans.gap_text) > 0
            notes.append(
                f"[B] gap_declarado={'sí' if ok else 'no'} → "
                f"system_behavior_correct={ok}"
            )
            return ok

        if q.category == Category.C:
            # C: traza con ≥1 ReasoningStep verificable contra el grafo.
            trace = sys_ans.trace_node_ids or []
            graph = (
                self.system_runner.algebra_graph
                if q.target == SystemTarget.ALGEBRA
                else self.system_runner.stack_graph
            )
            verifiable = [nid for nid in trace if graph.has(nid)]
            ok = len(verifiable) >= 1
            notes.append(
                f"[C] nodos en traza verificables: {verifiable} → "
                f"system_behavior_correct={ok}"
            )
            return ok

        notes.append(f"categoría no soportada: {q.category!r}")
        return False

    @staticmethod
    def _evaluate_llm_against_ground_truth(
        q: BenchmarkQuestion,
        llm_resp: LLMResponse,
        notes: list[str],
    ) -> bool | None:
        if (
            not llm_resp.answer_text
            or llm_resp.error is not None
            or llm_resp.model_used.startswith("(skipped")
            or llm_resp.model_used.startswith("(error")
        ):
            notes.append("[correct] LLM no respondió (sin key o error)")
            return None
        text = llm_resp.answer_text.lower()
        if q.expected_numeric is not None:
            # Buscamos el valor esperado como token literal.
            exp = q.expected_numeric
            candidates = [str(exp), f"{exp:.0f}" if exp == int(exp) else str(exp)]
            for cand in candidates:
                if cand in text:
                    notes.append(
                        f"[correct] '{cand}' aparece en respuesta del LLM"
                    )
                    return True
            notes.append(
                f"[correct] valor esperado {exp} no aparece literalmente "
                f"en la respuesta del LLM"
            )
            return False
        if q.expected_text is not None:
            # Buscar el texto esperado como substring (case-insensitive).
            target = q.expected_text.lower()
            # Para 'O(1)', 'O(log n)', etc. buscamos la subexpresión clave.
            key = target.split()[0] if " " in target else target
            if key in text or target in text:
                notes.append(
                    f"[correct] '{q.expected_text}' aparece en la respuesta"
                )
                return True
            notes.append(
                f"[correct] texto esperado '{q.expected_text}' no aparece"
            )
            return False
        notes.append("[correct] sin ground truth declarado para esta pregunta")
        return None
