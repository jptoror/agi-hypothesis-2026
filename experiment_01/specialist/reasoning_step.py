from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ReasoningStep:
    """Un paso discreto de la derivación.

    Cada paso es auditable: qué nodo se aplicó, qué condiciones se
    comprobaron, con qué entradas y qué salidas produjo. Reconstruir la
    derivación significa leer en orden los pasos — nada de cajas negras.

    Los pasos delegados a otro especialista conservan su sub-traza en
    `delegated_trace` — así la auditabilidad es transitiva: el lector
    puede expandir el paso y ver la derivación completa del sub-dominio.
    """

    index: int
    node_id: str
    node_statement: str
    purpose: str                        # por qué se eligió este nodo
    conditions_checked: list[str] = field(default_factory=list)
    inputs: dict[str, float] = field(default_factory=dict)
    outputs: dict[str, float] = field(default_factory=dict)
    rationale: str = ""
    # Si este paso es una delegación a otro especialista, aquí va la
    # traza que ese especialista produjo al resolver la consulta.
    # None para pasos locales normales.
    delegated_trace: "ReasoningTrace | None" = None

    def render(self) -> str:
        lines = [
            f"Paso {self.index}: usa {self.node_id}",
            f"  enunciado: {self.node_statement}",
            f"  propósito: {self.purpose}",
        ]
        if self.conditions_checked:
            lines.append("  condiciones verificadas:")
            for c in self.conditions_checked:
                lines.append(f"    ✓ {c}")
        if self.inputs:
            entradas = ", ".join(f"{k}={v}" for k, v in self.inputs.items())
            lines.append(f"  entradas: {entradas}")
        if self.outputs:
            salidas = ", ".join(f"{k}={v}" for k, v in self.outputs.items())
            lines.append(f"  salidas:  {salidas}")
        if self.rationale:
            lines.append(f"  justificación: {self.rationale}")
        if self.delegated_trace is not None and self.delegated_trace.steps:
            lines.append("  sub-traza delegada:")
            for sub in self.delegated_trace.render().splitlines():
                lines.append(f"    │ {sub}")
        return "\n".join(lines)


@dataclass
class ReasoningTrace:
    """Traza completa de una derivación."""

    steps: list[ReasoningStep] = field(default_factory=list)

    def add(self, step: ReasoningStep) -> None:
        self.steps.append(step)

    def nodes_used(self) -> list[str]:
        return [s.node_id for s in self.steps]

    def render(self) -> str:
        if not self.steps:
            return "(sin pasos)"
        return "\n\n".join(s.render() for s in self.steps)
