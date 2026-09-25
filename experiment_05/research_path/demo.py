"""Demo del ResearchPathProposer.

Encadena: bootstrap de grafos → EpistemicMapper → GapClassifierV2 →
ResearchPathProposer. Para las 8 semillas canónicas, muestra:
  - cada propuesta con su feasibility, acción (o None) y complejidad;
  - resúmenes por feasibility y proporción accionable.

Uso:
    python -m experiment_05.research_path.demo
"""
from __future__ import annotations

from experiment_05.epistemic_mapper.demo import (
    CANONICAL_QUESTION,
    SEED_CONCEPTS,
    _bootstrap_graphs,
)
from experiment_05.epistemic_mapper import ConceptQuery, EpistemicMapper
from experiment_05.gap_classifier_v2 import GapClassifierV2

from .proposer import ResearchPathProposer


def main() -> None:
    graphs = _bootstrap_graphs()
    mapper = EpistemicMapper(max_related=5)
    classifier = GapClassifierV2()
    proposer = ResearchPathProposer()

    inventory = mapper.map(
        ConceptQuery.of(CANONICAL_QUESTION, SEED_CONCEPTS),
        graphs,
    )
    classifications = classifier.classify(inventory)
    proposals = proposer.propose_all(classifications)

    print("=" * 72)
    print("PROPUESTAS DE INVESTIGACIÓN")
    print("=" * 72)
    print(f"Pregunta: {inventory.query_text}")
    print(f"Gaps clasificados: {len(classifications)}")
    print()

    for p in proposals:
        print(p.render())
        print()

    print("=" * 72)
    print("RESÚMENES")
    print("=" * 72)
    print(f"  por feasibility: {ResearchPathProposer.feasibility_summary(proposals)}")
    print(
        f"  accionables: {ResearchPathProposer.actionable_count(proposals)}"
        f"/{len(proposals)}"
    )
    print(
        f"  no accionables (proposed_action=None): "
        f"{sum(1 for p in proposals if p.proposed_action is None)}"
    )


if __name__ == "__main__":
    main()
