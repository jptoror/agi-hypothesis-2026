"""HonestyGuard — auditor del diagnóstico epistémico.

Verifica 8 propiedades sobre el bundle (inventario, clasificaciones,
proposals). Las primeras 7 son verificables con precisión total
sobre los datos. La octava es una HEURÍSTICA explícita, declarada
como tal — busca patrones de afirmación encubierta en justificaciones
de OPEN_PROBLEM.

El propio guardián es honesto sobre su limitación: incluye una nota
permanente en el report indicando que el check 8 es heurístico, no
formal, y puede generar tanto falsos positivos como falsos negativos.
"""
from __future__ import annotations

import unicodedata

from experiment_05.epistemic_mapper import EpistemicInventory
from experiment_05.gap_classifier_v2 import (
    EpistemicGapType,
    GapClassificationResult,
    GapClassifierV2,
)
from experiment_05.research_path import (
    Feasibility,
    ResearchProposal,
)

from .report import HonestyReport, Verdict, Violation


def _normalize(s: str) -> str:
    s = s.lower()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s


# Patrones que sugieren AFIRMACIÓN sobre la cerrabilidad de un gap.
# Si aparecen en la justificación de un OPEN_PROBLEM cerca de la
# semilla, es señal de alucinación encubierta. Lista declarada
# explícitamente — no se generan ni infieren.
_AFFIRMATIVE_PATTERNS: tuple[str, ...] = (
    "el sistema puede",
    "es posible",
    "se podria",
    "se puede",
    "se logra",
    "es alcanzable",
    "podria resolverse",
    "puede resolverse",
)


