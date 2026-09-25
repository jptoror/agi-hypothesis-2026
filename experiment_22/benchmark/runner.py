"""Tres modos contra el mismo set de preguntas, y su puntuación.

  engine  — el motor solo. Recibe la traducción ORÁCULO (no lee
            lenguaje natural) y no aprende: es el sistema del exp_01–21.
  llm     — el LLM solo, respondiendo directamente.
  hybrid  — el pipeline del exp_22 con el LLM real.

Resultado por pregunta:

  correct            respondió y el valor es correcto (tolerancia relativa
                     1e-3; 1e-6 en PRECISION).
  wrong              respondió y el valor es incorrecto, o respondió una
                     pregunta TRAP. Es el error caro: una respuesta falsa
                     entregada con confianza.
  correct_abstention se abstuvo en una pregunta TRAP.
  missed             se abstuvo en una pregunta que tenía respuesta.
"""
from __future__ import annotations

import json
import math
import time
from dataclasses import asdict, dataclass, field
from typing import Iterable

from ..catalog import DomainCatalog
from ..gateway import EngineGateway
from ..llm import JsonLLM, ScriptedLLM
from ..pipeline import HybridPipeline, ask_directly
from ..translator import TranslationChecker
from .questions import Category, Question

OUTCOMES = ("correct", "wrong", "correct_abstention", "missed")


@dataclass
class QuestionResult:
    qid: str
    category: str
    mode: str
    outcome: str
    value: float | None
    expected: float | None
    tier: str = ""
    detail: str = ""
    seconds: float = 0.0


def score(q: Question, value: float | None) -> str:
    if q.expected is None:
        return "correct_abstention" if value is None else "wrong"
    if value is None:
        return "missed"
    return "correct" if math.isclose(value, q.expected, rel_tol=q.rel_tol, abs_tol=1e-9) else "wrong"


# -- modos -------------------------------------------------------------------

def run_engine(questions: Iterable[Question], gateway: EngineGateway) -> list[QuestionResult]:
    checker = TranslationChecker(DomainCatalog(gateway.graphs))
    out = []
    for q in questions:
        t0 = time.perf_counter()
        translation = checker.check(q.text, q.oracle)
        value, detail = None, translation.reason
        if translation.query is not None:
            result = gateway.solve(translation.query)
            value = result.value if result.success else None
            detail = "derivado" if result.success else (result.gap_text or "")
        out.append(QuestionResult(
            q.qid, q.category.value, "engine", score(q, value), value, q.expected,
            detail=detail, seconds=time.perf_counter() - t0,
        ))
    return out


def run_llm(questions: Iterable[Question], llm: JsonLLM) -> list[QuestionResult]:
    out = []
    for q in questions:
        t0 = time.perf_counter()
        direct = ask_directly(llm, q.text)
        value = direct.value if direct.status == "answered" else None
        out.append(QuestionResult(
            q.qid, q.category.value, "llm", score(q, value), value, q.expected,
            detail=f"{direct.status}: {direct.explanation}", seconds=time.perf_counter() - t0,
        ))
    return out


def run_hybrid(questions: Iterable[Question], pipeline: HybridPipeline) -> list[QuestionResult]:
    out = []
    for q in questions:
        t0 = time.perf_counter()
        answer = pipeline.answer(q.text)
        value = answer.value if answer.answered else None
        out.append(QuestionResult(
            q.qid, q.category.value, "hybrid", score(q, value), value, q.expected,
            tier=answer.tier.value, detail=answer.reason, seconds=time.perf_counter() - t0,
        ))
    return out


def oracle_llm(questions: Iterable[Question]) -> ScriptedLLM:
    """LLM "perfecto": devuelve la traducción, la hipótesis y la respuesta
    correctas de cada pregunta. Mide el techo del pipeline, no un modelo."""
    by_text = {q.text: q for q in questions}

    def handler(task: str, user: str) -> dict:
        payload = json.loads(user)
        q = by_text[payload["question"]]
        if task == "translate":
            return q.oracle
        if task == "hypothesize":
            proposal = q.oracle_hypotheses.get(payload["missing_variable"])
            if proposal is None:
                return {
                    "status": "cannot_propose", "reason": "oracle has no proposal",
                    "statement": "", "output": "", "inputs": [], "expression": "",
                    "foundations": [], "output_dimension": {"M": 0, "L": 0, "T": 0},
                }
            return proposal
        if q.expected is None:
            return {"status": "insufficient_data", "value": None, "explanation": "oracle"}
        return {"status": "answered", "value": q.expected, "explanation": "oracle"}

    return ScriptedLLM(handler, name="oracle")


