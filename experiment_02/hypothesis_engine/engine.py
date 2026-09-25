from __future__ import annotations

from experiment_01.knowledge_graph import KnowledgeGraph
from experiment_01.specialist import Problem

from .candidate import HypothesisCandidate
from .patterns.base import Pattern
from .patterns.sum_of_equal_parts import SumOfEqualParts


class HypothesisEngine:
    """Motor que aplica un conjunto de patrones estructurales.

    El engine NO inventa teoremas: invoca cada patrón registrado sobre el
    gap y devuelve los candidatos ordenados por score ascendente (menor
    es mejor). La decisión de adoptar un candidato queda para componentes
    posteriores del experimento (validator, consolidation, orchestrator).
    """

    def __init__(self, patterns: list[Pattern] | None = None) -> None:
        # Por defecto cargamos sólo SumOfEqualParts — el único patrón
        # validado para el caso del perímetro. Los demás se añadirán
        # cuando un caso real los exija.
        self.patterns: list[Pattern] = patterns if patterns is not None else [
            SumOfEqualParts(),
        ]

    def generate(
        self,
        missing_variable: str,
        problem: Problem,
        graph: KnowledgeGraph,
    ) -> list[HypothesisCandidate]:
        all_candidates: list[HypothesisCandidate] = []
        for pattern in self.patterns:
            all_candidates.extend(
                pattern.propose(missing_variable, problem, graph)
            )

        # Orden estable por score ascendente; empate por nombre de patrón
        # para trazabilidad determinista.
        all_candidates.sort(key=lambda c: (c.rank_score, c.pattern_name, c.node.id))
        return all_candidates
