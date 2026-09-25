"""Demo del GapClassifierV2.

Encadena: bootstrap de grafos → EpistemicMapper → GapClassifierV2.
Para las 8 semillas canónicas, muestra:
  - su clasificación (tipo + justificación + ruta de cierre);
  - quién clasificó cada una (engineer vs system);
  - resúmenes por tipo y por autoría.

Uso:
    python -m experiment_05.gap_classifier_v2.demo
"""
from __future__ import annotations

from experiment_05.epistemic_mapper.demo import (
    CANONICAL_QUESTION,
    SEED_CONCEPTS,
    _bootstrap_graphs,
)
from experiment_05.epistemic_mapper import ConceptQuery, EpistemicMapper

from .classifier import GapClassifierV2


def main() -> None:
    graphs = _bootstrap_graphs()
    mapper = EpistemicMapper(max_related=5)
    classifier = GapClassifierV2()

    inventory = mapper.map(
        ConceptQuery.of(CANONICAL_QUESTION, SEED_CONCEPTS),
        graphs,
    )
    results = classifier.classify(inventory)

    print("=" * 72)
    print("CLASIFICACIÓN DE GAPS EPISTÉMICOS")
    print("=" * 72)
    print(f"Pregunta: {inventory.query_text}")
    print(f"Gaps a clasificar: {len(inventory.unknown_concepts)}")
    print(f"Catálogo del ingeniero: {len(classifier.catalogue)} entradas")
    print()

    for r in results:
        print(r.render())
        print()

    print("=" * 72)
    print("RESÚMENES")
    print("=" * 72)
    print(f"  por autoría: {classifier.authorship_summary(results)}")
    print(f"  por tipo:    {classifier.type_summary(results)}")


if __name__ == "__main__":
    main()
