"""Especialista de Física — backward chaining sobre el grafo físico,
con el MISMO mecanismo que GeometrySpecialist y la capacidad de
delegar vía el callback del protocolo inter-dominio.

Lo único que se sobreescribe es `_conditions_apply`: la heurística
'si menciona "square" rechazo' es específica de geometría. Aquí
verificamos condiciones numéricas reales (p. ej. 'm >= 0') y
ignoramos cualquier referencia a figuras — este especialista no
tiene concepto de figura.
"""
from __future__ import annotations

import re
from typing import Optional

from experiment_01.knowledge_graph import KnowledgeNode
from experiment_01.specialist import GeometrySpecialist, Problem

# Patrón que localiza condiciones del tipo "<var> <op> <número>".
# Deliberadamente restrictivo y auditable: si la condición no cabe en
# esta forma, no la evaluamos — lo registramos pero no la tratamos
# como violación (preservamos 'no adivinar').
_NUMERIC_COND = re.compile(
    r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*(>=|<=|==|=|>|<)\s*(-?\d+(?:\.\d+)?)\s*$"
)


class PhysicsSpecialist(GeometrySpecialist):
    """Especialista de física 1D.

    Hereda todo el mecanismo de backward chaining del especialista base:
    `_derive`, `_try_delegate`, `solve(..., delegate=...)`. Sólo cambia
    el intérprete de condiciones de validez, porque las condiciones de
    un grafo físico no hablan de 'cuadrados' o 'triángulos'.
    """

    domain = "physics"

    # ------------------------------------------------------------------
    # Verificación de condiciones — GENÉRICA, no específica de geometría.
    # ------------------------------------------------------------------

    def _conditions_apply(self, node: KnowledgeNode, problem: Problem) -> bool:
        """Evalúa sólo condiciones numéricas bien formadas.

        - Si la condición casa con '<var> <op> <número>', la evaluamos
          contra las variables conocidas del problema. Si no tenemos
          valor de la variable aún, la condición NO cuenta como
          violada — el backward chaining la reevaluará cuando tenga el
          valor.
        - Si la condición es prosa libre (p. ej. 'la figura debe ser un
          square'), la IGNORAMOS en física. Este especialista no modela
          figuras.
        """
        for cond in node.validity_conditions:
            m = _NUMERIC_COND.match(cond)
            if not m:
                # Condición no numérica — fuera del alcance del intérprete.
                continue
            var, op, rhs = m.group(1), m.group(2), float(m.group(3))
            if var not in problem.context.known:
                # Aún no conocemos el valor: no podemos rechazar el nodo
                # sólo por eso; el backward chaining resolverá la
                # variable y luego el compute se ejecutará con valores
                # concretos.
                continue
            lhs = float(problem.context.known[var])
            if not self._eval_op(lhs, op, rhs):
                return False
        return True

    @staticmethod
    def _eval_op(lhs: float, op: str, rhs: float) -> bool:
        if op == ">=":
            return lhs >= rhs
        if op == "<=":
            return lhs <= rhs
        if op == ">":
            return lhs > rhs
        if op == "<":
            return lhs < rhs
        if op in ("=", "=="):
            return lhs == rhs
        # Defensivo — no debería alcanzarse dado el regex.
        return False

    # ------------------------------------------------------------------
    # Filtro de nodos relevantes — sin sesgo geométrico.
    # ------------------------------------------------------------------

    def _scan_relevant_nodes(self, problem: Problem) -> list[KnowledgeNode]:
        """El escáner del base busca nodos cuyo id mencione el 'kind' de
        la figura. En física ese 'kind' es algo como 'physics.object',
        que no aparece en los ids del grafo físico. Sustituimos por un
        escáner que simplemente siembra desde los productores del
        objetivo y cierra transitivamente. Es auditable y sin sesgo.
        """
        relevant: dict[str, KnowledgeNode] = {}
        for seed in self.graph.find_relations_producing(problem.target):
            relevant[seed.id] = seed
            for dep in self.graph.transitive_foundations(seed.id):
                relevant[dep.id] = dep
        return list(relevant.values())
