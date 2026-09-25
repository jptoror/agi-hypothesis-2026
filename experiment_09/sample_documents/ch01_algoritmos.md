# Capítulo 1 — Diseño y análisis de algoritmos
*Fuente: Algoritmos y Estructuras de Datos — Arriondo et al., FICH-UNL*

---

## Sección 1.1.2 — Introducción básica a grafos

**Definición:**
**Id:** def.grafo
Un grafo es un subconjunto del conjunto G de pares de vértices.
La base del grafo es un conjunto finito V de puntos llamados vértices.
La estructura del grafo está dada por las conexiones entre los vértices.

**Definición:**
**Id:** def.vertice
Los vértices pueden identificarse con un número de 0 a m-1 donde m es
el número total de vértices. También es usual representarlos gráficamente
con una letra a, b, c, ... encerrada en un círculo o usar cualquier etiqueta
única relativa al problema.
**Depende de:** def.grafo

**Definición:**
**Id:** def.arista
Las conexiones entre vértices se llaman aristas (edges) del grafo.
Si dos vértices están conectados se dibuja una línea que va desde
un vértice al otro. Un par de vértices está en el grafo si existe
una arista que los conecta.
**Depende de:** def.grafo, def.vertice

**Definición:**
**Id:** def.adyacencia
Si existe una arista entre dos vértices i y j entonces decimos
que i es adyacente a j.
**Depende de:** def.grafo, def.vertice, def.arista

**Definición:**
**Id:** def.grafo.no_orientado
Un grafo no orientado es aquel donde si el vértice i está conectado
con el j entonces el j está conectado con el i.
**Depende de:** def.grafo, def.arista

**Definición:**
**Id:** def.grafo.orientado
También existen grafos orientados donde las aristas se representan
por flechas.
**Depende de:** def.grafo, def.arista

**Definición:**
**Id:** def.grafo.ponderado
Se puede también agregar un peso (un número real) a los vértices o
aristas del grafo. Este peso puede representar, por ejemplo, un
costo computacional.
**Depende de:** def.grafo, def.arista, def.vertice

**Definición:**
**Id:** def.grafo.matriz_adyacencia
Un grafo también puede representarse como una matriz A simétrica de
tamaño m × m con 0s y 1s. Si hay una arista entre el vértice i y
el j entonces el elemento Aij es uno, y sino es cero.
**Condición:** el grafo debe ser no orientado para que la matriz sea simétrica
**Depende de:** def.grafo, def.arista, def.grafo.no_orientado

---

## Sección 1.1.8 — Algoritmo heurístico ávido de coloración

**Algoritmo:**
**Id:** alg.greedy_coloring
Para cada color nuevo, determinar el conjunto de vértices no coloreados
que pueden recibir ese color sin entrar en conflicto con los ya coloreados.
Repetir hasta colorear todos los vértices.
La rutina greedyc toma como argumentos un grafo G, el conjunto de vértices
no coloreados no_col, y determina un conjunto nuevo_color de nodos
que pueden ser coloreados con el nuevo color.
**Entrada:** grafo G, conjunto de vértices no coloreados
**Salida:** coloración de todos los vértices del grafo
**Depende de:** def.grafo, def.vertice, def.adyacencia

**Teorema:**
**Id:** thm.greedy_coloring.complejidad
El tiempo de ejecución del algoritmo heurístico ávido de coloración
es a lo sumo m³ operaciones donde m es el número de vértices.
**Complejidad:** def.complexity.On3
**Depende de:** alg.greedy_coloring, def.grafo

---

## Sección 1.2 — Tipos abstractos de datos

**Definición:**
**Id:** def.tad
Un Tipo Abstracto de Datos (TAD) es la descripción matemática de
un objeto abstracto, definido por las operaciones que actúan sobre el mismo.

**Definición:**
**Id:** def.tad.operaciones_abstractas
Las operaciones abstractas son las operaciones que se pueden realizar
sobre un TAD, independientemente de su implementación concreta.
**Depende de:** def.tad

**Definición:**
**Id:** def.tad.interfaz
La interfaz es el conjunto de operaciones (con una sintaxis definida)
que producen las operaciones del TAD.
**Depende de:** def.tad, def.tad.operaciones_abstractas

**Definición:**
**Id:** def.tad.implementacion
La implementación es la realización concreta de la interfaz del TAD
en un lenguaje de programación específico.
**Depende de:** def.tad, def.tad.interfaz

**Definición:**
**Id:** def.tad.conjunto
Contiene elementos, los cuales deben ser diferentes entre sí.
No existe un orden particular entre los elementos del conjunto.
Se pueden insertar o eliminar elementos del mismo.
Dado un elemento se puede preguntar si está dentro del conjunto o no.
Se pueden hacer las operaciones binarias bien conocidas entre conjuntos
a saber, unión, intersección y diferencia.
**Depende de:** def.tad, def.tad.operaciones_abstractas

---

## Sección 1.3.1 — Notación asintótica

**Axioma:**
**Id:** ax.asintotica.constante
En la notación asintótica no interesa cómo se comporta T(n) para
valores de n pequeños sino solo la tendencia para n → ∞.

