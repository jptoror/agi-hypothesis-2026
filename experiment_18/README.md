# Experiment 18 — Expresión autocontenida

Generaliza el patrón de **exp_16** (generación de código C++ desde
nodos) a generación de prosa en español desde cualquier
especialista.

## Hipótesis

Un sistema que deriva conocimiento verificado puede expresarlo en
lenguaje natural sin componentes estadísticos, siempre que la
expresión esté declarada como **estructura del nodo**. Cada
oración generada tiene un puntero al nodo que la fundamenta; la
prosa y la traza son la misma cosa vista distinto.

## Decisiones de diseño

1. **Marcador del parser:** `**Expresión:**` con plantilla string
   (almacenada **cruda**, sin normalización).
2. **Sintaxis de plantilla:**
   - `{node.X}` → expresión rendereada del nodo X (recursivo)
   - `{input.Y}` → binding de entrada Y del paso/problema
   - `{output.Z}` → binding de salida Z del paso
   - `{step.N}` → texto rendereado del paso N
   - `{self.name}` → statement del nodo actual (atajo)
   - `{{` y `}}` para llaves literales
3. **Fallback:** si un nodo no tiene `expression_template`, se usa
   su `statement`. **Compatibilidad total** con todos los
   documentos previos (sin marcador → comportamiento intacto).
4. **Errores explícitos:** plantilla mal formada o referencia no
   resoluble lanza excepción (`TemplateParseError`,
   `UnresolvedReferenceError`, `CyclicReferenceError`). Sin
   degradación silenciosa.
5. **Renderer por especialista:** vive en el `Specialist` (no en
   el orquestador). Cross-specialist se resuelve con
   `CrossSpecialistRenderer` que particiona la traza por
   `delegated_to` y delega cada segmento a su renderer.
6. **Sin libertad creativa.** Cada output es función pura de
   `(plantilla, bindings, grafo)`. Mismo input → mismo output,
   siempre.

## Componentes

```
experiment_18/
├── README.md
├── expression/
│   ├── template.py         parse_template + render_template + errores
│   └── renderer.py         ExpressionRenderer + CrossSpecialistRenderer
├── tests/
│   ├── test_template.py     20 tests del parser/resolutor
│   ├── test_renderer.py     11 tests del renderer (ciclos, conectores, fallback)
│   ├── test_integration.py   6 tests end-to-end con SpecialistFactory
│   └── test_cross_specialist.py  5 tests del renderer cruzado
└── data/
    └── algorithms_with_expression.md   5 nodos con `**Expresión:**` poblado
```

Cambios mínimos en código existente (retro-compatibles):

- `experiment_06/document_parser/node_extractor.py` — añade
  marcador `**Expresión:**`. Si está, popula
  `properties["expression_template"]` (raw). Si no, propiedad
  ausente (no `""`, no `None`).
- `experiment_01/specialist/specialist.py` — `renderer` (lazy
  property) + `express(trace)` heredados por todas las subclases
  (`Physics`, `SubdomainSpecialist`, etc.).

## Demo de evidencia

Construyendo el especialista desde
`experiment_18/data/algorithms_with_expression.md` y verbalizando
una traza canónica de coloreo:

```python
trace = ReasoningTrace(steps=[
    step(1, "def.grafo"),
    step(2, "def.vertice"),
    step(3, "def.adyacencia"),
    step(4, "alg.greedy_coloring", inputs={"grafo G": "G"}),
    step(5, "thm.greedy_coloring.complejidad"),
])
print(specialist.express(trace))
```

Output literal (output del runner real, no parafraseado):

> un grafo es una estructura de vértices conectados por aristas
> Luego, los vértices son los puntos del grafo, identificados por
> un número de 0 a m-1 A continuación, dos vértices son
> adyacentes cuando existe una arista entre ellos Después, para
> colorear G aplicamos el algoritmo greedy de coloración: para
> cada color nuevo, seleccionamos los vértices no coloreados que
> no entran en conflicto con los ya coloreados, hasta cubrir todo
> el grafo Luego, la complejidad del coloreo greedy es a lo sumo
> m³ operaciones, donde m es el número de vértices del grafo

### Mapeo oración → nodo (auditabilidad)

Cada oración del párrafo proviene EXACTAMENTE de la plantilla
`**Expresión:**` declarada en su nodo. Esa correspondencia **es**
la evidencia de que la prosa es derivación verificada, no
generación.

| Oración | Nodo |
|---|---|
| "un grafo es una estructura de vértices conectados por aristas" | `def.grafo` |
| "los vértices son los puntos del grafo, identificados por un número de 0 a m-1" | `def.vertice` |
| "dos vértices son adyacentes cuando existe una arista entre ellos" | `def.adyacencia` |
| "para colorear G aplicamos el algoritmo greedy de coloración: para cada color nuevo, …" | `alg.greedy_coloring` (con `{input.grafo G}` = "G") |
| "la complejidad del coloreo greedy es a lo sumo m³ operaciones, donde m es el número de vértices del grafo" | `thm.greedy_coloring.complejidad` |

Las palabras de conexión (`Luego,`, `A continuación,`, `Después,`)
provienen de `Specialist.trace_connectors` (con default rotando
sobre los tres) — son agnósticas al contenido y declaradas, no
elegidas por un modelo.

## Lo que NO hay

Por contrato del experimento:

- Cero LLM (ni siquiera para "suavizar" prosa).
- Cero generación procedural más allá de sustitución de
  plantillas.
- Cero conocimiento de dominio en el orquestador (el conector de
  transición entre especialistas es agnóstico).
- Cero degradación silenciosa: errores de plantilla → excepción
  con kind/target/path explícitos.
- Cero ruptura de compat: nodos sin `**Expresión:**` se
  verbalizan con su `statement` exactamente como antes.

## Tests

42 tests del exp_18 (20 template + 11 renderer + 6 integration +
5 cross-specialist). Suite total del proyecto: **228/228 verde**
(186 anteriores + 42 nuevos).
