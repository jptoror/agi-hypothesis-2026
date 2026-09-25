# FINDINGS — experiment_11

Registro científico del scale test del `KnowledgeGraph`. El propósito
es medir empíricamente si las tres operaciones críticas se degradan
al crecer el número de nodos, y documentar tanto los datos
cuantitativos obtenidos como los bugs latentes que la corrida
expuso.

---

## INFORME DEL EXPERIMENT 11 — SCALE TEST

### Objetivo

Medir empíricamente si las tres operaciones críticas del
`KnowledgeGraph` se degradan al crecer el número de nodos. El
proyecto hasta ahora ha trabajado con grafos de 6 a 20 nodos
(validación estructural). El exp_11 responde la pregunta
cuantitativa que `OPEN_PROBLEMS.md` PROB-05 formula: **¿qué pasa
cuando el grafo es grande?**

### Diseño metodológico

#### Generador de grafos sintéticos (`synth_graph.py`)

Construye grafos con exactamente N nodos, estructurados para
ejercitar el peor caso realista del sistema:

- **1 axioma raíz** (`ax.synth.base`).
- **N-2 definiciones encadenadas linealmente**: `def.synth.var_0`
  depende del axioma; `def.synth.var_i` (i>0) depende del axioma +
  `def.synth.var_{i-1}`. Cada definición es ejecutable (`compute`
  produce su propia variable como constante).
- **1 teorema final** (`thm.synth.target`) cuyas inputs son las
  últimas K=5 definiciones (fan-in). Produce la variable objetivo
  `synth_target`.

La cadena lineal asegura que `transitive_foundations` tenga
profundidad ~N (peor caso) y que el backward chaining tenga que
recursar a través de toda la cadena para resolver las inputs del
teorema.

#### Medición (`measure.py`)

- **Reloj**: `time.perf_counter` (alta resolución, monotónico).
- **Política**: cada operación se ejecuta N repeticiones; se reporta
  la **mediana en milisegundos**. La mediana es robusta a picos por
  GC o context switch.
- **Warm-up**: 1 ejecución previa no contada para que el primer hit
  (cargas, primeras alocaciones) no contamine.
- **Repeticiones por tamaño**:
  - N ≤ 100 → 200 repeticiones (tiempos sub-ms necesitan más
    muestras).
  - N = 500 → 50 repeticiones.
  - N ≥ 1000 → 20 repeticiones (operaciones más caras; queremos
    terminar en tiempo razonable).

#### Operaciones medidas

1. **`find_relations_producing(target_var)`** — busca nodos cuyo
   `outputs` incluye la variable objetivo. Implementación actual:
   itera el grafo entero (O(N)).

2. **`backward_chaining`** — `GeometrySpecialist.solve(problem)` con
   la variable objetivo. Recurre por cada input del teorema final
   hasta agotar la cadena.

3. **`transitive_foundations(target_node_id)`** — recorre
   recursivamente todos los fundamentos del nodo. La profundidad de
   recursión es ~N por construcción del grafo sintético.

#### Tamaños evaluados

```
10, 50, 100, 500, 1000, 5000
```

Span de ×500 entre extremos — suficiente para distinguir
comportamiento lineal de polinomial y de superpolinomial.

### Hallazgo en runtime: RecursionError con N≥1000

Primera corrida del script falló con N=1000:

```
RecursionError: maximum recursion depth exceeded while calling a Python object
  File ".../knowledge_graph/graph.py", line 93, in visit
    visit(dep)
  File ".../knowledge_graph/graph.py", line 93, in visit
    visit(dep)
  [Previous line repeated 985 more times]
```

**Causa**: `KnowledgeGraph.transitive_foundations` está implementado
como recursión pura (graph.py:88-94). El default
`sys.setrecursionlimit` es 1000. Para grafos con cadena lineal de
profundidad >~990 niveles, Python aborta.

**Decisión**: el propósito del exp_11 es **medir el comportamiento
actual del sistema**, no arreglarlo. Subo
`sys.setrecursionlimit(20000)` en el script con un comentario que
apunta a PROB-08, y dejo el bug del sistema sin tocar.

### Resultados (números reales, máquina actual)

Corrida con `sys.setrecursionlimit(20000)`, mediana de N
repeticiones, 1 warm-up por operación.

#### Output literal del script

