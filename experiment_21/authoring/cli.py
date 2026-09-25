"""CLI `agi-author` para autoría de especialistas (exp_21).

Subcomandos:
    agi-author validate <document> [--root agi_data]
    agi-author preview  <document> [--root agi_data] [--id ID]
    agi-author build    <document> [--root agi_data] [--id ID] [--yes] [--overwrite]
    agi-author list                 [--root agi_data]
    agi-author show     <id>        [--root agi_data]
    agi-author remove   <id>        [--root agi_data] [--yes] [--keep-files]
    agi-author reload   <document>  [--root agi_data] [--id ID] [--yes]

Salida:
    Mensajes en castellano, número de línea + fragmento + sugerencia.
    Ningún stack trace en operación normal — todo error de validación
    se reporta como issue tipado.

Códigos de salida:
    0  éxito
    1  validación falló o cancelado por el usuario
    2  uso incorrecto del CLI (argumentos malformados)
    3  archivo o especialista inexistente
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable

from experiment_01.knowledge_graph import KnowledgeGraph
from experiment_09.knowledge_graph import build_complexity_base_graph
from experiment_17.vocabulary import VocabularyRegistry

from .document_validator import (
    KNOWN_MARKERS,
    ValidationIssue,
    ValidationReport,
    validate_document,
)
from .preview import (
    SpecialistPreview,
    build_preview,
)
from .persister import (
    list_specialists,
    persist_specialist,
    remove_specialist,
)


DEFAULT_ROOT = "agi_data"


# ---------------------------------------------------------------------
# Helpers de I/O y formateo
# ---------------------------------------------------------------------

def _err(msg: str) -> None:
    print(msg, file=sys.stderr)


def _confirm(prompt: str, *, yes: bool) -> bool:
    if yes:
        return True
    try:
        ans = input(f"{prompt} [y/N]: ").strip().lower()
    except EOFError:
        return False
    return ans in ("y", "yes", "s", "si", "sí")


def _format_issue(issue: ValidationIssue) -> str:
    sev_label = {
        "error": "ERROR  ",
        "warning": "WARN   ",
        "info": "INFO   ",
    }[issue.severity]
    out = [
        f"{sev_label} línea {issue.line:<5} {issue.code}",
        f"   {issue.message}",
    ]
    if issue.fragment:
        out.append("")
        out.append("   Fragmento:")
        for line in issue.fragment.splitlines():
            out.append(f"      {line}")
    if issue.suggestion:
        out.append("")
        out.append(f"   Sugerencia: {issue.suggestion}")
    return "\n".join(out)


def _print_report(report: ValidationReport) -> None:
    print(f"Validando: {report.document_path}")
    print()
    e = len(report.errors)
    w = len(report.warnings)
    if e == 0 and w == 0:
        print("✓ Sin issues. Documento válido.")
        return
    icon = "✗" if e else "!"
    parts = []
    if e:
        parts.append(f"{e} error{'es' if e != 1 else ''}")
    if w:
        parts.append(f"{w} advertencia{'s' if w != 1 else ''}")
    print(f"{icon} {', '.join(parts)}")
    print()
    for issue in report.issues:
        print(_format_issue(issue))
        print()


def _print_preview(preview: SpecialistPreview) -> None:
    s = preview.statistics
    print(f"Documento: {preview.document_path}")
    print(f"Especialista propuesto: {preview.proposed_specialist_id}")
    print("Estado: ✓ válido, listo para construir")
    print()
    print(f"Nodos: {s.total_nodes}")
    for status_key in sorted(s.by_status.keys()):
        n = s.by_status[status_key]
        print(f"  {status_key.upper():<11} {n}")
    print()
    print("Vocabulario:")
    print(f"  {s.surface_forms_added} surface forms nuevas")
    if s.surface_forms_in_conflict:
        print(f"  {s.surface_forms_in_conflict} en conflicto con especialistas existentes:")
        for sf in preview.surface_forms:
            if sf.conflicts_with:
                print(f"    \"{sf.form}\" ya existe en "
                      f"{', '.join(sf.conflicts_with)}")
    print()
    print("Foundations:")
    print(f"  resueltas localmente:        {s.foundations_resolved_locally}")
    if s.foundations_resolved_cross_specialist:
        print(f"  cross-specialist:            {s.foundations_resolved_cross_specialist}")
        for cr in preview.cross_specialist_references:
            target = cr.target_specialist or "?"
            print(f"    {cr.foundation_ref}  →  {target}:{cr.target_node}")
    print()
    print(f"Plantillas de expresión: {s.expression_templates}"
          + (f" ({s.nodes_without_template} nodos sin expresión — "
             f"fallback a statement)" if s.nodes_without_template else ""))


# ---------------------------------------------------------------------
# Resolución del estado del sistema (manifest + registry)
# ---------------------------------------------------------------------

def _load_known_specialists(root: Path) -> dict[str, KnowledgeGraph]:
    """Carga los especialistas YA persistidos en `root`. Útil para
    detectar cross-refs y conflictos durante validación. Si el
    manifest no existe, devuelve sólo el `_complexity_base`."""
    out: dict[str, KnowledgeGraph] = {
        "_complexity_base": build_complexity_base_graph(),
    }
    manifest_path = root / "manifest.json"
    if not manifest_path.exists():
        return out
    # Intentar load_system; si falla porque algún procedure no está
    # registrado, hacemos fallback a leer directamente los grafos
    # como JSON (sólo necesitamos los node ids para validación).
    try:
        from experiment_06.specialist_factory import PROCEDURES
        from experiment_19.persistence import (
            ProcedureRefRegistry,
            load_system,
            register_procedures_from,
        )
        preg = ProcedureRefRegistry()
        register_procedures_from(preg, PROCEDURES)
        loaded = load_system(root, procedure_registry=preg)
        for sid, g in loaded.graphs.items():
            out[sid] = g
    except Exception as e:  # pragma: no cover - defensivo
        _err(f"⚠ no se pudo cargar el sistema completo: {e}. "
             f"Continuando con los especialistas mínimos.")
    return out


def _build_global_registry(
    known: dict[str, KnowledgeGraph],
    exclude: str | None = None,
) -> VocabularyRegistry:
    """Re-indexa surface_forms de los especialistas conocidos.
    `exclude` permite descontar el especialista que estamos
    validando (caso reload), evitando que sus propias forms se
    reporten como conflicto."""
    reg = VocabularyRegistry()
    for sid, g in known.items():
        if sid == exclude:
            continue
        if sid == "_complexity_base":
            # No incluimos el base de complejidad en el lookup de
            # surface forms — sus nodos no declaran términos.
            continue
        reg.register(sid, g)
    return reg


# ---------------------------------------------------------------------
# Subcomandos
# ---------------------------------------------------------------------

def cmd_validate(args) -> int:
    root = Path(args.root)
    doc = Path(args.document)
    if not doc.exists():
        _err(f"✗ no existe el documento: {doc}")
        return 3
    known = _load_known_specialists(root)
    global_reg = _build_global_registry(known, exclude=args.id)
    report = validate_document(
        doc, global_registry=global_reg, known_specialists=known,
    )
    _print_report(report)
    return 0 if report.is_valid else 1


def cmd_preview(args) -> int:
    root = Path(args.root)
    doc = Path(args.document)
    if not doc.exists():
        _err(f"✗ no existe el documento: {doc}")
        return 3
    known = _load_known_specialists(root)
    global_reg = _build_global_registry(known, exclude=args.id)
    report = validate_document(
        doc, global_registry=global_reg, known_specialists=known,
    )
    if not report.is_valid:
        _print_report(report)
        return 1
    try:
        preview = build_preview(
            doc, proposed_specialist_id=args.id or doc.stem,
            global_registry=global_reg,
            known_specialists=known,
            validation=report,
        )
    except Exception as e:
        _err(f"✗ no se pudo construir el preview: {e}")
        return 1
    _print_preview(preview)
    return 0


def cmd_build(args) -> int:
    root = Path(args.root)
    doc = Path(args.document)
    if not doc.exists():
        _err(f"✗ no existe el documento: {doc}")
        return 3
    spec_id = args.id or doc.stem
    known = _load_known_specialists(root)
    global_reg = _build_global_registry(known, exclude=spec_id)
    report = validate_document(
        doc, global_registry=global_reg, known_specialists=known,
    )
    if not report.is_valid:
        _print_report(report)
        return 1
    preview = build_preview(
        doc, proposed_specialist_id=spec_id,
        global_registry=global_reg, known_specialists=known,
        validation=report,
    )
    _print_preview(preview)
    print()
    if not _confirm(
        f"¿Construir especialista \"{spec_id}\"?", yes=args.yes,
    ):
        print("Cancelado.")
        return 1
    print()
    print("Construyendo...")
    try:
        out = persist_specialist(
            doc, preview, target_root=root,
            overwrite=args.overwrite, known_specialists=known,
        )
    except FileExistsError as e:
        _err(f"✗ {e}")
        return 1
    print(f"  ✓ Grafo serializado: {out.graph_path}")
    print(f"  ✓ Documento copiado:  {out.document_path}")
    print(f"  ✓ Manifest actualizado")
    print()
    print(f"Especialista listo. {out.nodes_persisted} nodos, "
          f"{preview.statistics.surface_forms_added} surface forms.")
    return 0


def cmd_list(args) -> int:
    root = Path(args.root)
    entries = list_specialists(root)
    if not entries:
        print("(no hay especialistas registrados)")
        return 0
    print(f"Especialistas en {root}:")
    for e in entries:
        src = e.source_document or "(sin documento)"
        print(f"  · {e.specialist_id:30}  {e.graph_path}  ←  {src}")
    return 0


def cmd_show(args) -> int:
    root = Path(args.root)
    entries = list_specialists(root)
    entry = next(
        (e for e in entries if e.specialist_id == args.specialist_id),
        None,
    )
    if entry is None:
        _err(f"✗ no existe el especialista '{args.specialist_id}' en {root}")
        return 3
    print(f"specialist_id:    {entry.specialist_id}")
    print(f"specialist_class: {entry.specialist_class}")
    print(f"graph_path:       {entry.graph_path}")
    print(f"source_document:  {entry.source_document or '(ninguno)'}")
    # Cargar el grafo para mostrar conteos.
    graph_file = root / entry.graph_path
    if graph_file.exists():
        try:
            data = json.loads(graph_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print("(grafo corrupto)")
            return 3
        nodes = data.get("nodes", [])
        print(f"node_count:       {len(nodes)}")
        by_status: dict[str, int] = {}
        for n in nodes:
            by_status[n["status"]] = by_status.get(n["status"], 0) + 1
        for k in sorted(by_status):
            print(f"   {k:<11} {by_status[k]}")
    return 0


def cmd_remove(args) -> int:
    root = Path(args.root)
    if not _confirm(
        f"¿Quitar el especialista '{args.specialist_id}' "
        f"del manifest en {root}?",
        yes=args.yes,
    ):
        print("Cancelado.")
        return 1
    ok = remove_specialist(
        root, args.specialist_id, delete_files=not args.keep_files,
    )
    if not ok:
        _err(f"✗ no estaba registrado: {args.specialist_id}")
        return 3
    print(f"✓ removido: {args.specialist_id}")
    return 0


def cmd_reload(args) -> int:
    """Reconstruye un especialista existente desde su documento.
    Por defecto usa el path original del documento; si no se da
    `--id`, derivamos del filename."""
    args.overwrite = True
    return cmd_build(args)


# ---------------------------------------------------------------------
# argparse
# ---------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="agi-author",
        description=(
            "Herramienta de autoría de especialistas para "
            "agi-hypothesis. Valida documentos markdown con los "
            "marcadores del sistema y construye especialistas listos "
            "para registrarse."
        ),
    )
    p.add_argument(
        "--root", default=DEFAULT_ROOT,
        help=f"directorio de datos del sistema (default: {DEFAULT_ROOT})",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    # validate
    sp = sub.add_parser("validate", help="validar un documento")
    sp.add_argument("document")
    sp.add_argument("--id", default=None,
                    help="id propuesto (para excluir de conflictos)")
    sp.set_defaults(func=cmd_validate)

    # preview
    sp = sub.add_parser("preview", help="validar + mostrar preview")
    sp.add_argument("document")
    sp.add_argument("--id", default=None)
    sp.set_defaults(func=cmd_preview)

    # build
    sp = sub.add_parser("build", help="validar + preview + persistir")
    sp.add_argument("document")
    sp.add_argument("--id", default=None)
    sp.add_argument("--yes", action="store_true",
                    help="omitir confirmación interactiva")
    sp.add_argument("--overwrite", action="store_true",
                    help="reemplazar especialista existente")
    sp.set_defaults(func=cmd_build)

    # list
    sp = sub.add_parser("list", help="listar especialistas registrados")
    sp.set_defaults(func=cmd_list)

    # show
    sp = sub.add_parser("show", help="info del especialista")
    sp.add_argument("specialist_id")
    sp.set_defaults(func=cmd_show)

    # remove
    sp = sub.add_parser("remove", help="quitar un especialista")
    sp.add_argument("specialist_id")
    sp.add_argument("--yes", action="store_true",
                    help="omitir confirmación")
    sp.add_argument("--keep-files", action="store_true",
                    help="no borrar el .json del grafo ni la copia del doc")
    sp.set_defaults(func=cmd_remove)

    # reload
    sp = sub.add_parser("reload", help="reconstruir especialista existente")
    sp.add_argument("document")
    sp.add_argument("--id", default=None)
    sp.add_argument("--yes", action="store_true")
    sp.set_defaults(func=cmd_reload)

    return p


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
