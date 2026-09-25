"""ActiveContext — estado mínimo que el orquestador acumula entre
turnos para resolver referencias anafóricas (`"el grafo de antes"`).

Reglas operacionales (declarativas, sin estadística):

  - `active_bindings`: dict `nombre_de_clase → node_id`. El nombre
    de clase es la categoría conversacional ("grafo", "función",
    etc.). El node_id puede ser local (`conv_001:node_3`) o
    cross-graph (`alg_demo::alg.greedy_coloring`, ver
    `conversation_graph.cross_graph_foundation`).

  - `domain_hints`: cola FIFO con un máximo (`max_hints`). El
    último turno empuja su hint al final; cuando se llena, sale el
    más viejo. NO hay decaimiento por tiempo ni frecuencia — la
    salida es por edad en turnos, configurable.

  - `idle_turns_per_binding`: contador por binding. Cuando un
    binding no se referencia durante `binding_timeout` turnos, se
    elimina. El timeout es un parámetro, no una heurística
    inferida.

El reset explícito por parte del usuario se modela con
`ContextResetReason.USER_REQUEST`. El reset por timeout sin uso
queda en `IDLE_TIMEOUT`. Ambos son DECLARATIVOS: el orquestador
los aplica cuando se cumplen las condiciones explícitas.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ContextResetReason(str, Enum):
    USER_REQUEST = "user_request"
    IDLE_TIMEOUT = "idle_timeout"


@dataclass
class ActiveContext:
    """Estado de contexto serializable.

    Todos los campos son JSON-nativos para que la persistencia sea
    trivial (sin custom encoders). El orquestador actualiza los
    campos turn a turn."""

    last_specialist_id: str | None = None
    # nombre_clase → node_id. La "clase" la declara el caller al
    # registrar el binding; aquí no se infiere.
    active_bindings: dict[str, str] = field(default_factory=dict)
    # Pista de dominio acumulada por los últimos `max_hints` turnos.
    # Lista (no set) porque el orden importa: el más reciente al
    # final pesa más al desempatar conflictos del registry.
    domain_hints: list[str] = field(default_factory=list)
    # Por binding, cuántos turnos lleva sin referenciarse. Permite
    # caducar contexto sin actividad. Reset a 0 al usar el binding.
    idle_turns_per_binding: dict[str, int] = field(default_factory=dict)

    # Configuración (no son estado conversacional, son política).
    max_hints: int = 5
    binding_timeout: int = 6  # turnos sin uso → binding caduca

    # -- Serialización -----------------------------------------------

    def to_dict(self) -> dict:
        return {
            "last_specialist_id": self.last_specialist_id,
            "active_bindings": dict(self.active_bindings),
            "domain_hints": list(self.domain_hints),
            "idle_turns_per_binding": dict(self.idle_turns_per_binding),
            "max_hints": self.max_hints,
            "binding_timeout": self.binding_timeout,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ActiveContext":
        return cls(
            last_specialist_id=data.get("last_specialist_id"),
            active_bindings=dict(data.get("active_bindings", {})),
            domain_hints=list(data.get("domain_hints", [])),
            idle_turns_per_binding=dict(
                data.get("idle_turns_per_binding", {})
            ),
            max_hints=int(data.get("max_hints", 5)),
            binding_timeout=int(data.get("binding_timeout", 6)),
        )

    # -- Mutaciones explícitas (todas declarativas) ------------------

    def push_domain_hint(self, hint: str) -> None:
        """Añade un hint al final de la cola. Si excede `max_hints`,
        descarta el más viejo. NO deduplica — repetir el mismo
        especialista refuerza el peso (el resolver decide cómo
        usarlo)."""
        if not hint:
            return
        self.domain_hints.append(hint)
        while len(self.domain_hints) > self.max_hints:
            self.domain_hints.pop(0)

    def register_binding(self, name: str, node_id: str) -> None:
        """Declara que `name` referencia a `node_id`. Si ya existía,
        REEMPLAZA — la conversación pisa lo anterior, no acumula
        ambigüedad."""
        self.active_bindings[name] = node_id
        self.idle_turns_per_binding[name] = 0

    def use_binding(self, name: str) -> str | None:
        """Marca un binding como usado en este turno (resetea su
        contador idle) y devuelve el node_id, o None si no
        existe."""
        if name not in self.active_bindings:
            return None
        self.idle_turns_per_binding[name] = 0
        return self.active_bindings[name]

    def tick(self) -> list[str]:
        """Avanza un turno: incrementa el contador idle de cada
        binding y elimina los que pasen el timeout. Devuelve la
        lista de bindings caducados (para que el caller los reporte
        si lo desea). DECLARATIVO: el timeout viene de la política
        explícita, no de heurística."""
        expired: list[str] = []
        for name in list(self.idle_turns_per_binding.keys()):
            self.idle_turns_per_binding[name] += 1
            if self.idle_turns_per_binding[name] >= self.binding_timeout:
                expired.append(name)
                self.active_bindings.pop(name, None)
                self.idle_turns_per_binding.pop(name, None)
        return expired

    def reset(self, reason: ContextResetReason) -> None:
        """Limpia bindings + hints. `reason` queda registrado por el
        caller en el turno correspondiente."""
        self.active_bindings.clear()
        self.idle_turns_per_binding.clear()
        self.domain_hints.clear()
        # `last_specialist_id` se preserva — saber a quién se
        # delegó el último turno sigue siendo útil tras un reset.

    # -- Resolución anafórica (declarativa) --------------------------

    def resolve_anaphora(
        self,
        category: str,
    ) -> tuple[str | None, list[str]]:
        """Busca un binding cuya CLASE coincida con `category`.

        Devuelve `(node_id, candidates)`:
          - Si hay un solo binding de esa categoría → `(node_id, [])`.
          - Si hay varios → `(None, [name1, name2, ...])`. El
            caller emite ClarificationRequest con la lista.
          - Si no hay ninguno → `(None, [])`.

        El concepto de "categoría" es DECLARATIVO. El caller registra
        el binding con un nombre que incluye la categoría (ej:
        `"grafo_actual"`, `"grafo_secundario"`) y el resolver busca
        prefijos. Para exp_19 la heurística es: el binding pertenece a
        `category` si su nombre arranca con la cadena `category`. Sin
        embeddings, sin similitud — el caller controla el matching
        eligiendo nombres."""
        if not category:
            return None, []
        matches = [
            name for name in self.active_bindings
            if name == category or name.startswith(category + "_")
        ]
        if len(matches) == 1:
            return self.use_binding(matches[0]), []
        if len(matches) > 1:
            return None, list(matches)
        return None, []
