# Experiment 20 — Vocabulario y estado epistémico conversacional

## Hipótesis

Un sistema basado en derivación verificada puede mantener
vocabulario introducido **dinámicamente** por el usuario y estado
epistémico de la conversación **sin** componentes estadísticos. Los
símbolos del usuario son nodos del `conversation_graph` con
`surface_forms` declaradas; el estado epistémico es estructura
tipada (afirmaciones, hipótesis, gaps, clarificaciones, acuerdos)
con `turn_id` de origen y trazabilidad completa.

## Decisiones de diseño

1. **El vocabulario conversacional vive en el `conversation_graph`
   como nodos `DEFINITION` (o `HYPOTHESIS` si no resuelven
   foundations).** No es un mapa lateral.

2. **Registry de sesión separado del global.** Vive en `Session`,
   se persiste *como parte del conversation_graph* (no como índice
   propio) y se reconstruye en cada `resume_session`. Resolución:
   local gana sobre global en empates.

3. **Cuatro patrones de definición declarados** en
   `patterns/definition_patterns.py`:
   - `def_pat.llamemos`  → "llamemos X a Y"
   - `def_pat.sea_igual` → "sea X = Y" / "sea X igual a Y"
   - `def_pat.definamos` → "definamos X como Y"
   - `def_pat.representa` → "X representa Y"

4. **Redefinición → `ClarificationRequest` del exp_08.** El
   sistema NO sobrescribe silenciosamente.

5. **Una `Affirmation` por turno respondido.** Granularidad fina
   (paso a paso) queda como mejora futura, no contradicción.

6. **Cero inferencia automática.** `detect_inconsistency` es
   comparación exacta entre `asserted_entities`. No hay reglas
   "si A y A⇒B entonces B". El sistema registra; no propaga.

## Componentes

```
experiment_20/
├── README.md
├── orchestrator.py                 EpistemicSessionOrchestrator (subclase del exp_19)
├── vocabulary/
│   └── session_registry.py         SessionVocabularyRegistry + FallbackVocabularyView
├── patterns/
│   └── definition_patterns.py      4 patrones + match_definition()
├── conversation/
│   └── definition_handler.py       DefinitionAccepted/Conflict/Rejected
├── epistemic/
│   └── state.py                    EpistemicState + Affirmation/Hypothesis/Gap/Clarification/Agreement
└── tests/                          53 tests
```

Cambios mínimos al exp_19 (retro-compatibles):

- `experiment_19/conversation/session.py` — `Session` añade
  `epistemic_state` (serializable) y `session_registry`
  (reconstruible, no serializado). Defaults `None`; sesiones
  persistidas en exp_19 sin estos campos se cargan con estado
  vacío (migración silenciosa, declarada en el spec).

## Demo de evidencia (output literal del runner real)

```text
=== sesión session_7f1ed92ac2c8 ===

[T1] definamos G como un grafo con vértices 1,2,3,4
     y aristas (1,2),(2,3),(3,4),(4,1)
<    Definido G como un grafo con vértices 1,2,3,4 ...
     Vocabulario de sesión: "G", "el grafo G".
     conv:def.G surface_forms: ['G', 'el grafo G']
     conv:def.G foundations: []

[T2] llamemos H a G sin el vértice 4
<    Definido H como G sin el vértice 4.
     Vocabulario de sesión: "H", "el grafo H".
     conv:def.H surface_forms: ['H', 'el grafo H']      ← herencia estructural
     conv:def.H foundations: ['conv:def.G']

=== sistema apagado y reiniciado ===

[T3] cuál es el coloreado voraz de H
<    Asigna colores a los vértices de un grafo usando
     una heurística voraz: para cada vértice, elige el
     color de menor índice que no colisione con sus vecinos.
     resolved_terms:
       coloreado voraz  → alg_terms:alg.greedy_coloring
       h                → session:conv:def.H

epistemic_state.agreements:
  · G = un grafo con vértices 1,2,3,4 y aristas ...
  · H = G sin el vértice 4
epistemic_state.affirmations:
  · turn_0003 {alg.bound_node: alg.greedy_coloring,
               conv:def.bound_node: conv:def.H}
```

**Evidencia clave:**

- T2 hereda la categoría `"grafo"` de G *estructuralmente*: G ya
  declaró `surface_forms = ["G", "el grafo G"]`, y como H depende
  de G (foundation local), `_inherit_category_from_foundation`
  lee la surface form `"el grafo G"` y propaga `"el grafo H"`.
  Ninguna inferencia semántica — pura lectura del grafo previo.

- T3 ocurre **después de un reinicio total del sistema**. El
  `session_registry` no se persiste como índice; se reconstruye
  desde el `conversation_graph` cargado. Aun así, "H" resuelve a
  `session:conv:def.H` (local), "coloreado voraz" cae al global
  vía `FallbackVocabularyView`, y la respuesta se compone con
  ambos en la misma traza.

## Decisión sobre los patrones de definición

El spec menciona como ejemplo *"sea G un grafo con vértices..."*.
Esa frase NO coincide con ninguno de los 4 patrones declarados
(`def_pat.sea_igual` exige `=` o `igual a`). Tomé la decisión
honesta de **no extender el patrón silenciosamente** y usar
`definamos G como un grafo con vértices ...` en el integration
test, que sí está cubierto por `def_pat.definamos`. Agregar un
quinto patrón "sea X <body>" es un cambio de política explícito
que dejo para una iteración futura — declarar un patrón nuevo es
un cambio explícito de comportamiento, no un detalle de
implementación.

## Tests (53/53 verde)

| archivo | tests |
|---|---|
| `test_session_registry.py` | 11 (build, fallback, longest match, round-trip JSON) |
| `test_definition_patterns.py` | 16 (4 patrones, capitalización, whitespace, orden) |
| `test_definition_handler.py` | 8 (accepted, conflict, rejected, herencia de categoría) |
| `test_epistemic_state.py` | 13 (record, transition, inconsistency, gap resolution, round-trip) |
| `test_inconsistency.py` | 2 (no bloquea, payload con turn_id previo) |
| `test_gap_resolution.py` | 3 (gap registrado, especialista resuelve, no-match) |
| `test_integration.py` | 1 (ciclo completo con restart entre T2 y T3) |

Suite total del proyecto: **335/335 verde** (282 anteriores + 53
nuevos). Cero regresiones.

## Lo que NO hay

- ❌ Reglas de inferencia automática sobre estado epistémico.
- ❌ Embeddings o similitud para detectar inconsistencia.
- ❌ Autocorrección de afirmaciones inconsistentes (solo notifica).
- ❌ Memoria entre sesiones distintas (reservado).
- ❌ Degradación silenciosa: redefinición sin confirmación, body
  vacío, símbolo conflictivo — todos generan respuesta explícita.
