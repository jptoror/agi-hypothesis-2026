"""Orchestrator del experimento 03 — comunicación entre especialistas.

El orchestrator NO contiene conocimiento de ningún dominio. Sólo:

  1. Mantiene una registry de adapters.
  2. Recibe un problema y se lo asigna al especialista del dominio
     correspondiente (decisión inicial; input del usuario, no inferida).
  3. Construye un callback `delegate(request) -> response` que:
       - aplica los chequeos de ciclo y profundidad,
       - enruta vía la registry,
       - propaga la respuesta al especialista que delegó.
  4. Devuelve el resultado final con la traza completa (que ya incluye
     los delegated_steps con sub-trazas anidadas).

Uso:
    python -m experiment_03.orchestrator
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from experiment_01.specialist import (
    DomainContext,
    KnowledgeGap,
    Problem,
    ReasoningStep,
    SolveResult,
)

from .inter_specialist_protocol import (
    DelegationContext,
    GapRequest,
    GapResponse,
    ResponseStatus,
    SpecialistAdapter,
    SpecialistRegistry,
)
from .specialists.geometry import GeometryAdapter
from .specialists.physics import PhysicsAdapter, build_physics_graph

from experiment_01.knowledge_graph import build_geometry_2d_graph


@dataclass
class CrossDomainResult:
    problem: Problem
    initiating_domain: str
    solve_result: SolveResult
    delegation_history: list[GapRequest]

    def render(self) -> str:
        lines = [
            "=" * 72,
            "EXPERIMENTO 03 — RAZONAMIENTO CRUZADO ENTRE ESPECIALISTAS",
            "=" * 72,
            f"Problema: {self.problem.statement}",
            f"Dominio iniciador: {self.initiating_domain}",
            "",
            "── TRAZA DE RAZONAMIENTO ──",
            self.solve_result.trace.render() or "(sin pasos)",
            "",
            "── HISTORIAL DE DELEGACIONES ──",
        ]
        if not self.delegation_history:
            lines.append("(ninguna delegación)")
        else:
            for i, r in enumerate(self.delegation_history, 1):
                lines.append(f"  {i}. {r.render()}")
        lines.append("")
        if self.solve_result.success:
            lines.append(
                f"RESULTADO: {self.problem.target} = {self.solve_result.value}"
            )
        else:
            lines.append("RESULTADO: no resuelto")
            if self.solve_result.gap:
                lines.append(self.solve_result.gap.render())
        return "\n".join(lines)


class CrossDomainOrchestrator:
    """Orquestador inter-dominio.

    No conoce nodos ni axiomas — sólo enruta consultas. Esa es la
    propiedad central que el experimento 03 demuestra: dos sistemas
    de razonamiento independientes pueden colaborar a través de un
    canal que no posee conocimiento propio.
    """

    def __init__(
        self,
        registry: SpecialistRegistry,
        max_depth: int = 5,
        on_solve_complete: Optional[
            Callable[[Problem, "CrossDomainResult"], None]
        ] = None,
    ) -> None:
        self.registry = registry
        self.max_depth = max_depth
        # Hook opcional invocado al final de cada solve(). Recibe el
        # problema y el CrossDomainResult. El orchestrator no sabe ni
        # le importa qué hace el observador — preserva la separación.
        self.on_solve_complete = on_solve_complete

    def solve(
        self,
        problem: Problem,
        initiating_domain: str,
    ) -> CrossDomainResult:
        initiator: SpecialistAdapter = self.registry.get(initiating_domain)
        ctx = DelegationContext(max_depth=self.max_depth)

        def delegate(request: GapRequest) -> GapResponse:
            # Binding ontológico declarado en el problema. Si la
            # variable pedida (p. ej. 'v') equivale a otra (p. ej. 'l')
            # por el enunciado, el orchestrator:
            #   1. emite un binding_step para la traza principal del
            #      requester — paso explícito, NO silencioso;
            #   2. rescribe el target_variable hacia 'l' para el resto
            #      del enrutado;
            #   3. al recibir la respuesta, reetiqueta el valor como
            #      'v' antes de devolvérselo al requester.
            binding_step: ReasoningStep | None = None
            effective_target = request.target_variable
            src_name = None
            if effective_target in problem.variable_bindings:
                src_name = effective_target
                dst_name = problem.variable_bindings[src_name]
                binding_step = ReasoningStep(
                    index=0,  # el especialista reindexa al insertar
                    node_id=f"binding:{src_name}→{dst_name}",
                    node_statement=(
                        f"equivalencia declarada en el problema: "
                        f"{src_name} = {dst_name}"
                    ),
                    purpose="aplicar binding ontológico del enunciado",
                    inputs={},
                    outputs={},
                    rationale=(
                        f"el enunciado declara {src_name} = {dst_name} — "
                        f"vínculo ontológico entre dominios, no inferido "
                        f"por ningún especialista."
                    ),
                )
                effective_target = dst_name

            # Fusionamos el contexto del requester con las pistas
            # explícitas del enunciado. Las hints SOBREESCRIBEN al
            # contexto del requester porque son la fuente de verdad
            # ontológica (p. ej. el requester puede tener un
            # `figure_kind="physics.object"` técnico, mientras que el
            # enunciado declara `figure_kind="square"` — la pista del
            # enunciado gana).
            merged_context = dict(request.domain_context)
            merged_context.update(problem.delegation_hints)

            # El especialista emite el request con depth=0; el
            # orchestrator inyecta la profundidad real basada en su
            # contexto activo. Esto preserva el principio: el
            # especialista no necesita conocer el estado global.
            adjusted = GapRequest(
                requester=request.requester,
                target_variable=effective_target,
                domain_context=merged_context,
                rationale=request.rationale,
                depth=ctx.current_depth + 1,
                request_id=request.request_id,
            )

            # (5) Fatiga cognitiva.
            if ctx.exceeds_depth(adjusted):
                return GapResponse(
                    request_id=adjusted.request_id,
                    responder="orchestrator",
                    status=ResponseStatus.DELEGATION_DEPTH_EXCEEDED,
                    failure=KnowledgeGap(
                        missing_variable=adjusted.target_variable,
                        context=(
                            f"profundidad de delegación {adjusted.depth} "
                            f"supera max_depth={ctx.max_depth}."
                        ),
                    ),
                )

            # (4) Ciclo.
            if ctx.is_cycle(adjusted):
                return GapResponse(
                    request_id=adjusted.request_id,
                    responder="orchestrator",
                    status=ResponseStatus.CYCLE_DETECTED,
                    failure=KnowledgeGap(
                        missing_variable=adjusted.target_variable,
                        context=(
                            f"ciclo: ({adjusted.requester}, "
                            f"{adjusted.target_variable}) ya estaba activo."
                        ),
                    ),
                )

            # (2) Enrutado por la registry — ningún conocimiento de dominio aquí.
            responder = self.registry.find_for(adjusted)
            if responder is None:
                return GapResponse(
                    request_id=adjusted.request_id,
                    responder="orchestrator",
                    status=ResponseStatus.DOMAIN_MISMATCH,
                    failure=KnowledgeGap(
                        missing_variable=adjusted.target_variable,
                        context=(
                            f"ningún especialista registrado produce "
                            f"'{adjusted.target_variable}'."
                        ),
                    ),
                )

            # No nos auto-delegamos: si el único candidato es el propio
            # iniciador, devolvemos DOMAIN_MISMATCH para forzar un gap
            # local en vez de un loop trivial.
            if responder.name == adjusted.requester:
                return GapResponse(
                    request_id=adjusted.request_id,
                    responder="orchestrator",
                    status=ResponseStatus.DOMAIN_MISMATCH,
                    failure=KnowledgeGap(
                        missing_variable=adjusted.target_variable,
                        context=(
                            f"el único productor disponible es el propio "
                            f"requester '{adjusted.requester}'."
                        ),
                    ),
                )

            with ctx.track(adjusted):
                # Propagamos el mismo callback `delegate`: si el
                # responder necesita a su vez consultar a otro
                # especialista, volverá al orchestrator y los checks
                # de ciclo/depth se aplicarán uniformemente.
                response = responder.handle(adjusted, delegate=delegate)

            # Si hubo binding: reetiquetar el valor devuelto y adjuntar
            # el binding_step para que aparezca en la traza principal.
            if (
                binding_step is not None
                and src_name is not None
                and response.status == ResponseStatus.RESOLVED
                and response.value
            ):
                effective_dst = effective_target
                if effective_dst in response.value:
                    relabeled = dict(response.value)
                    relabeled[src_name] = relabeled.pop(effective_dst)
                    response = GapResponse(
                        request_id=response.request_id,
                        responder=response.responder,
                        status=response.status,
                        value=relabeled,
                        trace=response.trace,
                        failure=response.failure,
                        pre_steps=[binding_step] + (response.pre_steps or []),
                    )
            return response

        result = initiator.specialist.solve(problem, delegate=delegate)
        cross = CrossDomainResult(
            problem=problem,
            initiating_domain=initiating_domain,
            solve_result=result,
            delegation_history=list(ctx.history),
        )
        if self.on_solve_complete is not None:
            # Errores en el observador NO deben tumbar la resolución.
            # Los registramos en stderr y seguimos.
            try:
                self.on_solve_complete(problem, cross)
            except Exception as e:  # noqa: BLE001
                import sys
                print(
                    f"[orchestrator] hook on_solve_complete falló: {e!r}",
                    file=sys.stderr,
                )
        return cross


# ---------------------------------------------------------------------
# Demo del problema canónico del experimento 03.
# ---------------------------------------------------------------------

def main() -> None:
    geometry_graph = build_geometry_2d_graph()
    physics_graph = build_physics_graph()

    registry = SpecialistRegistry()
    registry.register(GeometryAdapter(geometry_graph))
    registry.register(PhysicsAdapter(physics_graph))

    orch = CrossDomainOrchestrator(registry=registry, max_depth=5)

    # Problema canónico del enunciado:
    # "¿Cuánta energía cinética tiene un objeto de masa 2kg
    #  moviéndose a la velocidad igual al lado de un cuadrado
    #  de diagonal 8?"
    #
    # El requester (Física) NO conoce que la velocidad procede del
    # lado de un cuadrado. Sólo sabe que necesita 'v'. La pista de
    # 'figura cuadrada con diagonal 8' viaja en `domain_context`
    # como contexto que el responder puede usar — y al construir
    # el problema le pasamos esos hints para que estén disponibles.
    problem = Problem(
        statement=(
            "¿Cuánta energía cinética tiene un objeto de masa 2 kg "
            "moviéndose a la velocidad igual al lado de un cuadrado "
            "de diagonal 8?"
        ),
        target="Ec",
        context=DomainContext(
            kind="physics.object",
            known={
                "m": 2.0,
                # Pista geométrica que Física no entiende pero que
                # transporta para que Geometría pueda usarla cuando
                # reciba la delegación.
                "d": 8.0,
            },
        ),
        # Vínculo ontológico del enunciado: 'velocidad igual al lado'.
        # Es conocimiento del enunciado, no de Física ni de Geometría.
        variable_bindings={"v": "l"},
        # Pista del enunciado para el especialista consultado: la figura
        # es un cuadrado. Física no sabe esto (no modela figuras);
        # Geometría sí lo necesita para aplicar sus teoremas.
        delegation_hints={"figure_kind": "square"},
    )

    result = orch.solve(problem, initiating_domain="physics")
    print(result.render())


if __name__ == "__main__":
    main()
