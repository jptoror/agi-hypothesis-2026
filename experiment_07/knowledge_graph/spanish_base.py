"""Grafo base del especialista de lenguaje español.

Usa la MISMA estructura `KnowledgeNode` que el resto del proyecto.
Cada nodo declara conocimiento lingüístico explícito mediante
`properties`. No hay NLP ni stemming: el matching es estricto sobre
tokens declarados o sobre patrones regex declarados.

Schema de propiedades por nodo:

  linguistic_role: str
      Rol semántico que el nodo reconoce. Valores:
        - "instruction_marker"  → produces['instruction'] = ...
        - "target_marker"       → produces['target']      = <token>
        - "data_marker"         → produces['known']       = {<var>: <num>}
        - "query_marker"        → produces['query_type']  = ...
        - "kind_inference"      → produces['kind']        = ...

  match_strategy: str   in {"tokens", "pattern", "inference"}

  tokens: list[str]
      Para match_strategy='tokens': lista cerrada de strings.
      Comparación case-insensitive después de normalizar tildes.

  pattern: str
      Para match_strategy='pattern': regex declarada explícitamente.

  produces: dict
      Lo que el nodo aporta al Problem si matchea. Las claves son
      campos del Problem/DomainContext. Para data_marker, 'known' es
      un dict acumulable. Para target_marker e inference, los valores
      pueden incluir el placeholder '<token>' o '<match>' que el
      especialista sustituye con el texto reconocido.

  inference_requires: list[str]
      Para match_strategy='inference': lista de claves que ya deben
      existir en el Problem en construcción para disparar la regla.

El especialista interpreta estos campos sin lógica oculta: lee tokens
del nodo, comprueba presencia, aplica produces. Todo auditable.
"""
from __future__ import annotations

from experiment_01.knowledge_graph import (
    EpistemicStatus,
    KnowledgeGraph,
    KnowledgeNode,
    NodeKind,
)


