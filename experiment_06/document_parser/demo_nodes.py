"""Demo del NodeExtractor sobre algebra_ch3.md.

Encadena structure_extractor → node_extractor y muestra el
ParseReport completo: 5 nodos, 1 sección ignorada (3.3 Ejemplo)
+ 1 preámbulo ignorado, 0 errores.

Uso:
    python -m experiment_06.document_parser.demo_nodes
"""
from __future__ import annotations

from pathlib import Path

from .node_extractor import NodeExtractor
from .structure_extractor import StructureExtractor


def main() -> None:
    doc_path = (
        Path(__file__).resolve().parent.parent
        / "sample_documents" / "algebra_ch3.md"
    )
    structure = StructureExtractor().extract_file(doc_path)
    report = NodeExtractor().extract(structure)
    print(report.render())


if __name__ == "__main__":
    main()
