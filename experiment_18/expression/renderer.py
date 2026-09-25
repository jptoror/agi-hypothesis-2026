"""ExpressionRenderer — verbalización auditable de derivaciones.

Toma un `KnowledgeGraph` y produce prosa a partir de las plantillas
`expression_template` declaradas en cada nodo (marcador
`**Expresión:**` del documento). Sin componentes estadísticos: la
salida es función pura de `(plantilla, bindings, grafo)`.

Reglas operacionales:
  - Si un nodo no tiene `expression_template`, fallback a su
    `statement`. Esto preserva compatibilidad con todos los nodos
    pre-exp_18.
  - Las plantillas pueden referenciar a otros nodos vía
    `{node.X}` — la resolución es recursiva.
  - Cliclos en `{node.X}` → `CyclicReferenceError` con el camino
    completo (no se intenta resolver "lo que se pueda"; cualquier
    ciclo es declarado).
  - El render por traza concatena un texto por paso y los une con
    conectores rotando determinísticamente sobre la lista provista.

`render_trace` también acepta trazas con `delegated_trace` (caso
exp_03/04: cross-specialist). Por defecto INLINE-iza la sub-traza
con sus mismos conectores; un caller que quiera separar voces puede
usar `CrossSpecialistRenderer` (ver renderer cruzado abajo).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from .template import (
    UnresolvedReferenceError,
    render_template,
)

if TYPE_CHECKING:
    from experiment_01.knowledge_graph import KnowledgeGraph
    from experiment_01.specialist import ReasoningStep, ReasoningTrace


# Conectores por defecto. CADA conector lleva su propio separador
# inicial — el renderer NO inserta espacios automáticamente entre
# oraciones. Eso permite conectores que empiezan con puntuación
# (`. Pero `, `; `, `, `) sin colisionar con el join.
_DEFAULT_CONNECTORS: list[str] = [
    " Luego, ",
    " A continuación, ",
    " Después, ",
]


class CyclicReferenceError(RuntimeError):
    """`{node.X}` referencia a un nodo ya en el stack de resolución."""

    def __init__(self, path: list[str]) -> None:
        self.path = list(path)
        super().__init__(
            "ciclo en plantillas de expresión: "
            + " → ".join(self.path)
        )


class ExpressionRenderer:
    """Renderea nodos individuales y trazas completas.

    El estado del renderer es sólo el grafo. La detección de ciclos
    usa un stack PASADO por argumento — el renderer es reentrante y
    seguro para usar concurrentemente sobre trazas distintas.
    """

    def __init__(self, graph: "KnowledgeGraph") -> None:
        self.graph = graph

    # -- API pública ---------------------------------------------------

    def render_node(
        self,
        node_id: str,
        bindings: dict | None = None,
        _stack: tuple[str, ...] = (),
    ) -> str:
        """Renderiza un nodo. `bindings` opcional para `{input.X}` y
        `{output.Y}`. La resolución de `{node.X}` es recursiva con
        detección de ciclos (camino completo en el error)."""
        if node_id in _stack:
            raise CyclicReferenceError(list(_stack) + [node_id])

        if not self.graph.has(node_id):
            raise UnresolvedReferenceError(
                "node", node_id,
                f"el grafo no contiene un nodo con id '{node_id}'",
            )
        node = self.graph.get(node_id)
        template = (node.properties or {}).get("expression_template")

        # Fallback explícito: si el nodo no declara plantilla, usar
        # el statement como su expresión. NO se considera error — los
        # documentos previos a exp_18 funcionan sin tocarse.
        if not isinstance(template, str) or template == "":
            return node.statement

        new_stack = _stack + (node_id,)

        def _resolver(target: str) -> str:
            return self.render_node(
                target, bindings=None, _stack=new_stack,
            )

        return render_template(
            template=template,
            bindings=bindings or {},
            resolver=_resolver,
            self_statement=node.statement,
        )

    def render_trace(
        self,
        trace: "ReasoningTrace",
        connectors: list[str] | None = None,
    ) -> str:
        """Renderiza una traza completa. Cada paso produce una
        oración a partir del nodo + sus inputs/outputs. Los pasos se
        unen con conectores rotando determinísticamente — el primer
        paso va sin conector, los siguientes alternan sobre la lista.

        Si un paso lleva `delegated_trace`, se inline-iza tal cual
        (con los mismos conectores). Para separar voces por
        especialista, usar `CrossSpecialistRenderer`."""
        conns = list(connectors) if connectors else list(_DEFAULT_CONNECTORS)
        sentences: list[str] = []

        for step in trace.steps:
            sentences.append(self._render_step(step))
            if step.delegated_trace is not None:
                # La sub-traza se aplana — cada uno de sus pasos
                # contribuye una oración más al texto principal.
                for sub in step.delegated_trace.steps:
                    sentences.append(self._render_step(sub))

        if not sentences:
            return ""

        out = [sentences[0]]
        for i, s in enumerate(sentences[1:], start=1):
            connector = conns[(i - 1) % len(conns)] if conns else ""
            out.append(connector + s)
        # Join sin espacio implícito — cada conector trae su propio
        # separador (ver `_DEFAULT_CONNECTORS`). Strip final por si
        # el primer sentence trae trailing whitespace.
        return "".join(out).strip()

    # -- helpers internos ---------------------------------------------

    def _render_step(self, step: "ReasoningStep") -> str:
        # Bindings construidos desde el step. Convertimos los valores
        # numéricos a string para que la plantilla los interpole sin
        # sorpresa (`render_template` ya hace `str(...)`, pero lo
        # explicitamos para legibilidad de los tests).
        bindings = {
            "input": dict(step.inputs or {}),
            "output": dict(step.outputs or {}),
            "step": {},  # plantillas pueden referenciar otros pasos
                         # vía `{step.N}` — el caller debe poblar este
                         # diccionario si lo usa. Hoy nadie lo usa.
        }
        return self.render_node(step.node_id, bindings=bindings)


class CrossSpecialistRenderer:
    """Renderea trazas que cruzan especialistas, manteniendo voces
    distintas por segmento.

    Recibe un mapa `{specialist_name: ExpressionRenderer}` y un
    conector de transición declarado por el caller (típicamente el
    orquestador). El conector NO contiene conocimiento de dominio:
    es un conectivo agnóstico (p. ej. `". "` o `". Por su parte, "`).

    Particiona la traza por especialista usando `delegated_trace`:
      - Pasos sin delegación → especialista por defecto (el primero).
      - Pasos con delegación → su `delegated_trace` se renderea con
        el especialista cuyo nombre matchee `step.purpose`/
        `delegated_trace.steps[*].node_id` — concretamente, el
        caller debe etiquetar cada delegación con el especialista
        receptor (ver `delegated_to` abajo).

    Para mantener el contrato simple, esta versión asume que la
    correspondencia paso → especialista viene en
    `step.delegated_to: str | None` (atributo opcional añadido por
    convención: si no existe, se asume el especialista por defecto).
    El orquestador es responsable de etiquetar las delegaciones.
    """

    def __init__(
        self,
        renderers: dict[str, ExpressionRenderer],
        default_specialist: str,
        transition_connector: str = ". ",
    ) -> None:
        if default_specialist not in renderers:
            raise ValueError(
                f"default_specialist '{default_specialist}' no está "
                f"en renderers={list(renderers)}"
            )
        self.renderers = dict(renderers)
        self.default_specialist = default_specialist
        self.transition_connector = transition_connector

    def render(self, trace: "ReasoningTrace") -> str:
        """Particiona y delega cada segmento al renderer
        correspondiente. Concatena con el conector de transición.

        Detalles del particionado:
          - Pasos consecutivos del MISMO especialista forman un
            segmento, rendereado por su renderer en una sola pasada
            (preserva los conectores internos del especialista).
          - Cambio de especialista → cierre del segmento previo,
            apertura del siguiente con el conector de transición."""
        from experiment_01.specialist import ReasoningTrace

        if not trace.steps:
            return ""

        segments: list[tuple[str, list]] = []  # (specialist, steps)
        current_spec: str | None = None
        current_steps: list = []

        for step in trace.steps:
            spec = self._step_specialist(step)
            if spec != current_spec:
                if current_spec is not None and current_steps:
                    segments.append((current_spec, current_steps))
                current_spec = spec
                current_steps = []
            # Si el paso lleva delegated_trace, los pasos delegados
            # se INTEGRAN al segmento del especialista delegado.
            if step.delegated_trace is not None:
                # Cerrar segmento actual antes de cambiar de voz.
                if current_steps:
                    segments.append((current_spec, current_steps))
                    current_steps = []
                delegated_spec = getattr(step, "delegated_to", None) or spec
                segments.append((
                    delegated_spec,
                    list(step.delegated_trace.steps),
                ))
                current_spec = spec
            else:
                current_steps.append(step)

        if current_spec is not None and current_steps:
            segments.append((current_spec, current_steps))

        rendered: list[str] = []
        for spec_name, steps in segments:
            renderer = self.renderers.get(spec_name)
            if renderer is None:
                raise KeyError(
                    f"no hay renderer registrado para especialista "
                    f"'{spec_name}'"
                )
            sub_trace = ReasoningTrace(steps=list(steps))
            rendered.append(renderer.render_trace(sub_trace))

        return self.transition_connector.join(t for t in rendered if t)

    def _step_specialist(self, step) -> str:
        """Identifica al especialista responsable de un paso.

        Convención: el paso lleva un atributo opcional
        `_specialist_name`/`delegated_to`. Si no, se usa el
        default."""
        return (
            getattr(step, "_specialist_name", None)
            or getattr(step, "delegated_to", None)
            or self.default_specialist
        )
