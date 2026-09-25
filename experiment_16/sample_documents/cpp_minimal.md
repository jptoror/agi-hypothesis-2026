# Capítulo C++ — Vocabulario mínimo para expresar algoritmos

Este capítulo declara un vocabulario mínimo de constructos de C++
suficiente para expresar el algoritmo de coloreo greedy del
capítulo 1 (`alg.greedy_coloring`) en código fuente.

Las plantillas concretas que cada nodo aplica viven en la
biblioteca Python `experiment_16.specialist_factory.cpp_templates`
— el documento sólo nombra los constructos y referencia el
procedimiento que las compone. Patrón consistente con la
biblioteca `PROCEDURES` del exp_06 (procedimientos ejecutables
viven en código, no en el documento).

---

## C.1 Directivas de preprocesador

**Definición:**
**Id:** def.cpp.include
La directiva `#include <header>` instruye al preprocesador para
incorporar el contenido del header indicado al inicio de la unidad
de compilación. Sin ella, el compilador no conoce los símbolos
declarados en la biblioteca estándar.

---

## C.2 Definición de funciones

**Definición:**
**Id:** def.cpp.function
Una función con tipo de retorno explícito, nombre y parámetros
se declara con la firma estándar de C++. El cuerpo contiene las
sentencias de la función.

---

## C.3 Lazo for con iterador

**Definición:**
**Id:** def.cpp.for_loop
El lazo for clásico de C++ con un iterador recorre un contenedor
desde `begin()` hasta `end()`. Se utiliza con cualquier contenedor
STL que exponga la interfaz de iterador. El cuerpo se ejecuta una
vez por elemento.

---

## C.4 Contenedores STL

**Definición:**
**Id:** def.cpp.set
El contenedor `set<T>` mantiene una colección ordenada de
elementos únicos del tipo `T`. Operaciones típicas: `insert(x)`,
`erase(x)`, `find(x)`. El acceso en orden iterativo está
garantizado por la implementación (árbol balanceado).

**Definición:**
**Id:** def.cpp.vector
El contenedor `vector<T>` mantiene una secuencia dinámica de
elementos del tipo `T` con acceso aleatorio O(1) e inserción en
el final amortizada O(1). Operaciones típicas: `push_back(x)`,
`size()`, indexación con `[i]`.

---

## C.5 Iteradores

**Definición:**
**Id:** def.cpp.iterator
Un iterador `T::iterator` apunta a un elemento de un contenedor
del tipo `T`. Sirve como índice abstracto para recorrer la
estructura sin asumir su disposición en memoria. La operación
`*iter` devuelve el elemento referenciado; `iter++` avanza al
siguiente.

---

## C.6 Mapping del algoritmo greedy_coloring a C++

Esta sección declara la correspondencia entre el algoritmo
abstracto `alg.greedy_coloring` (definido en el capítulo 1) y
los constructos C++ que lo expresan. El nodo de mapping no es
un constructo C++ adicional — es la receta estructural que el
especialista ejecuta (vía el procedimiento
`cpp_greedy_coloring_compose`) para componer el código fuente.

**Algoritmo:**
**Id:** alg.cpp.greedy_coloring_impl
Implementación en C++ del coloreo greedy: itera sobre el conjunto
de vértices no coloreados (`no_col`) usando un iterador `q`,
verifica adyacencia con los ya coloreados, e inserta los aptos
en `nuevo_color`. La estructura sigue el patrón canónico de
recorrer un `set<int>` con iterador y operar sobre otro `set<int>`
acumulador.
**Entrada:** abstract_node, target_container
**Salida:** cpp_code
**Procedimiento:** cpp_greedy_coloring_compose
**Depende de:** def.cpp.for_loop, def.cpp.set, def.cpp.iterator, alg.greedy_coloring