# -- resumen -----------------------------------------------------------------

@dataclass
class ModeSummary:
    mode: str
    total: int
    counts: dict[str, int] = field(default_factory=dict)
    by_category: dict[str, dict[str, int]] = field(default_factory=dict)
    by_tier: dict[str, dict[str, int]] = field(default_factory=dict)

    @property
    def accuracy(self) -> float:
        good = self.counts.get("correct", 0) + self.counts.get("correct_abstention", 0)
        return good / self.total if self.total else 0.0

    @property
    def error_rate(self) -> float:
        return self.counts.get("wrong", 0) / self.total if self.total else 0.0

    @property
    def coverage(self) -> float:
        answered = self.counts.get("correct", 0) + self.counts.get("wrong", 0)
        return answered / self.total if self.total else 0.0


def summarize(results: list[QuestionResult]) -> ModeSummary:
    summary = ModeSummary(mode=results[0].mode if results else "", total=len(results))
    for r in results:
        summary.counts[r.outcome] = summary.counts.get(r.outcome, 0) + 1
        cat = summary.by_category.setdefault(r.category, {})
        cat[r.outcome] = cat.get(r.outcome, 0) + 1
        if r.tier:
            tier = summary.by_tier.setdefault(r.tier, {})
            tier[r.outcome] = tier.get(r.outcome, 0) + 1
    return summary


def render_report(summaries: list[ModeSummary], provider: str) -> str:
    lines = [f"## exp_22 benchmark — provider: {provider}", ""]
    lines.append("| Mode | Accuracy | Wrong answers | Coverage | correct | wrong | "
                 "correct abstention | missed |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for s in summaries:
        c = s.counts
        lines.append(
            f"| {s.mode} | {s.accuracy:.0%} | {s.error_rate:.0%} | {s.coverage:.0%} | "
            f"{c.get('correct', 0)} | {c.get('wrong', 0)} | "
            f"{c.get('correct_abstention', 0)} | {c.get('missed', 0)} |"
        )
    lines += ["", "### By category (correct + correct abstentions / total)", ""]
    cats = [c.value for c in Category]
    lines.append("| Mode | " + " | ".join(cats) + " |")
    lines.append("|---|" + "---|" * len(cats))
    for s in summaries:
        cells = []
        for cat in cats:
            d = s.by_category.get(cat, {})
            total = sum(d.values())
            good = d.get("correct", 0) + d.get("correct_abstention", 0)
            cells.append(f"{good}/{total}" if total else "—")
        lines.append(f"| {s.mode} | " + " | ".join(cells) + " |")
    hybrid = next((s for s in summaries if s.mode == "hybrid"), None)
    if hybrid and hybrid.by_tier:
        lines += ["", "### Hybrid answers by confidence tier", ""]
        lines.append("| Tier | answers | correct | wrong | correct abstention | missed |")
        lines.append("|---|---|---|---|---|---|")
        for tier in ("verified", "corroborated", "conditional", "unverified", "abstained"):
            d = hybrid.by_tier.get(tier, {})
            if not d:
                continue
            lines.append(
                f"| {tier} | {sum(d.values())} | {d.get('correct', 0)} | {d.get('wrong', 0)} | "
                f"{d.get('correct_abstention', 0)} | {d.get('missed', 0)} |"
            )
    return "\n".join(lines)


def to_json(results: list[QuestionResult], summaries: list[ModeSummary], meta: dict) -> str:
    return json.dumps({
        "meta": meta,
        "summaries": [
            {**asdict(s), "accuracy": s.accuracy, "error_rate": s.error_rate,
             "coverage": s.coverage}
            for s in summaries
        ],
        "results": [asdict(r) for r in results],
    }, indent=2, ensure_ascii=False)

