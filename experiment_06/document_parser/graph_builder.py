"""GraphBuilder — tercera y última fase del parser de documentos.

Recibe el ParseReport del NodeExtractor y construye un KnowledgeGraph
real, ejecutando estos pasos:

  1. Resolución de procedimientos: cada ExtractedNode con
     `procedure_name` se enlaza con su ProcedureSpec en la biblioteca
     `specialist_factory.procedures.PROCEDURES`. Se verifica que las
     firmas declaradas en el documento (Inputs/Outputs) coincidan
     exactamente con las del spec; cualquier discrepancia produce
     `ProcedureSignatureMismatch`. Si el procedure_name no existe →
     `UnknownProcedure`.

  2. Ordenación topológica con Kahn sobre las dependencias declaradas
     (foundations). Si hay ciclo → `CyclicDependency`.

  3. Inserción en el KnowledgeGraph en orden topológico. La clase
     `KnowledgeGraph.add()` ya rechaza fundamentos inexistentes; el
     orden topológico asegura que nunca pasa.

  4. Validación final: `graph.validate()` debe devolver lista vacía.
     Si no, los errores se incorporan al BuildReport como
     `GraphValidationError` y `graph_valid=False`.

INVARIANTE arquitectónico (precisión 3 del enunciado): si
`graph_valid` es False, el caller (specialist_factory) NO debe
registrar el especialista. El builder no impone el invariante; lo
expone al caller — pero el BuildReport lleva `graph_valid` como
campo discreto para que la decisión sea trivial.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from experiment_01.knowledge_graph import (
    KnowledgeGraph,
    KnowledgeNode,
    NodeKind,
)

# Importamos `ProcedureSpec` SÓLO bajo TYPE_CHECKING y `PROCEDURES`
# de forma LAZY dentro del constructor para romper el ciclo:
#   experiment_06.document_parser.graph_builder
#     ↓ (top-level antes)
#   experiment_06.specialist_factory.procedures
#     → experiment_06.specialist_factory (__init__ importa factory)
#     → experiment_06.specialist_factory.factory
#     → experiment_06.document_parser  ← cierra el ciclo
#
# Como `from __future__ import annotations` ya difiere las
# anotaciones de tipo, podemos referenciar `ProcedureSpec` por
# nombre en signaturas sin necesitar el símbolo en runtime.
if TYPE_CHECKING:
    from experiment_06.specialist_factory.procedures import ProcedureSpec

from .node_extractor import (
    ExtractedNode,
    ParseError,
    ParseReport,
    ProcedureSignatureMismatch,
)


# ---------------------------------------------------------------------
# Tipos de error específicos del builder
# ---------------------------------------------------------------------

@dataclass
class BuildError:
    message: str

    def render(self) -> str:
        return f"  ✗ {type(self).__name__}: {self.message}"


@dataclass
class UnknownProcedure(BuildError):
    node_id: str
    procedure_name: str

    def render(self) -> str:
        return (
            f"  ✗ UnknownProcedure: nodo '{self.node_id}' referencia el "
            f"procedimiento '{self.procedure_name}' que no está en la "
            f"biblioteca PROCEDURES."
        )


@dataclass
class CyclicDependency(BuildError):
    cycle_nodes: list[str]

    def render(self) -> str:
        chain = " → ".join(self.cycle_nodes + [self.cycle_nodes[0]])
        return f"  ✗ CyclicDependency: ciclo detectado: {chain}"


@dataclass
class GraphValidationError(BuildError):
    detail: str

    def render(self) -> str:
        return f"  ✗ GraphValidationError: {self.detail}"


# ---------------------------------------------------------------------
# BuildReport
# ---------------------------------------------------------------------

@dataclass
class BuildReport:
    """Resultado de la fase 3 del parser.

    `errors` agrupa tanto los errores del graph_builder
    (UnknownProcedure, CyclicDependency, GraphValidationError) como
    los `ProcedureSignatureMismatch` que el builder genera durante la
    verificación de firmas (declarados en `node_extractor` por
    coherencia tipológica con el resto del parser).
    """

    nodes_built: int
    graph_valid: bool
    errors: list = field(default_factory=list)   # BuildError | ParseError
    topological_order: list[str] = field(default_factory=list)
    graph: KnowledgeGraph | None = None

    @property
    def is_valid(self) -> bool:
        return self.graph_valid and not self.errors

    def render(self) -> str:
        lines = [
            "=" * 72,
            "BUILD REPORT",
            "=" * 72,
            f"nodos construidos:    {self.nodes_built}",
            f"graph.validate() OK:  {self.graph_valid}",
            f"errores:              {len(self.errors)}",
            f"is_valid:             {self.is_valid}",
            "",
            "── orden topológico de inserción ──",
        ]
        if not self.topological_order:
            lines.append("  (vacío)")
        else:
            for i, nid in enumerate(self.topological_order, 1):
                lines.append(f"  {i:2}. {nid}")
        if self.errors:
            lines.append("")
            lines.append("── errores ──")
            for e in self.errors:
                lines.append(e.render())
        return "\n".join(lines)


# ---------------------------------------------------------------------
# GraphBuilder
# ---------------------------------------------------------------------

class GraphBuilder:
    def __init__(
        self,
        procedures: dict[str, ProcedureSpec] | None = None,
    ) -> None:
        # Default a la biblioteca canónica del experimento. Pasable
        # explícitamente para tests aislados (mock procedures). El
        # import de PROCEDURES es LAZY para romper el ciclo
        # graph_builder ↔ specialist_factory (ver PROB-07).
        if procedures is None:
            from experiment_06.specialist_factory.procedures import (
                PROCEDURES,
            )
            self.procedures = PROCEDURES
        else:
            self.procedures = procedures

    def build(
        self,
        parse_report: ParseReport,
        base_graph: KnowledgeGraph | None = None,
    ) -> BuildReport:
        """Construye el KnowledgeGraph desde el ParseReport.

        `base_graph` (opcional, exp_09): grafo del que se importan
        fundamentos referenciados por el documento que no aparecen
        en él mismo. Por cada referencia faltante que exista en
        `base_graph`, se importa el nodo y su cierre transitivo.
        Las referencias que tampoco existan en el base se reportan
        como `GraphValidationError` al validar.
        """
        from dataclasses import replace as _dc_replace

        nodes = parse_report.nodes_extracted
        errors: list = []

        # Paso 1: resolver procedimientos y verificar firmas.
        # Un nodo cuya verificación falla NO se descarta — se registra
        # el error y el nodo entra al grafo SIN compute. La decisión
        # de aceptar o no pertenece al caller (a través de is_valid).
        node_to_spec: dict[str, ProcedureSpec | None] = {}
        for node in nodes:
            if node.procedure_name is None:
                node_to_spec[node.node_id] = None
                continue
            spec = self.procedures.get(node.procedure_name)
            if spec is None:
                errors.append(UnknownProcedure(
                    message=f"procedimiento '{node.procedure_name}' no registrado",
                    node_id=node.node_id,
                    procedure_name=node.procedure_name,
                ))
                node_to_spec[node.node_id] = None
                continue
            if list(node.inputs) != list(spec.inputs) or \
               list(node.outputs) != list(spec.outputs):
                errors.append(ProcedureSignatureMismatch(
                    message=(
                        f"firma del nodo '{node.node_id}' no coincide con "
                        f"la del procedimiento '{node.procedure_name}'"
                    ),
                    node_id=node.node_id,
                    document_declares=list(node.inputs),
                    procedure_expects=list(spec.inputs),
                ))
                node_to_spec[node.node_id] = None
                continue
            node_to_spec[node.node_id] = spec

        # Paso 2: orden topológico (Kahn) sobre foundations.
        topo_order, cycle = self._topological_order(nodes)
        if cycle is not None:
            errors.append(CyclicDependency(
                message=f"ciclo en dependencias: {cycle}",
                cycle_nodes=cycle,
            ))
            return BuildReport(
                nodes_built=0,
                graph_valid=False,
                errors=errors,
                topological_order=[],
                graph=None,
            )

        # Paso 3: construir KnowledgeGraph. Si hay base_graph,
        # primero importamos los nodos del base referenciados por el
        # documento, con cierre transitivo de fundamentos. Cada nodo
        # importado conserva su forma original (status, foundations,
        # compute) — el subgrafo del documento queda anclado al
        # cierre del base, igual que en el SubdomainSynthesizer del
        # exp_04.
        graph = KnowledgeGraph()
        document_ids = {n.node_id for n in nodes}
        if base_graph is not None:
            referenced_external: set[str] = set()
            for n in nodes:
                for f in n.foundations:
                    if f not in document_ids and base_graph.has(f):
                        referenced_external.add(f)
            # Cierre transitivo en orden topológico (graph.add()
            # exige que los foundations existan al insertar).
            imported: set[str] = set()
            for ext_id in sorted(referenced_external):
                for dep in base_graph.transitive_foundations(ext_id):
                    if dep.id not in imported:
                        graph.add(_dc_replace(dep))
                        imported.add(dep.id)
                if ext_id not in imported:
                    graph.add(_dc_replace(base_graph.get(ext_id)))
                    imported.add(ext_id)

        node_by_id = {n.node_id: n for n in nodes}
        built: list[str] = []
        for nid in topo_order:
            node = node_by_id[nid]
            spec = node_to_spec.get(nid)
            kn = self._to_knowledge_node(node, spec)
            try:
                graph.add(kn)
                built.append(nid)
            except (ValueError, KeyError) as e:
                errors.append(GraphValidationError(
                    message=f"no se pudo insertar '{nid}': {e}",
                    detail=str(e),
                ))

        # Paso 4: validate() final del grafo.
        validate_errors = graph.validate()
        graph_valid = not validate_errors
        for ve in validate_errors:
            errors.append(GraphValidationError(
                message=ve, detail=ve,
            ))

        return BuildReport(
            nodes_built=len(built),
            graph_valid=graph_valid,
            errors=errors,
            topological_order=built,
            graph=graph,
        )

    # -- helpers internos ----------------------------------------------

    @staticmethod
    def _topological_order(
        nodes: list[ExtractedNode],
    ) -> tuple[list[str], list[str] | None]:
        """Kahn's algorithm.

        Devuelve (orden, None) si ordena correctamente.
        Devuelve ([], cycle_ids) si detecta ciclo — `cycle_ids` lista
        los nodos que no pudieron ordenarse (los que forman el ciclo y
        sus descendientes).
        """
        ids = {n.node_id for n in nodes}
        # Sólo contamos como dependencia las que apuntan a nodos del
        # documento; referencias a ids externos al documento no
        # aparecerían aquí (el extractor las habría marcado como
        # UnresolvedDependency).
        deps: dict[str, set[str]] = {
            n.node_id: {d for d in n.foundations if d in ids}
            for n in nodes
        }
        in_degree: dict[str, int] = {nid: len(deps[nid]) for nid in deps}
        # Conservamos el orden original de aparición para empates
        # — orden auditable y reproducible.
        order_index = {n.node_id: i for i, n in enumerate(nodes)}

        result: list[str] = []
        ready = sorted(
            [nid for nid, d in in_degree.items() if d == 0],
            key=lambda nid: order_index[nid],
        )

        # Construcción inversa: a → b significa "b depende de a".
        reverse_deps: dict[str, list[str]] = {nid: [] for nid in ids}
        for nid, foundations in deps.items():
            for f in foundations:
                reverse_deps[f].append(nid)

        while ready:
            nid = ready.pop(0)
            result.append(nid)
            for downstream in reverse_deps[nid]:
                in_degree[downstream] -= 1
                if in_degree[downstream] == 0:
                    # Inserción ordenada para mantener determinismo.
                    pos = 0
                    while pos < len(ready) and order_index[ready[pos]] < order_index[downstream]:
                        pos += 1
                    ready.insert(pos, downstream)

        if len(result) != len(ids):
            unresolved = [nid for nid in ids if nid not in result]
            return ([], unresolved)
        return (result, None)

    @staticmethod
    def _to_knowledge_node(
        node: ExtractedNode,
        spec: ProcedureSpec | None,
    ) -> KnowledgeNode:
        properties: dict = {
            "extracted_from_document": True,
            "section": node.section_title,
        }
        # Propagar properties extras declaradas por el extractor
        # (caso canónico exp_14: ALGORITHM con inputs/outputs en
        # properties para satisfacer el contrato de validate()).
        if node.extra_properties:
            properties.update(node.extra_properties)

        if node.procedure_name:
            properties["procedure_name"] = node.procedure_name
            if spec is None:
                properties["procedure_resolved"] = False
            else:
                properties["procedure_resolved"] = True

        # Si la firma se verificó, registramos compute desde el spec.
        # Si no hay spec, conservamos los inputs/outputs declarados
        # en el documento (necesario para nodos ALGORITHM, que pueden
        # no tener procedimiento registrado pero sí declarar I/O).
        compute = None
        inputs: list[str] = list(node.inputs)
        outputs: list[str] = list(node.outputs)
        if spec is not None:
            compute = spec.fn
            inputs = list(spec.inputs)
            outputs = list(spec.outputs)

        # Tipo del nodo: RELATION para ejecutables, axiomas, teoremas
        # y algoritmos (todos representan operaciones o relaciones
        # estructurales del dominio). Definiciones puras → CONCEPT.
        if compute is not None:
            kind = NodeKind.RELATION
        elif node.status.value in ("axiom", "theorem", "algorithm"):
            kind = NodeKind.RELATION
        else:
            kind = NodeKind.CONCEPT

        return KnowledgeNode(
            id=node.node_id,
            statement=node.statement,
            status=node.status,
            kind=kind,
            foundations=list(node.foundations),
            validity_conditions=list(node.conditions),
            compute=compute,
            inputs=inputs,
            outputs=outputs,
            rationale=(
                f"extraído automáticamente del documento "
                f"(sección «{node.section_title}»)."
            ),
            properties=properties,
        )
