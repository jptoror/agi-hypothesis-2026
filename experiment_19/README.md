# Experiment 19 — Persistencia completa con memoria episódica

## Hipótesis

Un sistema basado en derivación verificada puede mantener memoria
conversacional persistente **sin** introducir componentes
estadísticos. La conversación es un grafo episódico del sistema,
con nodos tipados y foundations explícitas, sometido a las mismas
reglas epistémicas que cualquier otro grafo. La persistencia es
total: apagar el sistema y volver a levantarlo reproduce el estado
exacto, incluyendo conversaciones en curso.

## Alcance

**Dentro del scope:**
- Capa 1 — serializer estricto de `KnowledgeGraph`
  (`format_version: "1.0"`, errores explícitos, `compute_ref`
  vía `ProcedureRefRegistry`).
- Capa 2 — `SystemManifest` con todos los especialistas, con
  escritura atómica por archivo (`.tmp` + `os.replace`).
- Capa 3.1 — `Session` con `turns`, `conversation_graph`,
  `active_context` y persistencia automática por turno.
- Capa 3.2 — `ActiveContext` serializable: `last_specialist_id`,
  `active_bindings` (cross-graph refs), `domain_hints` con FIFO
  configurable, idle-timeout por binding.
- Reconstrucción del `VocabularyRegistry` desde los grafos
  cargados — sin persistirlo como índice aparte.

