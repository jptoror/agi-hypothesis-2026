"""StructureExtractor — primera fase del parser.

Convierte un documento Markdown en una jerarquía de secciones SIN
interpretar marcadores ni decidir nodos. Su única responsabilidad es
trocear el documento por headings y dar a las fases siguientes una
estructura tipada sobre la que operar.

Reglas explícitas:
  - El primer heading `# ...` se considera título del capítulo (metadata).
  - Cada heading `## ...` abre una sección de primer nivel.
  - Headings más profundos (`###`, `####`...) se tratan como
    sub-secciones planas dentro de su `##` padre — el contenido se
    incorpora al cuerpo de la sección padre, pero el sub-heading se
    conserva en `subheadings` por trazabilidad.
  - Si el documento empieza con texto antes de cualquier heading, ese
    texto va a `preamble`.
  - Las líneas en blanco se preservan en el cuerpo (importan para que
    `node_extractor` distinga párrafos).

El extractor no asume nada sobre marcadores `**Definición:**` etc.
Eso es trabajo de `node_extractor`.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path


_HEADING_RE = re.compile(r"^(#+)\s+(.*?)\s*$")


def _slugify(title: str) -> str:
    """Normaliza un título a un slug ASCII auditable.

    Quita tildes, baja a minúsculas, reemplaza no-alfanuméricos por
    guion bajo y comprime guiones bajos consecutivos. Mantenemos los
    dígitos para preservar la numeración de las secciones (3_1, 3_2).
    """
    s = title.lower()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "section"


@dataclass
class Section:
    """Sección de primer nivel (heading `##`) del documento.

    `body` contiene el texto crudo de la sección, incluido cualquier
    sub-heading interno y sus párrafos — preservamos forma original
    para que `node_extractor` pueda procesar marcadores tal como
    aparecen.
    """

    index: int                       # orden de aparición (0-based)
    level: int                       # nivel del heading (2 para `##`)
    title: str                       # texto del heading sin '#'
    slug: str                        # versión normalizada
    body: str = ""                   # cuerpo crudo entre este heading y el siguiente
    subheadings: list[str] = field(default_factory=list)


@dataclass
class DocumentStructure:
    """Salida del StructureExtractor."""

    source_path: str | None
    title: str | None                # primer `# ...` si existe
    preamble: str                    # texto antes del primer heading
    sections: list[Section]

    def render(self) -> str:
        lines = [
            f"DocumentStructure(source={self.source_path!r})",
            f"  título: {self.title!r}",
            f"  preámbulo: {len(self.preamble)} chars",
            f"  secciones: {len(self.sections)}",
        ]
        for s in self.sections:
            lines.append(
                f"    [{s.index}] ## {s.title!r}  (slug={s.slug}, "
                f"body={len(s.body)} chars, "
                f"subheadings={len(s.subheadings)})"
            )
        return "\n".join(lines)


class StructureExtractor:
    def extract_text(
        self,
        markdown: str,
        source_path: str | None = None,
    ) -> DocumentStructure:
        title: str | None = None
        preamble_lines: list[str] = []
        sections: list[Section] = []
        current: Section | None = None
        # Buffer para acumular líneas del cuerpo de la sección actual.
        current_body: list[str] = []

        def flush_current() -> None:
            if current is not None:
                current.body = "\n".join(current_body).strip("\n")

        for raw_line in markdown.splitlines():
            m = _HEADING_RE.match(raw_line)
            if m is None:
                if current is None:
                    preamble_lines.append(raw_line)
                else:
                    current_body.append(raw_line)
                continue

            hashes, heading_text = m.group(1), m.group(2)
            level = len(hashes)

            if level == 1:
                # Título del capítulo. Guardamos sólo el primero.
                if title is None:
                    title = heading_text
                else:
                    # Si aparece otro `#`, lo tratamos como contenido
                    # ordinario de la sección actual o del preámbulo.
                    if current is None:
                        preamble_lines.append(raw_line)
                    else:
                        current_body.append(raw_line)
                continue

            if level == 2:
                # Cierra la sección anterior (si la hay) y abre nueva.
                flush_current()
                current_body = []
                current = Section(
                    index=len(sections),
                    level=2,
                    title=heading_text,
                    slug=_slugify(heading_text),
                )
                sections.append(current)
                continue

            # level >= 3 → sub-heading: lo conservamos en la sección
            # actual y dejamos su línea original en el cuerpo (para
            # que el node_extractor pueda usarla como pista de título
            # de fallback si aparece un nodo sin marcador en su zona).
            if current is None:
                # Sub-heading antes de cualquier `##`. Va al preámbulo.
                preamble_lines.append(raw_line)
            else:
                current.subheadings.append(heading_text)
                current_body.append(raw_line)

        flush_current()

        return DocumentStructure(
            source_path=source_path,
            title=title,
            preamble="\n".join(preamble_lines).strip("\n"),
            sections=sections,
        )

    def extract_file(self, path: str | Path) -> DocumentStructure:
        p = Path(path)
        text = p.read_text(encoding="utf-8")
        return self.extract_text(text, source_path=str(p))
