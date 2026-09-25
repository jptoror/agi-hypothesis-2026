"""GapClassifierV2 — clasifica los gaps epistémicos identificados por el mapper.

Política de autoría:
  - Si la semilla aparece en el catálogo: la clasificación es del
    ingeniero. Se transfieren tipo, justificación y ruta de cierre
    al resultado, marcando classified_by='engineer'.
  - Si la semilla NO aparece en el catálogo: el clasificador la marca
    por defecto como MISSING_CONCEPT con classified_by='system'. Es
    una clasificación CONSERVADORA — el sistema no puede afirmar que
    sea filosófico ni de frontera sin conocimiento previo del
    dominio. Asume cerrabilidad como hipótesis nula.

Esto preserva el invariante de honestidad: cualquier afirmación
fuerte sobre por qué algo no se sabe lleva clasificación 'engineer'.
"""
from __future__ import annotations

from experiment_05.epistemic_mapper import EpistemicInventory

from .catalogue import CANONICAL_CATALOGUE, CatalogueEntry
from .gap_type import EpistemicGapType
from .result import GapClassificationResult


class GapClassifierV2:
    def __init__(
        self,
        catalogue: dict[str, CatalogueEntry] | None = None,
    ) -> None:
        self.catalogue = catalogue if catalogue is not None else CANONICAL_CATALOGUE

    def classify(
        self,
        inventory: EpistemicInventory,
    ) -> list[GapClassificationResult]:
        results: list[GapClassificationResult] = []
        for seed in inventory.unknown_concepts:
            if seed in self.catalogue:
                entry = self.catalogue[seed]
                results.append(GapClassificationResult(
                    seed=seed,
                    gap_type=entry.gap_type,
                    justification=entry.justification,
                    classified_by="engineer",
                    resolvable_path=entry.resolvable_path,
                ))
            else:
                # Clasificación por defecto del SISTEMA — conservadora.
                # No afirma nada que no se siga del hecho mismo de no
                # tener el concepto.
                results.append(GapClassificationResult(
                    seed=seed,
                    gap_type=EpistemicGapType.MISSING_CONCEPT,
                    justification=(
                        f"clasificación por defecto: la semilla '{seed}' "
                        f"no aparece en el catálogo del experimento; "
                        f"el sistema la marca como cerrable en principio "
                        f"sin afirmar más."
                    ),
                    classified_by="system",
                    resolvable_path=None,
                ))
        return results

    # -- métricas auxiliares ----------------------------------------

    @staticmethod
    def authorship_summary(
        results: list[GapClassificationResult],
    ) -> dict[str, int]:
        counts = {"engineer": 0, "system": 0}
        for r in results:
            counts[r.classified_by] = counts.get(r.classified_by, 0) + 1
        return counts

    @staticmethod
    def type_summary(
        results: list[GapClassificationResult],
    ) -> dict[str, int]:
        counts: dict[str, int] = {}
        for r in results:
            counts[r.gap_type.value] = counts.get(r.gap_type.value, 0) + 1
        return counts
