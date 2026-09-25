# Capítulo demo — Algoritmos para integración exp_17

Documento mínimo para ejercitar el marcador `**Términos:**` con
varios nodos. Incluye el caso central del integration test
(`alg.greedy_coloring` con tres formas) y un nodo (`def.set`) que
comparte forma con un nodo C++ — así se ejercita el conflicto.

---

## A.1 Estructuras

**Definición:**
**Id:** def.grafo
**Términos:** grafo, grafo G
Un grafo es un par (V, E) de vértices y aristas.

**Definición:**
**Id:** def.set
**Términos:** set, conjunto
Un conjunto matemático es una colección no ordenada de elementos
distintos.

---

## A.2 Algoritmos

**Algoritmo:**
**Id:** alg.greedy_coloring
**Términos:** coloreado voraz, algoritmo greedy de coloración, greedy coloring
Asigna colores a los vértices de un grafo usando una heurística
voraz: para cada vértice, elige el color de menor índice que no
colisione con sus vecinos.
**Entrada:** grafo G, conjunto de vértices no coloreados
**Salida:** coloración de todos los vértices del grafo
