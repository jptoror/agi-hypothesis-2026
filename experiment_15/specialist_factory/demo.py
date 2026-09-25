"""Demo del especialista del capítulo 1 (algoritmos).

Verifica los puntos canónicos del patrón:
  1. graph.validate() sin errores
  2. Nodos construidos a mano: 0
  3. Pregunta específica del capítulo:
     "¿Cuál es la complejidad del coloreo greedy?"
     → thm.greedy_coloring.complejidad → O(n³)

Imprime también la tabla de nodos extraídos al estilo del exp_09/13.

Uso:
    python -m experiment_15.specialist_factory.demo
"""
from __future__ import annotations

from experiment_09.knowledge_graph import build_complexity_base_graph

from .factory import AlgorithmsCh1SpecialistFactory


def main() -> None:
    factory = AlgorithmsCh1SpecialistFactory()
    result = factory.build()

    print(result.render())
    print()

    if not result.registered:
        for e in result.errors:
            print(f"  ✗ {e}")
        return

    graph = result.graph

    # 1. validate()
    errors, warnings = graph.validate_with_warnings()
    print("=" * 72)
    print("1. graph.validate()")
    print("=" * 72)
    print(f"  errores:  {len(errors)} {'✓' if not errors else '✗'}")
    print(f"  warnings: {len(warnings)}")
    for e in errors:
        print(f"    - {e}")
    for w in warnings:
        print(f"    ! {w}")
    print()

    # 2. Nodos construidos a mano.
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
    for nid in manual:
        print(f"    - {nid}")
    print()

    # 3. Pregunta específica del capítulo.
    print("=" * 72)
    print("3. ¿Cuál es la complejidad del coloreo greedy?")
    print("=" * 72)
    target = "thm.greedy_coloring.complejidad"
    if not graph.has(target):
        print(f"  ✗ el grafo no contiene '{target}'")
    else:
        thm = graph.get(target)
        print(f"  nodo: {thm.id}")
        print(f"  fundamentos: {thm.foundations}")
        complexity_id = next(
            (f for f in thm.foundations if f.startswith("def.complexity.")),
            None,
        )
        if complexity_id:
            c = graph.get(complexity_id)
            symbol = (c.properties or {}).get(
                "symbol",
                (c.properties or {}).get("complexity_class", complexity_id),
            )
            ok = symbol == "O(n³)"
            print(f"  complejidad: {symbol} {'✓' if ok else '✗'}")
    print()

    # Tabla de nodos extraídos.
    print("=" * 72)
    print("TABLA DE NODOS EXTRAÍDOS")
    print("=" * 72)
    parse_nodes = result.underlying.parse_report.nodes_extracted
    print(f"{'#':>2}  {'tipo':<11}  {'id':<48}  marcadores")
    print("-" * 110)
    for i, n in enumerate(parse_nodes, 1):
        markers = []
        comp = next(
            (f for f in n.foundations if f.startswith("def.complexity.")),
            None,
        )
        if comp:
            markers.append(f"Complejidad={comp.split('.')[-1]}")
        if n.conditions:
            markers.append(f"Condición×{len(n.conditions)}")
        if n.procedure_name:
            markers.append(f"Procedimiento={n.procedure_name}")
        if n.inputs:
            markers.append(f"Entrada×{len(n.inputs)}")
        if n.outputs:
            markers.append(f"Salida×{len(n.outputs)}")
        others = [
            f for f in n.foundations
            if not f.startswith("def.complexity.")
        ]
        if others:
            markers.append(f"Depende de×{len(others)}")
        marker_str = ", ".join(markers) if markers else "—"
        print(f"{i:>2}  {n.status.value:<11}  {n.node_id:<48}  {marker_str}")

    # Conteo por tipo.
    print()
    print("=" * 72)
    print("CONTEO POR TIPO")
    print("=" * 72)
    from collections import Counter
    counts = Counter(n.status.value for n in parse_nodes)
    for status in ("axiom", "definition", "theorem", "algorithm", "hypothesis"):
        c = counts.get(status, 0)
        if c:
            print(f"  {status:11} {c}")
    print(f"  {'TOTAL':11} {sum(counts.values())}")

    # Procedencia del grafo final.
    print()
    print("=" * 72)
    print("PROCEDENCIA DE LOS NODOS DEL GRAFO FINAL")
    print("=" * 72)
    from_doc = sum(
        1 for n in graph
        if (n.properties or {}).get("extracted_from_document")
    )
    from_base = sum(1 for n in graph if n.id in base_ids)
    print(f"  del documento:           {from_doc}")
    print(f"  del base de complejidad: {from_base}")
    print(f"  total:                   {len(graph)}")


if __name__ == "__main__":
    main()
