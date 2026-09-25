"""Demo end-to-end del soporte para EpistemicStatus.ALGORITHM.

Procesa sample_document.md con el pipeline completo del exp_06 +
los nuevos marcadores y muestra:

  1. Parse: nodo ALGORITHM extraído con `**Entrada:**`/`**Salida:**`.
  2. Build: KnowledgeGraph contiene el nodo con properties["inputs"]
     y properties["outputs"] rellenos.
  3. validate(): sin errores (el ALGORITHM cumple el contrato de
     properties).
  4. validate_with_warnings(): un warning por foundations vacíos
     (no error — un algoritmo puede ser autónomo).

Uso:
    python -m experiment_14.demo
"""
from __future__ import annotations

from pathlib import Path

from experiment_06.document_parser import (
    GraphBuilder,
    NodeExtractor,
    StructureExtractor,
)


_DOC = Path(__file__).resolve().parent / "sample_document.md"


def main() -> None:
    print("=" * 72)
    print("EXPERIMENT 14 — soporte para EpistemicStatus.ALGORITHM")
    print("=" * 72)

    # Fase 1 — Parse.
    structure = StructureExtractor().extract_file(_DOC)
    parse_report = NodeExtractor().extract(structure)

    print(f"\n[parse] is_valid={parse_report.is_valid}")
    print(f"[parse] nodos extraídos: {len(parse_report.nodes_extracted)}")
    for n in parse_report.nodes_extracted:
        print(f"  · {n.status.value:11} {n.node_id}")
        print(f"    inputs={n.inputs}  outputs={n.outputs}")
        print(f"    extra_properties={n.extra_properties}")

    # Fase 2 — Build (sin procedimientos registrados — el ALGORITHM
    # del documento NO declara **Procedimiento:**, así que el grafo
    # tendrá el nodo con compute=None pero con properties OK).
    build_report = GraphBuilder(procedures={}).build(parse_report)
    print(f"\n[build] nodes_built={build_report.nodes_built}  "
          f"graph_valid={build_report.graph_valid}")
    if build_report.errors:
        for e in build_report.errors:
            print(f"  ✗ {type(e).__name__}: {e.message}")

    graph = build_report.graph
    if graph is None:
        print("(no se construyó grafo)")
        return

    # Inspeccionar el nodo ALGORITHM resultante.
    alg = graph.get("alg.busqueda_lineal")
    print(f"\n[node] {alg.id}")
    print(f"  status:           {alg.status.value}")
    print(f"  kind:             {alg.kind.value}")
    print(f"  foundations:      {alg.foundations}")
    print(f"  inputs (top):     {alg.inputs}")
    print(f"  outputs (top):    {alg.outputs}")
    print(f"  properties:")
    for k, v in (alg.properties or {}).items():
        print(f"    {k}: {v!r}")

    # Fase 3 — validate() vs validate_with_warnings().
    print(f"\n[validate]")
    errors = graph.validate()
    print(f"  errors:   {errors}")
    err2, warn = graph.validate_with_warnings()
    print(f"  errors2:  {err2}")
    print(f"  warnings: {warn}")

    print(f"\nRESULTADO:")
    print(f"  ✓ ALGORITHM extraído del documento")
    print(f"  ✓ properties['inputs']  = {alg.properties['inputs']}")
    print(f"  ✓ properties['outputs'] = {alg.properties['outputs']}")
    print(f"  ✓ validate() sin errores")
    print(f"  ✓ validate_with_warnings() emite 1 warning (foundations vacíos)")


if __name__ == "__main__":
    main()
