"""Demo del LanguageSpecialist con la instrucción canónica del exp_07.

Uso:
    python -m experiment_07.specialist.demo
"""
from __future__ import annotations

from experiment_07.knowledge_graph import build_spanish_base_graph

from .language_specialist import LanguageSpecialist


CANONICAL_INSTRUCTION = "resuelve x para a=3, b=6"


def main() -> None:
    graph = build_spanish_base_graph()
    specialist = LanguageSpecialist(graph)
    result = specialist.parse(CANONICAL_INSTRUCTION)
    print(f"Input: {CANONICAL_INSTRUCTION!r}\n")
    print(result.render())


if __name__ == "__main__":
    main()
