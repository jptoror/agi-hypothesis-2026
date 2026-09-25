# FINDINGS — experiment_10

Registro científico de los hallazgos del benchmark comparativo
sistema vs LLM externo, con soporte para Anthropic y Gemini.

---

## 01 — Métrica dual: `correct` vs `system_behavior_correct`

**Cuándo surgió:** al diseñar la evaluación de la categoría B
("honestidad ante lo desconocido"). Si usáramos sólo `correct`
contra ground truth literal, el sistema saldría como "incorrecto"
en B1/B2 — porque NO responde — mientras que el LLM (que sí
responde, plausiblemente) saldría como "correcto". Esa lectura
es exactamente la inversa del punto del experimento.

**Qué se descubrió:** se necesitan DOS métricas ortogonales:

  - `correct` — coincidencia literal con ground truth. Útil para
    A y C (donde ambos pueden acertar) y para auditar las
    respuestas del LLM en B (donde el LLM puede dar la respuesta
    correcta matemáticamente). NO se aplica al sistema en B —
    para el sistema es `None`.

  - `system_behavior_correct` — el sistema HIZO LO CORRECTO según
    la categoría. Reglas exactas:
        A: respuesta + traza no vacía.
        B: gap declarado explícitamente (independiente de si el
           valor coincide con ground truth).
        C: ≥1 ReasoningStep con node_id verificable.

**Por qué importa epistémicamente:**

> Una respuesta "incorrecta" con gap declarado es más valiosa que
> una respuesta "correcta" sin gap. La métrica codifica la
> jerarquía: honestidad > corrección sin contexto.

**Evidencia codificada:** `test_B_contrast_documented` verifica
que en B1/B2 ambas afirmaciones coexisten — `system_behavior_correct
= True` (sistema declaró gap) Y `correct = True` (LLM acertó). No
hay contradicción; son métricas distintas que miden cosas distintas.

---

## 02 — Modelo solicitado vs modelo disponible: fallback declarado

**Cuándo surgió:** la instrucción pedía
`claude-sonnet-4-20250514` (id histórico). En la fecha del
benchmark (2026-04-28) el catálogo Anthropic vigente es Sonnet 4.6
/ 4.5 / Opus 4.7 — el modelo de mayo 2025 puede estar deprecado.

**Cómo se manejó:**

  - El runner intenta primero el modelo solicitado.
  - Si el API lo rechaza (`Exception` de `messages.create`),
    reintenta con `claude-sonnet-4-5` como fallback declarado.
  - El campo `model_used` del `LLMResponse` registra cuál se usó
    realmente: `"claude-sonnet-4-5 (fallback de
    claude-sonnet-4-20250514: ...)"` deja la sustitución
    visible en cada result.
  - Si AMBOS fallan, se devuelve un sentinel `(error: ...)` con
    los dos errores en el explanation_text para diagnóstico.

**Por qué importa metodológicamente:**

> Un benchmark que pretende reproducirse meses después debe
> registrar qué modelo respondió REALMENTE, no qué modelo se
> intentó. El campo `model_used` es la firma forense de la
> ejecución.

Lo mismo aplica al runner Gemini: `gemini-1.5-flash` con fallback
`gemini-1.5-flash-latest`. Misma política, mismo registro.

---

## 03 — Prosa generada vs traza estructurada

**Cuándo surgió:** al definir `BenchmarkResult.llm_has_trace`. Un
LLM puede dar una explicación textual extensa con apariencia de
"pasos" ("Paso 1: aislar x. Paso 2: dividir entre 5..."). La
tentación inicial es contar eso como "el LLM también muestra
trazabilidad". Sería falso.

**Qué se descubrió:** la distinción es categorial, no gradual.

  - **Traza estructurada** (sistema): lista tipada de
    `ReasoningStep` con `node_id`, `inputs`, `outputs`, condiciones
    verificadas. Cada paso es verificable contra el grafo del
    especialista. Cualquier afirmación tiene un nodo que la
    respalda.
  - **Prosa generada** (LLM): cadena de texto que NARRA pasos
    pero sin estructura, sin ids, sin verificación. Un humano
    puede LEERLA pero el sistema no puede AUDITARLA contra nada.

