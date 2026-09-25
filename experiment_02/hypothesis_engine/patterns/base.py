from __future__ import annotations

from abc import ABC, abstractmethod

from experiment_01.knowledge_graph import KnowledgeGraph
from experiment_01.specialist import Problem

from ..candidate import HypothesisCandidate


class Pattern(ABC):
    """Interfaz de un patrón estructural de generación de hipótesis.

    Un patrón es una PLANTILLA explícita — no un modelo. Dada una variable
    objetivo que el grafo no sabe producir, y el grafo actual, intenta
    instanciar la plantilla usando nodos existentes como materia prima
    estructural (leyendo sus `properties`, sus `outputs`, su `status`).

    Cada patrón debe ser auditable: un humano leyendo la clase debe poder
    decir "sí, este patrón encaja aquí" o "no, no aplica" sin ejecutar
    nada. No hay heurísticas opacas ni modelos entrenados.
    """

    name: str

    @abstractmethod
    def propose(
        self,
        missing_variable: str,
        problem: Problem,
        graph: KnowledgeGraph,
    ) -> list[HypothesisCandidate]:
        """Devuelve 0..N candidatos. Vacío si el patrón no aplica.

        El patrón NO añade nodos al grafo — sólo los propone. La decisión
        de incorporarlos queda para componentes posteriores (validator,
        orchestrator).
        """
        ...