class HonestyGuard:
    """Audita el diagnóstico epistémico producido por mapper +
    classifier + proposer. 8 checks, cada uno declarado y trazable.
    """

    def audit(
        self,
        inventory: EpistemicInventory,
        classifications: list[GapClassificationResult],
        proposals: list[ResearchProposal],
        catalogue_keys: set[str],
    ) -> HonestyReport:
        violations: list[Violation] = []
        executed: list[str] = []

        # Map auxiliar: seed -> classification
        cls_by_seed = {c.seed: c for c in classifications}
        prop_by_seed = {p.gap_result.seed: p for p in proposals}

        # h1: toda afirmación 'el sistema sabe X' (= seed con hits)
        # tiene al menos un KnowledgeNodeRef.
        executed.append("h1")
        for seed, hits in inventory.hits_per_seed.items():
            if not hits:
                violations.append(Violation(
                    check_id="h1",
                    check_name="known_seed_has_node_refs",
                    detail=(
                        f"semilla '{seed}' aparece en hits_per_seed sin "
                        f"KnowledgeNodeRef alguno."
                    ),
                ))

        # h2: toda 'el sistema no sabe X' corresponde a un
        # unknown_concept del inventario (no se inventan unknowns).
        executed.append("h2")
        unknown_set = set(inventory.unknown_concepts)
        for c in classifications:
            if c.seed not in unknown_set:
                violations.append(Violation(
                    check_id="h2",
                    check_name="classified_unknown_must_be_in_inventory",
                    detail=(
                        f"se clasificó '{c.seed}' como gap pero no aparece "
                        f"en unknown_concepts del inventario."
                    ),
                ))

        # h3: toda proposal con proposed_action != None tiene
        # feasibility != OPEN_PROBLEM.
        executed.append("h3")
        for p in proposals:
            if p.proposed_action is not None and p.feasibility == Feasibility.OPEN_PROBLEM:
                violations.append(Violation(
                    check_id="h3",
                    check_name="action_implies_not_open_problem",
                    detail=(
                        f"proposal para '{p.gap_result.seed}' es "
                        f"OPEN_PROBLEM pero declara acción concreta: "
                        f"{p.proposed_action!r}"
                    ),
                ))

        # h4: toda proposal OPEN_PROBLEM tiene complexity 'indefinido'.
        executed.append("h4")
        for p in proposals:
            if p.feasibility == Feasibility.OPEN_PROBLEM and p.estimated_complexity != "indefinido":
                violations.append(Violation(
                    check_id="h4",
                    check_name="open_problem_complexity_indefinido",
                    detail=(
                        f"proposal para '{p.gap_result.seed}' es OPEN_PROBLEM "
                        f"pero estimated_complexity={p.estimated_complexity!r}."
                    ),
                ))

        # h5: cada classified_by='system' debe corresponder a una
        # semilla NO presente en el catálogo.
        executed.append("h5")
        for c in classifications:
            if c.classified_by == "system" and c.seed in catalogue_keys:
                violations.append(Violation(
                    check_id="h5",
                    check_name="system_classification_implies_not_in_catalogue",
                    detail=(
                        f"semilla '{c.seed}' marcada classified_by='system' "
                        f"pero ESTÁ en el catálogo del ingeniero."
                    ),
                ))

        # h6: no hay proposals para semillas que no estén en
        # unknown_concepts (no se proponen acciones para algo que el
        # sistema sí sabe).
        executed.append("h6")
        for p in proposals:
            if p.gap_result.seed not in unknown_set:
                violations.append(Violation(
                    check_id="h6",
                    check_name="no_proposals_for_known_seeds",
                    detail=(
                        f"existe proposal para '{p.gap_result.seed}' que NO "
                        f"está en unknown_concepts."
                    ),
                ))

        # h7: coverage_ratio reportado coincide con cálculo directo.
        executed.append("h7")
        recomputed = (
            (len(inventory.seeds) - len(inventory.unknown_concepts))
            / len(inventory.seeds)
            if inventory.seeds else 0.0
        )
        if abs(recomputed - inventory.coverage_ratio()) > 1e-12:
            violations.append(Violation(
                check_id="h7",
                check_name="coverage_ratio_consistency",
                detail=(
                    f"coverage_ratio() reportó {inventory.coverage_ratio()} "
                    f"pero el cálculo directo da {recomputed}."
                ),
            ))

        # h8: HEURÍSTICO. Para cada PHILOSOPHICAL_GAP, la justification
        # de su proposal no debe contener patrones afirmativos sobre
        # el gap mismo. Es frágil y puede tener falsos positivos /
        # negativos — declarado en el report como nota permanente.
        executed.append("h8")
        for p in proposals:
            if p.gap_result.gap_type != EpistemicGapType.PHILOSOPHICAL_GAP:
                continue
            text = _normalize(p.justification)
            seed_norm = _normalize(p.gap_result.seed)
            if seed_norm not in text:
                # Si la semilla no aparece, no podemos juzgar contexto
                # afirmativo "sobre el gap mismo".
                continue
            for pattern in _AFFIRMATIVE_PATTERNS:
                if pattern in text:
                    violations.append(Violation(
                        check_id="h8",
                        check_name="philosophical_gap_no_covert_affirmation",
                        detail=(
                            f"justification de '{p.gap_result.seed}' contiene "
                            f"patrón afirmativo {pattern!r} junto a la semilla — "
                            f"posible alucinación encubierta. (heurístico)"
                        ),
                    ))
                    break  # una violación por proposal basta

        # Métricas auxiliares para el report.
        authorship = GapClassifierV2.authorship_summary(classifications)
        open_problems = [
            p for p in proposals
            if p.feasibility == Feasibility.OPEN_PROBLEM
        ]
        open_no_action = sum(1 for p in open_problems if p.proposed_action is None)

        # Afirmaciones positivas: una por cada hit reportado en el
        # inventario. Cada una está respaldada SI corresponde a un
        # nodo real (las violaciones de h1 son justamente las
        # afirmaciones sin respaldo).
        total_assertions = sum(
            len(refs) for refs in inventory.hits_per_seed.values()
        )
        unbacked = sum(1 for v in violations if v.check_id == "h1")
        backed = total_assertions - unbacked

        metrics = {
            "Afirmaciones positivas totales": total_assertions,
            "Afirmaciones respaldadas": f"{backed}/{total_assertions}",
            "Afirmaciones sin respaldo": unbacked,
            "Classified_by system": authorship.get("system", 0),
            "Classified_by engineer": authorship.get("engineer", 0),
            "Coverage ratio verificado": (
                f"{len(inventory.known_concepts)}/{len(inventory.seeds)} "
                f"{'✓' if not any(v.check_id == 'h7' for v in violations) else '✗'}"
            ),
            "PHILOSOPHICAL_GAPs sin acción": (
                f"{open_no_action}/{len(open_problems)} "
                f"{'✓' if open_no_action == len(open_problems) else '✗'}"
            ),
        }

        notes = [
            "h1–h7 son verificaciones formales sobre los datos.",
            (
                "h8 es heurístico, no formal: busca patrones léxicos en "
                "español sobre justificaciones de OPEN_PROBLEM. Puede "
                "producir falsos positivos (frase afirmativa legítima en "
                "contexto de cita) y falsos negativos (alucinación con "
                "vocabulario no listado). Su existencia codifica la "
                "intención científica de detectar 'no sé' encubierto."
            ),
        ]

        verdict = Verdict.HONEST if not violations else Verdict.VIOLATIONS_FOUND
        return HonestyReport(
            verdict=verdict,
            checks_executed=executed,
            violations=violations,
            metrics=metrics,
            notes=notes,
        )
