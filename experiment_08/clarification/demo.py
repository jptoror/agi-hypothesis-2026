"""Demo del ClarificationResolver — ejercita los tres veredictos.

Construye un bus mínimo con:
  - el especialista de lenguaje (iniciador, será excluido)
  - el especialista de álgebra (extraído de algebra_ch3.md vía
    SpecialistFactory)

Y prueba el concepto 'coeficiente' bajo tres escenarios:
  1. Sin hint del caller — el bus decide.
  2. Con hint domain='algebra' — el caller zanja.
  3. Concepto inventado 'zxqwerty' — UNKNOWN.

Uso:
    python -m experiment_08.clarification.demo
"""
from __future__ import annotations

from pathlib import Path

from experiment_03.inter_specialist_protocol import (
    GapRequest,
    GapResponse,
    ResponseStatus,
    SpecialistAdapter,
    SpecialistRegistry,
)
from experiment_06.specialist_factory import SpecialistFactory
from experiment_07.knowledge_graph import build_spanish_base_graph

from .resolver import ClarificationResolver


# Adapter mínimo para que el bus tenga al especialista de lenguaje.
# El resolver sólo lee `graph` y `name`, así que un adapter trivial basta.
class _LanguageBusAdapter(SpecialistAdapter):
    name = "language"
    output_variables = frozenset()

    def __init__(self, graph) -> None:
        self.graph = graph

    def handle(self, request: GapRequest, delegate=None) -> GapResponse:  # noqa: D401
        return GapResponse(
            request_id=request.request_id,
            responder=self.name,
            status=ResponseStatus.UNRESOLVABLE,
        )


def _build_registry() -> SpecialistRegistry:
    registry = SpecialistRegistry()
    # Lenguaje (iniciador).
    registry.register(_LanguageBusAdapter(build_spanish_base_graph()))
    # Álgebra (desde el documento del exp_06).
    algebra_doc = (
        Path(__file__).resolve().parent.parent.parent
        / "experiment_06" / "sample_documents" / "algebra_ch3.md"
    )
    factory = SpecialistFactory(
        registry=registry,
        implicit_figure_kind="linear_equation",
    )
    factory.from_document(algebra_doc)
    return registry


def main() -> None:
    registry = _build_registry()
    resolver = ClarificationResolver(
        registry=registry, initiating_specialist="language"
    )

    print("=" * 72)
    print("ESCENARIO 1 — 'coeficiente' sin hint")
    print("=" * 72)
    a1 = resolver.assess("coeficiente", available_context={})
    print(a1.render())
    print()

    print("=" * 72)
    print("ESCENARIO 2 — 'coeficiente' con domain='algebra'")
    print("=" * 72)
    a2 = resolver.assess("coeficiente", available_context={"domain": "algebra"})
    print(a2.render())
    print()

    print("=" * 72)
    print("ESCENARIO 3 — concepto inventado 'zxqwerty'")
    print("=" * 72)
    a3 = resolver.assess("zxqwerty", available_context={})
    print(a3.render())


if __name__ == "__main__":
    main()
