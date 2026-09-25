from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CheckOutcome:
    """Resultado de un único check de consistencia."""

    name: str
    passed: bool
    detail: str

    def render(self) -> str:
        mark = "✓" if self.passed else "✗"
        return f"    {mark} {self.name}: {self.detail}"


@dataclass
class ValidationResult:
    """Resultado agregado de validar un candidato.

    La lista `checks` preserva el orden de ejecución — clave para la
    auditoría: se puede leer de arriba abajo como una traza.
    """

    valid: bool
    reason: str
    checks: list[CheckOutcome] = field(default_factory=list)

    @property
    def checks_passed(self) -> list[str]:
        return [c.name for c in self.checks if c.passed]

    @property
    def checks_failed(self) -> list[str]:
        return [c.name for c in self.checks if not c.passed]

    def render(self) -> str:
        lines = [
            f"VALIDACIÓN: {'válida' if self.valid else 'inválida'}",
            f"  resumen: {self.reason}",
            f"  checks ejecutados: {len(self.checks)} "
            f"(pasaron {len(self.checks_passed)}, "
            f"fallaron {len(self.checks_failed)})",
        ]
        for c in self.checks:
            lines.append(c.render())
        return "\n".join(lines)