```
==============================================================================
EXPERIMENT 11 — scale test
==============================================================================
medición: time.perf_counter, mediana de N repeticiones, 1 warm-up

  n=   10  reps=200  build=    0.05 ms  find=   0.0009 ms  chain=   0.0372 ms  foundations=   0.0019 ms
  n=   50  reps=200  build=    0.07 ms  find=   0.0039 ms  chain=   0.3627 ms  foundations=   0.0093 ms
  n=  100  reps=200  build=    0.16 ms  find=   0.0072 ms  chain=   1.3201 ms  foundations=   0.0216 ms
  n=  500  reps= 50  build=    1.72 ms  find=   0.0375 ms  chain=  33.6279 ms  foundations=   0.1212 ms
  n= 1000  reps= 20  build=    1.44 ms  find=   0.0697 ms  chain= 139.5511 ms  foundations=   0.2271 ms
  n= 5000  reps= 20  build=    8.60 ms  find=   0.3619 ms  chain=4354.9747 ms  foundations=   1.6924 ms

==============================================================================
TABLA DE RESULTADOS
==============================================================================
 nodos |  find_time_ms |  chain_time_ms | foundations_time_ms
------------------------------------------------------------------------------
    10 |        0.0009 |         0.0372 |              0.0019
    50 |        0.0039 |         0.3627 |              0.0093
   100 |        0.0072 |         1.3201 |              0.0216
   500 |        0.0375 |        33.6279 |              0.1212
  1000 |        0.0697 |       139.5511 |              0.2271
  5000 |        0.3619 |      4354.9747 |              1.6924

==============================================================================
CRECIMIENTO ENTRE EXTREMOS
==============================================================================
  tamaño:           10 →  5000  (×500)
  find             0.0009 ms →    0.3619 ms  (×413.5)
  chain            0.0372 ms → 4354.9747 ms  (×117108.6)
  foundations      0.0019 ms →    1.6924 ms  (×883.3)
```

### Análisis cuantitativo

#### Crecimiento entre tamaños consecutivos

| n→n' | factor n | factor find | factor chain | factor foundations |
|---|---|---|---|---|
| 10 → 50 | ×5 | ×4.3 | ×9.8 | ×4.9 |
| 50 → 100 | ×2 | ×1.8 | ×3.6 | ×2.3 |
| 100 → 500 | ×5 | ×5.2 | ×25.5 | ×5.6 |
| 500 → 1000 | ×2 | ×1.9 | ×4.1 | ×1.9 |
| 1000 → 5000 | ×5 | ×5.2 | ×31.2 | ×7.4 |

#### Interpretación por operación

**`find_relations_producing` — O(N) lineal limpia.**

Cada salto en el tamaño produce un salto proporcional en el tiempo.
Factor total ×413 sobre cambio de tamaño ×500 confirma comportamiento
lineal con poca constante. Para N=5000 son **0.36 ms por consulta**
— perfectamente usable.

**`transitive_foundations` — O(N) lineal con ligero overhead.**

Factor total ×883 sobre cambio de tamaño ×500 indica O(N) con un
coeficiente ligeramente superlineal — probable que sea por overhead
de la recursión (frames de Python) más que por complejidad
algorítmica genuina. Para N=5000 son **1.69 ms por consulta** —
usable.

**`backward_chaining` — superpolinomial. NO escalable.**

Factor total ×117108 sobre cambio de tamaño ×500. Si fuera O(N²)
esperaríamos ×250000; si fuera O(N²/2) esperaríamos ~×125000. El
comportamiento se acerca a **O(N²)** o **O(N² log N)**. Para
N=5000 una consulta tarda **4.35 segundos** — inviable para uso
interactivo.

Con N=100 (los grafos reales del proyecto, p. ej. el subdominio
emergente del exp_04 con 20 nodos) son **1.3 ms** — aceptable. Con
N=1000 son **139 ms** — al borde de usable. Con N=5000 son
**4.35 s** — bloqueante.

#### Comparación visual del crecimiento

```
                    10       50      100      500     1000     5000
find        :  0.0009   0.0039   0.0072   0.0375   0.0697   0.3619
foundations :  0.0019   0.0093   0.0216   0.1212   0.2271   1.6924
chain       :  0.0372   0.3627   1.3201   33.628   139.55  4354.97
                |        |        |        |        |        |
                |        |        |        |        |        |
                +--------+--------+--------+--------+--------+
                find/foundations crecen ~lineal
                chain explota en los últimos pasos
```

