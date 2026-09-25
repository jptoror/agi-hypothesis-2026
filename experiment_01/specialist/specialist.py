from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable, Optional

from ..knowledge_graph import KnowledgeGraph, KnowledgeNode
from .problem import Problem
from .reasoning_step import ReasoningStep, ReasoningTrace

if TYPE_CHECKING:  # evita import circular experiment_03 ↔ experiment_01
    from experiment_03.inter_specialist_protocol import GapRequest, GapResponse

    DelegateFn = Callable[["GapRequest"], "GapResponse"]
else:
    DelegateFn = Callable


@dataclass
class KnowledgeGap:
    """Indica qué pieza de conocimiento faltó para completar la derivación.

    `missing_variable` es la variable que el especialista no pudo producir
    con ningún nodo ejecutable del grafo. `context` describe qué se intentó
    antes de darse por vencido.
    """

    missing_variable: str
    context: str
    attempted_nodes: list[str] = field(default_factory=list)
    chain_at_failure: list[str] = field(default_factory=list)

    def render(self) -> str:
        lines = [
            "GAP DE CONOCIMIENTO",
            f"  variable no derivable: {self.missing_variable}",
            f"  contexto: {self.context}",
        ]
        if self.attempted_nodes:
            lines.append(f"  nodos considerados: {', '.join(self.attempted_nodes)}")
        if self.chain_at_failure:
            lines.append(f"  cadena de derivación activa: {' → '.join(self.chain_at_failure)}")
        return "\n".join(lines)


@dataclass
class SolveResult:
    """Resultado de un intento de resolución."""

    problem: Problem
    success: bool
    value: Optional[float]
    trace: ReasoningTrace
    gap: Optional[KnowledgeGap]
    relevant_nodes: list[str]

    def render(self) -> str:
        header = [
            f"Problema: {self.problem.statement}",
            f"Objetivo: resolver '{self.problem.target}' para {self.problem.context.describe()}",
            f"Nodos relevantes considerados: {', '.join(self.relevant_nodes) or '(ninguno)'}",
            "",
        ]
        body = [self.trace.render()] if self.trace.steps else []
        if self.success:
            footer = ["", f"RESULTADO: {self.problem.target} = {self.value}"]
        else:
            footer = ["", self.gap.render() if self.gap else "RESULTADO: no resuelto"]
        return "\n".join(header + body + footer)


