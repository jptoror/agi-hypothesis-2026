"""Demo del GraphBuilder sobre algebra_ch3.md.

Encadena las 3 fases:
  StructureExtractor → NodeExtractor → GraphBuilder

Y muestra:
  - el ParseReport (5 nodos extraídos, 0 errores)
  - el BuildReport (5 nodos construidos, graph.validate() OK,
    orden topológico determinista)
  - una verificación numérica del compute resuelto: 3x + 6 = 0 → -2.

Uso:
    python -m experiment_06.document_parser.demo_build
"""
from __future__ import annotations

from pathlib import Path

from .graph_builder import GraphBuilder
from .node_extractor import NodeExtractor
from .structure_extractor import StructureExtractor


def main() -> None:
    doc_path = (
        Path(__file__).resolve().parent.parent
        / "sample_documents" / "algebra_ch3.md"
    )

    structure = StructureExtractor().extract_file(doc_path)
    parse_report = NodeExtractor().extract(structure)
    print(parse_report.render())
    print()

    if not parse_report.is_valid:
        print("(parse no válido — saltando build)")
        return

    build_report = GraphBuilder().build(parse_report)
    print(build_report.render())
    print()

    # Sanity check del procedimiento resuelto.
    if build_report.graph is not None and build_report.is_valid:
        thm = build_report.graph.get("thm.solucion_general")
        result = thm.compute({"a": 3.0, "b": 6.0})
        print(f"compute(a=3, b=6) → {result}")
        assert result == {"x": -2.0}, "el procedimiento debería devolver -2.0"
        print("✓ verificación numérica: 3x + 6 = 0 → x = -2")


if __name__ == "__main__":
    main()
