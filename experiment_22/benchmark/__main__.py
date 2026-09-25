"""CLI del benchmark del exp_22.

    # Techo del pipeline con un LLM "perfecto" (offline, sin API key):
    python -m experiment_22.benchmark --provider oracle

    # Contra un LLM real:
    export ANTHROPIC_API_KEY=...      # o: ant auth login
    python -m experiment_22.benchmark --provider claude --out experiment_22/results/claude.json

    export GOOGLE_API_KEY=...
    python -m experiment_22.benchmark --provider gemini --out experiment_22/results/gemini.json

Opciones: --modes engine,llm,hybrid  --only LEARN,TRAP  --limit 10  --model <id>
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ..gateway import EngineGateway
from ..llm import LLMUnavailable, build_llm
from ..pipeline import HybridPipeline
from .questions import QUESTIONS
from .runner import (
    oracle_llm,
    render_report,
    run_engine,
    run_hybrid,
    run_llm,
    summarize,
    to_json,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m experiment_22.benchmark")
    parser.add_argument("--provider", default="oracle", choices=["oracle", "claude", "gemini"])
    parser.add_argument("--model", default=None)
    parser.add_argument("--modes", default="engine,llm,hybrid")
    parser.add_argument("--only", default="", help="categorías separadas por coma")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--out", default="", help="ruta de salida JSON")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    questions = list(QUESTIONS)
    if args.only:
        wanted = {c.strip().upper() for c in args.only.split(",")}
        questions = [q for q in questions if q.category.value in wanted]
    if args.limit:
        questions = questions[: args.limit]

    modes = [m.strip() for m in args.modes.split(",") if m.strip()]
    if args.provider == "oracle":
        llm = oracle_llm(QUESTIONS)
        # El modo llm contra un oráculo es trivialmente 100%: no mide nada.
        modes = [m for m in modes if m != "llm"]
    else:
        try:
            llm = build_llm(args.provider, args.model)
        except LLMUnavailable as e:
            print(f"error: {e}", file=sys.stderr)
            return 2

    gateway = EngineGateway()
    all_results = []
    summaries = []
    for mode in modes:
        print(f"· corriendo modo '{mode}' sobre {len(questions)} preguntas...", file=sys.stderr)
        if mode == "engine":
            results = run_engine(questions, gateway)
        elif mode == "llm":
            results = run_llm(questions, llm)
        elif mode == "hybrid":
            results = run_hybrid(questions, HybridPipeline(llm, gateway=gateway))
        else:
            print(f"error: modo desconocido '{mode}'", file=sys.stderr)
            return 2
        all_results += results
        summaries.append(summarize(results))

    print(render_report(summaries, getattr(llm, "name", args.provider)))
    if args.verbose:
        print("\n### Per question\n")
        for r in all_results:
            print(f"- [{r.mode}] {r.qid} {r.outcome} value={r.value} expected={r.expected} "
                  f"{r.tier} — {r.detail[:140]}")
    if args.out:
        path = Path(args.out)
        path.parent.mkdir(parents=True, exist_ok=True)
        meta = {"provider": getattr(llm, "name", args.provider), "questions": len(questions),
                "modes": modes}
        path.write_text(to_json(all_results, summaries, meta), encoding="utf-8")
        print(f"\nresultados guardados en {path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
