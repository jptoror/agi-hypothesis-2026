# FINDINGS — experiment_04

Registro científico de lo que el sistema nos enseña al construir el
experimento 04 (emergencia de subdominios por colaboración recurrente).

---

## 01 — Heurística monolingüe en el verificador de condiciones

**Cuándo surgió:** al correr por primera vez el demo del
`PatternDetector` con un problema cuya `delegation_hint` pedía
`figure_kind="triangle"`. El sistema "resolvió" el problema aplicando
`thm.square.side_from_diagonal` a un triángulo — es decir, trasladó
un teorema de cuadrados a una figura no-cuadrada sin rechazo.

**Qué se descubrió:** `GeometrySpecialist._conditions_apply` sólo
miraba palabras inglesas (`square`, `triangle`) al comparar el
`figure_kind` contra las `validity_conditions`. Como los statements
del grafo de Geometría están en castellano (`"la figura debe ser un
cuadrado"`), la heurística **nunca matcheaba** y dejaba pasar los
teoremas para cualquier figura. El problema estaba latente en los
exp_01/02/03 porque el `figure_kind` de esos problemas casaba
casualmente con lo que los teoremas necesitaban.

**Cambio aplicado:** la heurística ahora acepta tanto términos ingleses
como castellanos (`square`/`cuadrado`, `triangle`/`triángulo`,
`right`/`rectángulo`, `quadrilateral`/`cuadrilátero`). Es una
completación de la heurística existente, no magia nueva — el
validador sigue siendo lookup de substrings sobre las condiciones
declaradas.

**Reflexión:** es el tipo de bug que sólo aparece cuando estresas
el sistema con escenarios que los tests previos no cubrían. En este
caso, el ejercicio de detección de patrones (que explícitamente
construye problemas con hints variables) reveló una debilidad del
verificador que los tests unitarios previos no exhibían. Es parte
del valor de tener pipelines experimentales: se auto-documentan
defectos del diseño.

**Limitación residual:** el verificador sigue siendo una heurística
sobre lenguaje natural. Un paso futuro honesto es estructurar las
condiciones (p. ej. `applies_to_figures: {"square"}`) y dejar de
parsear prosa. Es trabajo para un experimento posterior; para el
experimento 04 no es bloqueante.

---

## 02 — Prioridad de `delegation_hints` sobre `domain_context` del requester

**Cuándo surgió:** tras arreglar el hallazgo 01, el problema canónico
del exp_03 (`physics → geometry`) dejó de resolverse: Geometría
rechazaba los teoremas de cuadrado porque la `Figure` que reconstruía
tenía `kind="physics.object"`, no `"square"`.

**Qué se descubrió:** en `CrossDomainOrchestrator`, el callback
`delegate` fusionaba `problem.delegation_hints` con
`request.domain_context`, pero `domain_context.update(hints)` no; era
al revés (`hints` perdía). Eso funcionaba mientras la heurística
anterior era monolingüe (no rechazaba nada), pero con el fix del
hallazgo 01 el bug quedó expuesto: el `figure_kind="physics.object"`
que el especialista de Física inyectaba automáticamente en el
`domain_context` sobreescribía el `figure_kind="square"` declarado por
el enunciado.

**Cambio aplicado:** invertida la prioridad. Las hints del enunciado
ganan sobre el `domain_context` del requester:

```python
merged_context = dict(request.domain_context)
merged_context.update(problem.delegation_hints)   # hints sobreescriben
```

**Reflexión:** esta es la segunda evidencia (junto con el hallazgo 02
del exp_03) de que los `delegation_hints` del enunciado son la fuente
de verdad ontológica del problema. Cualquier `domain_context` que el
especialista inyecte automáticamente es una conveniencia técnica, no
una afirmación epistémica — y debe ceder frente a lo que el enunciado
declara.

---

## 03 — Un subdominio emergente necesita un verificador HÍBRIDO de condiciones

**Cuándo surgió:** al construir el `SubdomainSpecialist`. Su subgrafo
contiene nodos con condiciones en dos idiomas ontológicos: numéricas
sobre magnitudes físicas (`"m >= 0"`) y de prosa sobre figuras
geométricas (`"la figura debe ser un cuadrado"`). Ninguno de los dos
verificadores previos (`GeometrySpecialist._conditions_apply` ni
`PhysicsSpecialist._conditions_apply`) servía solo.

**Cambio aplicado:** un `_conditions_apply` híbrido en
`SubdomainSpecialist` que:
  - evalúa las numéricas contra `problem.figure.known`;
  - contra las de figura usa un `figure_kind` EFECTIVO: el declarado
    por el problema si es geométricamente reconocible, o un
    `implicit_figure_kind` consolidado por el sintetizador (derivado
    del `delegation_hints["figure_kind"]` del patrón).

**Reflexión:** la emergencia de un subdominio no es sólo "copiar
nodos y añadir un binding" — también requiere reconciliar los
verificadores de condiciones de los dominios fuente. Es una
consecuencia no anticipada en el diseño original pero honesta: cada
dominio aporta SU manera de leer la validez, y el subdominio tiene
que saber leer ambas. El `implicit_figure_kind` es la memoria
estructural de 'el patrón asumió siempre figura cuadrada'.

---

## 04 — Emergencia = nuevos outputs, no sólo nuevos teoremas

**Cuándo surgió:** al registrar el `SubdomainAdapter` en la `Registry`
compartida del exp_03 observamos que el subdominio produce `Ec`, `v`
y `l` — tres variables. Las dos primeras vienen de nodos heredados;
`v` viene del `binding` consolidado.

**Qué se descubrió:** el binding, al ser un nodo ejecutable
`inputs=["l"] → outputs=["v"]`, aumenta las capacidades declaradas
del subdominio. No es sólo "conocimiento consolidado"; es
**capacidad declarada nueva**: el subdominio, en el nivel de la
registry, ahora anuncia que produce `v` directamente — algo que
ninguno de los grafos fuente hacía (Física tiene `v` como entrada,
no como salida).

**Reflexión:** esto se suma a la evidencia de que el subdominio es
estructuralmente MÁS que la unión de sus partes: aparece una
capacidad (producir `v` a partir de `l`) que no existía en ningún
grafo fuente. El binding no es meta-dato; es conocimiento derivado
con forma operacional.

