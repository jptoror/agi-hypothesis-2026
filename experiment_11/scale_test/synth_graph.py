"""Generador de grafos sintéticos para el test de escala.

Estructura del grafo generado (similar a los grafos reales del
proyecto, con cadena de dependencias para que `transitive_foundations`
y `backward_chaining` tengan trabajo no trivial):

  - 1 axioma raíz: `ax.synth.base`
  - N-2 definiciones, cada una depende del axioma + de la anterior
    (cadena lineal). Cada definición lleva variable propia y tiene
    `compute` ejecutable trivial.
  - 1 teorema final: `thm.synth.target` que produce la variable
    objetivo `target_var`. Sus inputs son las variables de las
    últimas K definiciones (rama de fan-in).

Total = N nodos exactos. La cadena lineal asegura que el cierre
transitivo crezca con N (peor caso para `transitive_foundations`).
El teorema final con K inputs asegura que el backward chaining
recurra a K niveles distintos de derivación.
"""
from __future__ import annotations

from experiment_01.knowledge_graph import (
    EpistemicStatus,
    KnowledgeGraph,
    KnowledgeNode,
    NodeKind,
)


# Variable objetivo del teorema final.
TARGET_VAR = "synth_target"

# Cuántas definiciones aporta inputs al teorema final.
_THM_FANIN = 5


def build_synthetic_graph(n_nodes: int) -> KnowledgeGraph:
    """Construye un grafo sintético con exactamente n_nodes nodos.

    Mínimo n_nodes = 2 (1 axioma + 1 teorema). Por debajo lanza
    ValueError. Para n_nodes < _THM_FANIN + 2, el teorema final
    usa todas las definiciones disponibles.
    """
    if n_nodes < 2:
        raise ValueError(f"n_nodes debe ser >= 2, recibido {n_nodes}")

    g = KnowledgeGraph()

    # Axioma raíz.
    g.add(KnowledgeNode(
        id="ax.synth.base",
        statement="(synth) axioma raíz para test de escala.",
        status=EpistemicStatus.AXIOM,
        kind=NodeKind.RELATION,
    ))

    # Definiciones encadenadas: def_0 depende del axioma; def_i (i>0)
    # depende del axioma y de def_{i-1}. Total: n_nodes - 2.
    n_defs = n_nodes - 2
    for i in range(n_defs):
        foundations = ["ax.synth.base"]
        if i > 0:
            foundations.append(f"def.synth.var_{i - 1}")
        var_name = f"v_{i}"
        node_id = f"def.synth.var_{i}"
        # Cada def es una RELATION ejecutable que produce su propia
        # variable como una constante (input vacío). Esto permite
        # que el teorema final pueda recursar a través de la cadena.
        g.add(KnowledgeNode(
            id=node_id,
            statement=f"(synth) define la variable {var_name}",
            status=EpistemicStatus.DEFINITION,
            kind=NodeKind.RELATION,
            foundations=foundations,
            inputs=[],
            outputs=[var_name],
            compute=lambda _v, _i=i: {f"v_{_i}": float(_i + 1)},
            properties={"synth_index": i},
        ))

    # Teorema final: produce TARGET_VAR a partir de las últimas K
    # definiciones (o todas si hay menos).
    fanin = min(_THM_FANIN, n_defs)
    if fanin == 0:
        # Caso extremo n_nodes==2: sin definiciones, teorema usa el
        # axioma como único fundamento y no tiene inputs.
        g.add(KnowledgeNode(
            id="thm.synth.target",
            statement=f"(synth) produce {TARGET_VAR} sin inputs.",
            status=EpistemicStatus.THEOREM,
            kind=NodeKind.RELATION,
            foundations=["ax.synth.base"],
            inputs=[],
            outputs=[TARGET_VAR],
            compute=lambda _v: {TARGET_VAR: 0.0},
        ))
    else:
        # Inputs: las últimas K variables.
        input_vars = [f"v_{n_defs - fanin + j}" for j in range(fanin)]
        # Foundations: el axioma + las últimas K definiciones.
        foundations = ["ax.synth.base"] + [
            f"def.synth.var_{n_defs - fanin + j}" for j in range(fanin)
        ]
        g.add(KnowledgeNode(
            id="thm.synth.target",
            statement=(
                f"(synth) produce {TARGET_VAR} sumando {fanin} variables."
            ),
            status=EpistemicStatus.THEOREM,
            kind=NodeKind.RELATION,
            foundations=foundations,
            inputs=input_vars,
            outputs=[TARGET_VAR],
            compute=lambda v, _vars=input_vars: {
                TARGET_VAR: sum(v[k] for k in _vars)
            },
        ))

    return g
