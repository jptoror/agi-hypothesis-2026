"""EngineGateway — el motor verificable detrás de una interfaz estable.

Recibe una `StructuredQuery` (lo que el traductor extrajo del
lenguaje natural) y la resuelve con los especialistas de los
experimentos previos: Geometría (exp_01), Física (exp_03) y Álgebra
(exp_06), con delegación inter-dominio (exp_03) cuando la consulta
declara bindings.

Dos decisiones de diseño:

1. **Grafos nuevos por consulta.** Cada `solve()` construye copias
   de los grafos. Una hipótesis inyectada para una pregunta no
   contamina la siguiente — el benchmark mide preguntas
   independientes, no una sesión de aprendizaje.

2. **Guarda de precondiciones (hallazgo del exp_22).** Los nodos
   declaran condiciones de validez ('a ≠ 0', 'l >= 0', 'el triángulo
   debe ser rectángulo'), pero el razonador del exp_01 sólo usaba
   una heurística sobre el TIPO de figura: las condiciones numéricas
   nunca se evaluaban (0·x + 5 = 0 lanzaba ZeroDivisionError; un
   lado de -4 producía área 16) y Pitágoras se aplicaba a cualquier
   triángulo. El gateway envuelve cada `compute` con una guarda que
   evalúa las condiciones numéricas contra las entradas reales, y
   desactiva los nodos que exigen un triángulo rectángulo cuando el
   contexto no lo es. Una violación produce un gap declarado, no una
   respuesta.
"""
from __future__ import annotations

import copy
import dataclasses
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Optional

from experiment_01.knowledge_graph import (
    KnowledgeGraph,
    KnowledgeNode,
    build_geometry_2d_graph,
)
from experiment_01.specialist import DomainContext, GeometrySpecialist, Problem
from experiment_01.specialist.reasoning_step import ReasoningTrace
from experiment_03.inter_specialist_protocol import SpecialistRegistry
from experiment_03.orchestrator import CrossDomainOrchestrator
from experiment_03.specialists.geometry import GeometryAdapter
from experiment_03.specialists.physics import (
    PhysicsAdapter,
    PhysicsSpecialist,
    build_physics_graph,
)
from experiment_06.specialist_factory import SpecialistFactory

_ALGEBRA_DOC = (
    Path(__file__).resolve().parent.parent
    / "experiment_06" / "sample_documents" / "algebra_ch3.md"
)


@dataclass
class StructuredQuery:
    """Consulta estructurada — el contrato entre traductor y motor."""

    domain: str
    context_kind: str
    target: str
    known: dict[str, float]
    statement: str = ""
    # Delegación inter-dominio (exp_03): {"v": "l"} = "la velocidad es el lado".
    variable_bindings: dict[str, str] = field(default_factory=dict)
    # Tipo de contexto del especialista al que se delega (p. ej. "square").
    partner_context_kind: str = ""


@dataclass
class EngineResult:
    success: bool
    value: Optional[float]
    trace_node_ids: list[str]
    trace: Optional[ReasoningTrace]
    gap_text: Optional[str] = None
    missing_variable: Optional[str] = None
    precondition_violation: Optional[str] = None

    def render_trace(self) -> str:
        return self.trace.render() if self.trace is not None else "(sin traza)"


class PreconditionViolation(RuntimeError):
    def __init__(self, node_id: str, condition: str, values: dict) -> None:
        super().__init__(
            f"{node_id}: la condición '{condition}' no se cumple con {values}"
        )
        self.node_id = node_id
        self.condition = condition
        self.values = values


# ---------------------------------------------------------------------
# Guarda de precondiciones
# ---------------------------------------------------------------------

_NUMERIC_CONDITION = re.compile(
    r"^\s*([A-Za-z_][A-Za-z_0-9]*)\s*(>=|≥|<=|≤|!=|≠|>|<)\s*(-?\d+(?:\.\d+)?)\s*$"
)
_COMPARATORS: dict[str, Callable[[float, float], bool]] = {
    ">=": lambda a, b: a >= b, "≥": lambda a, b: a >= b,
    "<=": lambda a, b: a <= b, "≤": lambda a, b: a <= b,
    ">": lambda a, b: a > b, "<": lambda a, b: a < b,
    "!=": lambda a, b: a != b, "≠": lambda a, b: a != b,
}
_RIGHT_TRIANGLE_TERMS = ("rectángulo", "rectangulo", "right")


def parse_numeric_condition(text: str) -> Optional[tuple[str, str, float]]:
    """'a ≠ 0' → ('a', '≠', 0.0). Condiciones en prosa → None."""
    m = _NUMERIC_CONDITION.match(text)
    if not m:
        return None
    return m.group(1), m.group(2), float(m.group(3))


def _guarded(node: KnowledgeNode) -> KnowledgeNode:
    """Copia del nodo cuyo compute verifica las condiciones numéricas."""
    if not node.is_executable():
        return node
    checks = [
        (cond, parsed)
        for cond in node.validity_conditions
        if (parsed := parse_numeric_condition(cond)) is not None
    ]
    if not checks:
        return node
    original = node.compute

    def compute(values: dict) -> dict:
        for cond, (var, op, bound) in checks:
            if var in values and not _COMPARATORS[op](values[var], bound):
                raise PreconditionViolation(node.id, cond, {var: values[var]})
        return original(values)

    return dataclasses.replace(node, compute=compute)


