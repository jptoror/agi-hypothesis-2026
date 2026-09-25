"""ClarificationResolver — evalúa si el contexto disponible basta
para continuar el pipeline ante un concepto no reconocido.

Algoritmo (5 pasos, todos auditables):

  1. Si available_context['domain'] está declarado por el caller →
     SUFFICIENT(domain). El caller ya zanjó la ambigüedad.

  2. Buscar especialistas del bus que 'conocen' el concepto:
        knows(specialist, concept) ≡
            existe nodo n en specialist.graph tal que
            normalize(concept) in normalize(n.id)
     (criterio A acordado: lookup por substring sobre ids,
      normalizando lowercase + sin tildes).
     Excluir explícitamente al especialista iniciador del pipeline
     — no tiene sentido considerarlo como candidato a dominio del
     concepto que él mismo no reconoció.

  3. Si len(candidates) == 1 → SUFFICIENT(candidates[0].name)

  4. Si len(candidates) == 0 → UNKNOWN, options = todos los
     especialistas disponibles (excepto el iniciador). El reason
     dice 'ningún dominio conoce X'.

  5. Si len(candidates) > 1 → AMBIGUOUS, options = candidates. El
     reason dice 'varios dominios conocen X: [...]'.
"""
from __future__ import annotations

import unicodedata

from experiment_03.inter_specialist_protocol import (
    SpecialistAdapter,
    SpecialistRegistry,
)

from .request import (
    ClarificationRequest,
    SufficiencyAssessment,
    SufficiencyVerdict,
)


def _normalize(s: str) -> str:
    s = s.lower()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s


class ClarificationResolver:
    def __init__(
        self,
        registry: SpecialistRegistry,
        initiating_specialist: str | None = None,
    ) -> None:
        """`initiating_specialist` es el nombre del especialista que
        delegó la consulta (típicamente 'language' en el exp_08). Se
        excluye de la lista de candidatos.
        """
        self.registry = registry
        self.initiating_specialist = initiating_specialist

    # -- API pública ---------------------------------------------------

    def assess(
        self,
        concept: str,
        available_context: dict | None = None,
    ) -> SufficiencyAssessment:
        ctx = dict(available_context or {})

        # Paso 1: hint declarado por el caller.
        if "domain" in ctx and ctx["domain"]:
            return SufficiencyAssessment(
                concept=concept,
                verdict=SufficiencyVerdict.SUFFICIENT,
                domain=str(ctx["domain"]),
                candidates=[str(ctx["domain"])],
            )

        # Paso 2: candidatos del bus.
        candidates = self._candidates_for(concept)

        # Paso 3: candidato único.
        if len(candidates) == 1:
            return SufficiencyAssessment(
                concept=concept,
                verdict=SufficiencyVerdict.SUFFICIENT,
                domain=candidates[0],
                candidates=candidates,
            )

        # Paso 4: ningún candidato.
        if len(candidates) == 0:
            options = self._all_eligible_names()
            return SufficiencyAssessment(
                concept=concept,
                verdict=SufficiencyVerdict.UNKNOWN,
                domain=None,
                candidates=[],
                clarification_request=ClarificationRequest(
                    missing_concept=concept,
                    available_context=ctx,
                    options=options,
                    reason=(
                        f"ningún especialista del bus reconoce el concepto "
                        f"'{concept}'. Declare un dominio explícito o "
                        f"reformule la instrucción."
                    ),
                ),
            )

        # Paso 5: múltiples candidatos.
        return SufficiencyAssessment(
            concept=concept,
            verdict=SufficiencyVerdict.AMBIGUOUS,
            domain=None,
            candidates=candidates,
            clarification_request=ClarificationRequest(
                missing_concept=concept,
                available_context=ctx,
                options=candidates,
                reason=(
                    f"varios especialistas reconocen '{concept}': "
                    f"{candidates}. Declare cuál aplica."
                ),
            ),
        )

    # -- helpers internos ---------------------------------------------

    def _candidates_for(self, concept: str) -> list[str]:
        needle = _normalize(concept)
        out: list[str] = []
        for adapter in self.registry.all():
            if adapter.name == self.initiating_specialist:
                continue
            if self._adapter_knows(adapter, needle):
                out.append(adapter.name)
        return out

    @staticmethod
    def _adapter_knows(adapter: SpecialistAdapter, normalized_needle: str) -> bool:
        """Criterio A: el adapter 'conoce' el concepto si su grafo
        tiene al menos un nodo cuyo id contiene la versión
        normalizada del concepto.

        Sólo se inspecciona el id — ni statement ni rationale.
        Decisión consciente: el id es el commitment estructural del
        nodo; el statement puede mencionar términos colateralmente
        sin que constituya 'conocer el concepto'.
        """
        graph = getattr(adapter, "graph", None)
        if graph is None:
            return False
        for n in graph:
            if normalized_needle in _normalize(n.id):
                return True
        return False

    def _all_eligible_names(self) -> list[str]:
        return [
            a.name for a in self.registry.all()
            if a.name != self.initiating_specialist
        ]
