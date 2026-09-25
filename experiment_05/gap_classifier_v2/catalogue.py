"""Catálogo epistemológico — declarado como CONOCIMIENTO DE DISEÑO.

Este catálogo es conocimiento del INGENIERO sobre el dominio del
experimento. No es capacidad emergente del sistema. Es el mapa explícito
de "por qué cada una de las 8 semillas canónicas no está en los grafos".

Cada entrada justifica el tipo asignado y declara explícitamente que
quien clasifica es un humano. El GapClassifierV2 lee este catálogo y
transfiere la justificación al resultado final — preservando trazabilidad
de AUTORÍA: nada de lo que produce el clasificador puede atribuirse al
sistema, porque el catálogo lo trae el ingeniero.

Esto hace explícita una propiedad del experimento 05 que debe entrar al
paper: clasificar POR QUÉ algo no se sabe requiere conocimiento previo
sobre POR QUÉ no se sabe, un problema circular. Ver FINDINGS.md #02.
"""
from __future__ import annotations

from dataclasses import dataclass

from .gap_type import EpistemicGapType


@dataclass(frozen=True)
class CatalogueEntry:
    gap_type: EpistemicGapType
    justification: str
    # Ruta o condición que cerraría este gap, en términos concretos.
    # None para PHILOSOPHICAL_GAP (no cerrable desde ingeniería).
    resolvable_path: str | None
    # Siempre "ingeniero" para las entradas de este catálogo — quien
    # clasifica es un humano que declara el tipo. Dejarlo como campo
    # en vez de constante obliga a confirmarlo en cada entrada.
    classified_by: str = "ingeniero"


# Catálogo canónico correspondiente a las 8 semillas del experimento 05.
# Cada justificación refleja el razonamiento epistémico del ingeniero —
# no es emergente ni descubierta por el sistema.
CANONICAL_CATALOGUE: dict[str, CatalogueEntry] = {
    "sistema": CatalogueEntry(
        gap_type=EpistemicGapType.MISSING_CONCEPT,
        justification=(
            "Existe como concepto informal en el código (clases, "
            "módulos) pero no como nodo epistemológico en ningún "
            "grafo. Cerrarlo significaría introducir 'sistema' como "
            "nodo formal con propiedades y relaciones."
        ),
        resolvable_path=(
            "añadir un grafo meta con nodos def.sistema, "
            "def.componente, def.arquitectura — modelar formalmente "
            "la propia estructura del proyecto."
        ),
    ),
    "entendimiento": CatalogueEntry(
        gap_type=EpistemicGapType.PHILOSOPHICAL_GAP,
        justification=(
            "Requiere distinguir operacionalmente procesamiento de "
            "comprensión. Ese problema precede a cualquier solución "
            "técnica — lo han formulado Searle, Dreyfus, Harnad y "
            "otros sin consenso. No es un gap cerrable por el "
            "sistema; depende de progreso en filosofía de la mente."
        ),
        resolvable_path=None,
    ),
    "comprensión": CatalogueEntry(
        gap_type=EpistemicGapType.PHILOSOPHICAL_GAP,
        justification=(
            "Mismo cluster filosófico que 'entendimiento'. Sin una "
            "teoría operativa de qué significa comprender — "
            "distinta de computar — cualquier nodo que se añadiera "
            "sería etiqueta vacía."
        ),
        resolvable_path=None,
    ),
    "procesamiento": CatalogueEntry(
        gap_type=EpistemicGapType.MISSING_CONCEPT,
        justification=(
            "Existe operacionalmente en los grafos — los `compute` "
            "de los nodos ejecutables SON procesamiento — pero no "
            "hay nodo formal que describa qué es procesar. "
            "Cerrable en principio."
        ),
        resolvable_path=(
            "añadir nodo def.compute con properties sobre pureza, "
            "determinismo, dominio de entrada y salida."
        ),
    ),
    "genuino": CatalogueEntry(
        gap_type=EpistemicGapType.PHILOSOPHICAL_GAP,
        justification=(
            "No hay criterio operativo para distinguir 'genuino' de "
            "'simulado'. Es la pregunta que Turing sustituyó por un "
            "test conductual — precisamente porque la versión "
            "original no tiene solución técnica."
        ),
        resolvable_path=None,
    ),
    "razonamiento": CatalogueEntry(
        gap_type=EpistemicGapType.FRONTIER_GAP,
        justification=(
            "El sistema EJERCE razonamiento (backward chaining del "
            "especialista) pero no lo modela sobre sí mismo. Existe "
            "en la frontera entre implementación y autodescripción. "
            "Cerrable con meta-modelado."
        ),
        resolvable_path=(
            "crear un grafo meta-razonamiento que describa las "
            "operaciones del propio especialista como nodos "
            "(def.backward_chaining, def.derivacion, etc.)."
        ),
    ),
    "conocimiento": CatalogueEntry(
        gap_type=EpistemicGapType.FRONTIER_GAP,
        justification=(
            "El sistema tiene `EpistemicStatus` (axioma/definición/"
            "teorema/hipótesis) pero no una teoría formal de qué es "
            "conocimiento. Ejerce una epistemología sin explicitarla."
        ),
        resolvable_path=(
            "formalizar la epistemología implícita: nodos "
            "def.conocimiento, def.justificacion, def.verdad, "
            "relacionados con los EpistemicStatus existentes."
        ),
    ),
    "consciencia": CatalogueEntry(
        gap_type=EpistemicGapType.PHILOSOPHICAL_GAP,
        justification=(
            "El problema difícil de Chalmers. Ningún sistema técnico "
            "conocido lo ha resuelto. Añadir un nodo no cerraría el "
            "gap — lo enmascararía."
        ),
        resolvable_path=None,
    ),
}
