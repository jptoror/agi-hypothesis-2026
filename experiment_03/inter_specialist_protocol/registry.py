"""Registro de especialistas para enrutar consultas inter-dominio.

El orchestrator consulta la registry — NO conoce los dominios. La
registry mapea variable-salida → lista de especialistas que la producen.
Si varios producen la misma variable, el `can_handle` fino del adapter
decide quién atiende.
"""
from __future__ import annotations

from .adapter import SpecialistAdapter
from .messages import GapRequest


class SpecialistRegistry:
    def __init__(self) -> None:
        # Mantiene orden de registro; para empates en can_handle gana el
        # primero registrado (determinismo auditable).
        self._specialists: dict[str, SpecialistAdapter] = {}

    # -- registro -------------------------------------------------------

    def register(self, adapter: SpecialistAdapter) -> None:
        if adapter.name in self._specialists:
            raise ValueError(f"especialista ya registrado: {adapter.name}")
        self._specialists[adapter.name] = adapter

    # -- consulta -------------------------------------------------------

    def get(self, name: str) -> SpecialistAdapter:
        if name not in self._specialists:
            raise KeyError(f"especialista no encontrado: {name}")
        return self._specialists[name]

    def all(self) -> list[SpecialistAdapter]:
        return list(self._specialists.values())

    def find_for(self, request: GapRequest) -> SpecialistAdapter | None:
        """Primer adapter cuyas output_variables incluyen el target
        y cuyo can_handle devuelve True. None si ninguno aplica.

        El orchestrator no sabe qué especialista 'debería' atender —
        sólo pregunta a la registry. La registry sólo sabe que tal
        especialista declara producir tal variable. Nadie conoce los
        dominios como cuerpo de conocimiento.
        """
        for adapter in self._specialists.values():
            if request.target_variable in adapter.output_variables and adapter.can_handle(request):
                return adapter
        return None
