"""ComputeRegistry — registro de funciones ejecutables por id de nodo.

JSON no serializa funciones. La estrategia es:

  - Al hacer dump: guardamos el id del nodo y un flag
    `has_compute` que indica si el nodo TENÍA compute.
  - Al hacer load: para cada nodo con `has_compute=True`, el caller
    aporta un ComputeRegistry que mapea node_id → callable. El nodo
    reconstruido recibe ese callable como su `compute`.

Esta separación es honesta: el código ejecutable vive en Python
(en la registry); el grafo en JSON sólo lleva el COMMITMENT de que
ese nodo tiene un compute, no el cómo se calcula.

Usos previstos:
  - Persistencia entre sesiones (PROB-01): el caller mantiene una
    registry de funciones canónicas y la pasa a `load`.
  - Mismo grafo en distintos procesos: ambos procesos comparten la
    registry, el JSON viaja entre ellos.

NO RESUELVE: serialización de funciones lambda inline. Si un grafo
tiene `compute=lambda v: ...` que no aparece en una registry, al
cargar se reconstruye sin compute y el `DeserializationReport`
listará el id como `unresolved_computes`.
"""
from __future__ import annotations

from typing import Callable


class ComputeRegistry:
    """Registro mutable de funciones ejecutables por id de nodo.

    Las funciones deben tener la signatura que `KnowledgeNode.compute`
    espera: `Callable[[dict], dict]`.
    """

    def __init__(self) -> None:
        self._fns: dict[str, Callable[[dict], dict]] = {}

    def register(self, node_id: str, fn: Callable[[dict], dict]) -> None:
        if node_id in self._fns:
            raise ValueError(f"compute ya registrado para id '{node_id}'")
        self._fns[node_id] = fn

    def get(self, node_id: str) -> Callable[[dict], dict] | None:
        return self._fns.get(node_id)

    def has(self, node_id: str) -> bool:
        return node_id in self._fns

    def all_ids(self) -> list[str]:
        return list(self._fns.keys())

    def __len__(self) -> int:
        return len(self._fns)
