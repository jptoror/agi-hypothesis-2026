"""Orquestador del experimento 04 — emergencia de subdominios.

Compone los cuatro componentes construidos en este experimento:

    CollaborationMonitor  →  PatternDetector  →  SubdomainSynthesizer
                                                         │
                                                         ▼
                                                 SubdomainAdapter
                                                 (se registra)

Cada solve():
  1. Imprime qué intenta (transparencia del mecanismo de preferencia).
  2. Prueba cada subdominio emergente; si alguno resuelve, se acepta.
  3. Si ninguno, cae al CrossDomainOrchestrator del exp_03.
  4. Tras resolver, el monitor observa el resultado.
  5. El detector revisa si hay patrón nuevo listo.
  6. Si lo hay (y no tiene subdominio ya sintetizado), el
     sintetizador construye el subgrafo y se registra el adapter.

El orchestrator no tiene ningún nodo de conocimiento. Sólo compone.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from experiment_01.knowledge_graph import KnowledgeGraph
from experiment_01.specialist import (
    DomainContext,
    Problem,
    SolveResult,
)

from experiment_03.inter_specialist_protocol import (
    SpecialistRegistry,
)
from experiment_03.orchestrator import CrossDomainOrchestrator, CrossDomainResult
from experiment_03.specialists.geometry import GeometryAdapter
from experiment_03.specialists.physics import PhysicsAdapter, build_physics_graph

from experiment_04.collaboration_monitor import CollaborationMonitor
from experiment_04.pattern_detector import Pattern, PatternDetector
from experiment_04.subdomain_specialist import SubdomainAdapter
from experiment_04.subdomain_synthesizer import SubdomainSynthesizer, SynthesisResult


@dataclass
class EmergentSolveReport:
    problem: Problem
    route: str                           # "subdomain:<name>" | "cross_domain" | "unresolved"
    solved_by: Optional[str]             # nombre del solver que tuvo éxito
    value: Optional[float]
    success: bool
    attempts: list[str] = field(default_factory=list)  # por orden, con resultado
    cross_result: Optional[CrossDomainResult] = None
    synthesized: Optional[SynthesisResult] = None       # si se sintetizó algo nuevo

    def render(self) -> str:
        lines = [
            f"Problema: {self.problem.statement}",
            f"  target: {self.problem.target}  |  figure: {self.problem.context.kind}",
            f"  variable_bindings: {self.problem.variable_bindings}",
            f"  delegation_hints: {self.problem.delegation_hints}",
            "",
            "Intentos:",
        ]
        for a in self.attempts:
            lines.append(f"  · {a}")
        lines.append("")
        if self.success:
            lines.append(f"RESULTADO: {self.problem.target} = {self.value} "
                         f"[ruta: {self.route}]")
        else:
            lines.append("RESULTADO: no resuelto")
        if self.synthesized is not None:
            lines.append("")
            lines.append("-- SÍNTESIS TRAS ESTE PROBLEMA --")
            lines.append(self.synthesized.render())
        return "\n".join(lines)


class EmergentOrchestrator:
    def __init__(
        self,
        source_graphs: dict[str, KnowledgeGraph],
        min_pattern_count: int = 3,
    ) -> None:
        self.source_graphs = source_graphs
        self.monitor = CollaborationMonitor()
        self.detector = PatternDetector(
            monitor=self.monitor, min_count=min_pattern_count
        )
        self.synthesizer = SubdomainSynthesizer(source_graphs=source_graphs)

        # Registry base: los especialistas originales.
        self.registry = SpecialistRegistry()
        self.registry.register(GeometryAdapter(source_graphs["geometry"]))
        self.registry.register(PhysicsAdapter(source_graphs["physics"]))

        # Cross-domain orchestrator (fallback).
        self.cross_orch = CrossDomainOrchestrator(
            registry=self.registry, max_depth=5,
            on_solve_complete=lambda p, r: self.monitor.observe(
                p, r, problem_id=self._pid(p)
            ),
        )

        # Subdominios emergentes sintetizados (nombre → adapter).
        self.emergent_adapters: dict[str, SubdomainAdapter] = {}
        # Signatures ya sintetizadas — evita re-sintetizar.
        self._synthesized_signatures: set[frozenset] = set()

    # -- API pública ---------------------------------------------------

    def solve(
        self,
        problem: Problem,
        initiating_domain: str,
        problem_id: str | None = None,
    ) -> EmergentSolveReport:
        attempts: list[str] = []

        # 1) Probar subdominios emergentes — preferencia explícita.
        for name, adapter in self.emergent_adapters.items():
            attempts.append(f"intentando subdominio {name}…")
            result = self._try_emergent(adapter, problem)
            if result is not None and result.success:
                attempts.append(f"resuelto por subdominio {name} ✓")
                # Aun así intentamos sintetizar en caso de que se hayan
                # generado registros nuevos por otra vía; aquí no hay.
                return EmergentSolveReport(
                    problem=problem,
                    route=f"subdomain:{name}",
                    solved_by=name,
                    value=result.value,
                    success=True,
                    attempts=attempts,
                )
            attempts.append(
                f"subdominio {name} no puede resolver → probando siguiente"
            )

        # 2) Fallback al CrossDomainOrchestrator.
        attempts.append("cayendo a flujo inter-dominio (physics+geometry)…")
        cross = self.cross_orch.solve(
            problem, initiating_domain=initiating_domain
        )
        ok = cross.solve_result.success
        if ok:
            attempts.append("resuelto por flujo inter-dominio ✓")
        else:
            attempts.append("flujo inter-dominio falló")

        # 3) Post-solve: detectar nuevos patrones y sintetizar.
        synthesized_now = self._maybe_synthesize()

        return EmergentSolveReport(
            problem=problem,
            route="cross_domain" if ok else "unresolved",
            solved_by="cross_domain" if ok else None,
            value=cross.solve_result.value if ok else None,
            success=ok,
            attempts=attempts,
            cross_result=cross,
            synthesized=synthesized_now,
        )

    # -- internos ------------------------------------------------------

    @staticmethod
    def _pid(problem: Problem) -> str:
        stmt = problem.statement
        # Si el enunciado empieza con "[ID]", usamos ese ID.
        if stmt.startswith("[") and "]" in stmt:
            return stmt[1:stmt.index("]")]
        return stmt[:48]

    def _try_emergent(
        self,
        adapter: SubdomainAdapter,
        problem: Problem,
    ) -> Optional[SolveResult]:
        """Ejecuta el especialista del subdominio directamente sobre el
        problema. Si su `output_variables` no incluye el target, no lo
        intentamos — evita trabajo inútil.
        """
        if problem.target not in adapter.output_variables:
            return None
        return adapter.specialist.solve(problem)

    def _maybe_synthesize(self) -> Optional[SynthesisResult]:
        """Revisa patrones ready que todavía no hayan sido sintetizados
        y genera el adapter del subdominio emergente.
        """
        for pattern in self.detector.detect_ready():
            if pattern.signature in self._synthesized_signatures:
                continue
            self._synthesized_signatures.add(pattern.signature)
            result = self.synthesizer.synthesize(pattern)

            # Determinar implicit_figure_kind desde los hints del patrón.
            sample = pattern.sample_record
            implicit_kind = None
            if sample is not None:
                implicit_kind = sample.delegation_hints.get("figure_kind")

            # Términos de dominio para el subdominio emergente. Como
            # los subdominios del exp_04 mezclan grafos de geometría
            # y física, declaramos los términos geométricos que el
            # verificador necesita para distinguir teoremas aplicables
            # (p. ej. rechazar 'thm.square.*' para un triángulo).
            # Esta lista es decisión del orchestrator del exp_04 — no
            # vive hardcoded en el SubdomainSpecialist.
            adapter = SubdomainAdapter(
                graph=result.subgraph,
                domain=result.specialist_name,
                implicit_figure_kind=implicit_kind,
                # Grupos de sinónimos: cada lista interna agrupa los
                # nombres del MISMO concepto en distintos idiomas. El
                # verificador del subdominio rechaza una condición si
                # menciona algún término de un grupo Y ningún término
                # de ese mismo grupo aparece en el kind del problema.
                domain_terms=[
                    ["square", "cuadrado"],
                    ["triangle", "triángulo", "triangulo"],
                    ["rectángulo", "rectangulo"],
                    ["quadrilateral", "cuadrilátero", "cuadrilatero"],
                ],
            )
            self.emergent_adapters[result.specialist_name] = adapter
            # Lo registramos también globalmente en la registry compartida
            # para que el flujo inter-dominio pueda considerarlo en
            # futuros enrutados (coexistencia con delegación normal).
            if not any(a.name == adapter.name for a in self.registry.all()):
                self.registry.register(adapter)
            return result
        return None


# ---------------------------------------------------------------------
# Demo canónico del experimento 04.
# ---------------------------------------------------------------------

def main() -> None:
    from experiment_01.knowledge_graph import build_geometry_2d_graph

    geometry_graph = build_geometry_2d_graph()
    physics_graph = build_physics_graph()
    orch = EmergentOrchestrator(
        source_graphs={"geometry": geometry_graph, "physics": physics_graph},
        min_pattern_count=3,
    )

    def p(pid: str, m: float, d: float, bindings=None, hints=None) -> Problem:
        return Problem(
            statement=f"[{pid}] Ec con m={m}, cuadrado de diagonal {d}",
            target="Ec",
            context=DomainContext(kind="physics.object", known={"m": m, "d": d}),
            variable_bindings=bindings if bindings is not None else {"v": "l"},
            delegation_hints=hints if hints is not None else {"figure_kind": "square"},
        )

    problems = [
        p("P1", m=2.0, d=8.0),
        p("P2", m=1.0, d=10.0),
        p("P3", m=3.0, d=6.0),
        # P4: problema nuevo SIN bindings ni hints — el conocimiento
        # consolidado en el subdominio debería permitir resolverlo.
        Problem(
            statement="[P4] Ec con m=4, cuadrado de diagonal 6 (sin binding declarado)",
            target="Ec",
            context=DomainContext(kind="square", known={"m": 4.0, "d": 6.0}),
            variable_bindings={},
            delegation_hints={},
        ),
    ]

    summary: list[tuple[str, Optional[float], str, dict]] = []
    for prob in problems:
        print("=" * 72)
        report = orch.solve(prob, initiating_domain="physics")
        print(report.render())
        print()
        summary.append((
            orch._pid(prob),
            report.value,
            report.route,
            dict(prob.variable_bindings),
        ))

    print("=" * 72)
    print("NARRATIVA COMPLETA")
    print("=" * 72)
    for pid, val, route, vb in summary:
        v = f"{val:.6f}" if val is not None else "None"
        print(f"  {pid}: Ec={v}  [{route}]  variable_bindings={vb}")


if __name__ == "__main__":
    main()
