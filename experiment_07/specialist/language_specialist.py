"""Especialista de lenguaje español.

Parsea una instrucción semi-estructurada y produce un Problem
verificado, sin NLP ni stemming. Tres modos de matching, declarados
en el grafo (no en el código del especialista):

  match_strategy='tokens'    → lookup en lista cerrada `tokens` del nodo
  match_strategy='pattern'   → regex declarada en `pattern` del nodo
  match_strategy='inference' → evalúa `inference_requires` y
                                `inference_constraints` sobre el
                                contexto acumulado por los nodos previos

El especialista NO entiende español. Reconoce vocabulario declarado.
Cualquier token no reconocido se reporta en
`LanguageParseResult.unrecognized_tokens` — el sistema es selectivo
por diseño, no oculta lo que no procesa.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from experiment_01.knowledge_graph import KnowledgeGraph, KnowledgeNode
from experiment_01.specialist import (
    DomainContext,
    Problem,
    ReasoningStep,
)


# Tokenización: separa por whitespace, comas, puntos, signos de
# interrogación/exclamación, paréntesis. Conservamos los tokens con
# su forma original para uso posterior; la normalización (lowercase
# + sin tildes) ocurre en la comparación, no en el almacenamiento.
_TOKEN_SPLIT = re.compile(r"[\s,;:.!?()¿¡]+")


def _normalize(s: str) -> str:
    s = s.lower()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s


@dataclass
class ResolvedTerm:
    """Una forma de superficie del input mapeada a una o más bindings
    del VocabularyRegistry (exp_17). `span_tokens` lleva los tokens
    originales consumidos por el match; `surface_form` es la forma
    normalizada que el registry indexó. Si `bindings` tiene más de un
    elemento, hubo conflicto entre especialistas — el caller decide
    cómo resolverlo (típicamente con un `domain_hint` o vía
    ClarificationRequest)."""

    surface_form: str
    span_tokens: list[str]
    start_index: int
    bindings: list  # list[VocabularyBinding] — evita import circular


@dataclass
class LanguageParseResult:
    problem: Problem | None
    steps: list[ReasoningStep]
    unrecognized_tokens: list[str]
    is_complete: bool
    resolved_terms: list[ResolvedTerm] = field(default_factory=list)
    clarification_requests: list = field(default_factory=list)

    def render(self) -> str:
        lines = [
            "=" * 72,
            "LANGUAGE PARSE RESULT",
            "=" * 72,
            f"is_complete: {self.is_complete}",
            f"unrecognized_tokens: {self.unrecognized_tokens}",
            f"resolved_terms: {len(self.resolved_terms)}",
            f"clarification_requests: {len(self.clarification_requests)}",
            "",
            "── pasos del especialista de lenguaje ──",
        ]
        for s in self.steps:
            lines.append(s.render())
            lines.append("")
        if self.problem is not None:
            lines.append("── Problem producido ──")
            lines.append(f"  statement: {self.problem.statement}")
            lines.append(f"  target:    {self.problem.target}")
            lines.append(
                f"  context:   kind={self.problem.context.kind!r} "
                f"known={self.problem.context.known}"
            )
        else:
            lines.append("(sin Problem — parse incompleto)")
        return "\n".join(lines)


class LanguageSpecialist:
    """Especialista cuyo razonamiento es lookup tipado sobre tokens."""

    domain = "language"

    def __init__(
        self,
        graph: KnowledgeGraph,
        vocabulary_registry=None,
    ) -> None:
        self.graph = graph
        # exp_17: registry compartido de surface_forms. None == sin
        # registry → el especialista opera sólo con el matcher local
        # (compatibilidad con todos los tests anteriores). Si se
        # inyecta, la pasada del registry PRECEDE al matcher local
        # y consume los tokens correspondientes.
        if vocabulary_registry is None:
            try:
                from experiment_17.vocabulary import DEFAULT_REGISTRY
                self.vocabulary_registry = DEFAULT_REGISTRY
            except ImportError:
                self.vocabulary_registry = None
        else:
            self.vocabulary_registry = vocabulary_registry

    # -- API pública ---------------------------------------------------

    def parse(
        self,
        text: str,
        domain_hint: str | None = None,
    ) -> LanguageParseResult:
        """Procesa la instrucción y devuelve el resultado.

        Pipeline:
          0. Pre-pasada del VocabularyRegistry (exp_17): resuelve
             spans declarados por especialistas registrados a sus
             nodos. Consume tokens. Si hay conflicto entre varias
             bindings, intenta resolver con `domain_hint`; si no
             alcanza, emite ClarificationRequest y deja el span SIN
             consumir (el caller decide).
          1. Extracción: nodos con strategy 'tokens' o 'pattern'
             contribuyen al contexto y consumen tokens NO consumidos
             por la pre-pasada.
          2. Inferencia: nodos con strategy 'inference' evalúan sus
             prerequisites/constraints sobre el contexto acumulado.

        Cada nodo ejercitado produce un ReasoningStep distinto. Si
        un nodo no aporta nada (no matchea), no genera step — el
        principio de 'no pasos silenciosos' aplica solo a los que SÍ
        contribuyeron.
        """
        tokens = self._tokenize(text)
        consumed: set[int] = set()  # índices de tokens consumidos
        accumulator: dict[str, Any] = {}
        steps: list[ReasoningStep] = []
        resolved_terms: list[ResolvedTerm] = []
        clarifications: list = []

        # Fase 0: registry de vocabulario (exp_17). Precede al matcher
        # local porque las declaraciones del grafo son más
        # informativas que la heurística de tokens sueltos.
        if self.vocabulary_registry is not None:
            self._apply_vocabulary_registry(
                tokens=tokens,
                consumed=consumed,
                domain_hint=domain_hint,
                resolved_terms=resolved_terms,
                clarifications=clarifications,
                steps=steps,
            )

        # Orden estable: por aparición en el grafo. Primero
        # extracción (tokens, pattern), luego inferencia.
        nodes = list(self.graph)

        # Fase 1: extracción.
        for node in nodes:
            strat = (node.properties or {}).get("match_strategy")
            if strat == "tokens":
                step = self._apply_tokens(node, tokens, consumed, accumulator,
                                          step_index=len(steps) + 1)
                if step is not None:
                    steps.append(step)
            elif strat == "pattern":
                step = self._apply_pattern(node, tokens, consumed, accumulator,
                                           step_index=len(steps) + 1)
                if step is not None:
                    steps.append(step)

        # Fase 2: inferencia.
        for node in nodes:
            strat = (node.properties or {}).get("match_strategy")
            if strat == "inference":
                step = self._apply_inference(node, accumulator,
                                             step_index=len(steps) + 1)
                if step is not None:
                    steps.append(step)

        unrecognized = [
            tokens[i] for i in range(len(tokens)) if i not in consumed
        ]

        problem = self._build_problem(text, accumulator)
        return LanguageParseResult(
            problem=problem,
            steps=steps,
            unrecognized_tokens=unrecognized,
            is_complete=problem is not None,
            resolved_terms=resolved_terms,
            clarification_requests=clarifications,
        )

    # -- pre-pasada del VocabularyRegistry (exp_17) -------------------

    def _apply_vocabulary_registry(
        self,
        tokens: list[str],
        consumed: set[int],
        domain_hint: str | None,
        resolved_terms: list[ResolvedTerm],
        clarifications: list,
        steps: list[ReasoningStep],
    ) -> None:
        """Recorre tokens izquierda→derecha aplicando longest-match.

        Cuando hay match:
          - 1 binding → resolver, consumir tokens, generar step.
          - >1 binding + domain_hint que matchea uno → resolver al
            preferido, consumir tokens, generar step.
          - >1 binding sin hint o hint que no coincide → emitir
            ClarificationRequest. El span NO se consume (el caller
            decide y reintenta).
        """
        registry = self.vocabulary_registry
        # Importar acá para evitar acoplar el módulo del exp_07 al
        # exp_08 cuando el registry no está siendo usado.
        from experiment_08.clarification import ClarificationRequest

        i = 0
        n = len(tokens)
        while i < n:
            if i in consumed:
                i += 1
                continue
            hit = registry.lookup_longest_match(tokens, start=i)
            if hit is None:
                i += 1
                continue
            bindings, span = hit
            span_tokens = tokens[i:i + span]
            surface_form = " ".join(t.lower() for t in span_tokens)

            chosen = self._resolve_bindings(bindings, domain_hint)

            if chosen is None:
                # Conflicto sin resolver. Emitir ClarificationRequest
                # y dejar el span sin consumir — el caller reintenta.
                options = sorted({
                    f"{b.specialist_id}:{b.node_id}" for b in bindings
                })
                clarifications.append(ClarificationRequest(
                    missing_concept=surface_form,
                    available_context={
                        "span_tokens": list(span_tokens),
                        "start_index": i,
                        "domain_hint": domain_hint,
                    },
                    options=options,
                    reason=(
                        f"forma '{surface_form}' está declarada por "
                        f"{len(bindings)} especialistas; falta "
                        f"contexto para elegir"
                    ),
                ))
                # Avanzar 1 token para no entrar en loop infinito; el
                # mismo span se podría volver a probar más adelante
                # porque el caller suele reformular el input.
                i += 1
                continue

            # Resolución exitosa — consumir el span y registrar la
            # binding elegida (quedan también guardadas las demás en
            # `bindings` para auditoría).
            for k in range(span):
                consumed.add(i + k)
            resolved_terms.append(ResolvedTerm(
                surface_form=surface_form,
                span_tokens=list(span_tokens),
                start_index=i,
                bindings=list(bindings),
            ))
            steps.append(ReasoningStep(
                index=len(steps) + 1,
                node_id=chosen.node_id,
                node_statement=(
                    f"surface form '{surface_form}' → {chosen.node_id} "
                    f"(especialista {chosen.specialist_id})"
                ),
                purpose=(
                    f"resolver forma de superficie '{surface_form}' "
                    f"vía VocabularyRegistry (exp_17)"
                ),
                inputs={"tokens": " ".join(span_tokens)},
                outputs={
                    "specialist_id": chosen.specialist_id,
                    "node_id": chosen.node_id,
                    "source_document": str(chosen.source_document),
                },
                rationale=(
                    "el nodo declaró esta forma con `**Términos:**` en "
                    "su documento; la resolución es estructural, no "
                    "estadística"
                ),
            ))
            i += span

    @staticmethod
    def _resolve_bindings(bindings, domain_hint):
        """Elige una binding entre varias. Si hay una sola, gana sin
        más. Si hay varias y el caller dio `domain_hint`, gana la
        binding cuyo specialist_id COINCIDE EXACTAMENTE con el hint
        (sin matching parcial — el hint debe nombrar al especialista).
        Si no hay forma de elegir, devuelve None — el caller emitirá
        ClarificationRequest."""
        if len(bindings) == 1:
            return bindings[0]
        if domain_hint is not None:
            for b in bindings:
                if b.specialist_id == domain_hint:
                    return b
        return None

    # -- helpers de tokenización ---------------------------------------

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        # Filtramos vacíos generados por el split sobre puntuación final.
        return [t for t in _TOKEN_SPLIT.split(text) if t]

    # -- handlers por estrategia --------------------------------------

    def _apply_tokens(
        self,
        node: KnowledgeNode,
        tokens: list[str],
        consumed: set[int],
        accumulator: dict[str, Any],
        step_index: int,
    ) -> ReasoningStep | None:
        props = node.properties
        declared = [_normalize(t) for t in props.get("tokens", [])]
        produces_template = props.get("produces", {})

        matched_tokens: list[str] = []
        matched_indices: list[int] = []
        for i, tok in enumerate(tokens):
            if i in consumed:
                continue
            if _normalize(tok) in declared:
                matched_tokens.append(tok)
                matched_indices.append(i)

        if not matched_tokens:
            return None

        # Aplicar produces — sustituye <token> por el token concreto.
        # Si un nodo matchea varios tokens distintos, sólo el primero
        # se usa para sustituir <token> (es lo que sucede con
        # target_marker.variable: si aparecen 'x' e 'y', el primero
        # gana — comportamiento determinista). Reportamos el resto
        # en el step para auditabilidad.
        produced = self._instantiate_produces(
            produces_template,
            substitutions={"<token>": matched_tokens[0]},
        )
        self._merge_into_accumulator(accumulator, produced)

        for i in matched_indices:
            consumed.add(i)

        return ReasoningStep(
            index=step_index,
            node_id=node.id,
            node_statement=node.statement,
            purpose=(
                f"reconocer tokens {matched_tokens} como rol "
                f"'{props.get('linguistic_role')}'"
            ),
            inputs={"tokens": ",".join(matched_tokens)},
            outputs={k: str(v) for k, v in produced.items()},
            rationale=node.rationale,
        )

    def _apply_pattern(
        self,
        node: KnowledgeNode,
        tokens: list[str],
        consumed: set[int],
        accumulator: dict[str, Any],
        step_index: int,
    ) -> ReasoningStep | None:
        props = node.properties
        pattern = re.compile(props["pattern"])
        produces_template = props.get("produces", {})

        # Aplicar la regex a cada token NO consumido (los datos como
        # 'a=3' suelen llegar como un único token tras la tokenización).
        captures: list[tuple[int, re.Match]] = []
        for i, tok in enumerate(tokens):
            if i in consumed:
                continue
            m = pattern.fullmatch(tok)
            if m is not None:
                captures.append((i, m))

        if not captures:
            return None

        # Combinamos todas las capturas en el produces resultante.
        # Para data_marker, esto significa acumular todas las
        # asignaciones en un solo dict 'known'.
        combined_produced: dict[str, Any] = {}
        matched_strs: list[str] = []
        for i, m in captures:
            substitutions = self._build_group_substitutions(m)
            local_produced = self._instantiate_produces(
                produces_template, substitutions=substitutions
            )
            self._merge_into_accumulator(combined_produced, local_produced)
            matched_strs.append(tokens[i])
            consumed.add(i)

        self._merge_into_accumulator(accumulator, combined_produced)

        return ReasoningStep(
            index=step_index,
            node_id=node.id,
            node_statement=node.statement,
            purpose=(
                f"extraer mediante regex {len(captures)} ocurrencia(s) "
                f"de patrón '{props.get('linguistic_role')}'"
            ),
            inputs={"matches": ",".join(matched_strs)},
            outputs={k: str(v) for k, v in combined_produced.items()},
            rationale=node.rationale,
        )

    def _apply_inference(
        self,
        node: KnowledgeNode,
        accumulator: dict[str, Any],
        step_index: int,
    ) -> ReasoningStep | None:
        props = node.properties
        requires = props.get("inference_requires", [])
        constraints = props.get("inference_constraints", {})
        produces_template = props.get("produces", {})

        # Prerequisitos.
        for key in requires:
            if key not in accumulator:
                return None

        # Constraints.
        for ckey, cval in constraints.items():
            if ckey == "known.min_entries":
                known = accumulator.get("known", {})
                if not isinstance(known, dict) or len(known) < int(cval):
                    return None
                continue
            # Constraint simple: la clave debe valer exactamente cval.
            if accumulator.get(ckey) != cval:
                return None

        # Inferencia OK — aplicar produces sin sustituciones.
        produced = self._instantiate_produces(produces_template, substitutions={})
        self._merge_into_accumulator(accumulator, produced)

        return ReasoningStep(
            index=step_index,
            node_id=node.id,
            node_statement=node.statement,
            purpose=(
                f"inferir '{props.get('linguistic_role')}' a partir "
                f"de {requires}"
            ),
            inputs={k: str(accumulator.get(k)) for k in requires},
            outputs={k: str(v) for k, v in produced.items()},
            rationale=node.rationale,
        )

    # -- helpers de produces -----------------------------------------

    @staticmethod
    def _build_group_substitutions(m: re.Match) -> dict[str, Any]:
        """Construye sustituciones <group:N> y <group:N:tipo> a partir
        de los grupos de captura de un Match.

        Las conversiones a tipo (`<group:N:float>`, `<group:N:int>`)
        son LAZY: se etiquetan con un sentinel y solo se convierten
        cuando el especialista usa esa sustitución concreta. Esto
        permite que un mismo Match tenga grupos no convertibles a
        float (p. ej. el nombre de variable `a` en `a=3`) sin que la
        construcción de sustituciones falle.
        """
        subs: dict[str, Any] = {}
        for i, val in enumerate(m.groups(), start=1):
            subs[f"<group:{i}>"] = val
            subs[f"<group:{i}:float>"] = ("__cast__", "float", val)
            subs[f"<group:{i}:int>"] = ("__cast__", "int", val)
        return subs

    @staticmethod
    def _resolve_lazy(value: Any) -> Any:
        """Resuelve sentinels de conversión lazy. Si la conversión
        falla, devuelve el valor original (el caller decide cómo
        tratar la inconsistencia)."""
        if isinstance(value, tuple) and len(value) == 3 and value[0] == "__cast__":
            _, kind, raw = value
            if raw is None:
                return None
            if kind == "float":
                return float(raw)
            if kind == "int":
                return int(raw)
        return value

    def _instantiate_produces(
        self,
        template: Any,
        substitutions: dict[str, Any],
    ) -> dict:
        """Sustituye placeholders en el dict de produces.

        Soporta sustitución recursiva sobre dicts. Las claves también
        pueden ser placeholders (caso de data_marker:
        `{"known": {"<group:1>": "<group:2:float>"}}`).
        """
        return self._sub_recursive(template, substitutions)

    def _sub_recursive(self, value: Any, subs: dict[str, Any]) -> Any:
        if isinstance(value, dict):
            out: dict = {}
            for k, v in value.items():
                new_k = subs.get(k, k) if isinstance(k, str) else k
                new_k = self._resolve_lazy(new_k)
                new_v = self._sub_recursive(v, subs)
                out[new_k] = new_v
            return out
        if isinstance(value, str):
            return self._resolve_lazy(subs.get(value, value))
        return self._resolve_lazy(value)

    @staticmethod
    def _merge_into_accumulator(acc: dict[str, Any], new: dict[str, Any]) -> None:
        """Mezcla el dict 'new' en el acumulador.

        Para clave 'known' (dict), acumula entradas en lugar de
        sobrescribir. Para el resto, sobrescritura simple — los nodos
        del grafo no deberían producir conflictos sobre la misma
        clave; si lo hicieran, gana el último.
        """
        for k, v in new.items():
            if k == "known" and isinstance(v, dict):
                existing = acc.get("known")
                if isinstance(existing, dict):
                    merged = dict(existing)
                    merged.update(v)
                    acc["known"] = merged
                else:
                    acc["known"] = dict(v)
            else:
                acc[k] = v

    # -- construcción del Problem ------------------------------------

    @staticmethod
    def _build_problem(text: str, acc: dict[str, Any]) -> Problem | None:
        """Construye un Problem si el acumulador tiene los campos
        mínimos: target, kind, known, instruction.

        Si falta alguno, devuelve None y el caller verá
        `is_complete=False` para diagnosticar qué pieza no se
        produjo.
        """
        target = acc.get("target")
        kind = acc.get("kind")
        known = acc.get("known")
        if not (isinstance(target, str) and isinstance(kind, str)
                and isinstance(known, dict)):
            return None
        return Problem(
            statement=text,
            target=target,
            context=DomainContext(kind=kind, known=dict(known)),
        )
