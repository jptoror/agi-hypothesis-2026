"""SystemRunner — invoca al especialista correspondiente por pregunta.

Reutiliza los factories de los experimentos previos:
  - SpecialistFactory del exp_06 para álgebra (linear_equation).
  - StackSpecialistFactory del exp_09 para pilas (anclado al grafo
    base de complejidad).

Devuelve una proyección uniforme (`SystemAnswer`) que el Benchmark
consume sin saber qué especialista respondió. Las preguntas
declarativas (categoría B sobre álgebra/pilas, A2 sobre pilas) NO
se invocan vía `Specialist.solve(...)` porque no hay un Problem
ejecutable — se inspecciona el grafo directamente.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from experiment_01.specialist import DomainContext, Problem
from experiment_03.inter_specialist_protocol import SpecialistRegistry
from experiment_06.specialist_factory import SpecialistFactory
from experiment_09.specialist_factory import StackSpecialistFactory

from .question import BenchmarkQuestion, SystemTarget


@dataclass
class SystemAnswer:
    """Proyección uniforme de la respuesta del sistema."""

    answer_text: str
    trace_node_ids: list[str] | None
    gap_text: str | None              # texto del KnowledgeGap si lo hubo
    raw_value: float | None = None    # valor numérico si aplica
    raw_text: str | None = None       # respuesta textual si aplica
    extras: dict = field(default_factory=dict)


class SystemRunner:
    def __init__(self) -> None:
        # Especialista de álgebra del exp_06.
        algebra_doc = (
            Path(__file__).resolve().parent.parent.parent
            / "experiment_06" / "sample_documents" / "algebra_ch3.md"
        )
        registry = SpecialistRegistry()
        algebra_factory = SpecialistFactory(
            registry=registry,
            implicit_figure_kind="linear_equation",
        )
        algebra_reg = algebra_factory.from_document(algebra_doc)
        if not algebra_reg.registered:
            raise RuntimeError(
                f"benchmark: no se pudo registrar álgebra: {algebra_reg.errors}"
            )
        self.algebra_specialist = algebra_reg.specialist
        self.algebra_graph = algebra_reg.build_report.graph

        # Especialista de pilas del exp_09.
        stack_factory = StackSpecialistFactory()
        stack_reg = stack_factory.build()
        if not stack_reg.registered:
            raise RuntimeError(
                f"benchmark: no se pudo registrar pilas: {stack_reg.errors}"
            )
        self.stack_specialist = stack_reg.specialist
        self.stack_graph = stack_reg.graph

    # -- API pública ---------------------------------------------------

    def run(self, question: BenchmarkQuestion) -> SystemAnswer:
        if question.target == SystemTarget.ALGEBRA:
            return self._run_algebra(question)
        if question.target == SystemTarget.STACK:
            return self._run_stack(question)
        raise ValueError(f"target no soportado: {question.target!r}")

    # -- runners por especialista --------------------------------------

    def _run_algebra(self, q: BenchmarkQuestion) -> SystemAnswer:
        """Para álgebra: construir Problem y delegar al especialista.

        - A1, C1: Problem con a y b → resuelve.
        - B1: Problem con coeficientes cuadráticos (a, b_quadratic,
          c_quadratic). El especialista no tiene productor para 'x'
          a partir de esas variables → declarará gap.
        """
        problem = Problem(
            statement=q.natural_language,
            target=q.algebra_target or "x",
            context=DomainContext(
                kind="linear_equation",
                known=dict(q.algebra_inputs or {}),
            ),
        )
        result = self.algebra_specialist.solve(problem)
        if result.success:
            return SystemAnswer(
                answer_text=f"{q.algebra_target} = {result.value}",
                trace_node_ids=[s.node_id for s in result.trace.steps],
                gap_text=None,
                raw_value=result.value,
            )
        gap_text = result.gap.context if result.gap is not None else "(sin detalle)"
        return SystemAnswer(
            answer_text=f"(sin respuesta) gap: {gap_text}",
            trace_node_ids=[s.node_id for s in result.trace.steps] or None,
            gap_text=gap_text,
        )

    def _run_stack(self, q: BenchmarkQuestion) -> SystemAnswer:
        """Para pilas: inspección declarativa.

        El especialista de pilas no tiene `compute` ejecutables; el
        razonamiento es por inspección de fundamentos (cf. FINDINGS
        exp_09 #04). El runner busca el nodo declarado en
        `stack_node_id` y extrae su clase de complejidad de los
        foundations.
        """
        node_id = q.stack_node_id or ""
        if not self.stack_graph.has(node_id):
            # A2 con id válido NO entra aquí; B2 sí (id inventado).
            return SystemAnswer(
                answer_text=f"(sin respuesta) gap: nodo '{node_id}' no existe en el grafo de pilas",
                trace_node_ids=None,
                gap_text=(
                    f"el grafo del especialista de pilas no contiene "
                    f"'{node_id}' — operación fuera del dominio."
                ),
            )

        node = self.stack_graph.get(node_id)
        # Buscar la clase de complejidad declarada como fundamento.
        complexity_id = next(
            (f for f in node.foundations if f.startswith("def.complexity.")),
            None,
        )
        if complexity_id is None:
            return SystemAnswer(
                answer_text=(
                    f"(sin respuesta) el nodo '{node_id}' no declara "
                    f"complejidad como fundamento"
                ),
                trace_node_ids=[node_id],
                gap_text=(
                    f"'{node_id}' existe pero no referencia ningún "
                    f"def.complexity.* en sus foundations."
                ),
            )

        complexity_node = self.stack_graph.get(complexity_id)
        symbol = (complexity_node.properties or {}).get("symbol", complexity_id)
        return SystemAnswer(
            answer_text=symbol,
            # La "traza" para inspección declarativa es la cadena
            # de fundamentos consultados: el teorema y la clase de
            # complejidad referenciada.
            trace_node_ids=[node_id, complexity_id],
            gap_text=None,
            raw_text=symbol,
            extras={"complexity_node_id": complexity_id},
        )
