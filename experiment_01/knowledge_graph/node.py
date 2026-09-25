from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional


class EpistemicStatus(str, Enum):
    """Estado epistemológico de un nodo de conocimiento.

    AXIOM       — se acepta sin demostración, base del sistema.
    DEFINITION  — introduce un término; no es verdad ni falsedad, es convención.
    THEOREM     — verdad derivable a partir de axiomas y definiciones.
    HYPOTHESIS  — afirmación propuesta, aún no demostrada en este grafo.
    ALGORITHM   — procedimiento operativo con entradas y salidas declaradas
                  en `properties["inputs"]` / `properties["outputs"]`. NO
                  requiere foundations (a diferencia de THEOREM); si carece
                  de cualquier dependencia declarada, validate_with_warnings
                  emite un warning (no un error). Modela operaciones que
                  se aplican como receta sin necesidad de demostración.
    """

    AXIOM = "axiom"
    DEFINITION = "definition"
    THEOREM = "theorem"
    HYPOTHESIS = "hypothesis"
    ALGORITHM = "algorithm"


class NodeKind(str, Enum):
    """Categoría operativa del nodo — para que el especialista sepa cómo usarlo."""

    CONCEPT = "concept"          # "cuadrado", "diagonal", "área"
    RELATION = "relation"        # "d^2 = l^2 + l^2"
    PROCEDURE = "procedure"      # cómputo ejecutable asociado a la relación


@dataclass
class KnowledgeNode:
    """Un nodo del grafo de conocimiento.

    El razonamiento del especialista se apoya en estos campos — no en un modelo
    estadístico. Cada nodo declara explícitamente qué sabe, de qué depende,
    cuándo es aplicable y con qué nivel de certeza.
    """

    id: str
    statement: str
    status: EpistemicStatus
    kind: NodeKind

    # IDs de otros nodos que fundan la verdad de este nodo (axiomas,
    # definiciones o teoremas previos). Para un AXIOM o DEFINITION esta
    # lista está vacía.
    foundations: list[str] = field(default_factory=list)

    # Precondiciones que deben cumplirse para que el nodo sea aplicable en
    # un razonamiento. Expresadas como strings legibles por humanos; el
    # especialista las verifica contra el contexto del problema.
    validity_conditions: list[str] = field(default_factory=list)

    # Para nodos de tipo RELATION/PROCEDURE, una implementación ejecutable.
    # Recibe un dict de variables conocidas y devuelve un dict con lo derivado.
    # Debe ser una función pura y determinista.
    compute: Optional[Callable[[dict], dict]] = None

    # Variables que el procedimiento espera como entrada y produce como salida.
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)

    # Justificación en lenguaje natural — para que el razonamiento sea auditable.
    rationale: str = ""

    # Propiedades estructuradas del nodo, legibles por máquina.
    # Sirven para que componentes de descubrimiento (p. ej. el
    # hypothesis_engine del experimento 02) razonen sobre el nodo sin
    # parsear lenguaje natural. Ejemplos: {"n_sides": 4, "sides_equal": True}.
    properties: dict = field(default_factory=dict)

    def is_executable(self) -> bool:
        return self.compute is not None

    def describe(self) -> str:
        parts = [
            f"[{self.status.value.upper()}] {self.id}: {self.statement}",
        ]
        if self.foundations:
            parts.append(f"  fundamentos: {', '.join(self.foundations)}")
        if self.validity_conditions:
            parts.append("  condiciones de validez:")
            for c in self.validity_conditions:
                parts.append(f"    - {c}")
        if self.rationale:
            parts.append(f"  justificación: {self.rationale}")
        return "\n".join(parts)
