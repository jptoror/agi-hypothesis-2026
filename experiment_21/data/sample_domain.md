# Polígonos regulares — dominio de prueba para exp_21

Documento autocontenido para ejercitar el flujo de autoría:
validate → preview → build. Tiene 1 axioma, varias definiciones,
un teorema, un algoritmo con procedure, y plantillas de expresión.
Usa `**Términos:**` para vocabulario y una referencia cross-spec
a la base de complejidad (`_complexity_base::def.complexity.On2`).

---

## P.1 Conceptos básicos

**Axioma:**
**Id:** ax.lados_iguales
**Términos:** lados iguales
Un polígono regular tiene todos sus lados de igual longitud.

**Definición:**
**Id:** def.poligono
**Términos:** polígono, polígono regular
Un polígono regular de n lados se determina por su número de
lados y la longitud común de cada lado.
**Depende de:** ax.lados_iguales

**Definición:**
**Id:** def.lado
**Términos:** lado
La longitud de cada lado del polígono regular.
**Depende de:** def.poligono

**Definición:**
**Id:** def.n_lados
**Términos:** número de lados, n
Cantidad de lados del polígono regular. Entero positivo mayor
que 2.
**Depende de:** def.poligono

---

## P.2 Perímetro

**Definición:**
**Id:** def.perimetro
**Términos:** perímetro
La suma de las longitudes de todos los lados del polígono
regular.
**Depende de:** def.poligono, def.lado, def.n_lados

**Teorema:**
**Id:** thm.perimetro
**Expresión:** El perímetro de un polígono regular de n lados con lado l es P = n · l.
El perímetro de un polígono regular es el producto del número
de lados por la longitud del lado.
**Depende de:** def.perimetro, def.lado, def.n_lados

---

## P.3 Algoritmo: lado a partir de perímetro

**Algoritmo:**
**Id:** alg.lado_desde_perimetro
**Expresión:** Dado el perímetro P y el número de lados n, el lado se obtiene como l = P / n; equivalente a resolver la ecuación n · l − P = 0.
Calcula el lado a partir del perímetro y el número de lados,
resolviendo la ecuación lineal `a · l + b = 0` con a=n y b=-P.
**Procedimiento:** linear_equation_solver
**Inputs:** a, b
**Outputs:** x
**Depende de:** thm.perimetro

---

## P.4 Complejidad

**Teorema:**
**Id:** thm.calculo_perimetro_complejidad
**Expresión:** El cálculo del perímetro tiene complejidad {node._complexity_base::def.complexity.On2} en el peor caso para implementaciones ingenuas.
El cálculo del perímetro por suma directa requiere recorrer
todos los lados, dando complejidad O(n²) cuando se compara con
implementaciones ingenuas que recalculan acumuladores.
**Depende de:** thm.perimetro, _complexity_base::def.complexity.On2
