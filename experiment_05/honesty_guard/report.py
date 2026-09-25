"""HonestyReport — auditoría del diagnóstico epistémico del sistema."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Verdict(str, Enum):
    HONEST = "honest"
    VIOLATIONS_FOUND = "violations_found"


@dataclass
class Violation:
    check_id: str          # "h1".."h8"
    check_name: str
    detail: str

    def render(self) -> str:
        return f"  ✗ [{self.check_id}] {self.check_name}: {self.detail}"


@dataclass
class HonestyReport:
    verdict: Verdict
    checks_executed: list[str]
    violations: list[Violation] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    @property
    def is_honest(self) -> bool:
        return self.verdict == Verdict.HONEST

    def render(self) -> str:
        lines = [
            "=" * 72,
            "REPORTE DE HONESTIDAD",
            "=" * 72,
            f"VEREDICTO: {self.verdict.value.upper()}",
            f"Checks ejecutados: {len(self.checks_executed)}",
            f"Violaciones encontradas: {len(self.violations)}",
        ]
        for k, v in self.metrics.items():
            lines.append(f"  {k}: {v}")
        if self.violations:
            lines.append("")
            lines.append("VIOLACIONES:")
            for v in self.violations:
                lines.append(v.render())
        if self.notes:
            lines.append("")
            lines.append("NOTAS DEL GUARDIÁN:")
            for n in self.notes:
                lines.append(f"  · {n}")
        return "\n".join(lines)
