# Capítulo 3 — Ecuaciones lineales en una variable

Las ecuaciones lineales son la primera familia de ecuaciones que se
estudia formalmente porque su estructura permite ilustrar, sin más
maquinaria que la aritmética de los reales, qué significa "resolver"
y qué condiciones aseguran que una solución existe y es única. Este
capítulo introduce los conceptos básicos, enuncia la propiedad de la
igualdad sobre la que descansa todo el procedimiento, y deduce la
fórmula general que cierra el caso de una incógnita.

## 3.1 Conceptos básicos

Antes de hablar de soluciones conviene fijar con precisión qué es lo
que pretendemos resolver. Llamamos ecuación a una igualdad entre dos
expresiones; cuando una de ellas contiene una variable, resolver la
ecuación consiste en hallar los valores de esa variable que hacen
verdadera la igualdad.

**Definición:**
**Id:** def.ecuacion_lineal
Una ecuación lineal en la variable x es una expresión
de la forma a·x + b = 0, donde a y b son números reales y a, llamado
coeficiente principal, no es cero.

El coeficiente que acompaña a la variable y el término independiente
son las dos cantidades que determinan por completo la ecuación. Como
veremos, basta con conocer ambos para escribir la solución.

**Definición:**
**Id:** def.coeficiente_principal
El coeficiente principal de una ecuación lineal
a·x + b = 0 es el número real a que multiplica a la variable; el
término b recibe el nombre de término independiente.

## 3.2 Resolución de ecuaciones lineales

Resolver una ecuación lineal significa encontrar el valor de la
variable que hace verdadera la igualdad. El proceso se basa en una
propiedad fundamental de la igualdad que nos permite operar ambos
lados sin alterar la solución.

**Axioma:**
**Id:** ax.propiedad_suma
Si a = b entonces a + c = b + c para todo c ∈ ℝ.

Esta propiedad, conocida como propiedad uniforme de la suma, es la
que justifica que podamos sumar el mismo número a ambos miembros de
una igualdad sin que la igualdad deje de cumplirse. Aplicada a una
ecuación lineal, nos permite aislar la variable sumando el inverso
aditivo del término independiente en ambos lados.

**Teorema:**
**Id:** thm.aislar_variable
Si a·x + b = 0 entonces a·x = -b.
**Condición:** a, b ∈ ℝ
**Depende de:** ax.propiedad_suma

El paso de pasar de a·x + b = 0 a a·x = -b se obtiene sumando -b en
ambos miembros y aplicando que b + (-b) = 0. La igualdad resultante
deja la variable rodeada únicamente por su coeficiente, con lo que
basta dividir entre a — operación legítima cuando a ≠ 0 — para
despejarla. Lo enunciamos como teorema general.

**Teorema:**
**Id:** thm.solucion_general
La solución de a·x + b = 0 es x = -b/a.
**Condición:** a ≠ 0
**Condición:** a, b ∈ ℝ
**Procedimiento:** linear_equation_solver
**Inputs:** a, b
**Outputs:** x
**Depende de:** thm.aislar_variable, def.ecuacion_lineal

La condición a ≠ 0 no es un detalle técnico sino la frontera misma
del teorema: cuando el coeficiente principal se anula, la ecuación
deja de ser lineal y la fórmula pierde sentido — el caso a = 0
corresponde, según el valor de b, a una identidad trivial o a una
contradicción, y se trata por separado.

## 3.3 Ejemplo

Para fijar las ideas, consideremos la ecuación 3x + 6 = 0. El
coeficiente principal es a = 3 y el término independiente es b = 6.
Aplicando el teorema general obtenemos x = -6/3 = -2. La verificación
es inmediata: 3·(-2) + 6 = -6 + 6 = 0, como queríamos.
