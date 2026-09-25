"""Demo del StructureExtractor sobre algebra_ch3.md.

Uso:
    python -m experiment_06.document_parser.demo_structure
"""
from __future__ import annotations

from pathlib import Path

from .structure_extractor import StructureExtractor


def main() -> None:
    doc_path = (
        Path(__file__).resolve().parent.parent
        / "sample_documents" / "algebra_ch3.md"
    )
    structure = StructureExtractor().extract_file(doc_path)

    print(structure.render())
    print()
    print("=" * 72)
    print("CUERPOS DE SECCIÓN (primeras 200 chars de cada una)")
    print("=" * 72)
    for s in structure.sections:
        snippet = s.body[:200].replace("\n", " ⏎ ")
        print(f"  [{s.index}] {s.title}")
        print(f"      → {snippet}{'…' if len(s.body) > 200 else ''}")
        print()


if __name__ == "__main__":
    main()
