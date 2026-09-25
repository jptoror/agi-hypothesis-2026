"""NodeExtractor — segunda fase del parser.

Recibe la DocumentStructure de la fase 1 y produce:

  - una lista de ExtractedNode (proyección intermedia previa al
    KnowledgeNode real, que se construye en graph_builder cuando
    se resuelven los procedimientos);
  - un ParseReport con secciones ignoradas y errores tipados.

El extractor es SELECTIVO POR DISEÑO: sólo crea nodos a partir de
bloques con marcador reconocido. Cualquier párrafo de prosa libre
queda fuera y se reporta como `IgnoredSection` cuando una sección
entera no produce ningún nodo. Eso permite responder con precisión
'esto no se procesó' en vez de 'esto no se vio'.

Convención de marcadores reconocida (definida en algebra_ch3.md):

    **Definición:**            \\
    **Id:** def.<slug>          | encabezado de bloque
    <enunciado en prosa>       /

    **Condición:** ...         | metadata 0..N
    **Procedimiento:** name    |
    **Inputs:** a, b           |
    **Outputs:** x             |
    **Depende de:** id1, id2   |

Reglas de bloque:
  - El bloque se abre con una línea que es exactamente uno de los
    tres marcadores principales.
  - La siguiente línea DEBE ser `**Id:** <id>`. Si falta → MissingId.
  - Las líneas posteriores forman parte del bloque hasta encontrar
    una línea en blanco que no esté precedida de un marcador
    secundario (eso permite separar bloque del párrafo de prosa
    siguiente).
  - Líneas que empiezan con marcador secundario son metadata; el
    resto se concatena al enunciado.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from experiment_01.knowledge_graph import EpistemicStatus

from .structure_extractor import DocumentStructure, Section


# Marcadores principales: abren un bloque y determinan EpistemicStatus.
_PRIMARY_MARKERS: dict[str, EpistemicStatus] = {
    "**Definición:**": EpistemicStatus.DEFINITION,
    "**Teorema:**": EpistemicStatus.THEOREM,
    "**Axioma:**": EpistemicStatus.AXIOM,
    # Añadido en experiment_14: bloques que declaran un procedimiento
    # operativo con entradas y salidas. Ver EpistemicStatus.ALGORITHM.
    "**Algoritmo:**": EpistemicStatus.ALGORITHM,
}

# Marcadores secundarios: metadata dentro del bloque.
_SEC_ID = "**Id:**"
_SEC_CONDITION = "**Condición:**"
_SEC_PROCEDURE = "**Procedimiento:**"
_SEC_INPUTS = "**Inputs:**"
_SEC_OUTPUTS = "**Outputs:**"
_SEC_DEPENDS = "**Depende de:**"
# Marcador semántico añadido en exp_09: declara la(s) clase(s) de
# complejidad asociadas al teorema. Sintácticamente equivale a
# **Depende de:** (CSV de ids); su valor se MEZCLA con
# explicit_dependencies durante la extracción. La complejidad ES una
# dependencia conceptual del teorema y debe entrar al cierre
# transitivo de fundamentos.
_SEC_COMPLEXITY = "**Complejidad:**"
# Sinónimos castellanos añadidos en experiment_14: equivalentes
# semánticos de **Inputs:** y **Outputs:** para bloques
# **Algoritmo:** (y cualquier otro bloque). El handler los procesa
# idénticamente — la única diferencia es el idioma del marcador.
_SEC_ENTRADA = "**Entrada:**"
_SEC_SALIDA = "**Salida:**"
# Marcador añadido en experiment_17: declara las formas de superficie
# por las que el nodo puede ser referenciado en lenguaje natural.
# Lista CSV. Las formas se normalizan (lowercase + colapso de
# espacios) y entran a `properties["surface_forms"]`. Si el marcador
# no aparece, surface_forms queda como []. La duplicación dentro de
# la lista se preserva tal cual viene — el VocabularyRegistry
# tolera duplicados sin problema (set interno por especialista).
_SEC_TERMS = "**Términos:**"
# Marcador añadido en experiment_18: declara la plantilla de
# verbalización del nodo. El valor se almacena CRUDO (sin
# normalización ni recorte de espacios internos) porque la
# plantilla puede contener referencias `{node.X}` cuyo formato
# importa carácter a carácter. Si el marcador no aparece, NO se
# setea `properties["expression_template"]` — el renderer detecta
# ausencia y aplica fallback al statement.
_SEC_EXPRESSION = "**Expresión:**"

_SECONDARY_MARKERS = {
    _SEC_ID, _SEC_CONDITION, _SEC_PROCEDURE,
    _SEC_INPUTS, _SEC_OUTPUTS, _SEC_DEPENDS,
    _SEC_COMPLEXITY,
    _SEC_ENTRADA, _SEC_SALIDA,
    _SEC_TERMS,
    _SEC_EXPRESSION,
}


# ---------------------------------------------------------------------
# Tipos de salida
# ---------------------------------------------------------------------

@dataclass
class ExtractedNode:
    """Proyección intermedia previa a KnowledgeNode.

    No lleva `compute` resuelto — esa resolución (lookup en la
    biblioteca de procedimientos) es responsabilidad del
    graph_builder. Aquí guardamos sólo el NOMBRE del procedimiento
    declarado en el documento.
    """

    node_id: str
    status: EpistemicStatus
    statement: str                              # enunciado en prosa
    section_title: str
    conditions: list[str] = field(default_factory=list)
    procedure_name: str | None = None
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    explicit_dependencies: list[str] | None = None  # None = no marcador, []  = marcador vacío
    foundations: list[str] = field(default_factory=list)  # resueltos tras pasada 2
    # `extra_properties` lleva entradas adicionales que el extractor
    # quiere que aparezcan en KnowledgeNode.properties al construir.
    # Caso canónico (exp_14): para bloques **Algoritmo:**, el
    # extractor añade {"inputs": [...], "outputs": [...]} aquí para
    # que graph.validate() encuentre los campos donde EpistemicStatus
    # ALGORITHM exige (P literal — properties dict, no atributos).
    extra_properties: dict = field(default_factory=dict)

    def render(self) -> str:
        bits = [
            f"[{self.status.value:11}] {self.node_id}",
            f"  enunciado: {self.statement}",
            f"  sección:   {self.section_title}",
        ]
        if self.conditions:
            bits.append(f"  condiciones: {self.conditions}")
        if self.procedure_name:
            bits.append(
                f"  procedimiento: {self.procedure_name}"
                f" inputs={self.inputs} outputs={self.outputs}"
            )
        bits.append(f"  fundamentos: {self.foundations}")
        return "\n".join(bits)


@dataclass
class IgnoredSection:
    """Una sección (o el preámbulo) que no produjo ningún nodo."""

    section_index: int | None       # None para preámbulo
    title: str                      # "preámbulo" o título de la sección
    reason: str                     # texto auditable

    def render(self) -> str:
        idx = "preámbulo" if self.section_index is None else f"sección {self.section_index}"
        return f"  · {idx} «{self.title}»: {self.reason}"


# Jerarquía de errores tipados ---------------------------------------

@dataclass
class ParseError:
    """Base abstracta — los subtipos llevan campos específicos."""

    message: str

    def render(self) -> str:
        return f"  ✗ {type(self).__name__}: {self.message}"


@dataclass
class MissingId(ParseError):
    section_index: int
    marker_type: str
    line_offset: int

    def render(self) -> str:
        return (
            f"  ✗ MissingId: bloque '{self.marker_type}' en sección "
            f"{self.section_index} (offset línea {self.line_offset}) sin **Id:**"
        )


@dataclass
class UnresolvedDependency(ParseError):
    node_id: str
    references: str
    found_in_document: bool = False

    def render(self) -> str:
        return (
            f"  ✗ UnresolvedDependency: '{self.node_id}' referencia "
            f"'{self.references}' que no existe en el documento."
        )


@dataclass
class DuplicateId(ParseError):
    node_id: str
    section_indices: list[int]

    def render(self) -> str:
        return (
            f"  ✗ DuplicateId: id '{self.node_id}' aparece en secciones "
            f"{self.section_indices}."
        )


@dataclass
class ProcedureSignatureMismatch(ParseError):
    """Reservado para verificación posterior por graph_builder.

    Lo declaramos aquí (no en graph_builder) porque el ParseReport
    es el contenedor único de errores acordado con el caller. El
    graph_builder añadirá instancias de este tipo cuando ejecute la
    verificación de firma.
    """

    node_id: str
    document_declares: list[str]
    procedure_expects: list[str]

    def render(self) -> str:
        return (
            f"  ✗ ProcedureSignatureMismatch: nodo '{self.node_id}' "
            f"declara inputs={self.document_declares} pero la función "
            f"registrada espera {self.procedure_expects}."
        )


@dataclass
class ParseReport:
    nodes_extracted: list[ExtractedNode]
    sections_ignored: list[IgnoredSection]
    errors: list[ParseError]

    @property
    def is_valid(self) -> bool:
        return not self.errors

    def render(self) -> str:
        lines = [
            "=" * 72,
            "PARSE REPORT",
            "=" * 72,
            f"nodos extraídos: {len(self.nodes_extracted)}",
            f"secciones ignoradas: {len(self.sections_ignored)}",
            f"errores: {len(self.errors)}",
            f"is_valid: {self.is_valid}",
        ]
        if self.nodes_extracted:
            lines.append("")
            lines.append("── nodos ──")
            for n in self.nodes_extracted:
                lines.append(n.render())
                lines.append("")
        if self.sections_ignored:
            lines.append("── secciones ignoradas ──")
            for s in self.sections_ignored:
                lines.append(s.render())
        if self.errors:
            lines.append("")
            lines.append("── errores ──")
            for e in self.errors:
                lines.append(e.render())
        return "\n".join(lines)


# ---------------------------------------------------------------------
# Extractor
# ---------------------------------------------------------------------

# Helper: línea con marcador del tipo `**Algo:** valor` → (marker, value).
_MARKER_LINE = re.compile(r"^(\*\*[^*]+:\*\*)\s*(.*)$")


def _split_csv_ids(value: str) -> list[str]:
    return [p.strip() for p in value.split(",") if p.strip()]


def _split_csv_terms(value: str) -> list[str]:
    """Variante de _split_csv_ids para `**Términos:**`. Normaliza
    cada forma con la misma regla del VocabularyRegistry (lowercase
    + colapso de espacios internos) para que la indexación sea
    determinística desde la extracción. Las duplicadas se preservan
    — el registry deduplica internamente por especialista. Esto
    mantiene auditable lo que el documento declaró literalmente.
    """
    out: list[str] = []
    for raw in value.split(","):
        s = raw.strip().lower()
        if not s:
            continue
        # Colapso de runs de whitespace internos a un solo espacio.
        s = re.sub(r"\s+", " ", s)
        out.append(s)
    return out


class NodeExtractor:
    def extract(
        self,
        structure: DocumentStructure,
        external_ids: set[str] | None = None,
    ) -> ParseReport:
        """`external_ids` (opcional, exp_09): ids reconocidos por el
        caller como válidos aunque no aparezcan en el documento. Útil
        cuando el grafo final se construye combinando el documento
        con un grafo base (p. ej. complejidad). Si una referencia
        está en `external_ids`, se preserva en `foundations` y el
        `GraphBuilder` se encarga de importarla del base.
        """
        external = set(external_ids or ())
        nodes: list[ExtractedNode] = []
        ignored: list[IgnoredSection] = []
        errors: list[ParseError] = []

        # Preámbulo: si tiene contenido pero no tiene marcadores
        # principales, lo reportamos como ignorado. (Por construcción
        # el preámbulo nunca tendrá marcadores principales: van dentro
        # de secciones.)
        if structure.preamble.strip():
            ignored.append(IgnoredSection(
                section_index=None,
                title="preámbulo",
                reason="texto introductorio sin marcadores reconocidos",
            ))

        # Pasada 1: extracción por sección, en orden.
        per_section_nodes: dict[int, list[ExtractedNode]] = {}
        for section in structure.sections:
            section_nodes, section_errors = self._extract_from_section(section)
            errors.extend(section_errors)
            if not section_nodes:
                ignored.append(IgnoredSection(
                    section_index=section.index,
                    title=section.title,
                    reason="sin marcadores reconocidos",
                ))
                continue
            per_section_nodes[section.index] = section_nodes
            nodes.extend(section_nodes)

        # Detección de ids duplicados.
        seen: dict[str, list[int]] = {}
        for sec_idx, sec_nodes in per_section_nodes.items():
            for n in sec_nodes:
                seen.setdefault(n.node_id, []).append(sec_idx)
        for node_id, sections in seen.items():
            if len(sections) > 1:
                errors.append(DuplicateId(
                    message=f"id duplicado: {node_id}",
                    node_id=node_id,
                    section_indices=sections,
                ))

        # Pasada 2: resolver fundamentos.
        ids_in_document = set(seen.keys())
        for section_index, section_nodes in per_section_nodes.items():
            previous_in_section: list[str] = []
            for node in section_nodes:
                if node.explicit_dependencies is not None:
                    # Marcador presente: usarlo y validar referencias.
                    # Una referencia es válida si existe en el
                    # documento o en el conjunto de ids externos
                    # aportados por el caller (typicamente un
                    # base_graph que se importará al construir).
                    resolved: list[str] = []
                    for ref in node.explicit_dependencies:
                        if ref in ids_in_document or ref in external:
                            resolved.append(ref)
                        else:
                            errors.append(UnresolvedDependency(
                                message=(
                                    f"{node.node_id} → {ref} no existe ni en "
                                    f"el documento ni en external_ids"
                                ),
                                node_id=node.node_id,
                                references=ref,
                                found_in_document=False,
                            ))
                    node.foundations = resolved
                else:
                    # Sin marcador `**Depende de:**` explícito.
                    # Regla por status (PROB-10):
                    #   AXIOM → foundations=[] siempre. Un axioma se
                    #     acepta sin demostración; aplicarle la
                    #     heurística de hermano previo le asignaría
                    #     fundamentos espurios que contradicen su
                    #     naturaleza epistemológica y haría que
                    #     graph.validate() rechace el grafo.
                    #   DEFINITION / THEOREM → opción iii: hermanos
                    #     previos de la misma sección (todos, en
                    #     orden de aparición).
                    if node.status == EpistemicStatus.AXIOM:
                        node.foundations = []
                    else:
                        node.foundations = list(previous_in_section)
                previous_in_section.append(node.node_id)

        return ParseReport(
            nodes_extracted=nodes,
            sections_ignored=ignored,
            errors=errors,
        )

    # -- helpers internos ------------------------------------------------

    def _extract_from_section(
        self,
        section: Section,
    ) -> tuple[list[ExtractedNode], list[ParseError]]:
        """Recorre el cuerpo de una sección y produce nodos + errores.

        Algoritmo line-by-line: detecta líneas de marcador principal,
        abre bloque, consume líneas siguientes hasta:
          - línea en blanco que NO esté precedida por marcador secundario
            inmediatamente anterior;
          - aparición de otro marcador principal;
          - fin del cuerpo.
        """
        nodes: list[ExtractedNode] = []
        errors: list[ParseError] = []
        lines = section.body.splitlines()

        i = 0
        while i < len(lines):
            stripped = lines[i].strip()

            # Detectar marcador principal en la línea — admitiendo la
            # variante compacta `**Definición:** enunciado en la misma
            # línea`. En esa variante, el resto de la línea es la
            # primera parte del enunciado.
            primary = None
            inline_statement: str | None = None
            for marker in _PRIMARY_MARKERS:
                if stripped == marker:
                    primary = marker
                    break
                if stripped.startswith(marker + " ") or stripped == marker.rstrip(":") + " ":
                    primary = marker
                    inline_statement = stripped[len(marker):].strip()
                    break

            if primary is None:
                i += 1
                continue

            block_start = i
            i += 1

            # Acumuladores del bloque.
            node_id: str | None = None
            statement_parts: list[str] = []
            if inline_statement:
                statement_parts.append(inline_statement)
            conditions: list[str] = []
            procedure: str | None = None
            inputs: list[str] = []
            outputs: list[str] = []
            explicit_deps: list[str] | None = None
            # Formas de superficie declaradas vía **Términos:**.
            # Lista vacía si el marcador no aparece (contrato exp_17).
            surface_forms: list[str] = []
            # Plantilla de verbalización vía **Expresión:** (exp_18).
            # None = marcador ausente → renderer aplica fallback al
            # statement. Si aparece varias veces, las líneas se
            # concatenan con un espacio (el caso típico es 1 sola).
            expression_template: str | None = None

            # Regla de cierre de bloque:
            #   - Una línea en blanco INMEDIATAMENTE después del
            #     marcador principal se permite (autores que ponen
            #     espacio antes del **Id:**).
            #   - Cualquier otra línea en blanco cierra el bloque.
            #   - Otro marcador principal cierra el bloque.
            #   - El enunciado son las líneas no-marcador antes de
            #     ver el primer marcador secundario, salvo
            #     continuaciones inmediatas.
            saw_any_content = bool(inline_statement)

            while i < len(lines):
                line = lines[i]
                line_stripped = line.strip()

                if line_stripped in _PRIMARY_MARKERS:
                    break

                if line_stripped == "":
                    if not saw_any_content:
                        # Aún no hemos empezado; permitir blank inicial.
                        i += 1
                        continue
                    # Fin de bloque.
                    break

                # ¿Marcador secundario?
                m = _MARKER_LINE.match(line_stripped)
                if m and m.group(1) in _SECONDARY_MARKERS:
                    marker, value = m.group(1), m.group(2).strip()
                    if marker == _SEC_ID:
                        node_id = value
                    elif marker == _SEC_CONDITION:
                        if value:
                            conditions.append(value)
                    elif marker == _SEC_PROCEDURE:
                        procedure = value or None
                    elif marker == _SEC_INPUTS or marker == _SEC_ENTRADA:
                        # **Inputs:** y **Entrada:** son sinónimos
                        # (S1 — exp_14). Rellenan el mismo campo.
                        inputs = _split_csv_ids(value)
                    elif marker == _SEC_OUTPUTS or marker == _SEC_SALIDA:
                        outputs = _split_csv_ids(value)
                    elif marker == _SEC_DEPENDS:
                        # Fusiona con cualquier dependencia ya
                        # acumulada (p. ej. via **Complejidad:**),
                        # preservando orden y sin duplicados. El
                        # comportamiento previo era sobrescribir;
                        # eso perdía dependencias cuando el orden de
                        # marcadores no era el esperado.
                        new_deps = _split_csv_ids(value)
                        if explicit_deps is None:
                            explicit_deps = list(new_deps)
                        else:
                            for d in new_deps:
                                if d not in explicit_deps:
                                    explicit_deps.append(d)
                    elif marker == _SEC_COMPLEXITY:
                        # `**Complejidad:**` SE FUSIONA con
                        # explicit_dependencies. Cada id declarado
                        # entra como fundamento del nodo, igual que si
                        # apareciera en `**Depende de:**`. Si ambos
                        # marcadores aparecen, la unión es la lista
                        # final (sin duplicados, preservando orden).
                        complexity_ids = _split_csv_ids(value)
                        if explicit_deps is None:
                            explicit_deps = list(complexity_ids)
                        else:
                            for cid in complexity_ids:
                                if cid not in explicit_deps:
                                    explicit_deps.append(cid)
                    elif marker == _SEC_TERMS:
                        # `**Términos:**` (exp_17). Las formas se
                        # acumulan y se emiten al final del bloque a
                        # `extra_properties["surface_forms"]`. Si el
                        # marcador aparece varias veces, las listas
                        # se concatenan (autores que separan en
                        # bloques temáticos).
                        surface_forms.extend(_split_csv_terms(value))
                    elif marker == _SEC_EXPRESSION:
                        # `**Expresión:**` (exp_18). El valor se
                        # guarda CRUDO (sin .strip() del contenido
                        # interno, sólo del prefijo del marcador
                        # mismo). Líneas múltiples se concatenan con
                        # espacio para que la plantilla quede en una
                        # sola línea — los autores que necesiten
                        # saltos pueden meter `\n` literalmente o
                        # escribir un párrafo en una sola línea.
                        if expression_template is None:
                            expression_template = value
                        else:
                            expression_template = (
                                expression_template + " " + value
                            )
                    saw_any_content = True
                    i += 1
                    continue

                # Línea de enunciado.
                statement_parts.append(line_stripped)
                saw_any_content = True
                i += 1

            # Cierre del bloque — emitir nodo o error.
            statement = " ".join(statement_parts).strip()
            if node_id is None:
                errors.append(MissingId(
                    message=(
                        f"bloque '{primary}' en sección {section.index} "
                        f"(línea {block_start}) sin **Id:**"
                    ),
                    section_index=section.index,
                    marker_type=primary,
                    line_offset=block_start,
                ))
                continue

            # Para nodos ALGORITHM (exp_14), las entradas/salidas
            # también viven en `properties` — no sólo en los atributos
            # top-level. Eso satisface el contrato de validate() para
            # ese status (P literal del enunciado).
            extra_props: dict = {}
            if _PRIMARY_MARKERS[primary] == EpistemicStatus.ALGORITHM:
                extra_props["inputs"] = list(inputs)
                extra_props["outputs"] = list(outputs)
            # Surface forms (exp_17). Siempre presente, default [].
            # Mantener la propiedad incluso vacía simplifica el caller
            # — no hay que distinguir "falta marcador" de "marcador
            # vacío" en el VocabularyRegistry.
            extra_props["surface_forms"] = list(surface_forms)
            # Plantilla de expresión (exp_18). SOLO se emite cuando
            # el marcador apareció — el contrato es "ausente" vs
            # "presente con valor", no "siempre presente con default
            # vacío". Eso permite al renderer distinguir
            # explícitamente "el autor declaró expresión vacía"
            # (caso patológico que prefiere fallar) de "el autor no
            # declaró nada" (caso normal → fallback al statement).
            if expression_template is not None:
                extra_props["expression_template"] = expression_template

            nodes.append(ExtractedNode(
                node_id=node_id,
                status=_PRIMARY_MARKERS[primary],
                statement=statement,
                section_title=section.title,
                conditions=conditions,
                procedure_name=procedure,
                inputs=inputs,
                outputs=outputs,
                explicit_dependencies=explicit_deps,
                extra_properties=extra_props,
            ))

        return nodes, errors