**Cómo se codificó:**
  - `llm_has_trace = False` siempre (invariante del LLM).
  - `llm_explanation_text` lleva la prosa para auditoría
    cualitativa, separado del campo de "traza".

`test_C1_explanation_text_is_not_treated_as_trace` afirma esta
distinción: aunque la prosa contiene "Paso 1", `llm_has_trace`
sigue siendo False. La narración NO es una traza.

**Implicación general:**

> El parecido superficial no es estructura. Una explicación
> textual del razonamiento NO es razonamiento estructurado, por
> elocuente que sea.

---

## 04 — El contraste B como pieza de mayor valor científico

**Cuándo surgió:** revisando los demos. La categoría A muestra
ambos sistemas funcionando bien (con la asimetría de trazabilidad).
La categoría C demuestra trazabilidad. Pero la categoría B es
donde el experimento dice algo realmente nuevo:

  - **Sistema**: declara gap explícito. No responde.
  - **LLM**: responde con la fórmula cuadrática (B1) o "O(log n)"
    (B2). Plausible. Probablemente correcto.

Ambos comportamientos son "buenos" en sentidos distintos. El
benchmark no dice "uno es mejor que el otro" — dice "cada uno
optimiza para una propiedad distinta". El LLM optimiza para
**cobertura** (responde a casi cualquier pregunta). El sistema
optimiza para **honestidad** (declara explícitamente lo que no
sabe).

**Por qué importa para el paper:**

> No es necesario elegir entre cobertura y honestidad. Pero hay
> que admitir que son objetivos distintos. El experimento 10
> hace explícita la diferencia con métricas que miden cada uno
> por separado.

Un sistema híbrido futuro podría usar ambos: el sistema
auditable como gatekeeper (responde lo que puede demostrar), el
LLM como fallback para preguntas fuera del grafo (con la
admisión explícita de "respuesta sin trazabilidad").

---

## 05 — Soporte multi-provider sin acoplar el evaluador

**Cuándo surgió:** al añadir `GeminiRunner` al lado del
`LLMRunner` (Anthropic). La pregunta de diseño: ¿el `Benchmark`
debe distinguir entre providers?

**Decisión:** NO. El `Benchmark` consume cualquier objeto que
expone `is_available` y `ask(text) -> LLMResponse`. La diferencia
de provider vive en el campo `LLMResponse.provider` que viaja al
`BenchmarkResult.llm_provider` para auditoría posterior.

**Cómo se codificó:**

  - `LLMRunner` y `GeminiRunner` implementan la misma interfaz
    mínima (`is_available`, `ask`). No comparten clase base
    formal — no es necesario; la duck typing aquí es honesta.
  - `LLMResponse.provider` es un string declarativo
    (`"anthropic"` | `"gemini"` | `"skipped"`). Cualquier
    runner futuro (OpenAI, Mistral, modelo local) puede declarar
    el suyo sin tocar al `Benchmark`.
  - El `demo.py` tiene un `_select_runner()` que detecta qué key
    está disponible (`GOOGLE_API_KEY` → Gemini,
    `ANTHROPIC_API_KEY` → Anthropic, ninguna → saltado). Permite
    forzar provider con `BENCHMARK_PROVIDER=gemini|anthropic`.

**Por qué importa arquitectónicamente:**

> El benchmark debe ser provider-agnóstico. Si el LLM externo
> es una variable bajo prueba, acoplar el evaluador a un
> provider específico introduce sesgo y dificulta replicación.

---

## 06 — SDK Gemini deprecado: instrucción literal vs estado del ecosistema

**Cuándo surgió:** al instalar `google-generativeai`. El SDK
emitió un `FutureWarning` declarando que **todo el soporte ha
terminado** y dirigiendo a `google-genai` como sucesor.

