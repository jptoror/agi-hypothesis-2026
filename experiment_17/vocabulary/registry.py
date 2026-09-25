"""VocabularyRegistry — índice forma_normalizada → bindings.

Hipótesis del experimento: el vocabulario es ESTRUCTURA del nodo,
no inferencia sobre el token. Cada `KnowledgeNode` declara las
formas de superficie por las que puede ser referenciado en lenguaje
natural — el registry agrega esas declaraciones cuando los
especialistas se registran y las expone para consulta.

Reglas:
  - Normalización mínima: lowercase + strip + colapso de espacios
    internos. NO se quitan tildes — "voraz" y "vóraz" son palabras
    distintas y deben declararse independientemente si ambas valen.
  - `register` es IDEMPOTENTE por `specialist_id`: re-registrar el
    mismo especialista REEMPLAZA sus bindings (no acumula). Esto
    soporta hot-reload sin duplicar.
  - Conflictos (varias bindings para la misma forma) NO se resuelven
    aquí — el lookup retorna todas. La resolución es responsabilidad
    del orquestador (mecanismo `ClarificationRequest` del exp_08).
  - Entradas malformadas (no-string, vacías) se ignoran SILENCIOSAMENTE
    — no se considera error porque las surface_forms son metadatos
    declarativos opcionales, no parte del contrato del nodo.

`lookup_longest_match` aplica la regla del span más largo: sobre una
secuencia de tokens, prueba primero la ventana más larga posible
(acotada por `_max_token_len`) y va decreciendo. Esto evita romper
"coloreado voraz" en dos hits sueltos cuando ambos hijos también
están registrados.
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

from .bindings import VocabularyBinding

if TYPE_CHECKING:
    from experiment_01.knowledge_graph import KnowledgeGraph


_WHITESPACE = re.compile(r"\s+")


def normalize(phrase: str) -> str:
    """Normaliza una frase para indexación y lookup.

    Reglas: lowercase + strip + colapso de runs de whitespace a un
    único espacio. NO toca acentos. NO toca puntuación interna —
    si una declaración la incluye, debe matchearse exactamente.
    """
    if not isinstance(phrase, str):
        return ""
    return _WHITESPACE.sub(" ", phrase.strip().lower())


class VocabularyRegistry:
    """Índice centralizado de formas de superficie declaradas."""

    def __init__(self) -> None:
        # forma_normalizada → lista de bindings (orden de registro).
        self._index: dict[str, list[VocabularyBinding]] = {}
        # specialist_id → set de formas que declaró (para unregister).
        self._by_specialist: dict[str, set[str]] = {}
        # Cache de la longitud máxima en tokens — acota la ventana del
        # longest-match. Se recomputa lazy en register/unregister.
        self._max_token_len: int = 0

    # -- API pública --------------------------------------------------

    def register(
        self,
        specialist_id: str,
        graph: "KnowledgeGraph",
        source_document: str | None = None,
    ) -> int:
        """Registra (o re-registra) las formas declaradas en `graph`.

        Si `specialist_id` ya estaba registrado, primero hace
        unregister — la operación es idempotente. Devuelve el número
        de formas indexadas para este especialista (no de bindings
        agregadas; si una forma ya estaba para otro especialista,
        cuenta como agregada acá también).
        """
        if specialist_id in self._by_specialist:
            self.unregister(specialist_id)

        registered: set[str] = set()
        for node in graph:
            forms = (node.properties or {}).get("surface_forms", [])
            if not isinstance(forms, list):
                # Defensivo: si alguien puso un string suelto u otra
                # forma, ignoramos sin lanzar — surface_forms es
                # opcional por contrato.
                continue
            for raw in forms:
                if not isinstance(raw, str):
                    continue
                form = normalize(raw)
                if not form:
                    continue
                binding = VocabularyBinding(
                    specialist_id=specialist_id,
                    node_id=node.id,
                    source_document=source_document,
                )
                self._index.setdefault(form, []).append(binding)
                registered.add(form)

        self._by_specialist[specialist_id] = registered
        self._recompute_max_len()
        return len(registered)

    def unregister(self, specialist_id: str) -> int:
        """Quita TODAS las bindings de `specialist_id` del índice.

        Devuelve el número de formas que el especialista tenía
        registradas (0 si no estaba).
        """
        forms = self._by_specialist.pop(specialist_id, None)
        if forms is None:
            return 0
        for form in forms:
            bindings = self._index.get(form, [])
            remaining = [b for b in bindings if b.specialist_id != specialist_id]
            if remaining:
                self._index[form] = remaining
            else:
                self._index.pop(form, None)
        self._recompute_max_len()
        return len(forms)

    def lookup(self, phrase: str) -> list[VocabularyBinding]:
        """Devuelve las bindings asociadas a `phrase` (normalizada).

        Lista vacía si la forma no está registrada o `phrase` es
        vacía/whitespace. Si varios especialistas declaran la misma
        forma, devuelve todas — la resolución de conflicto es del
        caller (típicamente el orquestador con ClarificationRequest).
        """
        form = normalize(phrase)
        if not form:
            return []
        return list(self._index.get(form, []))

    def lookup_longest_match(
        self,
        tokens: list[str],
        start: int = 0,
    ) -> tuple[list[VocabularyBinding], int] | None:
        """Sobre `tokens`, busca el span más largo desde `start` que
        coincida con una forma registrada.

        Retorna `(bindings, span_length_in_tokens)` o `None` si
        ningún span coincide. Itera desde la ventana más larga
        (`_max_token_len` o `len(tokens) - start`, lo que sea menor)
        hacia 1. Esto asegura que "coloreado voraz" gane sobre
        "coloreado" cuando ambos están registrados — el principio
        es "el span más informativo".
        """
        n = len(tokens)
        if start < 0 or start >= n or self._max_token_len == 0:
            return None
        max_len = min(self._max_token_len, n - start)
        for span in range(max_len, 0, -1):
            phrase = " ".join(tokens[start:start + span])
            bindings = self.lookup(phrase)
            if bindings:
                return (bindings, span)
        return None

    def specialists(self) -> set[str]:
        return set(self._by_specialist.keys())

    def surface_forms(
        self,
        specialist_id: str | None = None,
    ) -> list[str]:
        """Devuelve todas las formas registradas, opcionalmente
        filtradas por especialista. Orden estable (alfabético) para
        que los tests sean determinísticos."""
        if specialist_id is None:
            return sorted(self._index.keys())
        return sorted(self._by_specialist.get(specialist_id, set()))

    def __len__(self) -> int:
        return len(self._index)

    # -- helpers internos --------------------------------------------

    def _recompute_max_len(self) -> None:
        """Recalcula la longitud máxima en tokens — acota el span
        del longest-match. Una forma vacía cuenta como 0."""
        if not self._index:
            self._max_token_len = 0
            return
        self._max_token_len = max(
            len(form.split(" ")) for form in self._index
        )


# Singleton compartido por todo el proyecto. Los especialistas que
# se construyen vía SpecialistFactory se registran aquí por defecto;
# tests que necesiten aislamiento pueden inyectar otra instancia.
DEFAULT_REGISTRY = VocabularyRegistry()
