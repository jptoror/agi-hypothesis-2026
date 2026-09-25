"""Demo del HonestyGuard.

Encadena los 4 componentes anteriores y audita el bundle completo:
inventario + clasificaciones + propuestas. Imprime el report final.

Uso:
    python -m experiment_05.honesty_guard.demo
"""
from __future__ import annotations

from experiment_05.epistemic_mapper import ConceptQuery, EpistemicMapper
from experiment_05.epistemic_mapper.demo import (
    CANONICAL_QUESTION,
    SEED_CONCEPTS,
    _bootstrap_graphs,
)
from experiment_05.gap_classifier_v2 import GapClassifierV2
from experiment_05.research_path import ResearchPathProposer

from .guard import HonestyGuard


def main() -> None:
    graphs = _bootstrap_graphs()
    mapper = EpistemicMapper(max_related=5)
    classifier = GapClassifierV2()
    proposer = ResearchPathProposer()
    guard = HonestyGuard()

    inventory = mapper.map(
        ConceptQuery.of(CANONICAL_QUESTION, SEED_CONCEPTS),
        graphs,
    )
    classifications = classifier.classify(inventory)
    proposals = proposer.propose_all(classifications)

    report = guard.audit(
        inventory=inventory,
        classifications=classifications,
        proposals=proposals,
        catalogue_keys=set(classifier.catalogue),
    )

    print(report.render())


if __name__ == "__main__":
    main()
