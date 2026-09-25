"""Grafo base de complejidad algorítmica.

Pieza compartible: cualquier especialista de estructuras de datos
puede usarlo como grafo fundamento para anclar la noción de "esta
operación es O(1)" sin redefinir el concepto de complejidad.

Schema de propiedades de los nodos de clase `def.complexity.*`:

  order: int
      Posición en el orden total de complejidad asintótica. Menor =
      más eficiente. Los valores son discretos y arbitrarios — sólo
      su ORDEN RELATIVO es significativo. Si en el futuro añadimos
      def.complexity.Ologn_squared o def.complexity.O2n, basta con
      asignarles un order coherente con el orden total.

  symbol: str
      Notación matemática estándar (p. ej. "O(1)", "O(n log n)").
      Pieza informativa, no se usa para el razonamiento.

El teorema `thm.complexity.comparison` consume `order_a` y `order_b`
(extraídos por el caller a partir de `properties.order` de dos nodos
def.complexity.*) y devuelve `more_efficient: True/False`. Es la
única pieza ejecutable del grafo — el resto son axiomas y
definiciones que enuncian el orden total.
"""
from __future__ import annotations

from experiment_01.knowledge_graph import (
    EpistemicStatus,
    KnowledgeGraph,
    KnowledgeNode,
    NodeKind,
)


def build_complexity_base_graph() -> KnowledgeGraph:
    g = KnowledgeGraph()

    # ========== AXIOMA ==========
    g.add(KnowledgeNode(
        id="ax.complexity.total_order",
        statement=(
            "Las clases de complejidad asintótica admiten un orden "
            "total: dadas dos clases A y B, o A es estrictamente más "
            "eficiente que B, o B lo es que A, o son equivalentes. "
            "El orden se materializa con un entero `order`: menor "
            "valor = más eficiente."
        ),
        status=EpistemicStatus.AXIOM,
        kind=NodeKind.RELATION,
        rationale=(
            "Operacionaliza la jerarquía clásica O(1) < O(log n) < "
            "O(n) < O(n log n) < O(n²) sin codificar la semántica "
            "asintótica formal. El razonador comparará órdenes; el "
            "significado matemático queda fuera del alcance."
        ),
    ))

    # ========== DEFINICIONES (clases de complejidad) ==========
    g.add(KnowledgeNode(
        id="def.complexity.O1",
        statement=(
            "Complejidad constante O(1): el coste de la operación no "
            "depende del tamaño de la entrada."
        ),
        status=EpistemicStatus.DEFINITION,
        kind=NodeKind.CONCEPT,
        foundations=["ax.complexity.total_order"],
        properties={"order": 1, "symbol": "O(1)"},
    ))

    g.add(KnowledgeNode(
        id="def.complexity.Ologn",
        statement=(
            "Complejidad logarítmica O(log n): el coste crece como el "
            "logaritmo del tamaño de la entrada."
        ),
        status=EpistemicStatus.DEFINITION,
        kind=NodeKind.CONCEPT,
        foundations=["ax.complexity.total_order"],
        properties={"order": 2, "symbol": "O(log n)"},
    ))

    g.add(KnowledgeNode(
        id="def.complexity.On",
        statement=(
            "Complejidad lineal O(n): el coste crece proporcionalmente "
            "al tamaño de la entrada."
        ),
        status=EpistemicStatus.DEFINITION,
        kind=NodeKind.CONCEPT,
        foundations=["ax.complexity.total_order"],
        properties={"order": 3, "symbol": "O(n)"},
    ))

    g.add(KnowledgeNode(
        id="def.complexity.Onlogn",
        statement=(
            "Complejidad O(n log n): coste característico de los "
            "algoritmos de ordenación por comparación."
        ),
        status=EpistemicStatus.DEFINITION,
        kind=NodeKind.CONCEPT,
        foundations=["ax.complexity.total_order"],
        properties={"order": 4, "symbol": "O(n log n)"},
    ))

    g.add(KnowledgeNode(
        id="def.complexity.On2",
        statement=(
            "Complejidad cuadrática O(n²): el coste crece como el "
            "cuadrado del tamaño de la entrada."
        ),
        status=EpistemicStatus.DEFINITION,
        kind=NodeKind.CONCEPT,
        foundations=["ax.complexity.total_order"],
        properties={"order": 5, "symbol": "O(n²)"},
    ))

    # Añadido en posterior iteración: cubic complexity. Notar que
    # `properties` lleva `complexity_class` en lugar de `symbol`
    # (variación literal del enunciado original). El resto del
    # proyecto consume `properties.order` para la comparación
    # numérica vía thm.complexity.comparison; el campo descriptivo
    # del símbolo no se usa para razonamiento, sólo para render.
    g.add(KnowledgeNode(
        id="def.complexity.On3",
        statement=(
            "O(n³) — tiempo cúbico, crece con el cubo del tamaño"
        ),
        status=EpistemicStatus.DEFINITION,
        kind=NodeKind.CONCEPT,
        foundations=["ax.complexity.total_order", "def.complexity.On2"],
        properties={"complexity_class": "O(n³)", "order": 6},
    ))

    # ========== TEOREMA ==========
    g.add(KnowledgeNode(
        id="thm.complexity.comparison",
        statement=(
            "Dadas dos clases de complejidad con órdenes `order_a` y "
            "`order_b`, A es más eficiente que B si y sólo si "
            "order_a < order_b."
        ),
        status=EpistemicStatus.THEOREM,
        kind=NodeKind.RELATION,
        foundations=["ax.complexity.total_order"],
        validity_conditions=[
            "order_a y order_b son enteros provenientes de "
            "properties.order de algún def.complexity.*",
        ],
        inputs=["order_a", "order_b"],
        outputs=["more_efficient"],
        compute=lambda v: {"more_efficient": v["order_a"] < v["order_b"]},
        rationale=(
            "Trivial dado el axioma del orden total: menor order = "
            "más eficiente. La comparación se hace por enteros, no "
            "por símbolos asintóticos — eso evita parsear notación."
        ),
    ))

    return g
