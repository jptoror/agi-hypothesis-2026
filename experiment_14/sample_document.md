# Algoritmos básicos de búsqueda

Este capítulo introduce un algoritmo simple de búsqueda lineal, modelado
como un nodo de tipo ALGORITHM en el grafo de conocimiento del proyecto.

## 1.1 Búsqueda lineal

La búsqueda lineal recorre una colección de elementos comparando cada
uno con el valor buscado hasta encontrarlo o agotar la colección. Es
el procedimiento más simple posible y sirve como base para discutir
algoritmos más eficientes.

**Algoritmo:**
**Id:** alg.busqueda_lineal
La búsqueda lineal recorre la colección desde el primer elemento hasta
encontrar el valor objetivo. Si lo encuentra, devuelve su posición; si
agota la colección sin encontrarlo, devuelve -1.
**Entrada:** coleccion, valor_objetivo
**Salida:** posicion
