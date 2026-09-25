"""Demo del SpecialistFactory — la evidencia central del experimento 06.

Pipeline completo: documento → especialista registrado → problema resuelto.

Uso:
    python -m experiment_06.specialist_factory.demo
"""
from __future__ import annotations

from pathlib import Path

from experiment_01.specialist import DomainContext, Problem
from experiment_03.inter_specialist_protocol import SpecialistRegistry

from .factory import SpecialistFactory


def main() -> None:
    doc_path = (
        Path(__file__).resolve().parent.parent
        / "sample_documents" / "algebra_ch3.md"
    )

    registry = SpecialistRegistry()
    factory = SpecialistFactory(
        registry=registry,
        implicit_figure_kind="linear_equation",
    )
    result = factory.from_document(doc_path)

    print("=" * 72)
    print("EVIDENCIA CENTRAL — EXPERIMENTO 06")
    print("=" * 72)
    print(f"Documento:                   {doc_path.name}")
    print(f"Nodos construidos a mano:    {SpecialistFactory.count_manual_nodes(result.build_report.graph)}")
    print(f"Nodos extraídos del doc:     {result.build_report.nodes_built}")
    print(f"graph.validate():            {'OK' if result.build_report.graph_valid else 'FAIL'}")
    print(f"Especialista registrado:     {result.specialist_name} {'✓' if result.registered else '✗'}")
    print()

    if not result.registered:
        print("(no se pudo registrar — abortando)")
        for e in result.errors:
            print(f"  ✗ {e}")
        return

    # Resolver el problema canónico.
    problem = Problem(
        statement="3x + 6 = 0",
        target="x",
        context=DomainContext(kind="linear_equation", known={"a": 3.0, "b": 6.0}),
    )
    solve = result.specialist.solve(problem)

    print(f"Problema: {problem.statement}")
    if not solve.success:
        print(f"  no resuelto — gap: {solve.gap}")
        return
    for step in solve.trace.steps:
        print(f"Paso {step.index}: {step.node_id}")
        print(f"  inputs:  {step.inputs}")
        print(f"  outputs: {step.outputs}")
    print(f"Resultado: x = {solve.value} {'✓' if solve.value == -2.0 else '✗'}")


if __name__ == "__main__":
    main()