**Fuera del scope (reservado para experimentos futuros):**
- Vocabulario introducido por el usuario ("llamemos H a este
  subgrafo") — exp_20.
- Estado epistémico de la conversación (hipótesis, gaps) — exp_20.
- Consolidación episódica → semántica — exp_21/22. El campo
  `promotion_candidate: bool` ya está reservado en cada nodo del
  conversation_graph para que esa funcionalidad no requiera
  migración de datos.

## Componentes

```
experiment_19/
├── README.md
├── orchestrator.py              SessionOrchestrator (start/resume/process/end)
├── persistence/
│   ├── serialization.py         serialize/deserialize_{graph,node} + ProcedureRefRegistry
│   └── manifest.py              SystemManifest + save_system + load_system + LoadedSystem
├── conversation/
│   ├── active_context.py        ActiveContext + ContextResetReason
│   ├── conversation_graph.py    cross_graph_foundation + promotion_candidate helpers
│   └── session.py               Session + Turn + save_session + load_session
└── tests/                       54 tests (serialization, manifest, session, active_context, integration)
```

## Decisiones de diseño

1. **`format_version: "1.0"` como string.** Distingue
   explícitamente del `schema_version: 1` (int) de exp_02 — los
   dos coexisten sin colisión.

2. **`compute_ref` por nombre de procedure.** El callable no se
   serializa; sí se serializa el nombre que el `GraphBuilder` ya
   guarda en `properties["procedure_name"]`. La resolución pasa
   por `ProcedureRefRegistry`, un índice global que el caller
   puebla con las bibliotecas del exp_06 + exp_16 (helper
   `register_procedures_from`).

3. **Cero degradación silenciosa.** `properties` con valor no
   JSON-nativo → `UnsupportedPropertyError`. Manifest sin
   `format_version` → `UnsupportedSchemaError`. Clase no
   importable → `ManifestError`. Procedure no resoluble →
   `ProcedureNotResolvableError`. Todos llevan kind/target en el
   payload del error para diagnóstico.

4. **Atomicidad por archivo.** Cada archivo se escribe a `.tmp`
   en el mismo directorio y se promueve con `os.replace`. NO hay
   transacción multi-archivo: si el proceso muere a mitad de un
   `save_system`, el `manifest.json` puede quedar apuntando a un
   grafo no escrito. Limitación honesta y declarada — el caller
   que necesite garantía total puede orquestar un backup previo.

5. **`conversation_graph` no es un tipo nuevo.** Es un
   `KnowledgeGraph` normal con dos convenciones de uso:
   - Foundations a otros grafos se codifican con
     `cross_graph_foundation("alg_demo", "alg.greedy_coloring")`
     → `"alg_demo::alg.greedy_coloring"`. Como
     `KnowledgeGraph.add()` rechaza foundations no existentes en
     el mismo grafo, los refs cross-graph viven en
     `properties["external_foundations"]` y se reconstituyen al
     consultar.
   - Cada nodo lleva `properties["promotion_candidate"]: bool` con
     default `False`. Reservado para exp_21/22.

6. **Resolución anafórica DECLARATIVA.** Sin embeddings, sin
   similitud, sin búsqueda borrosa. El orquestador conoce un
   conjunto cerrado de patrones (`"el grafo de antes"`,
   `"(la|su) complejidad"`, etc.) y los resuelve contra
   `active_bindings`. Conflicto sin desempate →
   `ClarificationRequest` (exp_08). El usuario controla qué se
   reconoce; agregar un patrón nuevo es un cambio de código
   declarado, no inferencia.

## Demo de evidencia

Sesión real con dos especialistas (`alg_terms` de exp_17 aporta
vocabulario; `alg_expr` de exp_18 aporta plantillas `**Expresión:**`
y el teorema de complejidad). Output literal del runner real:

```text
=== [Sesión iniciada] session_707d0a5fa9f0 ===

[Sesión 1, turno 1]
> calculá el coloreado voraz del grafo G
< Asigna colores a los vértices de un grafo usando una
  heurística voraz: para cada vértice, elige el color de
  menor índice que no colisione con sus vecinos. Un grafo
  es un par (V, E) de vértices y aristas.
  active_bindings: {
    'alg_0': 'alg_terms::alg.greedy_coloring',
    'def_1': 'alg_terms::def.grafo',
  }

=== [Sistema apagado y reiniciado] ===

[Sesión 1 retomada, turno 2]
> ahora calculá la complejidad
< la complejidad del coloreo greedy es a lo sumo m³
  operaciones, donde m es el número de vértices del grafo
  trace.steps:
    - alg_expr:thm.greedy_coloring.complejidad
```

**Evidencia clave:** el turno 2 se procesa **después de un reinicio
total del sistema** (todo `del`ed + `gc.collect()` + reconstruir
todo desde disco). Aún así:

- Reconoce el patrón anafórico `(la|su) complejidad`.
- Camina desde el `alg_0` binding (cargado desde disco) al
  algoritmo `alg.greedy_coloring`.
- Atraviesa especialistas: busca `thm.greedy_coloring.complejidad`
  en `alg_expr` (otro grafo), porque la convención cross-graph se
  preservó.
- Renderea la respuesta con el `ExpressionRenderer` del exp_18,
  que también se reconstruye desde el grafo cargado.

La trazabilidad es completa: `trace.steps[0].node_id` apunta
exactamente al nodo que fundamenta la oración.

## Cosas que NO hay

- ❌ Embeddings, similitud, vector search.
- ❌ Decaimiento por frecuencia.
- ❌ Vocabulario conversacional dinámico ("llamemos H a...").
- ❌ Degradación silenciosa: todo fallo es excepción tipada.
- ❌ Abstracción especial para `conversation_graph`: es un
  `KnowledgeGraph` normal con convenciones de uso documentadas.

## Tests

54 tests en `experiment_19/tests/`:

| archivo | tests |
|---|---|
| `test_serialization.py` | 14 (round-trip, properties estrictas, compute_ref, format_version) |
| `test_manifest.py` | 10 (save/load, idempotencia, atomic write, errores) |
| `test_session.py` | 13 (Session+Turn+cross_graph_foundation+promotion_candidate) |
| `test_active_context.py` | 14 (hints, bindings, tick, expiración, reset) |
| `test_integration.py` | 3 (full cycle con restart, persistencia per-turn, registry reconstruido) |

Suite total del proyecto: **282/282 verde** (228 previos + 54
nuevos). Cero regresiones.
