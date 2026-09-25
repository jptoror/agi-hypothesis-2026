from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


def _utc_iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class UsageRecord:
    """Registro de un uso exitoso de una hipótesis al resolver un problema.

    Guardamos suficiente información para que un criterio futuro pueda
    evaluar diversidad real (no sólo conteo): qué problema concreto lo
    invocó, con qué inputs, qué output produjo, y cuándo. La estructura
    es deliberadamente plana y serializable — JSON-amigable.
    """

    problem_id: str
    inputs_used: dict
    output_produced: dict
    timestamp: str = field(default_factory=_utc_iso_now)

    def render(self) -> str:
        return (
            f"[{self.timestamp}] problema='{self.problem_id}' "
            f"inputs={self.inputs_used} output={self.output_produced}"
        )
