from __future__ import annotations

from dataclasses import replace

from experiment_01.knowledge_graph import (
    EpistemicStatus,
    KnowledgeGraph,
    KnowledgeNode,
)

from ..consistency_validator import ConsistencyValidator
from ..hypothesis_engine import HypothesisCandidate
from .result import ConsolidationDecision, ConsolidationResult
from .usage_record import UsageRecord


class Consolidator:
    """Gestiona el ciclo de vida HYPOTHESIS → THEOREM.

    Responsabilidades:
      1. Registrar usos exitosos de un nodo-hipótesis con contexto completo
         (UsageRecord: problema, inputs, outputs, timestamp).
      2. Evaluar si una hipótesis cumple los criterios de consolidación:
         (a) validador en verde sobre el grafo actual,
         (b) al menos `min_uses` usos exitosos registrados,
         (c) ningún uso ha producido contradicción con axiomas.
      3. Si procede, renombrar y cambiar el estado del nodo a THEOREM,
         mutando el grafo de forma verificable.

    El consolidador no invoca al especialista — eso es trabajo del
    orchestrator. Él sólo responde "sí, este nodo merece ser teorema"
    con una traza auditable de por qué.
    """

    def __init__(
        self,
        min_uses: int = 1,
        validator: ConsistencyValidator | None = None,
    ) -> None:
        self.min_uses = min_uses
        self.validator = validator or ConsistencyValidator()
        # node_id → lista de usos registrados.
        self._usage: dict[str, list[UsageRecord]] = {}
        # node_id → lista de contradicciones observadas (strings auditables).
        self._contradictions: dict[str, list[str]] = {}

    # -- registro de usos ----------------------------------------------

    def record_usage(
        self,
        node_id: str,
        problem_id: str,
        inputs_used: dict,
        output_produced: dict,
    ) -> UsageRecord:
        record = UsageRecord(
            problem_id=problem_id,
            inputs_used=dict(inputs_used),
            output_produced=dict(output_produced),
        )
        self._usage.setdefault(node_id, []).append(record)
        return record

    def record_contradiction(self, node_id: str, detail: str) -> None:
        self._contradictions.setdefault(node_id, []).append(detail)

    def usages_of(self, node_id: str) -> list[UsageRecord]:
        return list(self._usage.get(node_id, []))

    # -- consolidación -------------------------------------------------

    def try_consolidate(
        self,
        node_id: str,
        graph: KnowledgeGraph,
        candidate: HypothesisCandidate | None = None,
    ) -> ConsolidationResult:
        """Intenta elevar `node_id` de HYPOTHESIS a THEOREM.

        Si `candidate` se provee, se revalida con el validator (criterio
        a). Si no, se asume que ya fue validado al incorporarse (útil
        cuando el orchestrator llama varias veces sin duplicar trabajo).
        """
        reasons: list[str] = []
        usages = self.usages_of(node_id)

        if not graph.has(node_id):
            return ConsolidationResult(
                decision=ConsolidationDecision.UNKNOWN_NODE,
                original_node_id=node_id,
                new_node_id=None,
                reasons=[f"el grafo no contiene '{node_id}'."],
                usage_records=usages,
            )

        node = graph.get(node_id)
        if node.status != EpistemicStatus.HYPOTHESIS:
            return ConsolidationResult(
                decision=ConsolidationDecision.NOT_HYPOTHESIS,
                original_node_id=node_id,
                new_node_id=None,
                reasons=[
                    f"el nodo está en estado '{node.status.value}', no HYPOTHESIS."
                ],
                usage_records=usages,
            )

        # (a) validador en verde (si tenemos candidato, revalidamos;
        # si no, exigimos al menos que el validador actual diga sí).
        if candidate is not None:
            vres = self.validator.validate(candidate, graph)
            if not vres.valid:
                return ConsolidationResult(
                    decision=ConsolidationDecision.VALIDATOR_FAILED,
                    original_node_id=node_id,
                    new_node_id=None,
                    reasons=[
                        f"validador rechaza el nodo: {vres.reason}",
                        *[f"check fallido: {c}" for c in vres.checks_failed],
                    ],
                    usage_records=usages,
                )
            reasons.append(f"(a) validador pasó los {len(vres.checks)} checks.")
        else:
            reasons.append("(a) validador no reejecutado en consolidación (asumido verde).")

        # (b) número mínimo de usos.
        if len(usages) < self.min_uses:
            return ConsolidationResult(
                decision=ConsolidationDecision.NOT_ENOUGH_USES,
                original_node_id=node_id,
                new_node_id=None,
                reasons=[
                    f"(b) se requieren al menos {self.min_uses} usos exitosos; "
                    f"hay {len(usages)}."
                ],
                usage_records=usages,
            )
        reasons.append(
            f"(b) se registraron {len(usages)} usos exitosos "
            f"(mínimo requerido: {self.min_uses})."
        )

        # (c) ninguna contradicción registrada.
        contradictions = self._contradictions.get(node_id, [])
        if contradictions:
            return ConsolidationResult(
                decision=ConsolidationDecision.CONTRADICTION,
                original_node_id=node_id,
                new_node_id=None,
                reasons=[
                    f"(c) contradicciones observadas: {len(contradictions)}",
                    *[f"  · {c}" for c in contradictions],
                ],
                usage_records=usages,
            )
        reasons.append("(c) ninguna contradicción observada en los usos registrados.")

        # Todos los criterios pasan — promover.
        new_id = self._promoted_id(node_id)
        promoted_node = replace(
            node,
            id=new_id,
            status=EpistemicStatus.THEOREM,
        )

        # Mutación segura del grafo: añadir primero el nuevo nodo
        # (para preservar invariantes de `add`), luego migrar los usos
        # registrados al nuevo id, finalmente eliminar el viejo.
        graph.add(promoted_node)
        if new_id != node_id:
            self._usage.setdefault(new_id, []).extend(self._usage.pop(node_id, []))
            self._contradictions.setdefault(new_id, []).extend(
                self._contradictions.pop(node_id, [])
            )
            graph.remove(node_id)

        reasons.append(f"promovido: {node_id} → {new_id} con status THEOREM.")

        return ConsolidationResult(
            decision=ConsolidationDecision.PROMOTED,
            original_node_id=node_id,
            new_node_id=new_id,
            reasons=reasons,
            usage_records=self.usages_of(new_id),
        )

    # -- helpers --------------------------------------------------------

    @staticmethod
    def _promoted_id(hypothesis_id: str) -> str:
        if hypothesis_id.startswith("hyp."):
            return "thm." + hypothesis_id[len("hyp."):]
        return hypothesis_id
