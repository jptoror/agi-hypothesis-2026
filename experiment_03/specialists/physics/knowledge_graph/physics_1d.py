"""Grafo de conocimiento de mecánica clásica 1D — nodos mínimos.

Comparte TIPO con el grafo de Geometría (KnowledgeNode, EpistemicStatus,
NodeKind) pero es un grafo independiente. Que reutilicemos el id
`ax.arithmetic.real_numbers` es deliberado: ambos grafos necesitan ese
axioma y declararlo dos veces (uno por dominio) es más limpio que crear
dependencias cruzadas a nivel de grafo. Al integrar los dos dominios en
el orchestrator del exp_03 podremos verificar que los axiomas con mismo
id son consistentes entre sí.
"""
from __future__ import annotations

from experiment_01.knowledge_graph import (
    EpistemicStatus,
    KnowledgeGraph,
    KnowledgeNode,
    NodeKind,
)


def build_physics_graph() -> KnowledgeGraph:
    g = KnowledgeGraph()

    # ========== AXIOMAS ==========
    g.add(KnowledgeNode(
        id="ax.arithmetic.real_numbers",
        statement="Los números reales forman un cuerpo ordenado: +, -, *, / y <=.",
        status=EpistemicStatus.AXIOM,
        kind=NodeKind.RELATION,
        rationale=(
            "Necesario para que las fórmulas físicas produzcan valores "
            "numéricos. Declarado localmente en este grafo; su id coincide "
            "con el del grafo de Geometría por convención — mismo axioma."
        ),
    ))

    g.add(KnowledgeNode(
        id="ax.mass.nonnegative",
        statement="La masa es un escalar real no negativo.",
        status=EpistemicStatus.AXIOM,
        kind=NodeKind.RELATION,
        rationale="Dominio físico de la magnitud masa.",
    ))

    # ========== DEFINICIONES ==========
    g.add(KnowledgeNode(
        id="def.mass",
        statement="Masa m de un objeto — escalar real no negativo.",
        status=EpistemicStatus.DEFINITION,
        kind=NodeKind.CONCEPT,
        foundations=["ax.mass.nonnegative"],
        validity_conditions=["m >= 0"],
        properties={"symbol": "m", "unit": "kg"},
    ))

    g.add(KnowledgeNode(
        id="def.velocity",
        statement="Velocidad v de un objeto — escalar real (signo = sentido).",
        status=EpistemicStatus.DEFINITION,
        kind=NodeKind.CONCEPT,
        foundations=["ax.arithmetic.real_numbers"],
        properties={"symbol": "v", "unit": "m/s"},
    ))

    g.add(KnowledgeNode(
        id="def.kinetic_energy",
        statement="Energía cinética Ec — magnitud asociada al movimiento del objeto.",
        status=EpistemicStatus.DEFINITION,
        kind=NodeKind.CONCEPT,
        foundations=["ax.arithmetic.real_numbers"],
        properties={"symbol": "Ec", "unit": "J"},
    ))

    # ========== TEOREMAS ==========
    g.add(KnowledgeNode(
        id="thm.kinetic_energy",
        statement="La energía cinética de un objeto de masa m a velocidad v es Ec = ½·m·v².",
        status=EpistemicStatus.THEOREM,
        kind=NodeKind.RELATION,
        foundations=[
            "def.mass",
            "def.velocity",
            "def.kinetic_energy",
            "ax.arithmetic.real_numbers",
        ],
        validity_conditions=["m >= 0"],
        inputs=["m", "v"],
        outputs=["Ec"],
        compute=lambda vals: {"Ec": 0.5 * vals["m"] * (vals["v"] ** 2)},
        rationale=(
            "Teorema clásico de la mecánica newtoniana. Ec = ½mv² se deduce "
            "del trabajo necesario para acelerar una masa m de 0 a v."
        ),
    ))

    return g
