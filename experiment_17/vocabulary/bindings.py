"""VocabularyBinding — par (especialista, nodo) que cubre una forma
de superficie declarada.

El registry mapea forma normalizada → lista de bindings. Cada binding
identifica EXACTAMENTE de dónde viene el reconocimiento de esa forma:
qué especialista lo declaró y en qué nodo. `source_document` es
opcional porque no todos los especialistas se construyen desde un
documento (los del exp_01 nacen en código). Cuando está, permite la
trazabilidad completa surface_form → documento → nodo.

Frozen para que sea hashable y reusable como elemento de sets.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VocabularyBinding:
    specialist_id: str
    node_id: str
    source_document: str | None = None
