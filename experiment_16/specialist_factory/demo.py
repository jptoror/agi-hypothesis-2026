"""Demo del especialista C++ mínimo (exp_16).

Ejercita los tres puntos canónicos del experimento:

  1. graph.validate() sin errores → la fusión cpp + ch1 es coherente.
  2. Nodos construidos a mano: 0 → todo viene del documento o del
     base_graph (especialista ch1 del exp_15).
  3. Pregunta canónica: "¿Cómo se expresa alg.greedy_coloring en C++?"
     → resolver `alg.cpp.greedy_coloring_impl.compute(...)` y comprobar
     que la traza atraviesa nodos de AMBOS especialistas (ch1 + cpp).

Uso:
    python -m experiment_16.specialist_factory.demo
"""
from __future__ import annotations

from experiment_15.specialist_factory import AlgorithmsCh1SpecialistFactory

from .factory import CppMinimalSpecialistFactory


def main() -> None:
    factory = CppMinimalSpecialistFactory()
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

    # 2. Nodos construidos a mano: ninguno. El discriminador es la
    # unión {nodos del documento cpp} ∪ {nodos del base_graph ch1}.
    # `extracted_from_document=True` es propiedad heredada — no
    # distingue por especialista.
    ch1_graph = AlgorithmsCh1SpecialistFactory().build().graph
    ch1_ids = {n.id for n in ch1_graph}
    cpp_doc_ids_pre = {
        n.node_id
        for n in result.underlying.parse_report.nodes_extracted
    }
    manual = [
        n.id for n in graph
        if n.id not in cpp_doc_ids_pre and n.id not in ch1_ids
    ]
    print("=" * 72)
    print("2. Nodos construidos a mano")
    print("=" * 72)
    print(f"  manuales: {len(manual)} {'✓' if not manual else '✗'}")
    for nid in manual:
        print(f"    - {nid}")
    print()

    # 3. Pregunta canónica: derivar greedy_coloring en C++.
    print("=" * 72)
    print("3. ¿Cómo se expresa alg.greedy_coloring en C++?")
    print("=" * 72)
    impl_id = "alg.cpp.greedy_coloring_impl"
    if not graph.has(impl_id):
        print(f"  ✗ el grafo no contiene '{impl_id}'")
        return
    impl = graph.get(impl_id)
    if impl.compute is None:
        print(f"  ✗ '{impl_id}' no tiene compute resuelto")
        return

    inputs = {
        "abstract_node": "alg.greedy_coloring",
        "target_container": "no_col",
    }
    result_dict = impl.compute(inputs)
    code = result_dict["cpp_code"]
    print("  inputs:")
    for k, v in inputs.items():
        print(f"    {k}: {v}")
    print("  cpp_code:")
    for line in code.splitlines():
        print(f"    | {line}")
    print()

    # Traza: ancestros transitivos del nodo de mapping. El
    # discriminador honesto es la pertenencia al base_graph del
    # ch1 — los nodos importados conservan `extracted_from_document=True`
    # de su documento de origen, así que esa propiedad NO sirve para
    # distinguir el origen aquí.
    cpp_doc_ids = {
        n.node_id
        for n in result.underlying.parse_report.nodes_extracted
    }
    print("=" * 72)
    print("TRAZA — ancestros transitivos de alg.cpp.greedy_coloring_impl")
    print("=" * 72)
    ancestors = list(graph.transitive_foundations(impl_id))
    print(f"{'origen':<12}  {'tipo':<11}  id")
    print("-" * 72)
    for n in sorted(ancestors, key=lambda x: x.id):
        if n.id in cpp_doc_ids:
            origin = "cpp_doc"
        elif n.id in ch1_ids:
            origin = "ch1_base"
        else:
            origin = "?"
        print(f"{origin:<12}  {n.status.value:<11}  {n.id}")

    origins = {
        "cpp_doc" if n.id in cpp_doc_ids
        else "ch1_base" if n.id in ch1_ids
        else "?"
        for n in ancestors
    }
    cross = "cpp_doc" in origins and "ch1_base" in origins
    print()
    print(f"  traza atraviesa AMBOS especialistas: "
          f"{'✓' if cross else '✗'}")


if __name__ == "__main__":
    main()
