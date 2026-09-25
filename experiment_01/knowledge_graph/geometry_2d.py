from __future__ import annotations

import math

from .graph import KnowledgeGraph
from .node import EpistemicStatus, KnowledgeNode, NodeKind


def build_geometry_2d_graph() -> KnowledgeGraph:
    """Construye el grafo base de geometría 2D.

    El orden de inserción respeta la jerarquía epistemológica: primero
    axiomas, luego definiciones, finalmente teoremas. Cada teorema declara
    sus fundamentos — así el especialista puede reconstruir la derivación
    y el orquestador puede detectar qué falta si se desactiva un nodo.
    """
    g = KnowledgeGraph()

    # ========== AXIOMAS ==========
    g.add(KnowledgeNode(
        id="ax.equality.reflexive",
        statement="Para todo x, x = x.",
        status=EpistemicStatus.AXIOM,
        kind=NodeKind.RELATION,
        rationale="Axioma de identidad. Base de toda manipulación simbólica.",
    ))

    g.add(KnowledgeNode(
        id="ax.equality.substitution",
        statement="Si a = b, entonces a puede sustituirse por b en cualquier expresión.",
        status=EpistemicStatus.AXIOM,
        kind=NodeKind.RELATION,
        rationale="Permite reescribir expresiones equivalentes durante la derivación.",
    ))

    g.add(KnowledgeNode(
        id="ax.arithmetic.real_numbers",
        statement="Los números reales forman un cuerpo ordenado: +, -, *, / y <=.",
        status=EpistemicStatus.AXIOM,
        kind=NodeKind.RELATION,
        rationale="Necesario para que las fórmulas geométricas produzcan valores numéricos.",
    ))

    g.add(KnowledgeNode(
        id="ax.length.nonnegative",
        statement="La longitud de un segmento es un número real no negativo.",
        status=EpistemicStatus.AXIOM,
        kind=NodeKind.RELATION,
        rationale="Define el dominio válido para operar con longitudes.",
    ))

    # ========== DEFINICIONES ==========
    g.add(KnowledgeNode(
        id="def.point",
        statement="Un punto es una localización en el plano, sin dimensión.",
        status=EpistemicStatus.DEFINITION,
        kind=NodeKind.CONCEPT,
    ))

    g.add(KnowledgeNode(
        id="def.segment",
        statement="Un segmento es el conjunto de puntos entre dos extremos A y B.",
        status=EpistemicStatus.DEFINITION,
        kind=NodeKind.CONCEPT,
        foundations=["def.point"],
    ))

    g.add(KnowledgeNode(
        id="def.length",
        statement="La longitud de un segmento AB es la distancia euclídea entre A y B.",
        status=EpistemicStatus.DEFINITION,
        kind=NodeKind.CONCEPT,
        foundations=["def.segment", "ax.length.nonnegative"],
    ))

    g.add(KnowledgeNode(
        id="def.angle.right",
        statement="Un ángulo recto es un ángulo de 90°.",
        status=EpistemicStatus.DEFINITION,
        kind=NodeKind.CONCEPT,
    ))

    g.add(KnowledgeNode(
        id="def.triangle",
        statement="Un triángulo es una figura de tres vértices no colineales unidos por segmentos.",
        status=EpistemicStatus.DEFINITION,
        kind=NodeKind.CONCEPT,
        foundations=["def.point", "def.segment"],
    ))

    g.add(KnowledgeNode(
        id="def.triangle.right",
        statement="Un triángulo rectángulo es un triángulo que contiene un ángulo recto.",
        status=EpistemicStatus.DEFINITION,
        kind=NodeKind.CONCEPT,
        foundations=["def.triangle", "def.angle.right"],
    ))

    g.add(KnowledgeNode(
        id="def.quadrilateral",
        statement="Un cuadrilátero es un polígono de cuatro lados.",
        status=EpistemicStatus.DEFINITION,
        kind=NodeKind.CONCEPT,
        foundations=["def.segment"],
        properties={"n_sides": 4},
    ))

    g.add(KnowledgeNode(
        id="def.square",
        statement=(
            "Un cuadrado es un cuadrilátero con cuatro lados iguales y cuatro "
            "ángulos rectos."
        ),
        status=EpistemicStatus.DEFINITION,
        kind=NodeKind.CONCEPT,
        foundations=["def.quadrilateral", "def.angle.right", "def.length"],
        validity_conditions=[
            "las cuatro longitudes de lado son iguales",
            "los cuatro ángulos son rectos",
        ],
        properties={
            "n_sides": 4,
            "sides_equal": True,
            "side_variable": "l",
            "figure_kind": "square",
        },
    ))

    g.add(KnowledgeNode(
        id="def.diagonal",
        statement=(
            "Una diagonal de un polígono es un segmento que une dos vértices "
            "no adyacentes."
        ),
        status=EpistemicStatus.DEFINITION,
        kind=NodeKind.CONCEPT,
        foundations=["def.segment"],
    ))

    g.add(KnowledgeNode(
        id="def.diagonal.square",
        statement=(
            "La diagonal de un cuadrado une dos vértices opuestos y es la "
            "hipotenusa del triángulo rectángulo formado con dos lados consecutivos."
        ),
        status=EpistemicStatus.DEFINITION,
        kind=NodeKind.CONCEPT,
        foundations=["def.square", "def.diagonal", "def.triangle.right"],
        validity_conditions=["la figura debe ser un cuadrado"],
        rationale=(
            "Trazar la diagonal parte el cuadrado en dos triángulos rectángulos "
            "congruentes cuyos catetos son los lados y cuya hipotenusa es la diagonal."
        ),
    ))

    g.add(KnowledgeNode(
        id="def.area",
        statement="El área de una figura plana es la medida de la superficie que ocupa.",
        status=EpistemicStatus.DEFINITION,
        kind=NodeKind.CONCEPT,
        foundations=["ax.arithmetic.real_numbers"],
    ))

    # ========== TEOREMAS ==========
    g.add(KnowledgeNode(
        id="thm.pythagoras",
        statement=(
            "En un triángulo rectángulo con catetos a y b e hipotenusa c, "
            "se cumple a² + b² = c²."
        ),
        status=EpistemicStatus.THEOREM,
        kind=NodeKind.RELATION,
        foundations=[
            "def.triangle.right",
            "def.length",
            "ax.arithmetic.real_numbers",
        ],
        validity_conditions=[
            "el triángulo debe ser rectángulo",
            "a, b, c son longitudes no negativas",
        ],
        inputs=["a", "b"],
        outputs=["c"],
        compute=lambda v: {"c": math.sqrt(v["a"] ** 2 + v["b"] ** 2)},
        rationale=(
            "Teorema clásico de Pitágoras. Permite relacionar los lados y la "
            "hipotenusa de cualquier triángulo rectángulo."
        ),
    ))

    g.add(KnowledgeNode(
        id="thm.square.area_from_side",
        statement="El área de un cuadrado de lado l es A = l².",
        status=EpistemicStatus.THEOREM,
        kind=NodeKind.RELATION,
        foundations=["def.square", "def.area", "ax.arithmetic.real_numbers"],
        validity_conditions=["la figura debe ser un cuadrado", "l >= 0"],
        inputs=["l"],
        outputs=["A"],
        compute=lambda v: {"A": v["l"] ** 2},
        rationale=(
            "Un cuadrado de lado l puede cubrirse por l·l unidades cuadradas, "
            "de donde A = l²."
        ),
    ))

    g.add(KnowledgeNode(
        id="thm.square.side_from_diagonal",
        statement=(
            "En un cuadrado de lado l y diagonal d se cumple d² = 2·l², "
            "o equivalentemente l = d / √2."
        ),
        status=EpistemicStatus.THEOREM,
        kind=NodeKind.RELATION,
        foundations=["def.diagonal.square", "thm.pythagoras"],
        validity_conditions=["la figura debe ser un cuadrado", "d >= 0"],
        inputs=["d"],
        outputs=["l"],
        compute=lambda v: {"l": v["d"] / math.sqrt(2)},
        rationale=(
            "Aplicando Pitágoras al triángulo rectángulo formado por dos lados "
            "consecutivos (catetos = l) y la diagonal (hipotenusa = d): "
            "l² + l² = d²  ⇒  2l² = d²  ⇒  l = d/√2."
        ),
    ))

    g.add(KnowledgeNode(
        id="thm.square.area_from_diagonal",
        statement="El área de un cuadrado de diagonal d es A = d²/2.",
        status=EpistemicStatus.THEOREM,
        kind=NodeKind.RELATION,
        foundations=[
            "thm.square.side_from_diagonal",
            "thm.square.area_from_side",
            "ax.equality.substitution",
        ],
        validity_conditions=["la figura debe ser un cuadrado", "d >= 0"],
        inputs=["d"],
        outputs=["A"],
        compute=lambda v: {"A": (v["d"] ** 2) / 2.0},
        rationale=(
            "Derivable: l = d/√2 (thm.square.side_from_diagonal) y A = l² "
            "(thm.square.area_from_side). Sustituyendo: A = (d/√2)² = d²/2."
        ),
    ))

    return g
