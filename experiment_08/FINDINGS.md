# FINDINGS — experiment_08

Registro científico de lo que el sistema nos enseñó al construir el
mecanismo de clarificación.

---

## 01 — Las stop-words son decisión del orchestrator, no del resolver

**Cuándo surgió:** al ejecutar por primera vez el orchestrator con
la instrucción canónica `"calcula el coeficiente para x con a=3, b=6"`.
Los `unrecognized_tokens` del especialista de lenguaje incluían
`["el", "coeficiente", "para", "con"]`. Sin filtro, el resolver
habría intentado clasificar `"el"` y `"para"` como candidatos a
ambigüedad — produciendo `ClarificationRequest` espurios sobre
artículos y preposiciones.

**Qué se descubrió:** la suficiencia epistémica es responsabilidad
del resolver — *dado un concepto, ¿el bus puede manejarlo?* Pero la
selección de QUÉ tokens son conceptos a evaluar es responsabilidad
del orchestrator. Mezclar ambas en el resolver acoplaría la lógica
epistémica con conocimiento sobre español (qué palabras son
funcionales, qué palabras son contenido).

**Cómo se manejó:**
  - El `ClarificationResolver` acepta cualquier string como
    `concept` y lo evalúa sin filtros.
  - El `ClarifyingOrchestrator` declara una lista de stop-words
    (`el`, `la`, `de`, `para`, `con`, ...) y filtra los
    `unrecognized_tokens` antes de invocar al resolver.
  - Si el caller declara `clarification_terms=...` explícitamente,
    esa lista gana sobre las stop-words por defecto.

**Por qué importa epistémicamente:**

> El resolver responde a la pregunta *"¿el bus sabe sobre X?"*. El
> orchestrator responde a la pregunta *"¿debo preguntar al resolver
> sobre X?"*. Son dos decisiones distintas y vivirlas en
> componentes distintos preserva la composabilidad.

Si en el futuro queremos un orchestrator multilingüe (inglés,
portugués, etc.) o un orchestrator sin filtro (uso programático
donde todo input es ya conceptual), basta con cambiar el conjunto
de stop-words sin tocar el resolver.

---

## 02 — La ClarificationRequest no es un error: es un turno de diálogo

**Cuándo surgió:** al diseñar el `ClarifyingPipelineResult` y
preguntarme dónde colocar la `ClarificationRequest`. La tentación
inicial era tratarla como un fallo (campo `error: ...`) o como un
warning (campo `warnings: list[...]`).

**Qué se descubrió:** una solicitud de clarificación es
**estructuralmente distinta** de un error o un warning:

  - Un error es una afirmación de "no funcionó".
  - Un warning es una afirmación de "funcionó pero atención".
  - Una `ClarificationRequest` es una **pregunta** dirigida al
    caller. Tiene `options`, tiene `reason`, espera respuesta.

Tratarla como error envenenaría la semántica: el sistema no falló,
el sistema admitió honestamente que necesita más información para
continuar. Esa admisión es la propiedad central del experimento, no
un fallo a ocultar.

**Cómo se manejó:**
  - `ClarificationRequest` es un campo de primer orden en
    `ClarifyingPipelineResult`, junto con `solve_result`.
  - El orchestrator PARA cuando encuentra el primer concepto
    insuficiente, devuelve el resultado parcial con la request, y
    el caller decide cómo responder.
  - El caller puede invocar `run(text, hints={"domain": "..."})`
    para reintentar — el `hints` es la respuesta al `request`.

**Implicación arquitectónica:**

> Un sistema honesto distingue entre fallar y preguntar. La
> diferencia es semántica, no técnica.

El experimento codifica esa distinción en el tipo de salida.
Cualquier futuro componente que construya conversaciones
multi-turno hereda esta forma: cada turno puede ser
`SolveResult`, `ClarificationRequest`, o un híbrido si la cadena
es más compleja.

---

## 03 — Un especialista no puede resolver sus propios gaps consultándose a sí mismo

**Cuándo surgió:** al implementar la regla de exclusión del
`initiating_specialist` en el resolver. La pregunta natural era:
"¿es realmente necesario excluirlo? Si el lenguaje no reconoció el
token, su grafo no tendrá un id que matchee — el filtro sería
redundante."

**Qué se descubrió:** la exclusión NO es redundante porque el
matching es por substring sobre ids, no por coincidencia exacta. Un
nodo `def.kind.linear_equation` podría matchear el concepto
`"linear"` o `"equation"` aunque el lenguaje haya fallado en
procesarlo por otra razón (p. ej. el token no es una keyword
declarada). Sin la exclusión, el lenguaje aparecería como
"candidato" para conceptos que él mismo no procesó — un absurdo
epistémico.

**Cómo se manejó:**
  - `ClarificationResolver.__init__(initiating_specialist=...)`
    recibe el nombre del especialista que delegó la consulta.
  - Tanto en `_candidates_for` como en `_all_eligible_names`, el
    iniciador queda fuera explícitamente.
  - Cuatro tests verifican que `language` no aparece en `options`
    en ningún veredicto.

**Por qué importa epistémicamente:**

> Si X no pudo procesar Y, preguntar a X si Y le pertenece es
> circular. La auto-consulta como mecanismo de resolución es un
> bug categorial, no un caso edge.

Es la misma lógica del exp_03 cuando el orchestrator detecta que
"el único productor disponible es el propio requester" y devuelve
DOMAIN_MISMATCH. La regla aquí es la versión específica del exp_08:
**el resolver del bus no propone al especialista que activó la
clarificación**.

---

## 04 — Dos tipos de suficiencia distintos, mismo resultado

**Cuándo surgió:** al verificar el demo canónico. Sin hints, el
sistema responde `SUFFICIENT(domain=algebra_ch3)` por unicidad —
álgebra es el único especialista del bus que conoce "coeficiente".
Con `hints={"domain":"algebra"}`, también responde `SUFFICIENT`,
pero por declaración explícita del caller. Ambos caminos resuelven
en `x = -2.0`.

**Qué se descubrió:** existe una distinción epistemológica
relevante entre:

  - **Suficiencia por unicidad estructural** (paso 2 del algoritmo
    del resolver): el bus solo tiene un candidato. La decisión es
    automática y deductiva — *no hay otra opción posible*.
  - **Suficiencia por declaración explícita** (paso 1): el caller
    aportó la información. La decisión la zanja un agente externo
    al sistema.

El resultado es el mismo, pero las **razones** son distintas y la
traza lo refleja: la `domain` del `SufficiencyAssessment` viene de
fuentes diferentes en cada caso.

**Implicación para auditoría:**

> Saber QUE el sistema decidió X es necesario. Saber POR QUÉ
> decidió X — porque era la única opción versus porque alguien lo
> declaró — es lo que hace la decisión auditable.

Si más adelante el bus crece y un mismo concepto pasa a tener
múltiples candidatos, el camino de "suficiencia por unicidad" deja
de funcionar y el sistema empezará a emitir `ClarificationRequest`.
Ese cambio de comportamiento es **deseable** y **detectable** —
los `SufficiencyAssessment` históricos quedan como evidencia de
qué bus había en el momento.

**Reflexión más amplia:**

Los dos caminos son la versión epistémica del exp_05: el sistema
distingue entre lo que sabe por estructura propia y lo que sabe
porque un humano lo declaró. Mantener la distinción explícita en
los tipos de salida es lo que permite no confundir capacidad
emergente con conocimiento inyectado.
