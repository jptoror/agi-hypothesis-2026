# Capítulo demo — Algoritmos con plantillas de verbalización

Versión enriquecida del documento de algoritmos del exp_15. Cada
nodo declara una plantilla `**Expresión:**` para que el especialista
pueda verbalizar las derivaciones que lo involucran. Las plantillas
usan la sintaxis del exp_18:

  - `{self.name}`     → statement del nodo actual
  - `{node.X}`        → expresión rendereada del nodo X
  - `{input.K}`       → valor del binding de entrada K
  - `{output.K}`      → valor del binding de salida K

El documento es **autónomo**: NO modifica `experiment_09/sample_documents/
ch01_algoritmos.md`. Reutiliza ids ya conocidos (`def.grafo`,
`alg.greedy_coloring`, `thm.greedy_coloring.complejidad`) para
poder beneficiarse del base_graph de complejidad del exp_09.

---

## Sección 1.1 — Estructura del grafo

**Definición:**
**Id:** def.grafo
**Expresión:** un grafo es una estructura de vértices conectados por aristas
Un grafo es un conjunto V de vértices junto con un conjunto E de
aristas que conectan pares de vértices.

**Definición:**
**Id:** def.vertice
**Expresión:** los vértices son los puntos del grafo, identificados por un número de 0 a m-1
Los vértices son los puntos del grafo. Cada vértice se identifica
con un número entre 0 y m-1, donde m es el número total de vértices.
**Depende de:** def.grafo

**Definición:**
**Id:** def.adyacencia
**Expresión:** dos vértices son adyacentes cuando existe una arista entre ellos
Si existe una arista entre dos vértices i y j entonces decimos que
i es adyacente a j.
**Depende de:** def.grafo, def.vertice

---

## Sección 1.2 — Algoritmo de coloreo greedy

**Algoritmo:**
**Id:** alg.greedy_coloring
**Expresión:** para colorear {input.grafo G} aplicamos el algoritmo greedy de coloración: para cada color nuevo, seleccionamos los vértices no coloreados que no entran en conflicto con los ya coloreados, hasta cubrir todo el grafo
Para cada color nuevo, determinar el conjunto de vértices no
coloreados que pueden recibir ese color sin entrar en conflicto
con los ya coloreados. Repetir hasta colorear todos los vértices.
**Entrada:** grafo G, conjunto de vértices no coloreados
**Salida:** coloración de todos los vértices del grafo
**Depende de:** def.grafo, def.vertice, def.adyacencia

**Teorema:**
**Id:** thm.greedy_coloring.complejidad
**Expresión:** la complejidad del coloreo greedy es a lo sumo m³ operaciones, donde m es el número de vértices del grafo
El tiempo de ejecución del algoritmo heurístico ávido de coloración
es a lo sumo m³ operaciones donde m es el número de vértices.
**Complejidad:** def.complexity.On3
**Depende de:** alg.greedy_coloring, def.grafo