class GeometrySpecialist:
    """Agente especialista en geometría 2D.

    Razona por *backward chaining* sobre el grafo: dada la variable objetivo,
    busca un nodo ejecutable que la produzca, resuelve recursivamente sus
    entradas y verifica sus condiciones de validez contra la figura. No
    adivina y no interpola — si no encuentra una derivación, reporta el gap.

    Cuando se le pasa un `delegate` en `solve()`, el especialista puede
    pedir variables que su grafo no produce a OTRO especialista vía el
    protocolo inter-dominio. El callback `delegate` es opcional — sin él
    el comportamiento es el original del exp_01/02.
    """

    #: Nombre del dominio — aparece en el GapRequest.requester cuando
    #: el especialista delega. Subclases (p. ej. PhysicsSpecialist) lo
    #: sobreescriben.
    domain: str = "geometry"

    #: Conectores rotativos para `express()` (exp_18). Subclases pueden
    #: sobrescribir si quieren voz distinta. None → defaults del
    #: ExpressionRenderer (`Luego, ` / `A continuación, ` / `Después, `).
    trace_connectors: Optional[list[str]] = None

    def __init__(
        self,
        graph: KnowledgeGraph,
        disabled_nodes: Optional[set[str]] = None,
    ) -> None:
        self.graph = graph
        # Nodos que el orchestrator puede silenciar para probar gaps o
        # forzar derivaciones desde primeros principios.
        self.disabled_nodes: set[str] = set(disabled_nodes or ())
        # Renderer perezoso (exp_18). Se construye al primer acceso
        # vía la property `renderer` para no acoplar el módulo del
        # exp_01 al exp_18 cuando el caller no usa expresión.
        self._renderer = None

    # -- Verbalización (exp_18) ---------------------------------------

    @property
    def renderer(self):
        """`ExpressionRenderer` ligado a este grafo.

        Construcción lazy: la primera llamada importa el módulo del
        exp_18 y crea la instancia; las siguientes la reusan. Eso
        permite que cualquier especialista que herede de esta clase
        herede también la capacidad de verbalizar sin acoplamiento
        en tiempo de import."""
        if self._renderer is None:
            from experiment_18.expression import ExpressionRenderer
            self._renderer = ExpressionRenderer(self.graph)
        return self._renderer

    def express(self, trace) -> str:
        """Verbaliza una `ReasoningTrace` usando las plantillas
        `**Expresión:**` declaradas en los nodos del grafo. Nodos
        sin plantilla caen al `statement` (compatibilidad total)."""
        return self.renderer.render_trace(
            trace, connectors=self.trace_connectors,
        )

    # -- API pública ----------------------------------------------------

    def solve(
        self,
        problem: Problem,
        delegate: Optional[DelegateFn] = None,
    ) -> SolveResult:
        trace = ReasoningTrace()
        # Estado de variables conocidas — arranca con las de la figura.
        known: dict[str, float] = dict(problem.context.known)
        relevant = self._scan_relevant_nodes(problem)

        gap = self._derive(
            variable=problem.target,
            problem=problem,
            known=known,
            trace=trace,
            chain=[],
            attempted_log=[],
            delegate=delegate,
        )

        if gap is None:
            return SolveResult(
                problem=problem,
                success=True,
                value=known[problem.target],
                trace=trace,
                gap=None,
                relevant_nodes=[n.id for n in relevant],
            )

        return SolveResult(
            problem=problem,
            success=False,
            value=None,
            trace=trace,
            gap=gap,
            relevant_nodes=[n.id for n in relevant],
        )

    # -- búsqueda de contexto ------------------------------------------

    def _scan_relevant_nodes(self, problem: Problem) -> list[KnowledgeNode]:
        """Nodos plausiblemente útiles para este problema:
        - nodos ejecutables cuya salida es la variable objetivo
        - nodos cuyo id menciona el tipo de figura del problema
        - fundamentos transitivos de los anteriores

        Esto es sólo para trazabilidad — el razonamiento real se hace por
        backward chaining, no por este filtro.
        """
        kind = problem.context.kind.lower()
        relevant: dict[str, KnowledgeNode] = {}

        seeds: list[KnowledgeNode] = []
        seeds.extend(self.graph.find_relations_producing(problem.target))
        for n in self.graph:
            if kind in n.id.lower():
                seeds.append(n)

        for seed in seeds:
            relevant[seed.id] = seed
            for dep in self.graph.transitive_foundations(seed.id):
                relevant[dep.id] = dep
        return list(relevant.values())

    # -- núcleo de razonamiento ----------------------------------------

    def _derive(
        self,
        variable: str,
        problem: Problem,
        known: dict[str, float],
        trace: ReasoningTrace,
        chain: list[str],
        attempted_log: list[str],
        delegate: Optional[DelegateFn] = None,
    ) -> Optional[KnowledgeGap]:
        """Deriva `variable` por backward chaining. Devuelve None si lo logra,
        o un KnowledgeGap describiendo por qué falló.
        """
        if variable in known:
            return None

        if variable in chain:
            return KnowledgeGap(
                missing_variable=variable,
                context=f"ciclo al intentar derivar '{variable}'",
                chain_at_failure=list(chain),
            )

        candidates = [
            n
            for n in self.graph.find_relations_producing(variable)
            if n.id not in self.disabled_nodes
        ]
        if not candidates:
            # Delegación inter-dominio: si nadie en nuestro grafo produce
            # esta variable y hay un canal delegate disponible, preguntamos
            # a otro especialista antes de declarar gap. El orchestrator
            # que ha creado `delegate` se encarga del depth real, de los
            # checks de ciclo y del enrutado.
            if delegate is not None:
                delegated_gap = self._try_delegate(
                    variable=variable,
                    problem=problem,
                    known=known,
                    trace=trace,
                    delegate=delegate,
                )
                if delegated_gap is None:
                    return None
                # La delegación no consiguió el valor; propagamos el gap
                # que reportó el responder (o fabricamos uno local si no
                # hubo responder).
                return delegated_gap

            return KnowledgeGap(
                missing_variable=variable,
                context=(
                    f"ningún nodo del grafo produce '{variable}' como salida "
                    f"ejecutable"
                ),
                attempted_nodes=list(attempted_log),
                chain_at_failure=list(chain),
            )

        # Preferimos nodos cuyas entradas ya son conocidas (menos pasos).
        candidates.sort(key=lambda n: sum(1 for i in n.inputs if i not in known))

        last_gap: Optional[KnowledgeGap] = None
        for node in candidates:
            attempted_log.append(node.id)

            if not self._conditions_apply(node, problem):
                continue

            # Resolver entradas — recursivamente si hace falta.
            new_chain = chain + [variable]
            inputs_ok = True
            for inp in node.inputs:
                if inp in known:
                    continue
                sub_gap = self._derive(
                    variable=inp,
                    problem=problem,
                    known=known,
                    trace=trace,
                    chain=new_chain,
                    attempted_log=attempted_log,
                    delegate=delegate,
                )
                if sub_gap is not None:
                    last_gap = sub_gap
                    inputs_ok = False
                    break

            if not inputs_ok:
                continue

            # Ejecutar el nodo.
            inputs_snapshot = {k: known[k] for k in node.inputs}
            outputs = node.compute(inputs_snapshot)
            known.update(outputs)

            trace.add(ReasoningStep(
                index=len(trace.steps) + 1,
                node_id=node.id,
                node_statement=node.statement,
                purpose=f"derivar '{variable}' a partir de {', '.join(node.inputs) or '(sin entradas)'}",
                conditions_checked=list(node.validity_conditions),
                inputs=inputs_snapshot,
                outputs=dict(outputs),
                rationale=node.rationale,
            ))
            return None

        return last_gap or KnowledgeGap(
            missing_variable=variable,
            context=(
                f"los nodos que producen '{variable}' no son aplicables a "
                f"{problem.context.describe()}"
            ),
            attempted_nodes=list(attempted_log),
            chain_at_failure=list(chain),
        )

    # -- delegación inter-dominio --------------------------------------

    def _try_delegate(
        self,
        variable: str,
        problem: Problem,
        known: dict[str, float],
        trace: ReasoningTrace,
        delegate: DelegateFn,
    ) -> Optional[KnowledgeGap]:
        """Emite un GapRequest y procesa la GapResponse.

        Devuelve None si la delegación resolvió la variable (en cuyo caso
        `known` ya se actualizó y la traza recibió el delegated_step).
        Devuelve un KnowledgeGap si la respuesta fue no-RESOLVED —
        propagado hacia arriba para que el backward chaining lo trate
        como cualquier otro gap.

        El especialista NO conoce el protocolo en detalle; sólo usa las
        piezas públicas (GapRequest, GapResponse, ResponseStatus). El
        import es local para evitar dependencia circular.
        """
        from experiment_03.inter_specialist_protocol import (
            GapRequest,
            ResponseStatus,
        )

        request = GapRequest(
            requester=self.domain,
            target_variable=variable,
            domain_context={
                "figure_kind": problem.context.kind,
                "known": dict(known),
                "original_target": problem.target,
            },
            rationale=(
                f"{self.domain} necesita '{variable}' para resolver "
                f"'{problem.target}' en {problem.context.describe()}."
            ),
            # depth=0 desde el especialista; el orchestrator que ha
            # creado el callback inyecta la profundidad real sumándole
            # su propio nivel.
            depth=0,
        )

        response = delegate(request)

        if response.status == ResponseStatus.RESOLVED and response.value:
            known.update(response.value)
            # Pasos que el orchestrator pidió insertar en la traza
            # principal antes de registrar la delegación (p. ej. un
            # binding ontológico). Los reindexamos en orden.
            for pre in getattr(response, "pre_steps", []) or []:
                pre.index = len(trace.steps) + 1
                trace.add(pre)
            trace.add(ReasoningStep(
                index=len(trace.steps) + 1,
                node_id=f"delegated:{response.responder}:{','.join(response.value.keys())}",
                node_statement=(
                    f"(delegación a {response.responder} para obtener "
                    f"{', '.join(response.value.keys())})"
                ),
                purpose=(
                    f"{self.domain} delega la obtención de '{variable}' "
                    f"porque ningún nodo local la produce."
                ),
                inputs={},
                outputs=dict(response.value),
                rationale=request.rationale,
                delegated_trace=response.trace,
            ))
            return None

        # No resuelta — empaquetamos un KnowledgeGap que lleva el detalle
        # del responder si lo hubo, para que la traza superior lo propague
        # con contexto auditable.
        if response.failure is not None:
            ctx = (
                f"delegación a {response.responder} terminó en "
                f"{response.status.value}: {response.failure.context}"
            )
        else:
            ctx = (
                f"delegación para '{variable}' terminó en "
                f"{response.status.value} (sin detalle)"
            )
        return KnowledgeGap(
            missing_variable=variable,
            context=ctx,
        )

    def _conditions_apply(self, node: KnowledgeNode, problem: Problem) -> bool:
        """Heurística explícita: si alguna condición menciona un tipo de figura
        distinto al del problema, el nodo no aplica.

        Es deliberadamente simple y auditable — queremos que el gap se note
        cuando el grafo no tiene un nodo adecuado, no enmascararlo con un
        matcher laxo.
        """
        figure_kind = problem.context.kind.lower()
        # Términos de figura conocidos. Cada entrada mapea el slug
        # ASCII (que aparece en figure.kind) a la lista de palabras
        # que pueden aparecer en condiciones de validez en lenguaje
        # natural — incluyendo español, porque los statements del
        # grafo de Geometría están escritos en castellano.
        known_kinds: dict[str, list[str]] = {
            "square": ["square", "cuadrado"],
            "triangle": ["triangle", "triángulo", "triangulo"],
            "triangle.right": ["right", "rectángulo", "rectangulo"],
            "quadrilateral": ["quadrilateral", "cuadrilátero", "cuadrilatero"],
        }

        for cond in node.validity_conditions:
            cond_low = cond.lower()
            for kind, terms in known_kinds.items():
                short = kind.split(".")[-1]
                cond_mentions_kind = any(t in cond_low for t in terms)
                if cond_mentions_kind and short not in figure_kind:
                    # La condición exige una figura concreta distinta
                    # a la nuestra. Subtipos compatibles de triángulo
                    # se aceptan: cualquier 'triangle*' admite 'triangle'.
                    if kind.startswith("triangle") and "triangle" in figure_kind:
                        continue
                    return False
        return True
