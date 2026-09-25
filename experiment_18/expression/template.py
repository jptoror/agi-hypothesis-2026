"""Parser y resolutor de plantillas `**Expresión:**` (exp_18).

Una plantilla es un string con literales y referencias entre llaves:

  `{node.X}`    → expresión del nodo cuyo id es X (recursivo)
  `{input.Y}`   → binding de entrada Y (del problema/paso)
  `{output.Z}`  → binding de salida Z (del paso)
  `{step.N}`    → referencia al texto rendereado del paso N
  `{self.name}` → statement del nodo actual (atajo)

Llaves literales se escapan duplicando: `{{` y `}}` (mismo patrón
que f-strings de Python).

Errores explícitos:
  - Llave abierta sin cerrar  → `TemplateParseError`
  - Referencia con `kind` desconocido → `TemplateParseError`
  - Resolución que falla            → `UnresolvedReferenceError`

NO hay degradación silenciosa. Una plantilla que no se puede
resolver lanza excepción — es responsabilidad del autor del nodo
declarar plantillas válidas, y del caller proveer los bindings
correctos.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal


_VALID_KINDS = ("node", "input", "output", "step", "self")
RefKind = Literal["node", "input", "output", "step", "self"]


# ---------------------------------------------------------------------
# Errores
# ---------------------------------------------------------------------

class TemplateParseError(ValueError):
    """Plantilla mal formada: llave sin cerrar, kind desconocido,
    o sintaxis inválida en general."""


class UnresolvedReferenceError(KeyError):
    """Referencia válida sintácticamente pero que no resuelve a un
    valor concreto (nodo inexistente, binding faltante, etc.)."""

    def __init__(self, kind: str, target: str, reason: str = "") -> None:
        self.kind = kind
        self.target = target
        msg = f"referencia {{{kind}.{target}}} no resoluble"
        if reason:
            msg = f"{msg}: {reason}"
        super().__init__(msg)


# ---------------------------------------------------------------------
# Token de referencia
# ---------------------------------------------------------------------

@dataclass(frozen=True)
class TemplateRef:
    kind: RefKind
    target: str  # identificador después del primer punto


# ---------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------

def parse_template(template: str) -> list[str | TemplateRef]:
    """Tokeniza una plantilla en literales y `TemplateRef`.

    El parser es char-by-char para soportar el escape `{{`/`}}` sin
    sorpresas (regex con lookbehind se vuelve frágil). La salida es
    una lista alternada de `str` (literales) y `TemplateRef`.
    """
    tokens: list[str | TemplateRef] = []
    buf: list[str] = []
    i = 0
    n = len(template)
    while i < n:
        c = template[i]
        if c == "{":
            # Escape `{{` → literal `{`.
            if i + 1 < n and template[i + 1] == "{":
                buf.append("{")
                i += 2
                continue
            # Apertura de referencia: buscar `}`.
            close = template.find("}", i + 1)
            if close == -1:
                raise TemplateParseError(
                    f"llave abierta sin cerrar en posición {i}"
                )
            inner = template[i + 1:close].strip()
            if "." not in inner:
                raise TemplateParseError(
                    f"referencia '{inner}' sin formato 'kind.target'"
                )
            kind, _, target = inner.partition(".")
            kind = kind.strip()
            target = target.strip()
            if kind not in _VALID_KINDS:
                raise TemplateParseError(
                    f"kind desconocido '{kind}'; "
                    f"válidos: {_VALID_KINDS}"
                )
            if not target:
                raise TemplateParseError(
                    f"referencia '{inner}' sin target tras el punto"
                )
            if buf:
                tokens.append("".join(buf))
                buf = []
            tokens.append(TemplateRef(kind=kind, target=target))
            i = close + 1
            continue
        if c == "}":
            # Escape `}}` → literal `}`.
            if i + 1 < n and template[i + 1] == "}":
                buf.append("}")
                i += 2
                continue
            raise TemplateParseError(
                f"llave de cierre '}}' sin apertura en posición {i}"
            )
        buf.append(c)
        i += 1
    if buf:
        tokens.append("".join(buf))
    return tokens


# ---------------------------------------------------------------------
# Resolutor
# ---------------------------------------------------------------------

NodeResolver = Callable[[str], str]


def render_template(
    template: str,
    bindings: dict,
    resolver: NodeResolver,
    self_statement: str,
) -> str:
    """Sustituye referencias por sus valores y devuelve el texto.

    `bindings` espera la forma:
      {
        "input":  {nombre: valor, ...},
        "output": {nombre: valor, ...},
        "step":   {numero: texto_rendereado, ...},
      }

    Faltantes se reportan con `UnresolvedReferenceError`. El resolver
    de nodos debe lanzar `UnresolvedReferenceError(kind="node", ...)`
    cuando el id no existe o cuando se detecta un ciclo.
    """
    parts: list[str] = []
    for tok in parse_template(template):
        if isinstance(tok, str):
            parts.append(tok)
            continue
        ref = tok
        if ref.kind == "self":
            # `{self.name}` (o cualquier `self.X`) devuelve el
            # statement del nodo actual. El segmento tras el punto se
            # acepta como etiqueta libre — se reserva el caso por si
            # más adelante queremos varios slots de self (id, status,
            # etc.); hoy todos resuelven al statement.
            parts.append(self_statement)
            continue
        if ref.kind == "node":
            parts.append(resolver(ref.target))
            continue
        if ref.kind == "input":
            d = bindings.get("input") or {}
            if ref.target not in d:
                raise UnresolvedReferenceError(
                    "input", ref.target,
                    f"bindings.input no contiene '{ref.target}'",
                )
            parts.append(str(d[ref.target]))
            continue
        if ref.kind == "output":
            d = bindings.get("output") or {}
            if ref.target not in d:
                raise UnresolvedReferenceError(
                    "output", ref.target,
                    f"bindings.output no contiene '{ref.target}'",
                )
            parts.append(str(d[ref.target]))
            continue
        if ref.kind == "step":
            d = bindings.get("step") or {}
            if ref.target not in d:
                raise UnresolvedReferenceError(
                    "step", ref.target,
                    f"bindings.step no contiene '{ref.target}'",
                )
            parts.append(str(d[ref.target]))
            continue
        # Inalcanzable — parse_template valida _VALID_KINDS antes.
        raise TemplateParseError(f"kind no manejado: {ref.kind}")
    return "".join(parts)
