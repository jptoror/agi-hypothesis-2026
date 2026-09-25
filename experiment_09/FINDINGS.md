# FINDINGS — experiment_09

Registro científico de lo que el sistema nos enseñó al construir
el especialista de pilas anclado al grafo base de complejidad.

---

## 01 — Cierre transitivo selectivo: el subgrafo importa solo lo referenciado

**Cuándo surgió:** al construir el especialista de pilas y verificar
qué nodos del grafo base de complejidad acabaron en su grafo final.
La intuición inicial era "el especialista necesita conocer toda la
teoría de complejidad". La realidad fue otra: el documento de pilas
sólo referencia `def.complexity.O1`, y eso es lo único que el
builder importa — junto con su fundamento transitivo
`ax.complexity.total_order`.

**Qué se descubrió:** el cierre transitivo del builder es
**selectivo por referencia**, no exhaustivo. Sólo entran al grafo
final los nodos del base que el documento referencia (directa o
indirectamente). Los nodos `def.complexity.Ologn`, `def.complexity.On`,
`def.complexity.Onlogn`, `def.complexity.On2` y
`thm.complexity.comparison` quedan FUERA del grafo del especialista
de pilas — porque el documento no los menciona.

**Conteo final:**
  - 8 nodos del documento (def.stack, def.stack.top_pointer,
    def.op.{push,pop,top}, thm.stack.{push,pop,top}_complexity)
  - 2 nodos importados del base (def.complexity.O1 y
    ax.complexity.total_order)
  - **Total: 10 nodos**, no 15 (que serían 8 + los 7 del base).

**Por qué importa epistémicamente:**

> Un especialista no debe arrastrar conocimiento que no usa. La
> selectividad del cierre transitivo materializa el principio "cada
> dominio sabe lo que necesita saber".

Esta propiedad es la diferencia entre una arquitectura de grafos y
una arquitectura monolítica. Si el builder importara TODO el base,
cualquier especialista que tocara complejidad arrastraría el grafo
entero — y el subgrafo perdería su carácter específico de dominio.

**Implicación arquitectónica:**

Los grafos base son **bibliotecas**, no **prerequisitos completos**.
Cada documento toma lo que necesita; el base puede crecer
indefinidamente sin que los especialistas que lo consultan crezcan
con él.

---

## 02 — Separación de responsabilidades: especialista vs grafo base

**Cuándo surgió:** al diseñar el demo de la pregunta "¿Es push más
eficiente que búsqueda lineal?". La tentación inicial era ejercitar
`thm.complexity.comparison` desde el especialista de pilas
(invocándolo sobre `graph.get(...)`). Falló: `thm.complexity.comparison`
y `def.complexity.On` NO están en el grafo del especialista de pilas
(consecuencia del hallazgo 01). Para responder la pregunta, hay que
invocar el teorema **directamente sobre el grafo base**.

