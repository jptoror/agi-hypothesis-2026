from __future__ import annotations

from experiment_01.knowledge_graph import (
    EpistemicStatus,
    KnowledgeGraph,
    KnowledgeNode,
    NodeKind,
)
from experiment_01.specialist import Problem

from ..candidate import HypothesisCandidate
from .base import Pattern


class SumOfEqualParts(Pattern):
    """Patrón: 'magnitud = n_partes × medida_de_una_parte'.

    Aplica cuando:
      1. El grafo contiene un nodo-definición con properties tal que:
         - n_sides: int (o, en general, n_parts)
         - sides_equal: True
         - side_variable: str  (nombre de la variable que representa una parte)
         - figure_kind: str    (tipo de figura, debe casar con problem.context.kind)
      2. La variable faltante coincide con una magnitud que este patrón
         sabe componer — declarada EXPLÍCITAMENTE en `known_magnitudes`.

    No hay NL parsing ni inferencia estadística. El conocimiento
    estructural del patrón es:
      - existe una relación 'magnitud total = N × parte' para ciertas
        magnitudes conocidas de antemano (actualmente sólo perímetro).

    Si el usuario pide una magnitud que el patrón no conoce, devuelve
    lista vacía — honesto y auditable.
    """

    name = "SumOfEqualParts"

    # Magnitudes que este patrón sabe componer como suma de partes iguales.
    # Cada entrada mapea el NOMBRE DE VARIABLE que el usuario puede pedir a
    # una descripción legible. Añadir aquí es una decisión consciente y
    # trazable — no emergente.
    # Cada magnitud se registra con (etiqueta-humana, slug-id). El slug
    # entra en el id del nodo (sin acentos, ASCII) para que ids generados
    # automáticamente sean estables y portables. La etiqueta se usa en
    # el statement legible.
    known_magnitudes: dict[str, tuple[str, str]] = {
        "P": ("perímetro", "perimeter"),
        "perimeter": ("perímetro", "perimeter"),
    }

    def propose(
        self,
        missing_variable: str,
        problem: Problem,
        graph: KnowledgeGraph,
    ) -> list[HypothesisCandidate]:
        if missing_variable not in self.known_magnitudes:
            return []

        magnitude_label, magnitude_slug = self.known_magnitudes[missing_variable]
        candidates: list[HypothesisCandidate] = []

        for node in graph:
            props = node.properties or {}
            if not props.get("sides_equal"):
                continue
            n_sides = props.get("n_sides")
            side_var = props.get("side_variable")
            figure_kind = props.get("figure_kind")
            if not (isinstance(n_sides, int) and isinstance(side_var, str) and figure_kind):
                continue
            if figure_kind.lower() != problem.context.kind.lower():
                continue

            # Construir la relación P = n_sides * l como nodo HIPÓTESIS.
            n = n_sides
            side_variable_name = side_var

            def make_compute(k: int, var: str):
                return lambda v, _k=k, _v=var: {missing_variable: _k * v[_v]}

            # Axiomas necesarios: el nodo fuente (define la figura y sus
            # propiedades estructurales) y la aritmética de reales (para
            # poder multiplicar). Usamos sólo nodos que YA existen en el
            # grafo — no inventamos fundamentos.
            foundations = [node.id]
            if graph.has("ax.arithmetic.real_numbers"):
                foundations.append("ax.arithmetic.real_numbers")

            hypothesis_node = KnowledgeNode(
                id=f"hyp.{figure_kind}.{magnitude_slug}_from_side",
                statement=(
                    f"El {magnitude_label} de un {figure_kind} de lado "
                    f"{side_variable_name} es {missing_variable} = {n} · {side_variable_name}."
                ),
                status=EpistemicStatus.HYPOTHESIS,
                kind=NodeKind.RELATION,
                foundations=foundations,
                validity_conditions=[
                    f"la figura debe ser un {figure_kind}",
                    f"{side_variable_name} >= 0",
                ],
                inputs=[side_variable_name],
                outputs=[missing_variable],
                compute=make_compute(n, side_variable_name),
                rationale=(
                    f"Aplicando el patrón {self.name}: el nodo {node.id} declara "
                    f"que la figura tiene {n} partes iguales de medida "
                    f"'{side_variable_name}'. La suma de longitudes iguales es "
                    f"{n} · {side_variable_name}."
                ),
                properties={
                    "generated_by_pattern": self.name,
                    "source_definition": node.id,
                },
            )

            justification = (
                f"{node.id} declara properties={{'n_sides': {n}, 'sides_equal': True, "
                f"'side_variable': '{side_variable_name}'}}. El patrón compone "
                f"{missing_variable} = {n} · {side_variable_name} — una suma de {n} "
                f"longitudes iguales."
            )

            # Ranking: menos fundamentos externos = más local al grafo = mejor.
            rank_score = float(len(foundations))

            candidates.append(HypothesisCandidate(
                node=hypothesis_node,
                pattern_name=self.name,
                source_nodes=[node.id],
                justification=justification,
                rank_score=rank_score,
                metadata={
                    "n_parts": n,
                    "part_variable": side_variable_name,
                    "magnitude": magnitude_label,
                    "magnitude_slug": magnitude_slug,
                    "figure_kind": figure_kind,
                },
            ))

        return candidates
