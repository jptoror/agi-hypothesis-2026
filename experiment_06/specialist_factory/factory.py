"""SpecialistFactory — fábrica de especialistas a partir de documentos.

Encadena las tres fases del parser y produce un SubdomainSpecialist
listo para registrarse en una SpecialistRegistry. Reutiliza el
SubdomainSpecialist del exp_04 (ya validado para grafos mixtos con
condiciones numéricas + prosa) — eso evita duplicar 50 líneas y
demuestra que la arquitectura de subdominios del exp_04 es genérica:
sirve tanto para grafos sintetizados a partir de patrones como para
grafos extraídos a partir de documentos.

INVARIANTE arquitectónico: si el BuildReport tiene `is_valid=False`,
la fábrica NO registra el especialista. El campo `registered` del
RegistrationResult expresa el resultado de la decisión.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from experiment_03.inter_specialist_protocol import SpecialistRegistry

from experiment_04.subdomain_specialist import (
    SubdomainAdapter,
    SubdomainSpecialist,
)

from experiment_06.document_parser import (
    BuildReport,
    GraphBuilder,
    NodeExtractor,
    ParseReport,
    StructureExtractor,
)
# Importado lazy abajo para no acoplar el módulo del exp_06 al exp_17
# en tiempo de import. El registry default se usa sólo si la factory
# se construye sin uno explícito.


@dataclass
class RegistrationResult:
    specialist_name: str
    specialist: SubdomainSpecialist | None
    adapter: SubdomainAdapter | None
    build_report: BuildReport
    parse_report: ParseReport
    registered: bool
    errors: list[str] = field(default_factory=list)

    def render(self) -> str:
        lines = [
            "=" * 72,
            "REGISTRATION RESULT",
            "=" * 72,
            f"specialist_name: {self.specialist_name}",
            f"registered:      {self.registered}",
            f"parse.is_valid:  {self.parse_report.is_valid}",
            f"build.is_valid:  {self.build_report.is_valid}",
            f"graph.validate:  {self.build_report.graph_valid}",
            f"nodos extraídos: {len(self.parse_report.nodes_extracted)}",
            f"nodos construidos: {self.build_report.nodes_built}",
        ]
        if self.errors:
            lines.append("errores:")
            for e in self.errors:
                lines.append(f"  ✗ {e}")
        return "\n".join(lines)


class SpecialistFactory:
    """Convierte un documento Markdown en un especialista registrado."""

    def __init__(
        self,
        registry: SpecialistRegistry,
        implicit_figure_kind: str | None = None,
        domain_terms: list[list[str]] | None = None,
        vocabulary_registry=None,
    ) -> None:
        self.registry = registry
        # Usamos el verificador híbrido del SubdomainSpecialist con un
        # `implicit_figure_kind` opcional para problemas que no
        # declaren un kind reconocible. Para álgebra el default
        # (sin domain_terms) es apropiado: las condiciones del grafo
        # son numéricas o prosa libre, no nombran tipos de figura.
        self.implicit_figure_kind = implicit_figure_kind
        self.domain_terms = [list(g) for g in (domain_terms or [])]
        # exp_17: cuando un especialista se construye desde un
        # documento, sus surface_forms (declaradas con `**Términos:**`)
        # se publican al VocabularyRegistry — sin trabajo manual de
        # propagación. Default = DEFAULT_REGISTRY (singleton del
        # exp_17). Tests pueden inyectar uno aislado.
        if vocabulary_registry is None:
            from experiment_17.vocabulary import DEFAULT_REGISTRY
            self.vocabulary_registry = DEFAULT_REGISTRY
        else:
            self.vocabulary_registry = vocabulary_registry

    # -- API pública ---------------------------------------------------

    def from_document(
        self,
        path: str | Path,
        specialist_name: str | None = None,
        base_graph=None,
    ) -> RegistrationResult:
        """Pipeline completo: documento → especialista registrado.

        `base_graph` (opcional, exp_09): KnowledgeGraph del que el
        especialista importa fundamentos referenciados por el
        documento que no aparecen en él mismo. El extractor recibe
        los ids del base como `external_ids` y el builder lo
        importa con cierre transitivo.
        """
        p = Path(path)
        derived_name = specialist_name or p.stem  # algebra_ch3.md → algebra_ch3

        # external_ids para que el extractor acepte refs al base.
        external_ids = (
            {n.id for n in base_graph} if base_graph is not None else set()
        )

        structure = StructureExtractor().extract_file(p)
        parse_report = NodeExtractor().extract(
            structure, external_ids=external_ids
        )
        if not parse_report.is_valid:
            return RegistrationResult(
                specialist_name=derived_name,
                specialist=None,
                adapter=None,
                build_report=BuildReport(
                    nodes_built=0,
                    graph_valid=False,
                    errors=[],
                    topological_order=[],
                    graph=None,
                ),
                parse_report=parse_report,
                registered=False,
                errors=[
                    f"parse_report inválido: {len(parse_report.errors)} errores"
                ],
            )

        build_report = GraphBuilder().build(
            parse_report, base_graph=base_graph
        )
        if not build_report.is_valid or build_report.graph is None:
            return RegistrationResult(
                specialist_name=derived_name,
                specialist=None,
                adapter=None,
                build_report=build_report,
                parse_report=parse_report,
                registered=False,
                errors=[
                    f"build_report inválido: {len(build_report.errors)} errores"
                ],
            )

        # Construir el especialista y su adapter.
        adapter = SubdomainAdapter(
            graph=build_report.graph,
            domain=derived_name,
            implicit_figure_kind=self.implicit_figure_kind,
            domain_terms=self.domain_terms,
        )
        specialist = adapter.specialist

        # Intentar registrar — la registry puede rechazar duplicados.
        try:
            self.registry.register(adapter)
            registered = True
            errors: list[str] = []
        except ValueError as e:
            registered = False
            errors = [f"fallo al registrar: {e}"]

        # exp_17: publicar formas de superficie. Sólo si el adapter
        # se registró efectivamente — un especialista rechazado por la
        # registry de especialistas no debe contaminar el vocabulario.
        # `register` del VocabularyRegistry es idempotente por id
        # (re-registrar reemplaza), lo que soporta hot-reload.
        if registered:
            self.vocabulary_registry.register(
                specialist_id=derived_name,
                graph=build_report.graph,
                source_document=str(p),
            )

        return RegistrationResult(
            specialist_name=derived_name,
            specialist=specialist,
            adapter=adapter,
            build_report=build_report,
            parse_report=parse_report,
            registered=registered,
            errors=errors,
        )

    # -- helpers públicos para auditoría -------------------------------

    @staticmethod
    def count_manual_nodes(graph) -> int:
        """Cuenta nodos del grafo NO marcados como extraídos del documento.

        La fábrica garantiza que todo nodo construido vía pipeline
        lleva `properties['extracted_from_document'] = True`. Este
        helper permite a tests/auditorías afirmar que el grafo no
        contiene nodos añadidos a mano fuera del pipeline.
        """
        manual = 0
        for node in graph:
            props = node.properties or {}
            if not props.get("extracted_from_document"):
                manual += 1
        return manual