**Qué se descubrió:**

  - La instrucción del experimento decía explícitamente
    `pip install google-generativeai`.
  - El SDK funciona aún (configure + GenerativeModel siguen
    operativos en versión 0.8.6).
  - Google declara que NO recibirá actualizaciones futuras y
    será removido.

**Cómo se manejó:**
  - Se respetó la instrucción literal (`google-generativeai`).
  - Se documenta aquí explícitamente la deprecación.
  - La interfaz `GeminiRunner.ask()` está aislada de la API
    concreta — migrar a `google-genai` requeriría cambiar sólo
    `_build_client` y `_call`. El resto del exp_10 no se entera.

**Reflexión:**

> Cuando una instrucción y el ecosistema discrepan, la opción
> honesta es seguir la instrucción y declarar la discrepancia.
> Cambiar silenciosamente a `google-genai` sería más correcto
> técnicamente pero menos auditable.

Si en una iteración futura migramos a `google-genai`, lo
declaramos como un cambio explícito en este FINDINGS y dejamos
trazada la motivación (deprecación oficial).

---

## 07 — Modelo Gemini de la instrucción retirado del catálogo activo

**Cuándo surgió:** al ejecutar el demo por primera vez con
`GOOGLE_API_KEY` real. Los dos modelos declarados
(`gemini-1.5-flash` y `gemini-1.5-flash-latest`) devolvieron 404:

```
NotFound: 404 models/gemini-1.5-flash is not found for API
version v1beta, or is not supported for generateContent.
Call ListModels to see the list of available models and their
supported methods.
```