**Definición:**
**Id:** def.notacion_asintotica
Decimos que T(n) = O(f(n)) si existen constantes c, n0 > 0 tales
que T(n) ≤ c·f(n) para n ≥ n0.
Se suele llamar a f(n) la tasa de crecimiento de T(n),
también llamada velocidad de crecimiento o complejidad algorítmica.
**Depende de:** ax.asintotica.constante

**Definición:**
**Id:** def.tiempo_peor
El tiempo de ejecución en el peor caso Tpeor(n) es el máximo
tiempo de ejecución sobre todos los posibles ensambles de entradas
de tamaño n.
**Depende de:** def.notacion_asintotica

**Definición:**
**Id:** def.tiempo_promedio
El tiempo de ejecución promedio Tprom(n) es el promedio de los
tiempos de ejecución de un algoritmo sobre un ensamble de posibles
entradas de tamaño n.
**Depende de:** def.notacion_asintotica

**Teorema:**
**Id:** thm.asintotica.invariancia_constante
Si T(n) = O(f(n)) entonces c·T(n) = O(f(n)) para cualquier
constante c > 0. La notación asintótica es invariante ante
constantes multiplicativas.
**Depende de:** def.notacion_asintotica, ax.asintotica.constante

---

## Secciones 1.3.2 a 1.3.9 — Propiedades de la notación asintótica

**Teorema:**
**Id:** thm.asintotica.invariancia_constante_multiplicativa
Si T(n) = O(c·f(n)) entonces T(n) = O(f(n)).
La tasa de crecimiento es invariante ante constantes multiplicativas.
**Depende de:** def.notacion_asintotica

**Teorema:**
**Id:** thm.asintotica.invariancia_conjunto_finito
Si dos funciones difieren solo en un conjunto finito de puntos,
sus tasas de crecimiento son equivalentes.
**Depende de:** def.notacion_asintotica

**Teorema:**
**Id:** thm.asintotica.transitividad
Si T(n) = O(f(n)) y f(n) = O(g(n)) entonces T(n) = O(g(n)).
La notación O() es transitiva.
**Depende de:** def.notacion_asintotica

**Teorema:**
**Id:** thm.asintotica.regla_suma
Si f(n) = O(g(n)) y a, b son constantes positivas,
entonces a·f(n) + b·g(n) = O(g(n)).
En una suma de términos, solo queda el mayor en el sentido de O().
**Condición:** la regla debe aplicarse un número constante de veces
**Depende de:** def.notacion_asintotica

**Teorema:**
**Id:** thm.asintotica.regla_producto
Si T1(n) = O(f1(n)) y T2(n) = O(f2(n))
entonces T1(n)·T2(n) = O(f1(n)·f2(n)).
**Depende de:** def.notacion_asintotica

**Definición:**
**Id:** def.asintotica.orden_tipico
Las funciones más usuales en notación asintótica en orden creciente son:
1 < log n < √n < n < n² < ... < nᵖ < 2ⁿ < 3ⁿ < ... < n! < nⁿ
**Depende de:** def.notacion_asintotica

**Definición:**
**Id:** def.asintotica.equivalencia
Si f(n) = O(g(n)) y g(n) = O(f(n)) entonces sus tasas de crecimiento
son equivalentes, denotado f ~ g.
**Depende de:** def.notacion_asintotica, thm.asintotica.transitividad

---

## Sección 1.3.12 — Tiempos de ejecución no-polinomiales

**Definición:**
**Id:** def.tiempo_polinomial
Se dice que un algoritmo tiene tiempo polinomial (P, para abreviar),
si es T(n) = O(nα) para algún α.
**Depende de:** def.notacion_asintotica

**Definición:**
**Id:** def.tiempo_no_polinomial
Aquellos algoritmos que tienen tiempo de ejecución mayor que cualquier
polinomio (funciones exponenciales aⁿ, n!, nⁿ) se les llama
no polinomiales.
**Depende de:** def.tiempo_polinomial, def.notacion_asintotica

---

## Sección 1.3.13 — Problemas P y NP

**Definición:**
**Id:** def.maquina_turing
Una máquina de Turing es una abstracción de la computadora más simple
posible, con un juego de instrucciones reducido.
En cada paso puede invocar una sola instrucción (determinística).

**Definición:**
**Id:** def.maquina_turing_no_deterministica
Una máquina de Turing no determinística es una máquina de Turing que
en cada paso puede invocar un cierto número de instrucciones, y no una
sola instrucción como es el caso de la máquina determinística.
En vez de tener un camino de cómputo, se tiene un árbol de cómputo.
**Depende de:** def.maquina_turing

**Definición:**
**Id:** def.problema_NP
Un problema es NP si tiene un tiempo de ejecución polinomial en una
máquina de Turing no determinística.
NP significa non-deterministic polynomial, y no non-polynomial.
**Depende de:** def.maquina_turing_no_deterministica, def.tiempo_polinomial

**Definición:**
**Id:** def.problema_P
Un problema es P si tiene un tiempo de ejecución polinomial en una
máquina de Turing determinística.
**Depende de:** def.maquina_turing, def.tiempo_polinomial
