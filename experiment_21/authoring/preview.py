"""Preview del especialista propuesto (exp_21).

Toma un documento previamente validado y produce una representación
LEGIBLE de qué se va a construir, sin persistir nada. El preview es
la pieza que el autor ve antes de decir "build".

Política:
  - Si la validación tiene `is_valid == False`, NO se construye
    preview — el caller debe corregir errores primero.
  - Las cross-references se identifican por convención
    `spec_id::node_id` o por id puro que aparece en
    `known_specialists`.
  - Las stats agregan: total nodos, conteo por status, surface
    forms nuevas vs en conflicto, foundations resueltas locales vs
    cross-spec.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from experiment_01.knowledge_graph import EpistemicStatus, KnowledgeGraph
from experiment_06.document_parser import (
    NodeExtractor,
    StructureExtractor,
)
from experiment_17.vocabulary import VocabularyRegistry, normalize

from .document_validator import (
    ValidationReport,
    validate_document,
)


# ---------------------------------------------------------------------
# Tipos públicos
# ---------------------------------------------------------------------

@dataclass(frozen=True)
class NodePreview:
    node_id: str
    status: str
    statement: str
    foundations: list[str]
    line_in_document: int


@dataclass(frozen=True)
class SurfaceFormPreview:
    form: str
    node_id: str
    conflicts_with: tuple[str, ...]   # specialist_ids con la misma forma


@dataclass(frozen=True)
class ExpressionPreview:
    node_id: str
    template: str
    referenced_nodes: tuple[str, ...]


@dataclass(frozen=True)
class CrossRefPreview:
    """Referencia a un nodo de OTRO especialista. `spec_id::node_id`
    cuando el autor usó la convención explícita; `spec_id` se
    deriva de `known_specialists` cuando el autor usó id puro."""

    foundation_ref: str
    target_specialist: Optional[str]
    target_node: str


@dataclass(frozen=True)
class PreviewStats:
    total_nodes: int
    by_status: dict[str, int]
    surface_forms_added: int
    surface_forms_in_conflict: int
    foundations_resolved_locally: int
    foundations_resolved_cross_specialist: int
    expression_templates: int
    nodes_without_template: int


@dataclass(frozen=True)
class SpecialistPreview:
    proposed_specialist_id: str
    document_path: str
    nodes: tuple[NodePreview, ...]
    surface_forms: tuple[SurfaceFormPreview, ...]
    expression_templates: tuple[ExpressionPreview, ...]
    cross_specialist_references: tuple[CrossRefPreview, ...]
    statistics: PreviewStats


# ---------------------------------------------------------------------
# Construcción
# ---------------------------------------------------------------------

def _scan_id_lines(raw_lines: list[str]) -> dict[str, int]:
    """Mapa `node_id → primera_línea`. Reusamos la lógica del
    validator pero local — evita import cíclico de helpers privados."""
    import re
    rgx = re.compile(r"^\s*\*\*Id:\*\*\s*(.+?)\s*$")
    out: dict[str, int] = {}
    for idx, line in enumerate(raw_lines, start=1):
        m = rgx.match(line)
        if m and m.group(1).strip() not in out:
            out[m.group(1).strip()] = idx
    return out


def build_preview(
    document_path: str | Path,
    proposed_specialist_id: str | None = None,
    *,
    global_registry: VocabularyRegistry | None = None,
    known_specialists: dict[str, KnowledgeGraph] | None = None,
    validation: ValidationReport | None = None,
) -> SpecialistPreview:
    """Construye el preview. Si `validation` no se provee, valida
    primero. Si la validación falla (is_valid=False), levanta
    `ValueError` con la lista de errores — el preview es UN
    PRODUCTO de validación exitosa."""
    path = Path(document_path)
    if validation is None:
        validation = validate_document(
            path,
            global_registry=global_registry,
            known_specialists=known_specialists,
        )
    if not validation.is_valid:
        codes = ", ".join(sorted({i.code for i in validation.errors}))
        raise ValueError(
            f"el documento tiene errores ({codes}); el preview no se "
            f"construye hasta corregirlos."
        )
    spec_id = proposed_specialist_id or path.stem
    raw_lines = path.read_text(encoding="utf-8").splitlines()
    line_index = _scan_id_lines(raw_lines)

    # Re-parse para obtener los nodos extraídos. El validator ya lo
    # hizo pero no expone el ParseReport — lo recomputamos.
    structure = StructureExtractor().extract_text("\n".join(raw_lines))
    external_ids = _external_ids_from(known_specialists)
    parse_report = NodeExtractor().extract(
        structure, external_ids=set(external_ids),
    )

    # -- nodos --
    nodes_pv: list[NodePreview] = []
    for n in parse_report.nodes_extracted:
        nodes_pv.append(NodePreview(
            node_id=n.node_id,
            status=n.status.value,
            statement=n.statement,
            foundations=list(n.foundations),
            line_in_document=line_index.get(n.node_id, 1),
        ))

    # -- foundations: clasificar local vs cross-spec --
    local_ids = {n.node_id for n in parse_report.nodes_extracted}
    cross_refs: list[CrossRefPreview] = []
    foundations_local = 0
    foundations_cross = 0
    seen_cross: set[str] = set()
    for n in parse_report.nodes_extracted:
        for f in n.foundations:
            if f in local_ids:
                foundations_local += 1
                continue
            foundations_cross += 1
            if f in seen_cross:
                continue
            seen_cross.add(f)
            if "::" in f:
                spec_id_ref, _, node_id_ref = f.partition("::")
                cross_refs.append(CrossRefPreview(
                    foundation_ref=f,
                    target_specialist=spec_id_ref,
                    target_node=node_id_ref,
                ))
            else:
                target_spec = _which_specialist(f, known_specialists)
                cross_refs.append(CrossRefPreview(
                    foundation_ref=f,
                    target_specialist=target_spec,
                    target_node=f,
                ))

    # -- surface forms --
    sf_pv: list[SurfaceFormPreview] = []
    sf_in_conflict = 0
    for n in parse_report.nodes_extracted:
        forms = (n.extra_properties or {}).get("surface_forms", []) or []
        for sf in forms:
            if not isinstance(sf, str) or not sf.strip():
                continue
            conflicts: tuple[str, ...] = ()
            if global_registry is not None:
                hits = global_registry.lookup(sf)
                conflict_specs = sorted({
                    h.specialist_id for h in hits
                    if h.specialist_id != spec_id
                })
                conflicts = tuple(conflict_specs)
                if conflicts:
                    sf_in_conflict += 1
            sf_pv.append(SurfaceFormPreview(
                form=sf, node_id=n.node_id, conflicts_with=conflicts,
            ))

    # -- expression templates --
    expr_pv: list[ExpressionPreview] = []
    nodes_without_template = 0
    for n in parse_report.nodes_extracted:
        template = (n.extra_properties or {}).get("expression_template")
        if not template:
            nodes_without_template += 1
            continue
        from experiment_18.expression import parse_template
        try:
            tokens = parse_template(template)
            refs = tuple(
                t.target for t in tokens
                if hasattr(t, "kind") and t.kind == "node"
            )
        except Exception:
            refs = ()
        expr_pv.append(ExpressionPreview(
            node_id=n.node_id, template=template, referenced_nodes=refs,
        ))

    # -- stats --
    by_status: dict[str, int] = {}
    for n in parse_report.nodes_extracted:
        key = n.status.value
        by_status[key] = by_status.get(key, 0) + 1
    stats = PreviewStats(
        total_nodes=len(parse_report.nodes_extracted),
        by_status=by_status,
        surface_forms_added=len(sf_pv),
        surface_forms_in_conflict=sf_in_conflict,
        foundations_resolved_locally=foundations_local,
        foundations_resolved_cross_specialist=foundations_cross,
        expression_templates=len(expr_pv),
        nodes_without_template=nodes_without_template,
    )

    return SpecialistPreview(
        proposed_specialist_id=spec_id,
        document_path=str(path),
        nodes=tuple(nodes_pv),
        surface_forms=tuple(sf_pv),
        expression_templates=tuple(expr_pv),
        cross_specialist_references=tuple(cross_refs),
        statistics=stats,
    )


def _external_ids_from(
    known_specialists: dict[str, KnowledgeGraph] | None,
) -> set[str]:
    if not known_specialists:
        return set()
    out: set[str] = set()
    for spec_id, graph in known_specialists.items():
        for node in graph:
            out.add(f"{spec_id}::{node.id}")
            out.add(node.id)
    return out


def _which_specialist(
    node_id: str,
    known_specialists: dict[str, KnowledgeGraph] | None,
) -> Optional[str]:
    if not known_specialists:
        return None
    for spec_id, g in known_specialists.items():
        if g.has(node_id):
            return spec_id
    return None