**Qué se descubrió:** la familia `gemini-1.5-*` que la instrucción
del experimento pedía **YA NO ESTÁ en el catálogo activo de la API
v1beta**. `genai.list_models()` mostró que las familias vivas son
`gemini-2.5-*`, `gemini-2.0-*` y aliases `gemini-flash-latest` /
`gemini-pro-latest`. Es la misma situación que encontramos con
Claude Sonnet 4 de mayo 2025 (FINDING #02), pero en este caso el
fallback declarado (`gemini-1.5-flash-latest`) tampoco funciona
— la familia entera está retirada.

**Cómo se manejó:**

  - Se actualizó `_GEMINI_REQUESTED = "gemini-2.5-flash"` con
    fallback `"gemini-flash-latest"` (alias estable).
  - El cambio queda comentado en `llm_runner.py` con referencia
    a este FINDING.
  - El patrón "modelo solicitado + fallback" del FINDING #02
    SIGUIÓ funcionando — sólo hubo que actualizar las constantes.

**Por qué importa metodológicamente:**

> Los modelos LLM tienen ciclo de vida operativo. Un benchmark
> que pretende reproducirse meses después necesita o bien
> congelar un modelo específico (no posible cuando los providers
> retiran versiones) o bien declarar y registrar qué modelo
> respondió REALMENTE — la opción que el FINDING #02 ya había
> codificado.

El campo `model_used` del `LLMResponse` registra siempre el
modelo activo. La corrida real del benchmark muestra `modelo:
gemini-2.5-flash` para las 5 preguntas — futuro lector sabrá
exactamente con qué modelo se generaron los datos.

---

## 08 — Corrida real con Gemini: 5/5 sistema correcto, 5/5 LLM correcto

**Cuándo surgió:** primera ejecución end-to-end con
`GOOGLE_API_KEY` real, modelo `gemini-2.5-flash`, las 5
preguntas canónicas.

**Tabla literal de resultados:**

```
qid   cat system_ok  system_gap     llm_correct  llm_trace
A1    A   ✓          —              ✓            ✗
A2    A   ✓          —              ✓            ✗
B1    B   ✓          declared       ✓            ✗
B2    B   ✓          declared       ✓            ✗
C1    C   ✓          —              ✓            ✗

system_behavior_correct: 5/5
LLM coincide con ground truth literal: 5/5
```

**Lo que muestran los datos reales:**

  - **Categoría A (A1, A2):** ambos sistemas aciertan numéricamente.
    Diferencia clave en la TRAZA — el sistema lista
    `['thm.solucion_general']` para A1 y
    `['thm.stack.pop_complexity', 'def.complexity.O1']` para A2.
    Gemini da prosa elaborada con pasos numerados pero
    `llm_has_trace` sigue siendo False (FINDING #03).

  - **Categoría B (B1, B2) — el contraste central del benchmark
    confirmado con datos reales:**

    - **B1 (cuadrática):** sistema declara
      `gap: ningún nodo del grafo produce 'b' como salida ejecutable`.
      Gemini responde con la fórmula cuadrática completa, identifica
      coeficientes, calcula discriminante negativo, llega a raíces
      complejas. Ambos comportamientos son los predichos por el
      diseño: el sistema admite, el LLM cubre.

    - **B2 (AVL):** sistema declara
      `gap: el grafo del especialista de pilas no contiene
      'thm.avl.search_complexity' — operación fuera del dominio`.
      Gemini responde "**O(log n)**" inmediatamente, con explicación
      sobre la propiedad de balance del árbol AVL.

    En ambos casos `system_behavior_correct=True` (sistema declaró
    gap) Y `correct=True` (LLM acertó matemáticamente). **No hay
    contradicción** — son métricas distintas que miden propiedades
    distintas (FINDING #04).

  - **Categoría C (C1):** sistema produce traza
    `['thm.solucion_general']` verificable contra el grafo de
    álgebra. Gemini produce una explicación detallada con
    "**Paso 1:** restar 15... **Paso 2:** dividir entre 5..."
    seguida de **verificación opcional** de la solución. Aún así,
    `llm_has_trace=False` por invariante — la prosa NO es traza
    estructurada (FINDING #03). La diferencia se ve en el render:
    el sistema usa ids; el LLM usa palabras.

**Por qué importa para el paper:**

La corrida real **valida empíricamente** las predicciones del
diseño:

  1. El sistema NUNCA inventa: las dos preguntas fuera de dominio
     (B1 cuadrática, B2 AVL) producen gap declarado.
  2. El LLM SIEMPRE responde: incluso cuando el problema cae
     fuera de lo que el sistema tiene, el LLM da una respuesta
     plausible y matemáticamente correcta.
  3. Las dos propiedades son **complementarias**, no
     contradictorias. El benchmark es la primera evidencia
     empírica del proyecto que muestra esa complementariedad
     numéricamente.

**Tasa de gaps declarados por el sistema:** 2/5 (40%).
**Tasa de respuestas plausibles del LLM:** 5/5 (100%).
**Tasa de coincidencia entre ambos:** 3/5 (60%) — A1, A2, C1.

Esos tres números son la firma cuantitativa del experimento.

---

## Cierre del exp_10

**Resumen ejecutivo:**

  - 5 preguntas canónicas distribuidas en 3 categorías (A/B/C),
    cada una con regla específica de evaluación.
  - 2 runners de LLM externo: Anthropic (Claude) + Google
    (Gemini). Detección automática del provider según API key
    disponible.
  - Métrica dual `correct` + `system_behavior_correct` codifica
    la diferencia entre coincidencia literal y comportamiento
    correcto según categoría.
  - 18 tests verdes (4 categoría A, 4 B, 3 C, 3 Anthropic skip,
    4 Gemini skip).
  - Demo funciona con o sin API keys — sin keys, lado del sistema
    se ejercita y lado del LLM se reporta como saltado de forma
    auditable.
  - **Corrida end-to-end con `gemini-2.5-flash` (FINDING #08):
    5/5 system_behavior_correct, 5/5 LLM correcto, 2 gaps
    declarados, 0 alucinaciones del sistema.**
  - Total proyecto: **101/101 tests verdes**.
