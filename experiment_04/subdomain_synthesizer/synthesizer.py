"""Sintetizador de subdominios emergentes.

Dado un Pattern `ready` y el mapping de grafos fuente, produce un
KnowledgeGraph nuevo, autocontenido, que encapsula la FORMA del
patrón como un subdominio propio.

Lo que entra al subgrafo:
  1. Todos los nodos ejercitados por el patrón (nodes_used_* del
     sample_record) — son las piezas activas que hicieron útil la
     colaboración.
  2. Los fundamentos transitivos de cada uno de esos nodos — para
     que el subgrafo sea autocontenido, no un fragmento que dependa
     de sus grafos padre para validarse.
  3. Un nodo DEFINITION por cada binding del patrón, que consolida
     la equivalencia ontológica del enunciado como convención
     permanente del subdominio.

Lo que NO entra:
  - Nodos no ejercitados (aunque estén en los grafos fuente). El
    subdominio es por construcción más pequeño que la unión de los
    grafos — sólo contiene lo que el patrón demostró necesario.
  - Los `delegation_hints` del patrón. Son pistas de enunciado; una
    vez consolidado, el subdominio asume implícitamente ese contexto.
    Quedan implícitos en las condiciones de validez de los nodos que
    sí se copian.
"""
from __future__ import annotations

from dataclasses import replace

from experiment_01.knowledge_graph import (
    EpistemicStatus,
    KnowledgeGraph,
    KnowledgeNode,
    NodeKind,
)
from experiment_04.pattern_detector import Pattern

from .result import SynthesisResult


class SubdomainSynthesizer:
    """Construye subdominios emergentes a partir de patrones ready."""

    def __init__(self, source_graphs: dict[str, KnowledgeGraph]) -> None:
        """source_graphs mapea el nombre del especialista (como aparece
        en el sample_record, p. ej. 'physics') al KnowledgeGraph del
        que se extraerán los nodos."""
        self.source_graphs = source_graphs

    # -- API pública ---------------------------------------------------

    def synthesize(self, pattern: Pattern) -> SynthesisResult:
        if pattern.sample_record is None:
            raise ValueError(
                "Pattern sin sample_record — no se puede sintetizar."
            )

        sample = pattern.sample_record
        initiator = sample.initiator
        responder = sample.responder

        if initiator not in self.source_graphs:
            raise KeyError(
                f"grafo del iniciador '{initiator}' no registrado en "
                f"source_graphs {list(self.source_graphs)}"
            )
        if responder not in self.source_graphs:
            raise KeyError(
                f"grafo del responder '{responder}' no registrado en "
                f"source_graphs {list(self.source_graphs)}"
            )

        subgraph = KnowledgeGraph()

        # 1. Incorporar nodos del iniciador (con fundamentos).
        nodes_from_initiator = self._import_with_foundations(
            sample.nodes_used_initiator,
            self.source_graphs[initiator],
            subgraph,
        )

        # 2. Incorporar nodos del responder (con fundamentos).
        nodes_from_responder = self._import_with_foundations(
            sample.nodes_used_responder,
            self.source_graphs[responder],
            subgraph,
        )

        # 3. Consolidar cada binding del patrón como nodo DEFINITION.
        binding_nodes: list[str] = []
        for src, dst in sample.variable_bindings.items():
            node = self._build_binding_node(src, dst, pattern)
            subgraph.add(node)
            binding_nodes.append(node.id)

        # 4. Nombre determinista (alfabético) del subdominio.
        specialist_name = "_".join(sorted({initiator, responder}))

        return SynthesisResult.new(
            subgraph=subgraph,
            specialist_name=specialist_name,
            binding_nodes=binding_nodes,
            nodes_from_initiator=nodes_from_initiator,
            nodes_from_responder=nodes_from_responder,
            pattern=pattern,
        )

    # -- importación con cierre transitivo -----------------------------

    @staticmethod
    def _import_with_foundations(
        node_ids: list[str],
        source: KnowledgeGraph,
        target: KnowledgeGraph,
    ) -> list[str]:
        """Copia cada nodo y sus fundamentos transitivos al target.

        Respeta el orden topológico: fundamentos primero, para que
        `target.add()` nunca falle por fundamento inexistente. Si un
        nodo ya existe en el target (p. ej. axiomas compartidos entre
        grafos como `ax.arithmetic.real_numbers`), no lo duplica.
        """
        imported_top_level: list[str] = []
        for nid in node_ids:
            if not source.has(nid):
                # El nodo ejercitado no está en el grafo fuente —
                # posible si vino de otro subdominio previo. Lo
                # registramos implícitamente: el test verá que no
                # aparece en la lista final.
                continue
            # Primero añadimos los fundamentos transitivos en orden
            # topológico (el método del grafo ya los entrega así).
            for dep in source.transitive_foundations(nid):
                if not target.has(dep.id):
                    target.add(replace(dep))
            # Luego el nodo mismo.
            if not target.has(nid):
                target.add(replace(source.get(nid)))
            imported_top_level.append(nid)
        return imported_top_level

    # -- construcción del nodo binding ---------------------------------

    @staticmethod
    def _build_binding_node(
        src: str,
        dst: str,
        pattern: Pattern,
    ) -> KnowledgeNode:
        problems_seen = sorted(pattern.problem_ids)
        return KnowledgeNode(
            id=f"binding.{src}_equals_{dst}",
            statement=(
                f"En este subdominio, {src} := {dst} (consolidado de "
                f"patrón recurrente)."
            ),
            status=EpistemicStatus.DEFINITION,
            kind=NodeKind.RELATION,
            foundations=[],
            validity_conditions=[],
            inputs=[dst],
            outputs=[src],
            compute=lambda v, _src=src, _dst=dst: {_src: v[_dst]},
            rationale=(
                f"Consolidado automáticamente desde {pattern.count} "
                f"colaboraciones con signature idéntica (problem_ids: "
                f"{problems_seen}). No es un teorema — es una "
                f"convención del subdominio."
            ),
            properties={
                "consolidated_from_pattern": True,
                "pattern_count": pattern.count,
                "binding_src": src,
                "binding_dst": dst,
            },
        )
