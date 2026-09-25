# Capítulo 2.3 — El TAD Cola
## Tipos de Datos Abstractos Fundamentales
*Fuente: Algoritmos y Estructuras de Datos — Arriondo et al., FICH-UNL*

---

## 2.3.1 Conceptos fundamentales

La cola es una estructura de datos en la cual los elementos se insertan por un
extremo (el fondo) y se eliminan por el otro (el frente). A diferencia de la pila,
la cola respeta el orden de llegada de los elementos.

**Definición:**
**Id:** def.cola
Una cola es un tipo abstracto de datos en el cual los elementos se insertan
por el fondo y se eliminan por el frente.

**Definición:**
**Id:** def.cola.frente
El frente de una cola es el extremo desde donde se eliminan los elementos.
Es el único elemento directamente accesible para lectura.
**Depende de:** def.cola

**Definición:**
**Id:** def.cola.fondo
El fondo de una cola es el extremo donde se insertan los nuevos elementos.
**Depende de:** def.cola

**Axioma:** La cola es el ejemplo típico de la estructura tipo FIFO.
**Id:** ax.fifo
El primer elemento insertado en la cola es el primero en ser eliminado
(First In First Out — el primero en entrar es el primero en salir).

**Definición:**
**Id:** def.cola.subtipo_lista
La cola es implementable sobre una lista. Las operaciones pop() y front()
operan sobre el principio de la lista, y push() opera sobre el fin.
**Depende de:** def.cola

---

## 2.3.2 Operaciones abstractas

Las operaciones fundamentales de una cola son obtener el elemento del frente,
eliminarlo, e insertar nuevos elementos.

**Definición:**
**Id:** def.op.cola.push
La operación push inserta un elemento en el fondo de la cola.
**Depende de:** def.cola, def.cola.fondo

**Definición:**
**Id:** def.op.cola.pop
La operación pop elimina el elemento del frente de la cola sin retornar su valor.
**Depende de:** def.cola, def.cola.frente

**Definición:**
**Id:** def.op.cola.front
La operación front retorna el valor del elemento en el frente de la cola
sin modificarla.
**Depende de:** def.cola, def.cola.frente

**Definición:**
**Id:** def.op.cola.empty
La operación empty retorna verdadero si la cola no contiene elementos.
No modifica la cola.
**Depende de:** def.cola

**Definición:**
**Id:** def.op.cola.size
La operación size retorna el número de elementos actualmente en la cola.
**Depende de:** def.cola

**Definición:**
**Id:** def.op.cola.clear
La operación clear elimina todos los elementos de la cola dejándola vacía.
Es diferente de empty(): empty() consulta, clear() vacía.
**Depende de:** def.cola, def.op.cola.empty

---

## 2.3.3 Complejidad de las operaciones

La elección de implementación afecta directamente la complejidad. Si pop() y
front() operan sobre el principio de la lista y push() sobre el fin, todas las
operaciones críticas son O(1).

**Teorema:** push tiene complejidad constante.
**Id:** thm.cola.complejidad.push
La operación push sobre una cola implementada sobre lista enlazada tiene
complejidad O(1) en tiempo de ejecución.
**Condición:** push opera sobre el fin de la lista
**Complejidad:** def.complexity.O1
**Depende de:** def.op.cola.push, ax.fifo

**Teorema:** pop tiene complejidad constante.
**Id:** thm.cola.complejidad.pop
La operación pop sobre una cola implementada sobre lista enlazada tiene
complejidad O(1) en tiempo de ejecución.
**Condición:** pop opera sobre el principio de la lista
**Complejidad:** def.complexity.O1
**Depende de:** def.op.cola.pop, ax.fifo

**Teorema:** front tiene complejidad constante.
**Id:** thm.cola.complejidad.front
La operación front sobre una cola implementada sobre lista enlazada tiene
complejidad O(1) en tiempo de ejecución.
**Condición:** front opera sobre el principio de la lista
**Complejidad:** def.complexity.O1
**Depende de:** def.op.cola.front, ax.fifo

**Teorema:** size y empty tienen complejidad constante.
**Id:** thm.cola.complejidad.size_empty
Las operaciones size y empty sobre cola tienen complejidad O(1).
Se implementan mediante un contador interno que se actualiza en push y pop.
**Complejidad:** def.complexity.O1
**Depende de:** def.op.cola.size, def.op.cola.empty

**Teorema:** clear tiene complejidad lineal.
**Id:** thm.cola.complejidad.clear
La operación clear sobre cola tiene complejidad O(n) donde n es el
número de elementos actuales en la cola.
**Complejidad:** def.complexity.On
**Depende de:** def.op.cola.clear

---

## 2.3.4 Decisión de implementación crítica

**Teorema:** La elección de extremo para pop determina la complejidad.
**Id:** thm.cola.implementacion.extremo
Si pop() y front() operan sobre el fin de la lista en lugar del principio,
entonces pop() tiene complejidad O(n) porque acceder al último elemento
de una lista enlazada (sin puntero al final) es O(n).
La implementación correcta usa el principio para pop/front y el fin para push.
**Condición:** implementación sobre lista enlazada sin puntero al último nodo
**Depende de:** def.op.cola.pop, def.op.cola.front, def.cola.subtipo_lista
