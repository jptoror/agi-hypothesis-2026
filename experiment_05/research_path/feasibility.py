"""Tipos de viabilidad de cierre de un gap.

Este eje es independiente del EpistemicGapType: clasifica QUÉ
ESFUERZO requiere cerrar el gap, no POR QUÉ no se sabe. El proposer
mapea EpistemicGapType → Feasibility con una tabla explícita y
auditable.
"""
from __future__ import annotations

from enum import Enum


class Feasibility(str, Enum):
    """Niveles de viabilidad.

    ENGINEERING
      Accionable directamente con código del propio sistema —
      añadir nodos, sintetizar especialistas, escribir patrones.
      El sistema podría cerrar el gap por sí mismo en una iteración
      del proyecto.

    RESEARCH
      Accionable pero requiere trabajo humano que va más allá de
      escribir código rutinario: diseñar una ontología nueva,
      formalizar una teoría implícita, validar empíricamente. El
      sistema puede DESCRIBIR el camino pero no recorrerlo solo.

    OPEN_PROBLEM
      No accionable desde ingeniería. Resolverlo exige primero
      resolver un problema filosófico/científico abierto. Para
      gaps OPEN_PROBLEM, `proposed_action` debe ser None y
      `estimated_complexity` debe ser "indefinido".
    """

    ENGINEERING = "engineering"
    RESEARCH = "research"
    OPEN_PROBLEM = "open_problem"