### Causa probable del backward chaining superpolinomial

La degradación del backward chaining no es por una sola razón — es
por la composición de varias:

1. **`find_relations_producing` se invoca múltiples veces durante
   una resolución** (una vez por variable que el chaining necesita
   derivar). Cada invocación es O(N). Si el chaining toca K
   variables, el costo agregado sería O(K·N).

2. **`_scan_relevant_nodes` llama a `transitive_foundations` por
   cada seed del grafo**. Para el grafo sintético, cualquier nodo
   cuyo id contenga el `kind` del problema entra como seed — y para
   el grafo sintético sin kind geométrico, los seeds son los
   productores del target. Cada seed dispara un cierre transitivo
   O(N).

3. **No hay memoización**: si `transitive_foundations(X)` se invoca
   dos veces durante un solve, recalcula entera. Un solve típico la
   invoca varias veces.

El producto de estos factores produce el ×117108 que observamos.

### Bugs y deuda técnica registrados en `OPEN_PROBLEMS.md`

#### PROB-08 — `transitive_foundations` revienta con N>1000

**Síntoma**: RecursionError al medir grafos de 1000+ nodos con
cadena lineal.
**Causa**: implementación recursiva pura, hereda el límite de
Python (default 1000).
**Solución**: reescribir como iterativo con stack explícito.
**Workaround temporal**: `sys.setrecursionlimit(20000)` en el
script.
**Estado**: Pendiente.

#### PROB-09 — `backward_chaining` escala superpolinomial

**Síntoma**: ×117000 en tiempo cuando el tamaño crece ×500.
**Causa probable**: composición de O(N) por
`find_relations_producing` repetido + O(N) por
`transitive_foundations` en el scan + ausencia de memoización.
**Soluciones candidatas**:
- Índice `{variable → list[node]}` construido al añadir nodos
  (búsqueda O(1)).
- Memoizar `transitive_foundations` por id de nodo.
- Cache de `relevant_nodes` por target dentro de un `solve`.
**Estado**: Pendiente — confirmar prioridad antes de optimizar.

### Veredicto operativo del proyecto actual

| Tamaño | Veredicto | Casos de uso |
|---|---|---|
| **N ≤ 100** | excelente, sub-ms en todas las operaciones | grafos manuales, especialistas de los exp_01-09 |
| **100 < N ≤ 1000** | usable, chain en decenas-cientos de ms | documentos largos, subgrafos emergentes |
| **N > 1000** | requiere optimización + fix de recursión | dominios reales con miles de nodos |

Hasta donde llega el proyecto hoy (grafos de 6-20 nodos en
producción), **el rendimiento es excelente y no hay urgencia**. Pero
el experimento confirma que escalar a dominios reales (cientos o
miles de nodos) requiere las optimizaciones de PROB-05/PROB-09.

### Estructura entregada

```
experiment_11/scale_test/
├── synth_graph.py    # generador con cadena lineal de N nodos exactos
├── measure.py        # Measurement + bench (mediana N reps, warm-up)
└── run.py            # corre los 6 tamaños, imprime tabla y crecimiento

OPEN_PROBLEMS.md
└── + PROB-08 (recursión)
└── + PROB-09 (chain superpolinomial)
```

### Lo que el experimento NO mide (declarado explícitamente)

- **Memoria**: sólo se midió tiempo, no consumo de RAM.
- **Concurrencia**: cada medición es single-thread sin contención.
- **Variabilidad por máquina**: los números son de la máquina actual;
  otra máquina dará otros valores absolutos pero los **factores de
  crecimiento** deberían reproducirse.
- **Grafos con estructura distinta**: el grafo sintético es cadena
  lineal con fan-in 5 al final. Grafos en forma de árbol balanceado,
  DAG ancho, etc. tendrán comportamientos distintos. La cadena
  lineal es el peor caso para `transitive_foundations`.
- **Grafos con `compute` complejo**: las funciones lambda del grafo
  sintético son triviales. Compute más caro (sympy, llamadas
  externas) cambiará la proporción tiempo-cómputo / tiempo-grafo.

### Regresión

```
101 passed in 0.20s
```

El exp_11 no modifica código existente. Los 101 tests del proyecto
siguen verdes.
