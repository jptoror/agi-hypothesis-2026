"""Registro estructural de una colaboración entre especialistas.

Una colaboración es un evento EPISTEMOLÓGICO: dos especialistas
produjeron juntos la solución de un problema. El record es la
proyección mínima que conserva lo que el pattern_detector y el
subdomain_synthesizer van a necesitar, sin arrastrar estado superfluo
(trazas completas, performance, etc.).

Un record responde a cuatro preguntas:
  1. ¿Quiénes colaboraron?     (initiator, responder)
  2. ¿Sobre qué?               (problem_id / statement)
  3. ¿Qué conocimiento se ejerció? (nodes_used_*)
  4. ¿Qué hizo posible el cruce?  (variable_bindings, delegation_hints)

Todo lo demás sería ruido.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


def _utc_iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class CollaborationRecord:
    problem_id: str
    problem_statement: str
    problem_initiating_domain: str     # el dominio que arrancó el solve
    initiator: str                     # el dominio que delegó
    responder: str                     # el dominio que respondió
    nodes_used_initiator: list[str]    # ids de nodos ejercitados por el iniciador
    nodes_used_responder: list[str]    # ids de nodos ejercitados por el responder
    variable_bindings: dict[str, str]  # del Problem — vínculos ontológicos del enunciado
    delegation_hints: dict             # del Problem — pistas para el responder
    delegated_variables: list[str]     # variables concretas que se pidieron
    timestamp: str = field(default_factory=_utc_iso_now)

    # -- firma estructural ---------------------------------------------

    def signature(self) -> frozenset:
        """Clave hashable que captura la FORMA de la colaboración
        independientemente del problema concreto.

        Dos colaboraciones tienen la misma signature si:
          - el par {initiator, responder} es el mismo (no importa el orden);
          - los variable_bindings son el mismo conjunto de pares (k, v);
          - los delegation_hints son el mismo conjunto de pares (k, v).

        Los valores de los hints deben ser hashables. Si algún valor
        no lo es (p. ej. un dict anidado), se serializa a `repr` —
        preservamos igualdad estructural sin esfuerzo simbólico.
        """
        return frozenset({
            ("pair", frozenset({self.initiator, self.responder})),
            ("bindings", frozenset(self.variable_bindings.items())),
            ("hints", frozenset(
                (k, v if _is_hashable(v) else repr(v))
                for k, v in self.delegation_hints.items()
            )),
        })

    # -- render --------------------------------------------------------

    def render(self) -> str:
        lines = [
            f"[{self.timestamp}] {self.initiator} ↔ {self.responder}",
            f"  problema: {self.problem_id} — {self.problem_statement}",
            f"  iniciador del solve: {self.problem_initiating_domain}",
            f"  variables delegadas: {self.delegated_variables}",
            f"  nodos {self.initiator}: {self.nodes_used_initiator}",
            f"  nodos {self.responder}: {self.nodes_used_responder}",
            f"  bindings: {self.variable_bindings}",
            f"  hints: {self.delegation_hints}",
        ]
        return "\n".join(lines)


def _is_hashable(v: object) -> bool:
    try:
        hash(v)
        return True
    except TypeError:
        return False
