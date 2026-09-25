"""Factory del especialista C++ mínimo.

Reutiliza el patrón establecido en exp_09/13/15: documento → parser
→ builder con base_graph → especialista registrado. Dos diferencias
arquitectónicas honestas:

  1. El `base_graph` NO es el de complejidad — es el grafo COMPLETO
     del especialista del capítulo 1 (exp_15). Esto importa
     `alg.greedy_coloring` y sus fundamentos transitivos al grafo
     C++. Cuando el especialista resuelve la pregunta canónica, su
     traza puede mostrar nodos de AMBOS dominios — exactamente lo
     que el test crítico exige.

  2. El procedimiento `cpp_greedy_coloring_compose` se inyecta vía
     un `procedures` dict propio. No vive en `experiment_06.
     specialist_factory.PROCEDURES` (la biblioteca del exp_06 es
     para álgebra). El SpecialistFactory acepta procedures
     custom — lo aprovechamos.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from experiment_03.inter_specialist_protocol import SpecialistRegistry
from experiment_06.specialist_factory import (
    RegistrationResult,
    SpecialistFactory,
)
from experiment_06.specialist_factory.procedures import ProcedureSpec

from experiment_15.specialist_factory import AlgorithmsCh1SpecialistFactory

from .cpp_templates import cpp_greedy_coloring_compose


_DEFAULT_DOC = (
    Path(__file__).resolve().parent.parent
    / "sample_documents" / "cpp_minimal.md"
)


# Procedimientos específicos del especialista C++. Se pasan al
# GraphBuilder vía SpecialistFactory(procedures=...). El builder
# verifica que las firmas declaradas en el documento coincidan con
# las del spec — exactamente el mismo contrato que el de álgebra.
CPP_PROCEDURES: dict[str, ProcedureSpec] = {
    "cpp_greedy_coloring_compose": ProcedureSpec(
        inputs=["abstract_node", "target_container"],
        outputs=["cpp_code"],
        fn=cpp_greedy_coloring_compose,
        description=(
            "Compone código C++ para alg.greedy_coloring usando "
            "las plantillas declaradas en CPP_TEMPLATES."
        ),
    ),
}


@dataclass
class CppMinimalRegistrationResult:
    """Wrapper sobre RegistrationResult con conteos de auditoría
    distinguiendo nodos del documento vs nodos importados del
    base_graph (que aquí es el grafo del especialista ch1)."""

    underlying: RegistrationResult
    base_graph_node_count: int
    document_node_count: int

    @property
    def specialist_name(self) -> str:
        return self.underlying.specialist_name

    @property
    def specialist(self):
        return self.underlying.specialist

    @property
    def adapter(self):
        return self.underlying.adapter

    @property
    def registered(self) -> bool:
        return self.underlying.registered

    @property
    def graph(self):
        return self.underlying.build_report.graph

    @property
    def errors(self) -> list[str]:
        return self.underlying.errors

    def render(self) -> str:
        lines = [
            "=" * 72,
            "CPP_MINIMAL SPECIALIST REGISTRATION",
            "=" * 72,
            f"specialist_name: {self.specialist_name}",
            f"registered:      {self.registered}",
            f"nodos del documento:    {self.document_node_count}",
            f"nodos importados ch1:   {self.base_graph_node_count}",
            f"nodos en grafo final:   "
            f"{len(self.graph) if self.graph else None}",
        ]
        if self.errors:
            lines.append("errores:")
            for e in self.errors:
                lines.append(f"  ✗ {e}")
        return "\n".join(lines)


class CppMinimalSpecialistFactory:
    """Construye el especialista C++ anclado al grafo del exp_15."""

    def __init__(
        self,
        registry: SpecialistRegistry | None = None,
        domain_terms: list[list[str]] | None = None,
    ) -> None:
        self.registry = registry or SpecialistRegistry()
        # Procedimientos específicos del C++ + (opcionalmente) los
        # del exp_06. Aquí basta con CPP_PROCEDURES porque ningún
        # nodo del documento C++ referencia procedimientos de álgebra.
        self.factory = SpecialistFactory(
            registry=self.registry,
            implicit_figure_kind="cpp_minimal",
            domain_terms=domain_terms,
        )
        # Sustituimos la biblioteca por defecto (PROCEDURES del exp_06)
        # por la del C++. SpecialistFactory acepta esto vía la
        # construcción de un GraphBuilder con `procedures=...`, que
        # se resuelve dentro de SpecialistFactory.from_document.
        # Como SpecialistFactory NO expone ese parámetro al exterior,
        # construimos el GraphBuilder manualmente más abajo.

    def build(
        self,
        doc_path: str | Path = _DEFAULT_DOC,
        specialist_name: str | None = None,
    ) -> CppMinimalRegistrationResult:
        # base_graph es el grafo del especialista del cap 1.
        ch1_factory = AlgorithmsCh1SpecialistFactory()
        ch1_result = ch1_factory.build()
        if not ch1_result.registered:
            raise RuntimeError(
                f"no se pudo construir el especialista ch1 (base): "
                f"{ch1_result.errors}"
            )
        base_graph = ch1_result.graph

        # SpecialistFactory.from_document NO acepta `procedures`
        # en su firma actual — usa GraphBuilder() con default
        # PROCEDURES del exp_06. Para inyectar CPP_PROCEDURES sin
        # modificar el factory del exp_06, llamamos al pipeline a
        # mano con un GraphBuilder configurado.
        from experiment_06.document_parser import (
            GraphBuilder,
            NodeExtractor,
            StructureExtractor,
        )
        from experiment_04.subdomain_specialist import SubdomainAdapter

        external_ids = {n.id for n in base_graph}
        structure = StructureExtractor().extract_file(Path(doc_path))
        parse_report = NodeExtractor().extract(
            structure, external_ids=external_ids
        )

        # Para evaluar igual el resultado, fabricamos un
        # RegistrationResult con la misma forma que el exp_06.
        # El builder usa CPP_PROCEDURES.
        builder = GraphBuilder(procedures=CPP_PROCEDURES)
        build_report = builder.build(parse_report, base_graph=base_graph)
        derived_name = specialist_name or "cpp_minimal"

        if not build_report.is_valid or build_report.graph is None:
            registered = False
            adapter = None
            specialist = None
            errors_list = [
                f"build_report inválido: {len(build_report.errors)} errores"
            ]
        else:
            adapter = SubdomainAdapter(
                graph=build_report.graph,
                domain=derived_name,
                implicit_figure_kind="cpp_minimal",
            )
            specialist = adapter.specialist
            try:
                self.registry.register(adapter)
                registered = True
                errors_list = []
            except ValueError as e:
                registered = False
                errors_list = [f"fallo al registrar: {e}"]

        result = RegistrationResult(
            specialist_name=derived_name,
            specialist=specialist,
            adapter=adapter,
            build_report=build_report,
            parse_report=parse_report,
            registered=registered,
            errors=errors_list,
        )
        doc_count = len(parse_report.nodes_extracted)
        base_count = (
            len(build_report.graph) - doc_count
            if build_report.graph else 0
        )
        return CppMinimalRegistrationResult(
            underlying=result,
            base_graph_node_count=base_count,
            document_node_count=doc_count,
        )
