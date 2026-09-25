# Capítulo 4 — Pilas

Las pilas son una de las estructuras de datos más simples y más
útiles. Su disciplina de acceso — añadir y retirar elementos
exclusivamente por un extremo — captura una intuición que aparece
una y otra vez en computación: la última cosa guardada es la
primera que se necesita recuperar. Este capítulo introduce el
concepto, define las tres operaciones fundamentales, y enuncia su
coste asintótico.

## 4.1 Concepto

Antes de hablar de operaciones conviene fijar qué llamamos pila.
La idea es restrictiva por diseño: una colección lineal en la que
el orden de inserción y el de retirada están vinculados por una
disciplina LIFO ("último en entrar, primero en salir").

**Definición:**
**Id:** def.stack
Una pila es una colección lineal de elementos en la que las
inserciones y las retiradas se realizan exclusivamente por el
mismo extremo, llamado tope. Esta disciplina se conoce como LIFO:
el último elemento insertado es el primero en ser retirado.

La elección del tope como único punto de acceso es lo que
diferencia a la pila de otras colecciones lineales como la cola
(que opera FIFO) o la lista (que admite acceso arbitrario).

**Definición:**
**Id:** def.stack.top_pointer
El tope de una pila es la posición lógica en la que se realizan
las operaciones de inserción y retirada. Su valor cambia con cada
push o pop pero no depende del número total de elementos
almacenados.

## 4.2 Operaciones fundamentales

Una pila expone tres operaciones primitivas: añadir un elemento,
retirar el último añadido, y consultar el último añadido sin
retirarlo. Las tres comparten una propiedad central: operan sobre
el tope y no recorren la estructura.

**Definición:**
**Id:** def.op.push
La operación push(s, x) añade el elemento x al tope de la pila s.
El tope pasa a apuntar al elemento recién insertado.

**Definición:**
**Id:** def.op.pop
La operación pop(s) retira el elemento del tope de la pila s y lo
devuelve. El tope retrocede a la posición anterior.

**Definición:**
**Id:** def.op.top
La operación top(s) devuelve el elemento del tope de la pila s sin
modificarla.

## 4.3 Análisis de complejidad

El interés práctico de las pilas reside en que las tres operaciones
fundamentales tienen coste constante: ni push, ni pop, ni top
recorren la estructura. Esa propiedad es la que hace que las pilas
aparezcan en algoritmos donde el coste por operación es crítico
— evaluación de expresiones, recorrido en profundidad, gestión de
llamadas a función.

**Teorema:**
**Id:** thm.stack.push_complexity
La operación push tiene complejidad temporal O(1): el coste de
añadir un elemento al tope no depende del tamaño actual de la pila.
**Complejidad:** def.complexity.O1
**Depende de:** def.op.push, def.stack.top_pointer

La razón es directa: push manipula únicamente el puntero al tope y
el espacio inmediatamente posterior. La estructura subyacente
— sea un array dinámico o una lista enlazada — admite inserción en
el extremo en tiempo constante amortizado.

**Teorema:**
**Id:** thm.stack.pop_complexity
La operación pop tiene complejidad temporal O(1): el coste de
retirar el elemento del tope no depende del tamaño actual de la
pila.
**Complejidad:** def.complexity.O1
**Depende de:** def.op.pop, def.stack.top_pointer

El argumento es simétrico al de push. Pop lee el elemento al que
apunta el tope, retrocede el puntero y devuelve el valor. Ninguna
de esas operaciones depende del número total de elementos.

**Teorema:**
**Id:** thm.stack.top_complexity
La operación top tiene complejidad temporal O(1): consultar el
elemento del tope no depende del tamaño actual de la pila.
**Complejidad:** def.complexity.O1
**Depende de:** def.op.top, def.stack.top_pointer

Top es una lectura simple de la posición a la que apunta el tope.
No modifica la estructura y por tanto su coste no puede crecer con
el tamaño.

## 4.4 Comentario

La uniformidad O(1) de las tres operaciones es lo que distingue a
la pila como estructura. Una colección lineal que admitiera
inserción en cualquier posición — una lista en sentido amplio —
tendría operaciones más generales pero perdería esa garantía
asintótica. La restricción del acceso al tope es lo que paga el
coste constante.
