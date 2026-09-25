from __future__ import annotations

from dataclasses import dataclass, field

from experiment_01.knowledge_graph import KnowledgeNode


@dataclass
class HypothesisCandidate:
    """Un candidato de teorema propuesto por un patrón.

    El campo `node` ya viene con status=HYPOTHESIS — ese es el estado con
    que debe entrar al grafo si el validador lo acepta. `pattern_name`
    identifica qué patrón lo generó (trazabilidad) y `source_nodes` son
    los ids de los nodos del grafo existente que se usaron como materia
    prima estructural; no son los foundations del nodo propuesto, son el
    rastro de cómo llegamos a él.

    `rank_score` es una puntuación monótona donde MENOR es mejor — el
    engine ordena candidatos de menor a mayor. Se calcula a partir de
    propiedades explícitas (nº de fundamentos, localidad al grafo), nunca
    por similitud estadística.
    """

    node: KnowledgeNode
    pattern_name: str
    source_nodes: list[str]
    justification: str
    rank_score: float = 0.0
    metadata: dict = field(default_factory=dict)

    def render(self) -> str:
        lines = [
            f"CANDIDATO [{self.pattern_name}] score={self.rank_score:.2f}",
            f"  propone nodo: {self.node.id}",
            f"    status: {self.node.status.value}",
            f"    enunciado: {self.node.statement}",
            f"    inputs: {self.node.inputs}  outputs: {self.node.outputs}",
            f"    fundamentos: {self.node.foundations}",
        ]
        if self.node.validity_conditions:
            lines.append("    condiciones de validez:")
            for c in self.node.validity_conditions:
                lines.append(f"      - {c}")
        lines.append(f"  nodos-fuente: {', '.join(self.source_nodes)}")
        lines.append(f"  justificación: {self.justification}")
        return "\n".join(lines)
