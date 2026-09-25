"""Catálogo de dominios expuesto al LLM.

El LLM no ve el grafo completo: ve un contrato. Para cada dominio,
qué tipos de contexto acepta, qué variables existen (con significado
y dimensión) y qué relaciones ejecutables hay. Cualquier traducción
que salga de ese contrato se rechaza ANTES de tocar el motor.

Las relaciones y los ids de nodos se leen de los grafos reales; las
descripciones y dimensiones de las variables son declaración del
ingeniero, porque los grafos del exp_01/03/06 no las modelan. Esa
declaración es la única pieza "a mano" del catálogo y está en un
sitio: `_VARIABLES`.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from experiment_01.knowledge_graph import KnowledgeGraph

from .expression import Dimension

LENGTH = Dimension.of(L=1)
AREA = Dimension.of(L=2)
MASS = Dimension.of(M=1)
SPEED = Dimension.of(L=1, T=-1)
ENERGY = Dimension.of(M=1, L=2, T=-2)
NUMBER = Dimension()


@dataclass(frozen=True)
class VariableSpec:
    name: str
    meaning: str
    dimension: Dimension


@dataclass
class DomainSpec:
    name: str
    context_kinds: list[str]
    variables: dict[str, VariableSpec]
    relations: list[str] = field(default_factory=list)     # "id: inputs -> outputs"
    node_ids: list[str] = field(default_factory=list)

    def describe(self) -> str:
        lines = [f"- domain '{self.name}' — context_kind one of {self.context_kinds}"]
        lines.append("  variables:")
        for v in self.variables.values():
            lines.append(f"    {v.name}: {v.meaning} [dimension {v.dimension.render()}]")
        lines.append("  executable relations:")
        for r in self.relations:
            lines.append(f"    {r}")
        return "\n".join(lines)


# Variables por dominio: significado y dimensión (declaración del ingeniero).
_VARIABLES: dict[str, list[VariableSpec]] = {
    "geometry": [
        VariableSpec("l", "side length of a square", LENGTH),
        VariableSpec("d", "diagonal of a square", LENGTH),
        VariableSpec("A", "area of a square", AREA),
        VariableSpec("a", "first leg of a right triangle", LENGTH),
        VariableSpec("b", "second leg of a right triangle", LENGTH),
        VariableSpec("c", "hypotenuse of a right triangle", LENGTH),
    ],
    "physics": [
        VariableSpec("m", "mass of an object", MASS),
        VariableSpec("v", "speed of an object", SPEED),
        VariableSpec("Ec", "kinetic energy of an object", ENERGY),
    ],
    "algebra": [
        VariableSpec("a", "coefficient of x in the equation a·x + b = 0", NUMBER),
        VariableSpec("b", "constant term in the equation a·x + b = 0", NUMBER),
        VariableSpec("x", "unknown of the linear equation a·x + b = 0", NUMBER),
    ],
}

_CONTEXT_KINDS: dict[str, list[str]] = {
    "geometry": ["square", "triangle.right", "triangle"],
    "physics": ["physics.object"],
    "algebra": ["linear_equation"],
}

# Magnitudes conocidas → dimensión. Sirve para comprobar la dimensión
# de una variable NUEVA (p. ej. 'P' de "perímetro") sin fiarse de la
# dimensión que declare el propio LLM.
QUANTITY_DIMENSIONS: dict[str, Dimension] = {
    "length": LENGTH, "side": LENGTH, "diagonal": LENGTH, "perimeter": LENGTH,
    "circumference": LENGTH, "radius": LENGTH, "diameter": LENGTH,
    "height": LENGTH, "width": LENGTH, "hypotenuse": LENGTH, "distance": LENGTH,
    "area": AREA, "volume": Dimension.of(L=3),
    "mass": MASS, "speed": SPEED, "velocity": SPEED,
    "momentum": Dimension.of(M=1, L=1, T=-1),
    "force": Dimension.of(M=1, L=1, T=-2), "weight": Dimension.of(M=1, L=1, T=-2),
    "energy": ENERGY, "kinetic energy": ENERGY, "potential energy": ENERGY,
    "work": ENERGY, "time": Dimension.of(T=1),
    "acceleration": Dimension.of(L=1, T=-2),
}


def quantity_dimension(quantity: str) -> Dimension | None:
    """Dimensión de una magnitud nombrada en lenguaje natural, si es conocida."""
    q = (quantity or "").strip().lower()
    if q in QUANTITY_DIMENSIONS:
        return QUANTITY_DIMENSIONS[q]
    # "perimeter of the square" → "perimeter"; se prueba la clave más larga primero.
    for key in sorted(QUANTITY_DIMENSIONS, key=len, reverse=True):
        if key in q:
            return QUANTITY_DIMENSIONS[key]
    return None


class DomainCatalog:
    """Contrato de dominios que el traductor y el broker muestran al LLM."""

    def __init__(self, graphs: dict[str, KnowledgeGraph]) -> None:
        self.domains: dict[str, DomainSpec] = {}
        for name, graph in graphs.items():
            relations = [
                f"{n.id}: {', '.join(n.inputs)} -> {', '.join(n.outputs)}"
                for n in graph
                if n.is_executable() and n.outputs
            ]
            self.domains[name] = DomainSpec(
                name=name,
                context_kinds=list(_CONTEXT_KINDS[name]),
                variables={v.name: v for v in _VARIABLES[name]},
                relations=relations,
                node_ids=[n.id for n in graph],
            )

    def get(self, domain: str) -> DomainSpec | None:
        return self.domains.get(domain)

    def describe(self) -> str:
        return "\n".join(d.describe() for d in self.domains.values())
