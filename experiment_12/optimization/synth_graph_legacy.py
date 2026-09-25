"""Réplica del generador de grafos sintéticos del exp_11 que produce
LegacyKnowledgeGraph en lugar de KnowledgeGraph.

Estructura idéntica al exp_11 — sólo cambia el tipo del grafo
construido. Eso garantiza que la única diferencia en el benchmark
sea la implementación del grafo, no la forma de los datos.
"""
from __future__ import annotations

from experiment_01.knowledge_graph import (
    EpistemicStatus,
    KnowledgeNode,
    NodeKind,
)

from .legacy_graph import LegacyKnowledgeGraph


# Reutilizamos las mismas constantes que el exp_11.
TARGET_VAR = "synth_target"
_THM_FANIN = 5


def build_synthetic_legacy_graph(n_nodes: int) -> LegacyKnowledgeGraph:
    if n_nodes < 2:
        raise ValueError(f"n_nodes debe ser >= 2, recibido {n_nodes}")

    g = LegacyKnowledgeGraph()
    g.add(KnowledgeNode(
        id="ax.synth.base",
        statement="(synth) axioma raíz para test de escala.",
        status=EpistemicStatus.AXIOM,
        kind=NodeKind.RELATION,
    ))

    n_defs = n_nodes - 2
    for i in range(n_defs):
        foundations = ["ax.synth.base"]
        if i > 0:
            foundations.append(f"def.synth.var_{i - 1}")
        var_name = f"v_{i}"
        node_id = f"def.synth.var_{i}"
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

    fanin = min(_THM_FANIN, n_defs)
    if fanin == 0:
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
        input_vars = [f"v_{n_defs - fanin + j}" for j in range(fanin)]
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
