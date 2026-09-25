# Experiment 21 — Herramienta de autoría operable

## Qué resuelve

Hasta exp_20, registrar un nuevo dominio en el sistema requería
escribir Python: instanciar `SpecialistFactory`, conocer el nombre
del archivo, manejar `base_graph` para cross-refs, llamar
`save_system`. Stack traces si algo fallaba. No escala.

Este experimento añade **un CLI de autoría** (`agi-author`) que:

- Lee un documento markdown con los marcadores del sistema.
- Lo valida exhaustivamente y reporta TODOS los issues a la vez,
  con número de línea, fragmento del documento y sugerencia.
- Genera un preview del especialista (qué nodos, qué surface
  forms, qué cross-refs) **antes** de persistir.
- Persiste atómicamente al directorio `agi_data/` en el formato
  del exp_19, con copia del documento fuente para auditabilidad.
- Maneja `list` / `show` / `remove` / `reload`.

**No agrega capacidades al motor.** Es una capa de operación
encima del motor existente.

## Decisiones de diseño

1. **CLI primero, no web.** Suficiente para uso interno.
2. **Validación exhaustiva, no incremental.** Todos los errores
   en una pasada.
3. **Preview obligatorio antes de persistir.** El autor ve qué se
   va a construir, en orden de líneas del documento.
4. **Mensajes en castellano para autores, no para programadores.**
   Cero stack traces en operación normal.
5. **Idempotencia.** `build --overwrite` reproduce el mismo
   `graphs/<id>.json` byte-a-byte.
6. **Conflictos con registry global = warning, no error.** El
   autor puede continuar; el sistema delegará al usuario en
   runtime vía `ClarificationRequest` (mecanismo del exp_08).

## Componentes

```
experiment_21/
├── README.md
├── authoring/
│   ├── document_validator.py   # 16 códigos, todos los issues en un pase
│   ├── preview.py              # SpecialistPreview + stats
│   ├── persister.py            # serializa grafo + copia doc + actualiza manifest
│   ├── cli.py                  # subcomandos: validate/preview/build/list/show/remove/reload
│   └── __main__.py             # python -m experiment_21.authoring
├── data/
│   └── sample_domain.md        # dominio de polígonos (~10 nodos, cross-spec)
└── tests/                      # 44 tests
```

## Sesión de uso (output literal del runner real)

```text
$ agi-author validate experiment_21/data/sample_domain.md
Validando: experiment_21/data/sample_domain.md

✓ Sin issues. Documento válido.


$ agi-author preview experiment_21/data/sample_domain.md --id poligonos
Documento: experiment_21/data/sample_domain.md
Especialista propuesto: poligonos
Estado: ✓ válido, listo para construir

Nodos: 8
  ALGORITHM   1
  AXIOM       1
  DEFINITION  4
  THEOREM     2

Vocabulario:
  7 surface forms nuevas

Foundations:
  resueltas localmente:        11
  cross-specialist:            1
    _complexity_base::def.complexity.On2  →  _complexity_base:def.complexity.On2

Plantillas de expresión: 3 (5 nodos sin expresión — fallback a statement)


$ agi-author build experiment_21/data/sample_domain.md --id poligonos --yes
[... preview ...]
Construyendo...
  ✓ Grafo serializado: agi_data/graphs/poligonos.json
  ✓ Documento copiado:  agi_data/sources/poligonos.md
  ✓ Manifest actualizado

Especialista listo. 10 nodos, 7 surface forms.


$ agi-author list
Especialistas en agi_data:
  · poligonos                       graphs/poligonos.json  ←  sources/poligonos.md
```

Tras `build`, el sistema bootstrapea el manifest actualizado y el
especialista nuevo está disponible para el `SessionOrchestrator`
sin trabajo adicional.

## Códigos de validación

| Código | Severidad | Significado |
|---|---|---|
| `MISSING_ID` | error | Bloque de nodo sin `**Id:**`. |
| `DUPLICATE_ID` | error | Dos nodos con el mismo id; reporta ambas líneas. |
| `MALFORMED_MARKER` | error | Marcador con sintaxis incorrecta (faltan `:`, `**`). |
| `UNKNOWN_MARKER` | error | Marcador no en la lista canónica. Mensaje incluye los válidos. |
| `AXIOM_HAS_FOUNDATIONS` | error | AXIOM con `**Depende de:**` declarado por el autor. |
| `THEOREM_MISSING_FOUNDATIONS` | error | THEOREM sin `**Depende de:**` declarado por el autor. |
| `ALGORITHM_MISSING_IO` | error | ALGORITHM sin `**Entrada:**` o `**Salida:**`. |
| `HYPOTHESIS_WITH_COMPLETE_FOUNDATIONS` | warning | HYPOTHESIS con foundations — quizás sea THEOREM. |
| `FOUNDATION_NOT_FOUND` | error | `**Depende de:**` referencia un id inexistente. |
| `EXPRESSION_REF_NOT_FOUND` | error | `{node.X}` apunta a un id no resoluble. |
| `EXPRESSION_PARSE_ERROR` | error | Plantilla mal formada (llave sin cerrar, etc.). |
| `EMPTY_SURFACE_FORM` | error | `**Términos:**` con coma seguida sin valor. |
| `DUPLICATE_SURFACE_FORM_IN_DOCUMENT` | error | Misma surface form en dos nodos del doc. |
| `SURFACE_FORM_CONFLICT_WITH_REGISTRY` | warning | Surface form ya existe en otro especialista cargado. |
| `EMPTY_DOCUMENT` | error | El documento no contiene ningún nodo. |
| `NO_AXIOMS_NO_FOUNDATIONS` | warning | Sin axiomas ni cross-refs — ¿es intencional? |

