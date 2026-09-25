# FINDINGS — experiment_03

Registro de hallazgos descubiertos durante la construcción del
experimento 03. Cada entrada documenta algo que el sistema nos enseñó
sobre sí mismo — no un cambio planificado, sino algo que emergió al
chocar el diseño contra un caso real.

Este archivo es parte del registro científico del proyecto. Su valor
para el paper es equivalente al de los resultados positivos: describe
el proceso real de diseño, incluidos los ajustes que sólo se hicieron
evidentes al escribir tests o resolver problemas concretos.

---

## 01 — Delegación recursiva desde cualquier eslabón de la cadena

**Cuándo surgió:** al escribir `test_cycle_detection` y
`test_depth_limit` para el exp_03.

**Qué se descubrió:** el protocolo original limitaba la delegación al
especialista iniciador. `SpecialistAdapter.handle(request) -> response`
no recibía el callback `delegate`, así que un especialista consultado
por el orchestrator no podía, a su vez, consultar a un tercero. Esto
hacía que los mecanismos de detección de ciclos y de fatiga cognitiva
(profundidad máxima) del `DelegationContext` **existieran pero no
pudieran ejercitarse en una cadena real** de especialistas — sólo en
escenarios que el iniciador mismo construyera.

**Por qué importa:** la arquitectura propuesta en el paper describe un
grafo de especialistas que pueden hablarse mutuamente, no una estrella
donde sólo el iniciador consulta. Sin delegación recursiva, la imagen
real del sistema era más pobre que la arquitectura declarada.

**Cambio aplicado:** `SpecialistAdapter.handle(request, delegate=None)`.
El orchestrator inyecta el mismo callback `delegate` cuando invoca al
responder; si el responder necesita a su vez consultar a otro
especialista, vuelve al orchestrator por el mismo canal y los checks
de ciclo/depth se aplican uniformemente. La firma con `delegate=None`
preserva compatibilidad: los adapters existentes que no delegan pueden
ignorar el parámetro.

**Cómo se demuestra:** `test_cycle_detection` construye dos adapters
mock A y B donde A→B→A→B…; el orchestrator aborta con
`CYCLE_DETECTED` en cuanto una clave `(requester, target_variable)` se
repite en la pila activa. `test_depth_limit` construye una cadena
A→B→C→D→E→F con `max_depth=4`: la resolución aborta con
`DELEGATION_DEPTH_EXCEEDED` antes de alcanzar F, y el número de
delegaciones registradas es menor que 6 — evidencia de que el sistema
abandonó la cadena antes de agotarla.

**Reflexión:** el cambio no fue un caso de uso previsto por el diseño
original, sino una necesidad detectada por los tests. Un sistema que
quiere demostrar metacognición (aquí: 'sabe cuándo una cadena de
dependencias es demasiado larga') necesita escenarios donde esa
metacognición se ejerza genuinamente. Los tests no sólo verificaron
propiedades — revelaron una asimetría en el protocolo que hicimos
explícita.

---

## 02 — Vínculos ontológicos como datos del enunciado, no inferencias

**Cuándo surgió:** al ejecutar por primera vez el problema canónico
del exp_03 ("energía cinética de un objeto cuya velocidad es igual al
lado de un cuadrado de diagonal 8").

**Qué se descubrió:** la frase "velocidad igual al lado" es una
equivalencia entre variables de dominios distintos (`v` en Física,
`l` en Geometría). No pertenece a ninguno de los dos dominios: es
conocimiento del enunciado. Si el orchestrator o cualquiera de los
especialistas codificara esa equivalencia, estaríamos metiendo
conocimiento ajeno donde no debe estar.

**Cambio aplicado:** `Problem.variable_bindings: dict[str, str]` —
p. ej. `{"v": "l"}`. El orchestrator honra las equivalencias al
enrutar, emitiendo un paso explícito `binding:v→l` en la traza
principal del iniciador. La razón declarada en el rationale de ese
paso lo marca como *vínculo ontológico, no inferido por ningún
especialista*.

**Corolario auditado por test:**
`test_binding_is_explicit_in_trace` verifica que (a) existe
exactamente un paso `binding:*` en la traza, (b) aparece antes de la
delegación y antes de la resolución final, (c) el rationale lo
identifica como ontológico y no como inferencia.

**Reflexión:** este hallazgo fuerza a declarar en el paper que el
sistema tiene tres clases de conocimiento — el del especialista
(teoremas, axiomas), el del enunciado (bindings, hints), y el del
orchestrator (ninguno). Distinguirlas limpiamente es una de las
propiedades más fuertes del diseño.

---

## 03 — Pistas de delegación como canal separado de la figura

**Cuándo surgió:** al intentar que Geometría entendiera "la figura es
un cuadrado" cuando Física delegaba. El `Figure.kind` de Física era
`"physics.object"`, no `"square"`; Geometría rechazaba sus propios
teoremas por `_conditions_apply`.

**Qué se descubrió:** la pista "figura cuadrada" no pertenece a Física
(que no modela figuras) ni está ya en Geometría. Tampoco es una
equivalencia entre variables: es un tipo ontológico que sólo tiene
sentido para Geometría.

**Cambio aplicado:** `Problem.delegation_hints: dict` — p. ej.
`{"figure_kind": "square"}`. El orchestrator fusiona estas pistas con
el `domain_context` de cada request antes de enrutarlo, permitiendo
que el responder las use sin que el requester haya tenido que
transportarlas explícitamente.

**Reflexión:** junto con `variable_bindings`, las `delegation_hints`
completan la caja del conocimiento del enunciado: una es 'qué
variables equivalen entre dominios', la otra es 'qué tipo ontológico
asume el enunciado para las figuras/objetos involucrados'.
