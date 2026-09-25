"""Biblioteca de plantillas C++ — patrón paralelo a `PROCEDURES`
del exp_06.

El documento `cpp_minimal.md` declara los CONSTRUCTOS por id; las
plantillas concretas viven aquí. El especialista resuelve el
nombre del procedimiento (declarado en `**Procedimiento:**`) a
una función Python que ensambla código a partir de las plantillas
y devuelve el texto estructurado.

Cada plantilla es un `CppTemplate` con:
  - `template`: string con placeholders entre llaves `{slot}`.
  - `slots`: lista de nombres de slot esperados.
  - `node_id`: id del nodo del documento al que corresponde —
    sirve para que la traza pueda nombrar de qué nodo del grafo
    sale cada fragmento.

El procedimiento `cpp_greedy_coloring_compose` consume estas
plantillas y produce el código fuente. Es la única pieza de
"código generador" del experimento — sin él, las plantillas son
strings inertes.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CppTemplate:
    node_id: str
    template: str
    slots: list[str]

    def render(self, **values) -> str:
        """Aplica las sustituciones declaradas en `slots`. Falla
        explícitamente si falta algún slot — no inventa defaults."""
        missing = [s for s in self.slots if s not in values]
        if missing:
            raise ValueError(
                f"plantilla {self.node_id} requiere slots {self.slots}; "
                f"faltan {missing}"
            )
        return self.template.format(**values)


# Biblioteca canónica. Cada entrada mapea node_id → CppTemplate.
# Añadir una plantilla nueva = añadir una entrada aquí + (si
# corresponde) un nodo nuevo en el documento.
CPP_TEMPLATES: dict[str, CppTemplate] = {
    "def.cpp.include": CppTemplate(
        node_id="def.cpp.include",
        template="#include <{header}>",
        slots=["header"],
    ),
    "def.cpp.function": CppTemplate(
        node_id="def.cpp.function",
        template="{ret} {name}({params}) {{\n  {body}\n}}",
        slots=["ret", "name", "params", "body"],
    ),
    "def.cpp.for_loop": CppTemplate(
        node_id="def.cpp.for_loop",
        template=(
            "for ({iter} = {coll}.begin(); {iter} != {coll}.end(); {iter}++) {{\n"
            "  {body}\n"
            "}}"
        ),
        slots=["iter", "coll", "body"],
    ),
    "def.cpp.set": CppTemplate(
        node_id="def.cpp.set",
        template="set<{T}> {name}",
        slots=["T", "name"],
    ),
    "def.cpp.vector": CppTemplate(
        node_id="def.cpp.vector",
        template="vector<{T}> {name}",
        slots=["T", "name"],
    ),
    "def.cpp.iterator": CppTemplate(
        node_id="def.cpp.iterator",
        template="{T}::iterator {name}",
        slots=["T", "name"],
    ),
}


# ---------------------------------------------------------------------
# Procedimiento ejecutable: compone código C++ para greedy_coloring.
# ---------------------------------------------------------------------

def cpp_greedy_coloring_compose(values: dict) -> dict:
    """Procedimiento referenciado por `alg.cpp.greedy_coloring_impl`.

    Recibe:
      - `abstract_node`: id del nodo abstracto del grafo del exp_15
        (en este experimento, "alg.greedy_coloring").
      - `target_container`: nombre del contenedor sobre el que
        iterar (típicamente "no_col").

    Devuelve:
      - `cpp_code`: string con el código C++ ensamblado a partir
        de las plantillas. Cada fragmento de la salida proviene
        de una plantilla del CPP_TEMPLATES — auditable.

    NO genera código — COMPONE plantillas. Cada llamada a
    `template.render()` es una sustitución determinista. La
    salida es función pura de las entradas y de las plantillas
    declaradas.
    """
    abstract_node = values["abstract_node"]
    target = values["target_container"]

    # Iterador `q` del tipo `set<int>::iterator`. Plantilla del
    # nodo def.cpp.iterator aplicada con T=set<int>, name=q.
    iter_decl = CPP_TEMPLATES["def.cpp.iterator"].render(
        T="set<int>", name="q",
    )

    # Lazo for sobre el contenedor objetivo. El cuerpo lleva dos
    # comentarios que nombran explícitamente el nodo abstracto y
    # el constructor C++ que justifica cada paso — la auditoría
    # del código apunta al grafo del que viene.
    body = (
        f"// verificar adyacencia ({abstract_node})\n"
        f"  // insertar en nuevo_color (def.cpp.set)"
    )
    for_loop = CPP_TEMPLATES["def.cpp.for_loop"].render(
        iter="q", coll=target, body=body,
    )

    # El iterador se declara antes del for. Los unimos.
    code = f"{iter_decl};\n{for_loop}"

    return {"cpp_code": code}
