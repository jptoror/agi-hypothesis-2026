"""Validador exhaustivo de documentos del autor (exp_21).

Recibe un documento markdown con marcadores del sistema y devuelve
una `ValidationReport` con TODOS los issues encontrados — no se
detiene en el primero.

Reglas de operación:

  - Cero excepciones al caller. Cualquier error de parsing del
    motor se captura y se traduce a un issue con código.
  - Cada issue lleva un `code` estable (apto para test exacto), un
    mensaje en castellano dirigido al autor, un fragmento del
    documento alrededor del problema, y una sugerencia.
  - Los números de línea son ABSOLUTOS al documento (1-based), no
    offsets relativos a una sección. Eso requiere un escaneo de
    líneas antes de delegar al StructureExtractor del exp_06.
  - Cero auto-corrección. La validación REPORTA; el autor edita.

Códigos definidos (registrados en `VALIDATION_CODES` para que el
README/CLI los puedan listar):

  Estructurales:    MISSING_ID, DUPLICATE_ID, MALFORMED_MARKER, UNKNOWN_MARKER
  Epistémicos:      AXIOM_HAS_FOUNDATIONS, THEOREM_MISSING_FOUNDATIONS,
                    ALGORITHM_MISSING_IO, HYPOTHESIS_WITH_COMPLETE_FOUNDATIONS
  Referenciales:    FOUNDATION_NOT_FOUND, EXPRESSION_REF_NOT_FOUND,
                    EXPRESSION_PARSE_ERROR
  Vocabulario:      EMPTY_SURFACE_FORM, DUPLICATE_SURFACE_FORM_IN_DOCUMENT,
                    SURFACE_FORM_CONFLICT_WITH_REGISTRY
  Coherencia:       EMPTY_DOCUMENT, NO_AXIOMS_NO_FOUNDATIONS
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Literal, Optional

from experiment_01.knowledge_graph import EpistemicStatus, KnowledgeGraph
from experiment_06.document_parser import (
    GraphBuilder,
    NodeExtractor,
    StructureExtractor,
)
from experiment_06.document_parser.node_extractor import (
    DuplicateId,
    MissingId,
    ProcedureSignatureMismatch,
    UnresolvedDependency,
)
from experiment_17.vocabulary import VocabularyRegistry, normalize
from experiment_18.expression import (
    TemplateParseError,
    parse_template,
)


Severity = Literal["error", "warning", "info"]


# ---------------------------------------------------------------------
# Tabla canónica de marcadores conocidos. Si el doc usa algo que NO
# está acá, levantamos UNKNOWN_MARKER. La lista es DECLARATIVA — añadir
# un marcador es un cambio explícito al validador.
# ---------------------------------------------------------------------

KNOWN_PRIMARY_MARKERS = (
    "**Definición:**",
    "**Teorema:**",
    "**Axioma:**",
    "**Algoritmo:**",
)

KNOWN_SECONDARY_MARKERS = (
    "**Id:**",
    "**Condición:**",
    "**Procedimiento:**",
    "**Inputs:**",
    "**Outputs:**",
    "**Depende de:**",
    "**Complejidad:**",
    "**Entrada:**",
    "**Salida:**",
    "**Términos:**",
    "**Expresión:**",
)

KNOWN_MARKERS = KNOWN_PRIMARY_MARKERS + KNOWN_SECONDARY_MARKERS


# ---------------------------------------------------------------------
# Catálogo de códigos
# ---------------------------------------------------------------------

VALIDATION_CODES: dict[str, str] = {
    # Estructurales
    "MISSING_ID":
        "Un bloque de nodo no tiene **Id:**. Cada nodo debe declarar un id único.",
    "DUPLICATE_ID":
        "Dos nodos del documento usan el mismo id.",
    "MALFORMED_MARKER":
        "Marcador con sintaxis incorrecta (faltan dos puntos, asteriscos, etc.).",
    "UNKNOWN_MARKER":
        "Marcador no reconocido por el sistema.",
    # Epistémicos
    "AXIOM_HAS_FOUNDATIONS":
        "Un AXIOM no puede tener foundations (no se demuestra desde otros nodos).",
    "THEOREM_MISSING_FOUNDATIONS":
        "Un THEOREM debe declarar al menos un foundation.",
    "ALGORITHM_MISSING_IO":
        "Un ALGORITHM debe declarar **Entrada:** y **Salida:**.",
    "HYPOTHESIS_WITH_COMPLETE_FOUNDATIONS":
        "Un HYPOTHESIS con todos sus foundations resueltos podría ser THEOREM.",
    # Referenciales
    "FOUNDATION_NOT_FOUND":
        "Una foundation referencia un id que no existe en este documento ni en especialistas registrados.",
    "EXPRESSION_REF_NOT_FOUND":
        "La plantilla **Expresión:** referencia un nodo o binding no resoluble.",
    "EXPRESSION_PARSE_ERROR":
        "La plantilla **Expresión:** está mal formada (llave sin cerrar, ref con sintaxis incorrecta).",
    # Vocabulario
    "EMPTY_SURFACE_FORM":
        "**Términos:** tiene una entrada vacía después de separar por coma.",
    "DUPLICATE_SURFACE_FORM_IN_DOCUMENT":
        "La misma surface form se declara en dos nodos del mismo documento.",
    "SURFACE_FORM_CONFLICT_WITH_REGISTRY":
        "La surface form ya existe en otro especialista cargado (advertencia, no error).",
    # Coherencia
    "EMPTY_DOCUMENT":
        "El documento no contiene ningún nodo válido.",
    "NO_AXIOMS_NO_FOUNDATIONS":
        "El documento no tiene axiomas locales ni referencias externas (advertencia).",
}


# ---------------------------------------------------------------------
# Tipos públicos
# ---------------------------------------------------------------------

@dataclass(frozen=True)
class ValidationIssue:
    severity: Severity
    line: int                          # 1-based, absoluto al documento
    column: int | None
    code: str
    message: str
    fragment: str                      # texto alrededor del issue
    suggestion: Optional[str] = None


@dataclass(frozen=True)
class ValidationReport:
    document_path: str
    issues: tuple[ValidationIssue, ...]
    nodes_extracted: int               # 0 si parsing global falló
    is_valid: bool                     # True iff sin severity="error"

    @property
    def errors(self) -> tuple[ValidationIssue, ...]:
        return tuple(i for i in self.issues if i.severity == "error")

    @property
    def warnings(self) -> tuple[ValidationIssue, ...]:
        return tuple(i for i in self.issues if i.severity == "warning")


# ---------------------------------------------------------------------
# Utilidades de líneas absolutas
# ---------------------------------------------------------------------

_ID_LINE_RE = re.compile(r"^\s*\*\*Id:\*\*\s*(.+?)\s*$")
_PRIMARY_LINE_RE = re.compile(
    r"^\s*\*\*(Definición|Teorema|Axioma|Algoritmo):\*\*"
)
_TERMS_LINE_RE = re.compile(r"^\s*\*\*Términos:\*\*\s*(.*)$")
_EXPRESSION_LINE_RE = re.compile(r"^\s*\*\*Expresión:\*\*\s*(.*)$")
_ANY_MARKER_RE = re.compile(r"^\s*\*\*([^*]+):\*\*")
# Detecta líneas que PARECEN marcadores pero están malformadas
# (sin asteriscos, faltan dos puntos, etc.). Usado para
# `MALFORMED_MARKER`. Patrón conservador: arranca con `**` o termina
# con `:` precedida de palabra y no matchea ninguno conocido.
_MALFORMED_HINT_RE = re.compile(
    r"^\s*(\*\*[A-Za-zÁÉÍÓÚáéíóúüÜñÑ ]+\b(?!:\*\*))",
)


def _scan_id_lines(raw_lines: list[str]) -> dict[str, list[int]]:
    """Devuelve `node_id → [línea_1based, ...]`. Permite duplicados."""
    out: dict[str, list[int]] = {}
    for idx, line in enumerate(raw_lines, start=1):
        m = _ID_LINE_RE.match(line)
        if m:
            out.setdefault(m.group(1).strip(), []).append(idx)
    return out


def _scan_primary_lines(raw_lines: list[str]) -> list[tuple[int, str]]:
    """Devuelve `[(línea_1based, marker), ...]` para los marcadores
    primarios reconocidos."""
    out: list[tuple[int, str]] = []
    for idx, line in enumerate(raw_lines, start=1):
        m = _PRIMARY_LINE_RE.match(line)
        if m:
            out.append((idx, m.group(1)))
    return out


def _fragment_around(raw_lines: list[str], line: int, span: int = 2) -> str:
    """Devuelve un bloque de `±span` líneas alrededor de `line`
    (1-based). La línea destacada se prefijada con `→`."""
    n = len(raw_lines)
    start = max(1, line - span)
    end = min(n, line + span)
    out_lines: list[str] = []
    for i in range(start, end + 1):
        prefix = "→  " if i == line else "   "
        out_lines.append(f"{prefix}{raw_lines[i - 1]}")
    return "\n".join(out_lines)


# ---------------------------------------------------------------------
# Helpers para construir issues con sugerencia estándar
# ---------------------------------------------------------------------

def _issue(
    severity: Severity,
    line: int,
    code: str,
    message: str,
    raw_lines: list[str],
    suggestion: Optional[str] = None,
    column: Optional[int] = None,
) -> ValidationIssue:
    return ValidationIssue(
        severity=severity,
        line=line,
        column=column,
        code=code,
        message=message,
        fragment=_fragment_around(raw_lines, line),
        suggestion=suggestion,
    )


# ---------------------------------------------------------------------
# Validador principal
# ---------------------------------------------------------------------

def validate_document(
    document_path: str | Path,
    global_registry: VocabularyRegistry | None = None,
    known_specialists: dict[str, KnowledgeGraph] | None = None,
    *,
    registered_procedures: Iterable[str] | None = None,
) -> ValidationReport:
    """Valida exhaustivamente. NO lanza excepciones.

    `global_registry` se usa para detectar conflictos de surface
    forms con especialistas ya cargados.
    `known_specialists` se usa para resolver foundations cross-spec
    en el formato `spec_id::node_id`.
    `registered_procedures`: nombres de procedure conocidos por el
    sistema. Si un nodo declara `**Procedimiento:** X` y X no está,
    se reporta como warning (no error: el motor del exp_19 lo carga
    perezosamente vía ProcedureRefRegistry). En este experimento
    solo aviso al autor.
    """
    path = Path(document_path)
    issues: list[ValidationIssue] = []

    # Lectura cruda del archivo.
    if not path.exists():
        return ValidationReport(
            document_path=str(path),
            issues=(ValidationIssue(
                severity="error", line=1, column=None,
                code="EMPTY_DOCUMENT",
                message=f"El archivo no existe: {path}",
                fragment="", suggestion=None,
            ),),
            nodes_extracted=0, is_valid=False,
        )
    raw_text = path.read_text(encoding="utf-8")
    raw_lines = raw_text.splitlines()

    # ---------------- escaneos absolutos ---------------------------
    id_lines = _scan_id_lines(raw_lines)
    primary_lines = _scan_primary_lines(raw_lines)

    # ---------------- 1. structural & marker scan ------------------
    issues.extend(_check_unknown_markers(raw_lines))
    issues.extend(_check_malformed_markers(raw_lines))

    # ---------------- 2. parse + build (best effort) --------------
    external_ids = _external_ids_from(known_specialists)
    structure = StructureExtractor().extract_text(raw_text)
    parse_report = NodeExtractor().extract(
        structure, external_ids=set(external_ids),
    )

    # Convertir errores de NodeExtractor a issues con línea absoluta.
    for err in parse_report.errors:
        issues.extend(_translate_parse_error(err, raw_lines, id_lines))

    # ---------------- 3. checks epistémicos por nodo --------------
    for node in parse_report.nodes_extracted:
        anchor = id_lines.get(node.node_id, [1])[0]
        issues.extend(_check_epistemic(node, anchor, raw_lines))

    # ---------------- 4. checks de vocabulario ---------------------
    issues.extend(_check_surface_forms(
        parse_report=parse_report,
        raw_lines=raw_lines,
        id_lines=id_lines,
        global_registry=global_registry,
    ))

    # ---------------- 5. checks de expression templates -----------
    issues.extend(_check_expressions(
        parse_report=parse_report,
        raw_lines=raw_lines,
        id_lines=id_lines,
        known_specialists=known_specialists,
    ))

    # ---------------- 6. coherencia general ------------------------
    issues.extend(_check_coherence(parse_report, raw_lines, external_ids))

    # ---------------- 7. cierre (build no obligatorio) ------------
    # Intentamos build() para detectar errores adicionales (firma de
    # procedure, foundations no resueltas en grafo). Captura
    # defensiva para que un fallo del builder NO se propague.
    if parse_report.is_valid and parse_report.nodes_extracted:
        try:
            GraphBuilder().build(parse_report)
        except Exception as e:
            # Reportamos como warning para no bloquear preview/build:
            # el fallo del builder revela un problema de coherencia
            # interna (caso raro). El autor puede inspeccionar.
            issues.append(_issue(
                severity="warning",
                line=1, code="EXPRESSION_PARSE_ERROR",
                message=f"Falló GraphBuilder: {type(e).__name__}: {e}",
                raw_lines=raw_lines,
                suggestion=(
                    "Revisar que todas las dependencias estén "
                    "declaradas y que el grafo final sea acíclico."
                ),
            ))

    # Orden estable: por línea ascendente, luego por code.
    issues.sort(key=lambda i: (i.line, i.code))

    is_valid = not any(i.severity == "error" for i in issues)
    return ValidationReport(
        document_path=str(path),
        issues=tuple(issues),
        nodes_extracted=len(parse_report.nodes_extracted),
        is_valid=is_valid,
    )


# ---------------------------------------------------------------------
# Sub-checks
# ---------------------------------------------------------------------

def _external_ids_from(
    known_specialists: dict[str, KnowledgeGraph] | None,
) -> set[str]:
    """Foundations resueltas externamente. Aceptamos DOS formatos:

      1. `spec_id::node_id`  — convención explícita del proyecto
         (cross-graph foundation declarado por el autor).
      2. `node_id`           — id puro, compatibilidad con docs
         pre-exp_21 que dependen de un base_graph importado por el
         caller (el `external_ids` del NodeExtractor del exp_06).

    Devolvemos ambas formas para que el NodeExtractor acepte
    cualquiera de las dos sin penalizar al autor que sigue la
    convención antigua. La preferencia (cuál es más higiénica)
    queda como recomendación en el README, no como bloqueo."""
    if not known_specialists:
        return set()
    out: set[str] = set()
    for spec_id, graph in known_specialists.items():
        for node in graph:
            out.add(f"{spec_id}::{node.id}")
            out.add(node.id)
    return out


def _check_unknown_markers(raw_lines: list[str]) -> list[ValidationIssue]:
    out: list[ValidationIssue] = []
    for idx, line in enumerate(raw_lines, start=1):
        m = _ANY_MARKER_RE.match(line)
        if not m:
            continue
        marker = f"**{m.group(1)}:**"
        if marker in KNOWN_MARKERS:
            continue
        out.append(_issue(
            severity="error", line=idx, code="UNKNOWN_MARKER",
            message=(
                f"Marcador '{marker}' no reconocido. "
                f"Marcadores válidos: {', '.join(KNOWN_MARKERS)}."
            ),
            raw_lines=raw_lines,
            suggestion=(
                "Revisá la lista de marcadores válidos. ¿Querías "
                "escribir uno de los reconocidos arriba?"
            ),
        ))
    return out


def _check_malformed_markers(raw_lines: list[str]) -> list[ValidationIssue]:
    """Detecta líneas que ARRANCAN como marcador pero están mal
    formadas (típicamente faltan los dos puntos de cierre o el
    asterisco final)."""
    out: list[ValidationIssue] = []
    for idx, line in enumerate(raw_lines, start=1):
        stripped = line.strip()
        if not stripped:
            continue
        # Patrón 1: arranca con `**Algo` pero NO termina con `:**`.
        if (
            stripped.startswith("**")
            and re.match(r"^\*\*[A-Za-zÁÉÍÓÚáéíóúüÜñÑ ]+", stripped)
            and "**" in stripped[2:]
            and not _ANY_MARKER_RE.match(stripped)
        ):
            # No es un marcador conocido y tampoco matchea la regex
            # de marcador bien-formado. Algunos casos son texto en
            # negrita normal (ej. `**énfasis** dentro de un párrafo`)
            # — los filtramos: si la línea contiene texto adicional
            # tras el closing `**`, lo tomamos como prosa.
            after_close = stripped.split("**", 2)
            if (
                len(after_close) >= 3
                and after_close[2].strip()
                and not after_close[2].lstrip().startswith(":")
            ):
                continue
            out.append(_issue(
                severity="error", line=idx, code="MALFORMED_MARKER",
                message=(
                    f"La línea parece un marcador pero no está bien "
                    f"formada: '{stripped[:60]}...'"
                ),
                raw_lines=raw_lines,
                suggestion=(
                    "Los marcadores tienen forma `**Nombre:**`. "
                    "Verificá que estén los dos puntos y los dos "
                    "asteriscos finales."
                ),
            ))
    return out


def _translate_parse_error(
    err,
    raw_lines: list[str],
    id_lines: dict[str, list[int]],
) -> list[ValidationIssue]:
    """Traduce errores tipados del NodeExtractor a issues con línea
    absoluta y mensaje amigable."""
    if isinstance(err, MissingId):
        # `err.line_offset` es relativo al cuerpo de la sección. La
        # ubicación exacta requiere mapear sección→línea absoluta;
        # como heurística usamos la primera línea del documento donde
        # aparezca el marcador primary `err.marker_type`. Si no hay
        # match (muy raro), línea 1.
        marker_str = err.marker_type
        candidate_line = 1
        for ln, label in _scan_primary_lines(raw_lines):
            if marker_str.endswith(f"{label}:**"):
                candidate_line = ln
                break
        return [_issue(
            severity="error", line=candidate_line, code="MISSING_ID",
            message=(
                f"Bloque '{marker_str}' sin **Id:**. Cada nodo "
                f"requiere un id único."
            ),
            raw_lines=raw_lines,
            suggestion=(
                "Agregá una línea `**Id:** <id_único>` inmediatamente "
                "después del marcador del bloque."
            ),
        )]
    if isinstance(err, DuplicateId):
        lines = id_lines.get(err.node_id, [])
        # Reportamos en cada ocurrencia para que el autor vea ambas.
        out: list[ValidationIssue] = []
        for ln in lines:
            out.append(_issue(
                severity="error", line=ln, code="DUPLICATE_ID",
                message=(
                    f"El id '{err.node_id}' aparece en varias líneas: "
                    f"{', '.join(str(x) for x in lines)}."
                ),
                raw_lines=raw_lines,
                suggestion=(
                    "Renombrá uno de los nodos para que cada id sea "
                    "único en el documento."
                ),
            ))
        return out
    if isinstance(err, UnresolvedDependency):
        anchor = id_lines.get(err.node_id, [1])[0]
        return [_issue(
            severity="error", line=anchor, code="FOUNDATION_NOT_FOUND",
            message=(
                f"El nodo '{err.node_id}' depende de '{err.references}' "
                f"pero ese id no existe en el documento ni en "
                f"especialistas registrados."
            ),
            raw_lines=raw_lines,
            suggestion=(
                "Verificá que el id esté escrito correctamente. Si "
                "viene de otro especialista, declaralo como "
                "`spec_id::node_id`."
            ),
        )]
    if isinstance(err, ProcedureSignatureMismatch):
        anchor = id_lines.get(err.node_id, [1])[0]
        return [_issue(
            severity="error", line=anchor, code="ALGORITHM_MISSING_IO",
            message=(
                f"La firma del nodo '{err.node_id}' no coincide con "
                f"el procedure registrado: documento declara "
                f"{err.document_declares}, registry espera "
                f"{err.procedure_expects}."
            ),
            raw_lines=raw_lines,
            suggestion=(
                "Ajustá los marcadores **Inputs:** / **Entrada:** "
                "para que coincidan con la firma del procedure."
            ),
        )]
    # Fallback genérico — lo tratamos como warning para no perder
    # información que el motor reportó.
    return [_issue(
        severity="warning", line=1,
        code="EXPRESSION_PARSE_ERROR",
        message=f"{type(err).__name__}: {err.message}",
        raw_lines=raw_lines,
    )]


def _check_epistemic(
    node,
    anchor_line: int,
    raw_lines: list[str],
) -> list[ValidationIssue]:
    out: list[ValidationIssue] = []
    # Para AXIOM, miramos `explicit_dependencies` — el campo crudo
    # ANTES de que el resolver descarte los unresolved. Si el autor
    # declaró `**Depende de:** def.base` y def.base no existe, el
    # validator emitirá `FOUNDATION_NOT_FOUND` por separado, pero
    # también queremos reportar `AXIOM_HAS_FOUNDATIONS` porque la
    # intención del autor (declarar foundations en un axioma) ya es
    # incorrecta.
    raw_deps = node.explicit_dependencies or []
    if node.status == EpistemicStatus.AXIOM and raw_deps:
        out.append(_issue(
            severity="error", line=anchor_line,
            code="AXIOM_HAS_FOUNDATIONS",
            message=(
                f"El nodo '{node.node_id}' está declarado AXIOM pero "
                f"tiene foundations: {raw_deps}. Un axioma "
                f"no puede depender de otros nodos."
            ),
            raw_lines=raw_lines,
            suggestion=(
                "Si depende de otros nodos, declaralo como THEOREM. "
                "Si es un principio fundamental, eliminá la línea "
                "**Depende de:**."
            ),
        ))
    # Para THEOREM, exigimos que el autor DECLARÓ explícitamente
    # foundations vía `**Depende de:**`. Si no lo hizo, el motor
    # del exp_06 aplica la heurística "hermanos previos en la
    # sección", lo cual produce un grafo válido en runtime pero NO
    # refleja la intención del autor. Acá reportamos en favor del
    # autor: te falta declarar las dependencias.
    if (
        node.status == EpistemicStatus.THEOREM
        and not node.explicit_dependencies
    ):
        out.append(_issue(
            severity="error", line=anchor_line,
            code="THEOREM_MISSING_FOUNDATIONS",
            message=(
                f"El nodo '{node.node_id}' es THEOREM pero no declara "
                f"foundations. Los teoremas requieren al menos una "
                f"dependencia explícita vía **Depende de:**."
            ),
            raw_lines=raw_lines,
            suggestion=(
                "Agregá **Depende de:** seguido de los ids de los "
                "axiomas, definiciones o teoremas que lo justifican."
            ),
        ))
    if node.status == EpistemicStatus.ALGORITHM:
        if not node.inputs or not node.outputs:
            out.append(_issue(
                severity="error", line=anchor_line,
                code="ALGORITHM_MISSING_IO",
                message=(
                    f"El nodo '{node.node_id}' es ALGORITHM pero "
                    f"falta declarar **Entrada:** o **Salida:**."
                ),
                raw_lines=raw_lines,
                suggestion=(
                    "Los algoritmos requieren ambas: "
                    "`**Entrada:** ...` y `**Salida:** ...` (o sus "
                    "sinónimos **Inputs:** / **Outputs:**)."
                ),
            ))
    if node.status == EpistemicStatus.HYPOTHESIS and node.foundations:
        # Si hay foundations declarados, sugerimos THEOREM.
        out.append(_issue(
            severity="warning", line=anchor_line,
            code="HYPOTHESIS_WITH_COMPLETE_FOUNDATIONS",
            message=(
                f"El nodo '{node.node_id}' es HYPOTHESIS pero "
                f"declara foundations completos. ¿Es realmente "
                f"hipótesis o ya se puede demostrar como THEOREM?"
            ),
            raw_lines=raw_lines,
            suggestion=(
                "Si las foundations alcanzan para demostrarlo, "
                "cambiá el marcador a **Teorema:**."
            ),
        ))
    return out


def _check_surface_forms(
    parse_report,
    raw_lines: list[str],
    id_lines: dict[str, list[int]],
    global_registry: VocabularyRegistry | None,
) -> list[ValidationIssue]:
    out: list[ValidationIssue] = []
    # Scan crudo de líneas `**Términos:**` para detectar entradas
    # vacías ANTES de que el _split_csv_terms las descarte
    # silenciosamente. Esta es la única forma de reportar "coma
    # sobrante" al autor — el ExtractedNode ya viene limpio.
    for idx, line in enumerate(raw_lines, start=1):
        m = _TERMS_LINE_RE.match(line)
        if not m:
            continue
        raw_value = m.group(1)
        # Forma vacía = una pieza entre comas que es solo espacios
        # (no contamos las comas finales/iniciales como vacío
        # explícito porque son tipográficamente comunes y benignas).
        pieces = raw_value.split(",")
        # Detectamos vacíos INTERIORES: aparece "alfa, , beta" pero
        # NO "alfa, beta," (trailing comma → benigno).
        for i, piece in enumerate(pieces):
            if 0 < i < len(pieces) - 1 and not piece.strip():
                out.append(_issue(
                    severity="error", line=idx,
                    code="EMPTY_SURFACE_FORM",
                    message=(
                        f"En la línea {idx}, **Términos:** tiene una "
                        f"entrada vacía entre comas."
                    ),
                    raw_lines=raw_lines,
                    suggestion=(
                        "Eliminá la coma sobrante o completá la "
                        "entrada vacía."
                    ),
                ))
                break  # un report por línea basta

    seen: dict[str, str] = {}  # forma_normalizada → node_id
    for node in parse_report.nodes_extracted:
        forms = (node.extra_properties or {}).get("surface_forms", []) or []
        anchor = id_lines.get(node.node_id, [1])[0]
        for sf in forms:
            if not isinstance(sf, str):
                continue
            if not sf.strip():
                # Cubrimos el caso patológico — el handler raw scan
                # ya capturó vacíos típicos; este es el cinturón
                # de seguridad si por algún motivo llega a la lista.
                continue
            normal = normalize(sf)
            if normal in seen and seen[normal] != node.node_id:
                out.append(_issue(
                    severity="error", line=anchor,
                    code="DUPLICATE_SURFACE_FORM_IN_DOCUMENT",
                    message=(
                        f"La surface form '{sf}' aparece tanto en "
                        f"'{seen[normal]}' como en '{node.node_id}'."
                    ),
                    raw_lines=raw_lines,
                    suggestion=(
                        "Cada surface form debe pertenecer a un "
                        "único nodo en el documento."
                    ),
                ))
            else:
                seen[normal] = node.node_id
            if global_registry is not None:
                hits = global_registry.lookup(sf)
                # Filtrar el propio especialista si ya estuviera
                # cargado (caso reload). Por convención de exp_21,
                # `global_registry` no incluye al especialista que
                # estamos validando — el caller decide.
                if hits:
                    spec_ids = sorted({h.specialist_id for h in hits})
                    out.append(_issue(
                        severity="warning", line=anchor,
                        code="SURFACE_FORM_CONFLICT_WITH_REGISTRY",
                        message=(
                            f"La surface form '{sf}' ya existe en "
                            f"otro(s) especialista(s): "
                            f"{', '.join(spec_ids)}."
                        ),
                        raw_lines=raw_lines,
                        suggestion=(
                            "Si el conflicto es intencional, ignorá "
                            "este aviso. El sistema delegará la "
                            "ambigüedad al usuario vía "
                            "ClarificationRequest."
                        ),
                    ))
    return out


def _check_expressions(
    parse_report,
    raw_lines: list[str],
    id_lines: dict[str, list[int]],
    known_specialists: dict[str, KnowledgeGraph] | None,
) -> list[ValidationIssue]:
    out: list[ValidationIssue] = []
    local_ids = {n.node_id for n in parse_report.nodes_extracted}
    for node in parse_report.nodes_extracted:
        template = (node.extra_properties or {}).get("expression_template")
        if not template:
            continue
        anchor = id_lines.get(node.node_id, [1])[0]
        try:
            tokens = parse_template(template)
        except TemplateParseError as e:
            out.append(_issue(
                severity="error", line=anchor,
                code="EXPRESSION_PARSE_ERROR",
                message=(
                    f"La plantilla **Expresión:** del nodo "
                    f"'{node.node_id}' no se pudo analizar: {e}."
                ),
                raw_lines=raw_lines,
                suggestion=(
                    "Verificá que las llaves estén balanceadas y que "
                    "cada referencia tenga la forma `{kind.target}` "
                    "con kind ∈ node|input|output|step|self."
                ),
            ))
            continue
        # Refs `{node.X}`: X debe existir local o cross-spec.
        for tok in tokens:
            if not hasattr(tok, "kind"):
                continue
            if tok.kind != "node":
                continue
            target = tok.target
            resolves = (
                target in local_ids
                or _resolves_cross_spec(target, known_specialists)
            )
            if not resolves:
                out.append(_issue(
                    severity="error", line=anchor,
                    code="EXPRESSION_REF_NOT_FOUND",
                    message=(
                        f"La plantilla del nodo '{node.node_id}' "
                        f"referencia '{{node.{target}}}' pero ese id "
                        f"no existe en el documento ni en "
                        f"especialistas registrados."
                    ),
                    raw_lines=raw_lines,
                    suggestion=(
                        "Verificá que el id esté bien escrito o que "
                        "el nodo referenciado esté declarado antes."
                    ),
                ))
    return out


def _resolves_cross_spec(
    target: str,
    known_specialists: dict[str, KnowledgeGraph] | None,
) -> bool:
    if not known_specialists:
        return False
    if "::" in target:
        spec, node_id = target.split("::", 1)
        g = known_specialists.get(spec)
        return bool(g and g.has(node_id))
    # Búsqueda por id "puro" en cualquier especialista.
    for g in known_specialists.values():
        if g.has(target):
            return True
    return False


def _check_coherence(
    parse_report,
    raw_lines: list[str],
    external_ids: set[str] | None = None,
) -> list[ValidationIssue]:
    out: list[ValidationIssue] = []
    if not parse_report.nodes_extracted:
        out.append(_issue(
            severity="error", line=1, code="EMPTY_DOCUMENT",
            message=(
                "El documento no contiene ningún nodo válido. "
                "Verificá que tenga al menos un bloque "
                "**Definición:** / **Teorema:** / **Axioma:** / "
                "**Algoritmo:** con su **Id:**."
            ),
            raw_lines=raw_lines,
            suggestion=(
                "Mirá `experiment_21/data/sample_domain.md` como "
                "ejemplo de la estructura mínima."
            ),
        ))
        return out
    ext_ids = external_ids or set()
    has_axiom = any(
        n.status == EpistemicStatus.AXIOM for n in parse_report.nodes_extracted
    )
    has_external_dep = any(
        any("::" in f or f in ext_ids for f in n.foundations)
        for n in parse_report.nodes_extracted
    )
    if not has_axiom and not has_external_dep:
        out.append(_issue(
            severity="warning", line=1, code="NO_AXIOMS_NO_FOUNDATIONS",
            message=(
                "El documento no declara axiomas locales ni "
                "referencias a especialistas externos. ¿El dominio "
                "es realmente autónomo?"
            ),
            raw_lines=raw_lines,
            suggestion=(
                "Si todos los teoremas dependen de definiciones, "
                "necesitás algún axioma raíz. Si dependen de otro "
                "especialista, declaralo como `spec_id::node_id`."
            ),
        ))
    return out
