"""Patrones de definición conversacional (exp_20).

Cuatro patrones DECLARADOS — no inferencia, no NLP. Cada uno
extrae `(symbol, body)` y un `DefinitionMatch` cuando matchea.

Orden de prueba (fijo, declarado en `DEFINITION_PATTERNS`):

  1. `def_pat.llamemos`     — "llamemos X a Y"
  2. `def_pat.sea_igual`    — "sea X = Y" / "sea X igual a Y"
  3. `def_pat.definamos`    — "definamos X como Y"
  4. `def_pat.representa`   — "X representa Y"     (el más débil)

El último, "X representa Y", es el más permisivo en `symbol` (lo
toma como cualquier token). Para que no genere falsos positivos
con frases que arrancan con función-palabra ("el", "la", "los",
"un"...), bloqueamos esos tokens en `symbol` mediante
`_BLOCKED_SYMBOLS`.

La capitalización del símbolo se preserva (la lista de blocked
compara contra la forma lowercase). El body se conserva crudo
(con su capitalización original) menos espacios laterales.

Estos patrones también pueden ser cargados como nodos PROCEDURE
en un grafo del LanguageSpecialist via `as_pattern_node(p)`; eso
deja la trazabilidad alineada con el resto del proyecto — un
patrón es conocimiento del sistema, no código escondido. La
carga del grafo de patrones es opcional y la hace el caller.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Optional


# Tokens que NO pueden actuar como símbolo en el patrón
# "X representa Y". Si symbol coincide (lowercase) → match
# rechazado. La lista es DECLARATIVA — agregar entradas es un
# cambio explícito de política.
_BLOCKED_SYMBOLS = frozenset({
    "el", "la", "los", "las", "un", "una", "unos", "unas",
    "este", "esta", "esto", "estos", "estas",
    "ese", "esa", "eso", "esos", "esas",
    "aquel", "aquella", "aquello",
    "que", "qué", "cuál", "cual",
})


@dataclass(frozen=True)
class DefinitionMatch:
    """Resultado de matchear un patrón. Inmutable para que sea
    seguro pasar entre componentes sin que muten."""

    symbol: str           # forma con capitalización original
    body: str             # texto que define al símbolo, trimmed
    pattern_id: str       # qué patrón lo produjo
    raw_input: str        # input completo del usuario


# El extractor es una función pura: `str -> DefinitionMatch | None`.
ExtractorFn = Callable[[str], Optional[DefinitionMatch]]


@dataclass(frozen=True)
class DefinitionPattern:
    pattern_id: str
    template: str         # descripción humana ("llamemos {symbol} a {body}")
    extractor: ExtractorFn
    statement: str        # texto humano del patrón (para el grafo de patrones)

    def as_pattern_node_data(self) -> dict:
        """Datos para construir un nodo PROCEDURE en un grafo de
        patrones (opcional para el caller). Sigue la convención del
        proyecto: cada pieza del sistema es estructura, no código
        suelto. El node_id es `def_pat.{pattern_id_suffix}`."""
        suffix = self.pattern_id.split(".", 1)[-1]
        return {
            "id": f"def_pat.{suffix}",
            "statement": self.statement,
            "properties": {"template": self.template},
        }


# ---------------------------------------------------------------------
# helpers de tokenización del símbolo
# ---------------------------------------------------------------------

# El símbolo puede incluir letras, dígitos, underscore, y unos pocos
# signos no-puntuación (`-`, `'`). Esto NO incluye `,`, `.`, `?`, `!`,
# para que un símbolo no contenga puntuación que en realidad pertenece
# al final de la frase.
_SYMBOL_REGEX = r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9_][A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9_'\-]*"


def _strip_trailing_punct(s: str) -> str:
    return s.rstrip(" \t\n\r,.;:!?")


def _clean_body(raw_body: str) -> str:
    """Trim de body. Conserva la capitalización interna."""
    return _strip_trailing_punct(raw_body.strip())


def _accept(symbol: str, body: str) -> bool:
    """Reglas comunes: símbolo y body no vacíos y símbolo no
    bloqueado."""
    if not symbol or not body:
        return False
    if symbol.lower() in _BLOCKED_SYMBOLS:
        return False
    return True


# ---------------------------------------------------------------------
# Extractores concretos
# ---------------------------------------------------------------------

_LLAMEMOS_RE = re.compile(
    rf"^\s*llamemos\s+(?P<symbol>{_SYMBOL_REGEX})\s+a\s+(?P<body>.+?)\s*$",
    re.IGNORECASE,
)


def _extract_llamemos(text: str) -> DefinitionMatch | None:
    m = _LLAMEMOS_RE.match(text)
    if not m:
        return None
    symbol = m.group("symbol")
    body = _clean_body(m.group("body"))
    if not _accept(symbol, body):
        return None
    return DefinitionMatch(
        symbol=symbol, body=body,
        pattern_id="def_pat.llamemos", raw_input=text,
    )


_SEA_RE = re.compile(
    rf"^\s*sea\s+(?P<symbol>{_SYMBOL_REGEX})\s+(?:=|igual\s+a)\s+(?P<body>.+?)\s*$",
    re.IGNORECASE,
)


def _extract_sea(text: str) -> DefinitionMatch | None:
    m = _SEA_RE.match(text)
    if not m:
        return None
    symbol = m.group("symbol")
    body = _clean_body(m.group("body"))
    if not _accept(symbol, body):
        return None
    return DefinitionMatch(
        symbol=symbol, body=body,
        pattern_id="def_pat.sea_igual", raw_input=text,
    )


_DEFINAMOS_RE = re.compile(
    rf"^\s*definamos\s+(?P<symbol>{_SYMBOL_REGEX})\s+como\s+(?P<body>.+?)\s*$",
    re.IGNORECASE,
)


def _extract_definamos(text: str) -> DefinitionMatch | None:
    m = _DEFINAMOS_RE.match(text)
    if not m:
        return None
    symbol = m.group("symbol")
    body = _clean_body(m.group("body"))
    if not _accept(symbol, body):
        return None
    return DefinitionMatch(
        symbol=symbol, body=body,
        pattern_id="def_pat.definamos", raw_input=text,
    )


_REPRESENTA_RE = re.compile(
    rf"^\s*(?P<symbol>{_SYMBOL_REGEX})\s+representa\s+(?P<body>.+?)\s*$",
    re.IGNORECASE,
)


def _extract_representa(text: str) -> DefinitionMatch | None:
    m = _REPRESENTA_RE.match(text)
    if not m:
        return None
    symbol = m.group("symbol")
    body = _clean_body(m.group("body"))
    if not _accept(symbol, body):
        return None
    return DefinitionMatch(
        symbol=symbol, body=body,
        pattern_id="def_pat.representa", raw_input=text,
    )


# Orden DECLARADO de prueba — el primero que matchea gana. Cambiar
# este orden es un cambio explícito de política conversacional.
DEFINITION_PATTERNS: list[DefinitionPattern] = [
    DefinitionPattern(
        pattern_id="def_pat.llamemos",
        template="llamemos {symbol} a {body}",
        extractor=_extract_llamemos,
        statement="Asigna un nombre nuevo a una entidad existente.",
    ),
    DefinitionPattern(
        pattern_id="def_pat.sea_igual",
        template="sea {symbol} = {body}  /  sea {symbol} igual a {body}",
        extractor=_extract_sea,
        statement="Introduce una variable con un valor o expresión.",
    ),
    DefinitionPattern(
        pattern_id="def_pat.definamos",
        template="definamos {symbol} como {body}",
        extractor=_extract_definamos,
        statement="Declara un nuevo concepto en términos de uno existente.",
    ),
    DefinitionPattern(
        pattern_id="def_pat.representa",
        template="{symbol} representa {body}",
        extractor=_extract_representa,
        statement="Asocia un símbolo a una entidad u objeto del dominio.",
    ),
]


def match_definition(text: str) -> DefinitionMatch | None:
    """Itera `DEFINITION_PATTERNS` en orden y devuelve el primer
    match. None si ninguno matchea (input normal, no es una
    definición)."""
    for pat in DEFINITION_PATTERNS:
        m = pat.extractor(text)
        if m is not None:
            return m
    return None
