from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .usage_record import UsageRecord


class ConsolidationDecision(str, Enum):
    PROMOTED = "promoted"            # HYPOTHESIS → THEOREM
    NOT_ENOUGH_USES = "not_enough_uses"
    VALIDATOR_FAILED = "validator_failed"
    CONTRADICTION = "contradiction"
    NOT_HYPOTHESIS = "not_hypothesis"
    UNKNOWN_NODE = "unknown_node"


@dataclass
class ConsolidationResult:
    """Resultado del intento de elevar HYPOTHESIS → THEOREM.

    Si `decision == PROMOTED`, `new_node_id` lleva el id resultante (puede
    diferir del original: por convención `hyp.*` se renombra a `thm.*`).
    Las razones son auditables — cada criterio anotado.
    """

    decision: ConsolidationDecision
    original_node_id: str
    new_node_id: str | None
    reasons: list[str] = field(default_factory=list)
    usage_records: list[UsageRecord] = field(default_factory=list)

    @property
    def promoted(self) -> bool:
        return self.decision == ConsolidationDecision.PROMOTED

    def render(self) -> str:
        lines = [
            f"CONSOLIDACIÓN: {self.decision.value}",
            f"  nodo original: {self.original_node_id}",
        ]
        if self.new_node_id and self.new_node_id != self.original_node_id:
            lines.append(f"  nuevo id: {self.new_node_id}")
        if self.reasons:
            lines.append("  razones:")
            for r in self.reasons:
                lines.append(f"    - {r}")
        if self.usage_records:
            lines.append(f"  usos exitosos registrados ({len(self.usage_records)}):")
            for u in self.usage_records:
                lines.append(f"    · {u.render()}")
        return "\n".join(lines)
