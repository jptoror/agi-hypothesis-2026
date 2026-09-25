"""Demo: especialista de pilas + razonamiento sobre complejidad.

Construye el especialista desde el documento (anclado al grafo
base de complejidad) y resuelve dos preguntas:

  1. "¿Cuál es la complejidad de push?"
     → thm.stack.push_complexity → fundamentos incluyen def.complexity.O1

  2. "¿Es push más eficiente que búsqueda lineal?"
     → thm.complexity.comparison aplicado con order(O1)=1, order(On)=3

Uso:
    python -m experiment_09.specialist_factory.demo
"""
from __future__ import annotations

from experiment_01.specialist import DomainContext, Problem
from experiment_09.knowledge_graph import build_complexity_base_graph

from .factory import StackSpecialistFactory


def main() -> None:
    factory = StackSpecialistFactory()
    result = factory.build()

    print(result.render())
    print()

    if not result.registered:
        return

    graph = result.graph

    # --- Pregunta 1: complejidad de push ---
    print("=" * 72)
    print("Pregunta 1: ¿Cuál es la complejidad de push?")
    print("=" * 72)
    push_thm = graph.get("thm.stack.push_complexity")
    print(f"  nodo: {push_thm.id}")
    print(f"  fundamentos: {push_thm.foundations}")
    # def.complexity.O1 está en foundations → es O(1).
    o1 = graph.get("def.complexity.O1")
    print(f"  complejidad: {o1.properties['symbol']} "
          f"(order={o1.properties['order']})")
    print()

    # --- Pregunta 2: ¿push más eficiente que búsqueda lineal? ---
    # Esta comparación involucra def.complexity.On, que NO entró al
    # grafo del especialista de pilas (no lo referencia el documento).
    # Es coherente: el especialista de pilas razona sobre pilas; las
    # comparaciones generales de complejidad viven en el grafo base.
    # Aquí lo invocamos directamente desde el grafo base.
    print("=" * 72)
    print("Pregunta 2: ¿Es push más eficiente que búsqueda lineal O(n)?")
    print("=" * 72)
    base = build_complexity_base_graph()
    comparison = base.get("thm.complexity.comparison")
    # `O1` lo lee del especialista; `On` del base.
    o1_order = graph.get("def.complexity.O1").properties["order"]
    on_order = base.get("def.complexity.On").properties["order"]
    answer = comparison.compute({"order_a": o1_order, "order_b": on_order})
    print(f"  thm.complexity.comparison(order_a={o1_order}, order_b={on_order})")
    print(f"  → {answer}")
    print(f"  push (O(1)) {'ES' if answer['more_efficient'] else 'NO ES'} "
          f"más eficiente que búsqueda lineal (O(n)) ✓")


if __name__ == "__main__":
    main()
