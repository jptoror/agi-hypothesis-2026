"""Demo del especialista de colas.

Verifica los 3 puntos pedidos:
  1. graph.validate() sin errores
  2. Nodos construidos a mano: 0
  3. Responde "¿Cuál es la complejidad de push en una cola?"
     → thm.cola.complejidad.push → O(1)

Imprime tabla de nodos extraídos al estilo del exp_09.

Uso:
    python -m experiment_13.specialist_factory.demo
"""
from __future__ import annotations

from experiment_09.knowledge_graph import build_complexity_base_graph

from .factory import QueueSpecialistFactory


def main() -> None:
    factory = QueueSpecialistFactory()
    result = factory.build()

    print(result.render())
    print()

    if not result.registered:
        for e in result.errors:
            print(f"  ✗ {e}")
        return

    graph = result.graph

    # 1. validate()
    errors = graph.validate()
    print("=" * 72)
    print("1. graph.validate()")
    print("=" * 72)
    print(f"  errores: {len(errors)} {'✓' if not errors else '✗'}")
    if errors:
        for e in errors:
            print(f"    - {e}")
    print()

    # 2. Nodos construidos a mano
    base = build_complexity_base_graph()
    base_ids = {n.id for n in base}
    manual = [
        n.id for n in graph
        if not (n.properties or {}).get("extracted_from_document")
        and n.id not in base_ids
    ]
    print("=" * 72)
    print("2. Nodos construidos a mano")
    print("=" * 72)
    print(f"  manuales: {len(manual)} {'✓' if not manual else '✗'}")
    if manual:
        for nid in manual:
            print(f"    - {nid}")
    print()

    # 3. Pregunta canónica.
    print("=" * 72)
    print("3. ¿Cuál es la complejidad de push en una cola?")
    print("=" * 72)
    push_thm = graph.get("thm.cola.complejidad.push")
    print(f"  nodo: {push_thm.id}")
    print(f"  fundamentos: {push_thm.foundations}")
    complexity_id = next(
        (f for f in push_thm.foundations if f.startswith("def.complexity.")),
        None,
    )
    if complexity_id:
        c = graph.get(complexity_id)
        symbol = (c.properties or {}).get("symbol", complexity_id)
        print(f"  complejidad: {symbol} {'✓' if symbol == 'O(1)' else '✗'}")
    print()

    # Tabla de nodos extraídos.
    print("=" * 72)
    print("TABLA DE NODOS EXTRAÍDOS")
    print("=" * 72)
    parse_nodes = result.underlying.parse_report.nodes_extracted
    print(
        f"{'#':>2}  {'tipo':<11}  {'id':<40}  marcadores"
    )
    print("-" * 78)
    for i, n in enumerate(parse_nodes, 1):
        markers = []
        if any(f.startswith("def.complexity.") for f in n.foundations):
            comp = next(
                f for f in n.foundations if f.startswith("def.complexity.")
            )
            markers.append(f"Complejidad={comp.split('.')[-1]}")
        if n.conditions:
            markers.append(f"Condición×{len(n.conditions)}")
        if any(
            f for f in n.foundations
            if not f.startswith("def.complexity.")
        ):
            others = [
                f for f in n.foundations
                if not f.startswith("def.complexity.")
            ]
            markers.append(f"Depende de×{len(others)}")
        marker_str = ", ".join(markers) if markers else "—"
        print(f"{i:>2}  {n.status.value:<11}  {n.node_id:<40}  {marker_str}")

    print()
    print("=" * 72)
    print("PROCEDENCIA DE LOS NODOS DEL GRAFO FINAL")
    print("=" * 72)
    from_doc = sum(
        1 for n in graph
        if (n.properties or {}).get("extracted_from_document")
    )
    from_base = sum(1 for n in graph if n.id in base_ids)
    print(f"  del documento: {from_doc}")
    print(f"  del base de complejidad: {from_base}")
    print(f"  total: {len(graph)}")


if __name__ == "__main__":
    main()