def build_spanish_base_graph() -> KnowledgeGraph:
    g = KnowledgeGraph()

    # ========== AXIOMA LINGÜÍSTICO ==========
    # Único axioma: el español tiene tokens separables por espacios y
    # puntuación. No es derivable, lo aceptamos como base operativa.
    g.add(KnowledgeNode(
        id="ax.spanish.tokenizable",
        statement=(
            "Una instrucción en español puede descomponerse en tokens "
            "separados por espacios, comas, puntos y signos de "
            "puntuación. Los tokens son la unidad mínima de "
            "reconocimiento de este especialista."
        ),
        status=EpistemicStatus.AXIOM,
        kind=NodeKind.RELATION,
        rationale=(
            "El especialista trabaja con vocabulario cerrado. Sin un "
            "criterio de tokenización no hay unidad sobre la que aplicar "
            "el lookup. Tokenizamos por whitespace + puntuación común."
        ),
    ))

    # ========== INSTRUCTION_MARKER ==========
    g.add(KnowledgeNode(
        id="def.instruction.solve",
        statement=(
            "Los verbos 'resuelve', 'calcula' y 'halla' marcan una "
            "instrucción de tipo 'solve' — pedir el valor de una "
            "incógnita."
        ),
        status=EpistemicStatus.DEFINITION,
        kind=NodeKind.CONCEPT,
        foundations=["ax.spanish.tokenizable"],
        properties={
            "linguistic_role": "instruction_marker",
            "match_strategy": "tokens",
            "tokens": ["resuelve", "calcula", "halla"],
            "produces": {"instruction": "solve"},
        },
        rationale=(
            "Vocabulario cerrado declarado por el ingeniero. No hay "
            "stemming ni lematización: 'resolver' no matchearía a menos "
            "que se añada explícitamente."
        ),
    ))

    # ========== TARGET_MARKER ==========
    g.add(KnowledgeNode(
        id="def.target_marker.variable",
        statement=(
            "Los símbolos 'x', 'y', 'z' aislados en la instrucción "
            "indican la variable objetivo de la resolución."
        ),
        status=EpistemicStatus.DEFINITION,
        kind=NodeKind.CONCEPT,
        foundations=["ax.spanish.tokenizable"],
        properties={
            "linguistic_role": "target_marker",
            "match_strategy": "tokens",
            "tokens": ["x", "y", "z"],
            # El placeholder '<token>' lo sustituye el especialista con
            # el token concreto que matcheó (p. ej. 'x').
            "produces": {"target": "<token>"},
        },
        rationale=(
            "Convención matemática: las últimas letras del alfabeto se "
            "usan para incógnitas. Lista cerrada — si aparece 'w' o 't' "
            "como variable, hay que añadirlas aquí."
        ),
    ))

    # ========== DATA_MARKER ==========
    g.add(KnowledgeNode(
        id="def.data.assignment",
        statement=(
            "Una asignación de la forma '<var>=<número>' aporta un dato "
            "conocido al contexto del problema. Ejemplo: 'a=3' indica "
            "que la variable 'a' vale 3."
        ),
        status=EpistemicStatus.DEFINITION,
        kind=NodeKind.RELATION,
        foundations=["ax.spanish.tokenizable"],
        properties={
            "linguistic_role": "data_marker",
            "match_strategy": "pattern",
            # Regex declarada en el nodo — auditable. Captura
            # var (identificador) y num (entero o decimal, opcional signo).
            "pattern": r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(-?\d+(?:\.\d+)?)",
            # El especialista interpreta estos placeholders extrayendo
            # los grupos de captura y construyendo {known: {<var>: <num>}}.
            "produces": {"known": {"<group:1>": "<group:2:float>"}},
        },
        rationale=(
            "Las asignaciones no son tokens simples — son micro-expresiones. "
            "El especialista trata pattern-based como una segunda estrategia "
            "de matching, distinta de la de tokens, pero igualmente "
            "declarada en el grafo (no en código)."
        ),
    ))

    # ========== QUERY_MARKER ==========
    g.add(KnowledgeNode(
        id="def.query_type.numeric",
        statement=(
            "Las palabras 'cuánto' y 'cuanto' marcan una pregunta de "
            "respuesta numérica."
        ),
        status=EpistemicStatus.DEFINITION,
        kind=NodeKind.CONCEPT,
        foundations=["ax.spanish.tokenizable"],
        properties={
            "linguistic_role": "query_marker",
            "match_strategy": "tokens",
            "tokens": ["cuánto", "cuanto"],
            "produces": {"query_type": "numeric"},
        },
        rationale=(
            "No se usa en el problema canónico del exp_07 ('resuelve x "
            "para a=3, b=6'), pero forma parte del vocabulario base "
            "para futuros problemas tipo '¿cuánto vale x si...?'."
        ),
    ))

    # ========== KIND_INFERENCE ==========
    g.add(KnowledgeNode(
        id="def.kind.linear_equation",
        statement=(
            "Si una instrucción contiene un marcador de instrucción "
            "'solve', un marcador de variable objetivo y al menos una "
            "asignación numérica, el contexto resultante es de tipo "
            "'linear_equation'."
        ),
        status=EpistemicStatus.DEFINITION,
        kind=NodeKind.RELATION,
        foundations=[
            "def.instruction.solve",
            "def.target_marker.variable",
            "def.data.assignment",
        ],
        properties={
            "linguistic_role": "kind_inference",
            "match_strategy": "inference",
            # Claves que ya deben haberse extraído antes de disparar
            # la regla. Si alguna falta, la inferencia no aplica.
            "inference_requires": ["instruction", "target", "known"],
            # Se exige además que `instruction == "solve"` y que `known`
            # tenga al menos una entrada — eso lo evalúa el especialista
            # leyendo `inference_constraints` declarado abajo.
            "inference_constraints": {
                "instruction": "solve",
                "known.min_entries": 1,
            },
            "produces": {"kind": "linear_equation"},
        },
        rationale=(
            "La inferencia de kind vive en el grafo, no en código. Si "
            "más adelante reconocemos otros kinds (cuadrática, sistemas, "
            "etc.), se añaden como nuevos nodos sin tocar el especialista."
        ),
    ))

    return g