**Qué se descubrió:** las preguntas se reparten epistemológicamente:

  - **Preguntas sobre PILAS** ("¿cuál es la complejidad de push?")
    se responden con el especialista de pilas — su grafo trae el
    teorema relevante con el fundamento O(1).
  - **Preguntas sobre COMPLEJIDAD GENERAL** ("¿O(1) es más
    eficiente que O(n)?") se responden con el grafo base — es el
    dominio nativo de esa pregunta.

Mezclar ambas en un único grafo del especialista de pilas sería
incorrecto: el especialista no es la autoridad sobre comparación
de complejidades; sólo sabe que push es O(1) porque el documento
lo declaró. La autoridad sobre el orden total de complejidades vive
en el grafo base, donde está el axioma que la sustenta.

**Por qué importa epistémicamente:**

> No todo el conocimiento debe vivir en el especialista que más se
> le parece. Algunas preguntas pertenecen estructuralmente a la
> base que sostiene a varios especialistas a la vez.

Si más adelante construimos especialistas de cola, lista y árbol
desde documentos análogos, todos referenciarán `def.complexity.O1`
o similares. Ninguno necesita el `thm.complexity.comparison`
internamente — esa pieza es de uso compartido entre dominios y
debe vivir donde TODOS pueden alcanzarla, no replicarse en cada
especialista.

**Decisión codificada en el demo:**

```python
# Pregunta sobre pilas: graph del especialista.
push_thm = graph.get("thm.stack.push_complexity")

# Pregunta sobre complejidad general: graph base.
base = build_complexity_base_graph()
comparison = base.get("thm.complexity.comparison")
```

La explicitud del paso `build_complexity_base_graph()` deja claro
que la comparación NO es capacidad del especialista de pilas. Es
una pieza compartida.

---

## 03 — Bug del orden de marcadores en exp_06: `**Depende de:**` sobrescribía

**Cuándo surgió:** al verificar el primer parse del documento de
pilas. Las foundations de los 3 teoremas de complejidad NO incluían
`def.complexity.O1` — sólo los `def.op.*` y `def.stack.top_pointer`.
El marcador `**Complejidad:** def.complexity.O1` parecía ignorado.

**Qué se descubrió:** el bug NO estaba en el handler nuevo de
`**Complejidad:**` sino en el handler existente de `**Depende de:**`.
Cuando ambos marcadores aparecían en el mismo bloque y `**Complejidad:**`
venía PRIMERO, su contribución a `explicit_dependencies` se
acumulaba; pero al llegar `**Depende de:**`, su handler hacía
**asignación**, no fusión:

```python
elif marker == _SEC_DEPENDS:
    explicit_deps = _split_csv_ids(value)   # ← sobrescribe TODO
```

El resultado: `def.complexity.O1` desaparecía del momento en que
llegaba `**Depende de:**`.

**Por qué no se había detectado antes:** en el exp_06 sólo había
**un** marcador que aportaba dependencias (`**Depende de:**`),
así que la asignación coincidía con la semántica deseada. La
adición de `**Complejidad:**` fue la primera vez que dos marcadores
coincidieron en el mismo bloque y expusieron la asunción implícita
del handler.

**Cómo se manejó:**

```python
elif marker == _SEC_DEPENDS:
    new_deps = _split_csv_ids(value)
    if explicit_deps is None:
        explicit_deps = list(new_deps)
    else:
        for d in new_deps:
            if d not in explicit_deps:
                explicit_deps.append(d)
```

Fusión consistente con el handler de `**Complejidad:**`. Sin
duplicados, preservando el orden de aparición.

**Por qué importa metodológicamente:**

> Una asunción implícita ("nadie más toca esta variable") es el
> tipo de bug que sólo aflora cuando alguien rompe la asunción.
> Añadir el primer caso que la rompe es el mejor test posible.

Los 3 tests del exp_06 seguían verdes con la asignación
sobreescrita — porque su único caso de uso (el documento de
álgebra) no tenía dos marcadores que aportaran dependencias. El
exp_09 fue el primer experimento que lo expuso. **El nuevo
comportamiento (fusión) no rompe ninguno de los tests previos**
porque la fusión sobre acumulador `None` es idempotente con la
asignación original.

**Lección general:**

Cuando se añade un marcador semánticamente equivalente a otro
existente, conviene auditar TODOS los handlers que tocan el mismo
campo del modelo. El campo compartido es la frontera donde la
asunción implícita puede vivir oculta.

---

## 04 — Especialistas declarativos vs especialistas ejecutables

**Cuándo surgió:** al revisar el demo del exp_09 — el especialista
de pilas resuelve "preguntas estructurales" pero NO tiene `compute`
ejecutables. Los 3 teoremas (`thm.stack.push_complexity`,
`thm.stack.pop_complexity`, `thm.stack.top_complexity`) son
declarativos: enuncian que push es O(1) sin computar nada
numéricamente.

**Qué se descubrió:** existen dos tipos de especialistas en el
proyecto:

  - **Ejecutables (exp_06: álgebra)**: el grafo tiene teoremas con
    `compute` (linear_equation_solver). El especialista responde
    `Problem(target="x", ...)` con un valor numérico (-2.0).
  - **Declarativos (exp_09: pilas)**: el grafo tiene teoremas sin
    `compute`. El especialista responde con NODOS y FUNDAMENTOS,
    no con valores. La pregunta "¿cuál es la complejidad de push?"
    se responde inspeccionando que `def.complexity.O1` está en los
    foundations del teorema.

Ninguna de las dos categorías es "más correcta" — son distintos
modos de razonamiento. El sistema soporta ambos sin codificar el
modo en ninguna parte: simplemente respeta `compute=None` cuando
el documento no declara procedimiento.

**Por qué importa epistémicamente:**

> No todo el conocimiento es ejecutable. Saber que "push es O(1)"
> es un hecho declarativo verificable por inspección de
> fundamentos, no por evaluación de una función.

El sistema modela ambas formas de saber. Un teorema con `compute`
sabe COMPUTAR su consecuencia; un teorema sin `compute` sabe
DECLARAR su contenido y dejar que el caller razone sobre los
fundamentos. El experimento 09 es el primero que ejercita
intencionalmente el segundo modo.

**Implicación para el paper:**

La distinción declarativo/ejecutable es ortogonal a la distinción
axioma/definición/teorema. Un teorema puede ser ejecutable
(`thm.solucion_general` del exp_06) o declarativo
(`thm.stack.push_complexity` del exp_09). El `EpistemicStatus`
clasifica la NATURALEZA epistémica del nodo; `compute` es None
clasifica el MODO de uso. Mantener los dos ejes separados permite
que el grafo modele dominios donde el "saber" no es siempre
"calcular".

---

## Cierre del exp_09

**Resumen ejecutivo:**

  - Grafo base de complejidad (7 nodos) construido a mano,
    `validate()` limpio.
  - Documento `data_structures_stack.md` (~85 líneas, prosa
    natural de capítulo) con 8 nodos extraíbles.
  - Marcador nuevo `**Complejidad:**` añadido al parser del exp_06
    (cambio aditivo).
  - Builder del exp_06 extendido con `base_graph` opcional + cierre
    transitivo selectivo (cambio aditivo).
  - Especialista de pilas con grafo final de **10 nodos** (8 doc
    + 2 base), 0 nodos manuales, `validate()` OK.
  - 17 tests del exp_09 verdes; los 66 tests previos del proyecto
    siguen verdes — **83/83 en total**.
  - Bug latente en `**Depende de:**` del exp_06 detectado y
    arreglado durante la integración con `**Complejidad:**`.