## Para autores: cómo escribir un documento

Estructura mínima de un nodo:

```markdown
**Definición:**           ← marcador primario (Definición/Teorema/Axioma/Algoritmo)
**Id:** def.alfa          ← id único en el documento
**Términos:** alfa, α     ← surface forms para reconocimiento NL (opcional)
**Expresión:** El alfa es {self.name}.    ← plantilla de verbalización (opcional)
La definición de alfa.    ← statement (texto crudo)
**Depende de:** ...       ← lista CSV de foundations (requerido para THEOREM)
```

Marcadores disponibles:

- **Primarios** (abren un bloque): `**Definición:**`, `**Teorema:**`,
  `**Axioma:**`, `**Algoritmo:**`.
- **Secundarios**: `**Id:**`, `**Términos:**`, `**Expresión:**`,
  `**Procedimiento:**`, `**Inputs:**`, `**Outputs:**`,
  `**Entrada:**`, `**Salida:**`, `**Depende de:**`,
  `**Complejidad:**`, `**Condición:**`.

Cross-spec: para depender de un nodo de OTRO especialista, usá
`spec_id::node_id` en `**Depende de:**`. La herramienta lo
canoniza a id puro al persistir, lo cual permite que el grafo
runtime importe el nodo via `base_graph` automáticamente.

Plantillas de expresión: ver `experiment_18/README.md` para la
sintaxis (`{node.X}`, `{input.Y}`, `{self.name}`, escapes con
`{{` y `}}`).

## Decisiones del ejecutor (documentadas)

1. **Manifest del exp_19 NO requirió extensión.** Los campos
   `source_document` e `init_kwargs` ya cubrían el flujo. La
   herramienta usa el formato tal cual.
2. **Cross-spec syntax `spec::node`**: la herramienta de autoría
   acepta y CANONIZA esta forma (la convierte a id puro al
   persistir). El motor canónico (`SpecialistFactory.from_document`
   del exp_06) NO la acepta; sólo trabaja con ids puros declarados
   como `external_ids`. Eso es un trade-off: el autor escribe la
   forma explícita (más legible), el grafo persiste la forma
   compatible. Documentado en el integration test
   `test_authored_graph_contains_expected_key_nodes`.
3. **`THEOREM_MISSING_FOUNDATIONS` y `AXIOM_HAS_FOUNDATIONS`
   miran `explicit_dependencies`** — el campo CRUDO antes de la
   resolución. Eso refleja la INTENCIÓN del autor (declaró/no
   declaró foundations) en lugar del estado post-heurística del
   parser. Sin este matiz, la heurística "hermanos previos en la
   sección" del exp_13 (PROB-10) ocultaría el aviso al autor.
4. **`SURFACE_FORM_CONFLICT_WITH_REGISTRY` es WARNING**, no error.
   Conflictos de vocabulario son legítimos y la
   `ClarificationRequest` del exp_08 los resuelve en runtime.
5. **`agi-author` no se instala** como entry point en
   `pyproject.toml` — el repo no tiene packaging file. Invocación
   canónica: `python -m experiment_21.authoring <subcomando>`.

## Tests (44/44 verde)

| archivo | tests |
|---|---|
| `test_validator.py` | 18 (un test por código + happy path + multi-issue) |
| `test_preview.py` | 8 (sample, conflicts, validation gating) |
| `test_persister.py` | 6 (idempotencia, overwrite, round-trip, remove) |
| `test_cli.py` | 9 (cada subcomando, exit codes, mensajes) |
| `test_integration.py` | 3 (CLI build → bootstrap → consulta resuelve) |

Suite total del proyecto: **379/379 verde** (335 anteriores + 44
nuevos). Cero regresiones.

## Lo que NO hay

- ❌ Auto-corrección de documentos.
- ❌ Inferencia de información no declarada.
- ❌ UI web.
- ❌ Stack traces en operación normal.
- ❌ Modificación al motor (exp_01–20). Si algo del motor no
  alcanzó, lo señalo en este README en lugar de tocarlo.
