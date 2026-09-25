"""Demo del benchmark — corre las 5 preguntas canónicas con el
provider de LLM disponible.

Detección automática (en orden de preferencia):
  1. GOOGLE_API_KEY  → GeminiRunner (gemini-1.5-flash)
  2. ANTHROPIC_API_KEY → LLMRunner (claude-sonnet-4-*)
  3. ninguna → LLM saltado (el lado del sistema se ejercita igual)

La preferencia por Gemini cuando AMBAS keys están presentes es
arbitraria (alfabética). Si quieres usar Anthropic explícitamente
con ambas keys disponibles, exporta `BENCHMARK_PROVIDER=anthropic`
antes de correr el demo.

Uso:
    python -m experiment_10.benchmark.demo
"""
from __future__ import annotations

import os

from .benchmark import Benchmark
from .llm_runner import GeminiRunner, LLMRunner


def _select_runner():
    """Elige el runner según las API keys disponibles.

    Devuelve un runner instanciado (siempre uno — si no hay key,
    devolvemos un LLMRunner que se reportará como saltado).
    """
    forced = os.environ.get("BENCHMARK_PROVIDER", "").lower().strip()
    google_key = os.environ.get("GOOGLE_API_KEY")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")

    if forced == "anthropic":
        return LLMRunner(), "anthropic (forzado)"
    if forced == "gemini":
        return GeminiRunner(api_key=google_key), "gemini (forzado)"

    # Detección automática por orden de preferencia.
    if google_key:
        return GeminiRunner(api_key=google_key), "gemini (auto)"
    if anthropic_key:
        return LLMRunner(), "anthropic (auto)"
    # Sin keys: devolvemos LLMRunner que se reportará como saltado.
    return LLMRunner(), "saltado (sin API keys)"


def main() -> None:
    runner, mode = _select_runner()
    print(f"LLM provider: {mode}")
    print(f"LLM disponible: {runner.is_available}")
    print()

    bench = Benchmark(llm_runner=runner)
    summary = bench.run()
    for r in summary.results:
        print(r.render())
        print()
    print(summary.render())


if __name__ == "__main__":
    main()
