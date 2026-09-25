"""Especialista de un subdominio emergente.

Opera sobre el subgrafo que produjo el SubdomainSynthesizer. Hereda el
backward chaining del GeometrySpecialist pero ofrece un verificador de
condiciones HÍBRIDO: acepta las condiciones numéricas tipo 'm >= 0' y
las condiciones de prosa tipo 'la figura debe ser un cuadrado', según
el problema — porque un subdominio emergente puede mezclar convenciones
de varios dominios fuente.

Si el problema no declara un `kind` reconocido por el catálogo del
subdominio, el verificador SUPLE con `implicit_figure_kind` (también
llamado kind implícito), inyectado al instanciar el especialista.

`domain_terms` es la LISTA EXPLÍCITA de GRUPOS de sinónimos que el
subdominio reconoce como categorías del dominio. Cada grupo es una
lista de strings que el caller declara como equivalentes (p. ej.
`["square", "cuadrado"]` = el mismo concepto en dos idiomas). El
verificador rechaza una condición si menciona algún término del
grupo X y NINGÚN término del grupo X aparece en el kind del problema.

La lista vacía (default) significa "no rechazar por términos" —
comportamiento maximalmente permisivo, útil para subdominios cuyas
condiciones son puramente numéricas o no catalogan tipos.
"""
from __future__ import annotations

import re
from typing import Optional

from experiment_01.knowledge_graph import KnowledgeGraph, KnowledgeNode
from experiment_01.specialist import GeometrySpecialist, Problem


_NUMERIC_COND = re.compile(
    r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*(>=|<=|==|=|>|<)\s*(-?\d+(?:\.\d+)?)\s*$"
)


class SubdomainSpecialist(GeometrySpecialist):
    """Backward chaining sobre un subgrafo sintetizado o importado."""

    def __init__(
        self,
        graph: KnowledgeGraph,
        domain: str,
        implicit_figure_kind: Optional[str] = None,
        disabled_nodes: Optional[set[str]] = None,
        domain_terms: Optional[list[list[str]]] = None,
    ) -> None:
        super().__init__(graph, disabled_nodes=disabled_nodes)
        # Sobrescribimos `domain` por instancia — no por clase —
        # porque cada subdominio emergente tiene su propio nombre.
        self.domain = domain
        # Tipo de figura/objeto que el subdominio asume si el problema
        # no declara uno reconocido. Permite que teoremas con prosa
        # "para un X" apliquen aunque el problema diga `kind="otro"`.
        self.implicit_figure_kind = implicit_figure_kind
        # Grupos de sinónimos que el subdominio reconoce. Cada grupo
        # es una lista de términos equivalentes; el matching considera
        # el grupo entero. Default vacío → permisivo.
        self.domain_terms: list[list[str]] = [
            [t.lower() for t in group]
            for group in (domain_terms or [])
        ]

    def _scan_relevant_nodes(self, problem: Problem) -> list[KnowledgeNode]:
        """Sin sesgo de dominio en la siembra."""
        relevant: dict[str, KnowledgeNode] = {}
        for seed in self.graph.find_relations_producing(problem.target):
            relevant[seed.id] = seed
            for dep in self.graph.transitive_foundations(seed.id):
                relevant[dep.id] = dep
        return list(relevant.values())

    def _conditions_apply(self, node: KnowledgeNode, problem: Problem) -> bool:
        """Verificador híbrido por grupos de sinónimos.

        - Numéricas (`x >= 0`): evaluadas contra `problem.context.known`.
          Si la variable aún no es conocida, la condición no cuenta
          como violada — el backward chaining la reevaluará tras
          derivarla.
        - Prosa con términos del dominio: por cada GRUPO de sinónimos
          mencionado en la condición, se verifica que al menos un
          término del MISMO grupo aparezca en el kind efectivo. Si
          ningún término del grupo aparece, la condición se rechaza.
        - Prosa sin término reconocido: ignorada (permisivo por diseño).
        """
        effective_kind = self._effective_kind(problem)

        for cond in node.validity_conditions:
            cond_low = cond.lower()

            # 1) Condición numérica.
            m = _NUMERIC_COND.match(cond)
            if m:
                var, op, rhs = m.group(1), m.group(2), float(m.group(3))
                if var not in problem.context.known:
                    continue
                lhs = float(problem.context.known[var])
                if not _eval_op(lhs, op, rhs):
                    return False
                continue

            # 2) Condición de prosa: revisar cada grupo.
            for group in self.domain_terms:
                cond_mentions_group = any(t in cond_low for t in group)
                kind_matches_group = any(t in effective_kind for t in group)
                if cond_mentions_group and not kind_matches_group:
                    return False
        return True

    def _effective_kind(self, problem: Problem) -> str:
        raw = problem.context.kind.lower()
        # Si el kind declarado contiene algún término de algún grupo,
        # ese kind ya está auto-clasificado y gana.
        for group in self.domain_terms:
            if any(t in raw for t in group):
                return raw
        # Si no, suple el implícito del subdominio.
        if self.implicit_figure_kind:
            return self.implicit_figure_kind.lower()
        return raw


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
    return False
