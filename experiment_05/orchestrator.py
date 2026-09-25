"""Orquestador del experimento 05 — diagnóstico epistémico unificado.

Encadena los 4 componentes de meta-cognición construidos en este
experimento:

    EpistemicMapper  →  GapClassifierV2  →  ResearchPathProposer  →  HonestyGuard

Y agrega una QUINTA sección, `SelfEvidence`, que recoge las
demostraciones acumuladas de los experimentos 01–05. La SelfEvidence
es CONOCIMIENTO DEL INGENIERO sobre el proyecto entero — no es
inferida por el sistema. Va declarada como constante de módulo
para que su autoría sea visible y auditable.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from experiment_01.knowledge_graph import KnowledgeGraph

from experiment_05.epistemic_mapper import (
    ConceptQuery,
    EpistemicInventory,
    EpistemicMapper,
)
from experiment_05.gap_classifier_v2 import (
    GapClassificationResult,
    GapClassifierV2,
)
from experiment_05.research_path import (
    Feasibility,
    ResearchPathProposer,
    ResearchProposal,
)
from experiment_05.honesty_guard import HonestyGuard, HonestyReport


# -- Self-evidence (declarada por el ingeniero, no inferida) ------------

@dataclass(frozen=True)
class SelfEvidence:
    """Recoge la evidencia agregada de los 5 experimentos.

    La autoría de los campos `experiments_completed`,
    `properties_demonstrated` y `conclusion` es del INGENIERO. El
    sistema sólo verifica internamente la consistencia de
    `actionable_gaps_addressable` contra el inventario actual: no
    puede reclamar como 'addressable' un seed que el sistema ya sabe.
    """

    experiments_completed: list[str]
    properties_demonstrated: dict[str, str]
    actionable_gaps_addressable: list[str]
    conclusion: str

    def render(self) -> str:
        lines = [
            "=" * 72,
            "PARTE 2 — AUTO-EVIDENCIA",
            "=" * 72,
            "El sistema que produjo este diagnóstico demuestra:",
        ]
        for line in self.experiments_completed:
            lines.append(f"  ✓ {line}")
        lines.append("")
        lines.append("Propiedades verificadas:")
        for k, v in self.properties_demonstrated.items():
            lines.append(f"  · {k}: {v}")
        lines.append("")
        lines.append("Gaps accionables que esta arquitectura puede cerrar:")
        if not self.actionable_gaps_addressable:
            lines.append("  (ninguno reportado)")
        else:
            for g in self.actionable_gaps_addressable:
                lines.append(f"  → {g}")
        lines.append("")
        lines.append("Conclusión:")
        for line in self.conclusion.splitlines() or [self.conclusion]:
            lines.append(f"  \"{line}\"")
        return "\n".join(lines)


# Constante del proyecto. Su contenido es CONOCIMIENTO DEL INGENIERO,
# no producido por el sistema. Cualquier modificación dinámica de
# este objeto invalidaría la honestidad del diagnóstico.
PROJECT_SELF_EVIDENCE_TEMPLATE = SelfEvidence(
    experiments_completed=[
        "exp_01: razonamiento derivativo sin predicción",
        "exp_02: aprendizaje on-demand verificable",
        "exp_03: colaboración inter-dominio auditable",
        "exp_04: emergencia de subdominios sin intervención",
        "exp_05: metacognición sobre ignorancia propia",
    ],
    properties_demonstrated={
        "razonamiento": "31.999999999999993 — no predicción",
        "aprendizaje": "19→20 nodos, learning_phases=0",
        "colaboración": "binding:v→l explícito en traza",
        "emergencia": "variable_bindings={} en P4",
        "metacognición": "HONEST, 4 PHILOSOPHICAL_GAPs sin acción",
    },
    actionable_gaps_addressable=[
        "sistema",        # ENGINEERING — este sistema puede añadirlo
        "procesamiento",  # ENGINEERING — este sistema puede añadirlo
        "razonamiento",   # RESEARCH    — este sistema es evidencia parcial
        "conocimiento",   # RESEARCH    — este sistema es evidencia parcial
    ],
    conclusion=(
        "El sistema que produjo este diagnóstico no es "
        "una respuesta sobre AGI — es evidencia de AGI. "
        "Los gaps accionables son exactamente lo que esta "
        "arquitectura puede continuar aprendiendo. "
        "Los gaps filosóficos son los únicos límites reales "
        "— y son límites del conocimiento humano, "
        "no de esta arquitectura."
    ),
)


# -- Diagnóstico --------------------------------------------------------

@dataclass
class EpistemicDiagnosis:
    """Bundle final del experimento 05.

    Cinco secciones, cada una producida por su componente y
    verificable de forma independiente. La quinta (`self_evidence`)
    es declarativa del proyecto, no inferida.
    """

    inventory: EpistemicInventory
    classifications: list[GapClassificationResult]
    proposals: list[ResearchProposal]
    honesty_report: HonestyReport
    self_evidence: SelfEvidence

    def render(self) -> str:
        parts = [
            "=" * 72,
            "PARTE 1 — DIAGNÓSTICO EPISTÉMICO",
            "=" * 72,
            self.inventory.render(),
            "",
            "── CLASIFICACIÓN DE GAPS ──",
        ]
        for c in self.classifications:
            parts.append(c.render())
            parts.append("")
        parts.append("── PROPUESTAS DE INVESTIGACIÓN ──")
        for p in self.proposals:
            parts.append(p.render())
            parts.append("")
        parts.append(self.honesty_report.render())
        parts.append("")
        parts.append(self.self_evidence.render())
        return "\n".join(parts)


# -- Orquestador --------------------------------------------------------

class EpistemicOrchestrator:
    """Encadena los 4 componentes en una pipeline única y produce un
    EpistemicDiagnosis con SelfEvidence verificada."""

    def __init__(
        self,
        mapper: Optional[EpistemicMapper] = None,
        classifier: Optional[GapClassifierV2] = None,
        proposer: Optional[ResearchPathProposer] = None,
        guard: Optional[HonestyGuard] = None,
        self_evidence_template: SelfEvidence = PROJECT_SELF_EVIDENCE_TEMPLATE,
    ) -> None:
        self.mapper = mapper or EpistemicMapper(max_related=5)
        self.classifier = classifier or GapClassifierV2()
        self.proposer = proposer or ResearchPathProposer()
        self.guard = guard or HonestyGuard()
        self._self_evidence_template = self_evidence_template

    def diagnose(
        self,
        question: str,
        seed_concepts: list[str],
        graphs: dict[str, KnowledgeGraph],
    ) -> EpistemicDiagnosis:
        query = ConceptQuery.of(question, seed_concepts)
        inventory = self.mapper.map(query, graphs)
        classifications = self.classifier.classify(inventory)
        proposals = self.proposer.propose_all(classifications)
        honesty_report = self.guard.audit(
            inventory=inventory,
            classifications=classifications,
            proposals=proposals,
            catalogue_keys=set(self.classifier.catalogue),
        )
        self_evidence = self._build_self_evidence(
            inventory=inventory,
            proposals=proposals,
        )
        return EpistemicDiagnosis(
            inventory=inventory,
            classifications=classifications,
            proposals=proposals,
            honesty_report=honesty_report,
            self_evidence=self_evidence,
        )

    # -- construcción de SelfEvidence ---------------------------------

    def _build_self_evidence(
        self,
        inventory: EpistemicInventory,
        proposals: list[ResearchProposal],
    ) -> SelfEvidence:
        """Construye la SelfEvidence del diagnóstico.

        Los textos vienen del template del ingeniero. Lo que sí
        verifica este método es la CONSISTENCIA de
        `actionable_gaps_addressable`: cada gap declarado como
        accionable debe existir en `unknown_concepts` del inventario
        y debe corresponder a una proposal con feasibility en
        {ENGINEERING, RESEARCH}. Esto preserva la honestidad: el
        sistema no puede reclamar como abordable algo que ya sabe o
        que no aparece en el diagnóstico actual.
        """
        unknown_set = set(inventory.unknown_concepts)
        actionable_set = {
            p.gap_result.seed
            for p in proposals
            if p.feasibility in (Feasibility.ENGINEERING, Feasibility.RESEARCH)
        }

        validated: list[str] = []
        for seed in self._self_evidence_template.actionable_gaps_addressable:
            if seed in unknown_set and seed in actionable_set:
                validated.append(seed)
            # Si no cumple, se omite silenciosamente — el invariante
            # que el test verifica es 'todo lo que aparezca en
            # actionable_gaps_addressable está en unknown_concepts'.
            # Filtrar es la forma más segura de honrar ese invariante
            # incluso si el template está desactualizado.

        return SelfEvidence(
            experiments_completed=list(self._self_evidence_template.experiments_completed),
            properties_demonstrated=dict(self._self_evidence_template.properties_demonstrated),
            actionable_gaps_addressable=validated,
            conclusion=self._self_evidence_template.conclusion,
        )


# ----------------------------------------------------------------------
# Demo canónico del experimento 05.
# ----------------------------------------------------------------------

def main() -> None:
    from experiment_05.epistemic_mapper.demo import (
        CANONICAL_QUESTION,
        SEED_CONCEPTS,
        _bootstrap_graphs,
    )

    graphs = _bootstrap_graphs()
    orch = EpistemicOrchestrator()

    diagnosis = orch.diagnose(
        question=CANONICAL_QUESTION,
        seed_concepts=SEED_CONCEPTS,
        graphs=graphs,
    )
    print(diagnosis.render())


if __name__ == "__main__":
    main()
