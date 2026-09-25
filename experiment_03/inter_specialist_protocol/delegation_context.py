"""Contexto de delegación — lleva la pila activa y el límite de profundidad.

El orchestrator crea una DelegationContext por problema resuelto. Cada
delegación recursiva comparte la misma instancia y la usa para:

  - Detectar ciclos: si (requester, target_variable) ya está en la pila
    activa, abortar con CYCLE_DETECTED.
  - Detectar fatiga cognitiva: si la profundidad supera `max_depth`,
    abortar con DELEGATION_DEPTH_EXCEEDED.

La estructura es un context manager por cada entrada a una delegación,
para que el cleanup del stack sea automático e imposible de olvidar.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field

from .messages import GapRequest


@dataclass
class DelegationContext:
    max_depth: int = 5

    # Pila activa de (requester, target_variable). Si un request nuevo
    # tiene el mismo par, hay ciclo.
    _active: list[tuple[str, str]] = field(default_factory=list)

    # Histórico de todos los requests atendidos (para trazabilidad;
    # no afecta la lógica de detección de ciclos).
    history: list[GapRequest] = field(default_factory=list)

    @property
    def current_depth(self) -> int:
        return len(self._active)

    def is_cycle(self, request: GapRequest) -> bool:
        return (request.requester, request.target_variable) in self._active

    def exceeds_depth(self, request: GapRequest) -> bool:
        return request.depth > self.max_depth

    @contextmanager
    def track(self, request: GapRequest):
        """Marca una delegación como activa durante la resolución.

        Uso:
            with ctx.track(req):
                response = adapter.handle(req)
        """
        key = (request.requester, request.target_variable)
        self._active.append(key)
        self.history.append(request)
        try:
            yield
        finally:
            # Idempotente frente a re-entradas: quita la última aparición.
            for i in range(len(self._active) - 1, -1, -1):
                if self._active[i] == key:
                    self._active.pop(i)
                    break