def guarded_copy(graph: KnowledgeGraph, extra: Iterable[KnowledgeNode] = ()) -> KnowledgeGraph:
    out = KnowledgeGraph()
    for node in graph:
        out.add(_guarded(node))
    for node in extra:
        out.add(_guarded(node))
    return out


def requires_right_triangle(node: KnowledgeNode, context_kind: str) -> bool:
    """True si el nodo exige un triángulo rectángulo y el contexto no lo es."""
    if "right" in context_kind:
        return False
    return any(
        "triáng" in c.lower() or "triang" in c.lower()
        for c in node.validity_conditions
    ) and any(
        t in c.lower() for c in node.validity_conditions for t in _RIGHT_TRIANGLE_TERMS
    )


def collect_node_ids(trace: Optional[ReasoningTrace]) -> list[str]:
    """Ids de nodos de la traza, incluyendo las trazas delegadas."""
    if trace is None:
        return []
    ids: list[str] = []
    for step in trace.steps:
        ids.append(step.node_id)
        ids.extend(collect_node_ids(step.delegated_trace))
    return ids


# ---------------------------------------------------------------------
# Gateway
# ---------------------------------------------------------------------


class EngineGateway:
    DOMAINS = ("geometry", "physics", "algebra")

    def __init__(self) -> None:
        self._base_graphs: dict[str, KnowledgeGraph] = {
            "geometry": build_geometry_2d_graph(),
            "physics": build_physics_graph(),
        }
        factory = SpecialistFactory(
            registry=SpecialistRegistry(),
            implicit_figure_kind="linear_equation",
        )
        reg = factory.from_document(_ALGEBRA_DOC)
        if not reg.registered:
            raise RuntimeError(f"exp_22: no se pudo construir álgebra: {reg.errors}")
        self._algebra_template = reg.specialist
        self._base_graphs["algebra"] = reg.build_report.graph

    @property
    def graphs(self) -> dict[str, KnowledgeGraph]:
        return dict(self._base_graphs)

    def graph(self, domain: str) -> KnowledgeGraph:
        return self._base_graphs[domain]

    # -- API pública ---------------------------------------------------

    def solve(
        self,
        query: StructuredQuery,
        extra_nodes: Iterable[KnowledgeNode] = (),
    ) -> EngineResult:
        if query.domain not in self._base_graphs:
            return EngineResult(
                success=False, value=None, trace_node_ids=[], trace=None,
                gap_text=f"dominio desconocido: '{query.domain}'",
            )
        problem = Problem(
            statement=query.statement or f"obtener {query.target}",
            target=query.target,
            context=DomainContext(kind=query.context_kind, known=dict(query.known)),
            variable_bindings=dict(query.variable_bindings),
            delegation_hints=(
                {"figure_kind": query.partner_context_kind}
                if query.partner_context_kind else {}
            ),
        )
        try:
            if query.variable_bindings:
                result = self._solve_cross_domain(query, problem)
            else:
                specialist = self._specialist(query, list(extra_nodes))
                result = specialist.solve(problem)
        except PreconditionViolation as v:
            return EngineResult(
                success=False, value=None, trace_node_ids=[], trace=None,
                gap_text=f"precondición violada — {v}",
                precondition_violation=str(v),
            )
        except ZeroDivisionError as e:  # red de seguridad: condición no declarada
            return EngineResult(
                success=False, value=None, trace_node_ids=[], trace=None,
                gap_text=f"operación indefinida en el cómputo: {e}",
                precondition_violation=str(e),
            )

        if result.success:
            return EngineResult(
                success=True, value=result.value,
                trace_node_ids=collect_node_ids(result.trace), trace=result.trace,
            )
        gap = result.gap
        return EngineResult(
            success=False, value=None,
            trace_node_ids=collect_node_ids(result.trace), trace=result.trace,
            gap_text=gap.context if gap else "sin detalle",
            missing_variable=gap.missing_variable if gap else None,
        )

    # -- construcción de especialistas --------------------------------

    def _specialist(self, query: StructuredQuery, extra: list[KnowledgeNode]):
        graph = guarded_copy(self._base_graphs[query.domain], extra)
        disabled = {
            n.id for n in graph if requires_right_triangle(n, query.context_kind)
        }
        if query.domain == "geometry":
            return GeometrySpecialist(graph, disabled_nodes=disabled)
        if query.domain == "physics":
            return PhysicsSpecialist(graph)
        specialist = copy.copy(self._algebra_template)
        specialist.graph = graph
        specialist.disabled_nodes = set(disabled)
        specialist._renderer = None
        return specialist

    def _solve_cross_domain(self, query: StructuredQuery, problem: Problem):
        registry = SpecialistRegistry()
        registry.register(GeometryAdapter(guarded_copy(self._base_graphs["geometry"])))
        registry.register(PhysicsAdapter(guarded_copy(self._base_graphs["physics"])))
        orchestrator = CrossDomainOrchestrator(registry=registry, max_depth=5)
        return orchestrator.solve(problem, initiating_domain=query.domain).solve_result

