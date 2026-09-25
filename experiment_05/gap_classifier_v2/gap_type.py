"""Tipos de gap EPISTÉMICO — eje distinto a los tipos de gap del exp_01.

Los tipos del exp_01 (MISSING_RELATION, MISSING_INPUT, etc.) clasifican
POR QUÉ un problema concreto no se pudo resolver. Los tipos de aquí
clasifican POR QUÉ el sistema no conoce un concepto. Son dos ejes
ortogonales y conviene no mezclarlos en un mismo enum — el paper los
tratará como dimensiones separadas de la ignorancia del sistema.
"""
from __future__ import annotations

from enum import Enum


class EpistemicGapType(str, Enum):
    """Tipología de ignorancia epistémica.

    MISSING_CONCEPT
      El concepto existe en el código o en la arquitectura del sistema
      de forma informal u operacional, pero no como nodo epistemológico
      formal en ningún grafo. Es un gap CERRABLE añadiendo nodos.

    FRONTIER_GAP
      El sistema HACE algo relacionado con este concepto (lo ejerce
      operacionalmente), pero no tiene un modelo DE SÍ MISMO que lo
      describa. Vive en la frontera entre lo que el sistema implementa
      y lo que el sistema entiende sobre lo que implementa. Cerrarlo
      requiere meta-modelado — un nivel distinto al de los grafos
      actuales.

    PHILOSOPHICAL_GAP
      No hay criterio operativo aceptado (ni dentro ni fuera del
      proyecto) que permita capturar este concepto desde primeros
      principios. Cerrar este gap requiere PRIMERO resolver un
      problema filosófico abierto — no es trabajo de ingeniería.
    """

    MISSING_CONCEPT = "missing_concept"
    FRONTIER_GAP = "frontier_gap"
    PHILOSOPHICAL_GAP = "philosophical_gap"
