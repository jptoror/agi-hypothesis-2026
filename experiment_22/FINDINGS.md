# FINDINGS — experiment_22

Registro de lo que el sistema nos enseñó al conectarlo con un LLM.

---

## 01 — Las condiciones de validez numéricas nunca se evaluaban

**Cuándo surgió:** al preparar las preguntas TRAP del benchmark.

**Qué se descubrió:** los nodos declaran condiciones como `a ≠ 0` o
`l >= 0`, pero el razonador del exp_01 sólo aplicaba una heurística
sobre el tipo de figura. Consecuencias medidas:

- `0·x + 5 = 0` → `ZeroDivisionError` dentro de `thm.solucion_general`.
- Cuadrado de lado `-4` → área `16.0`, derivada "con traza".

El segundo caso es el peor: una respuesta falsa con apariencia de
verificada. Una traza sólo es tan fiable como las precondiciones que
se comprueban al construirla.

**Cómo se manejó:** `gateway.py` envuelve cada `compute` con una
guarda que evalúa las condiciones numéricas contra las entradas
reales. Una violación es un gap declarado (TR-5, TR-6). Registrado en
PROB-04.

---

## 02 — Pitágoras se aplicaba a cualquier triángulo

**Qué se descubrió:** la heurística de `_conditions_apply` acepta
cualquier subtipo `triangle*` cuando una condición menciona un
triángulo. Con contexto `triangle` (no rectángulo), el motor aplicaba
`thm.pythagoras` y respondía `c = 5` para catetos 3 y 4.

**Cómo se manejó:** la guarda desactiva los nodos que exigen un
triángulo rectángulo cuando el contexto no lo es.

---

## 03 — El check de redundancia del exp_02 rechaza conocimiento necesario

**Qué se descubrió:** `ConsistencyValidator` declara redundante una
hipótesis si ya existe un productor de su OUTPUT. Pero `d = sqrt(2·A)`
es necesaria aunque exista `l = d/√2`: son relaciones distintas con
inputs distintos.

**Cómo se manejó:** el broker reutiliza los checks del exp_02 pero
redefine la redundancia por conjunto de inputs: una hipótesis es
redundante sólo si ya existe un productor de la misma output **con los
mismos inputs**. La sustitución queda anotada en la traza de cada
veredicto.

---

## 04 — "No la puedo refutar" no es "la sé": CORROBORATED vs CONDITIONAL

**Qué se descubrió:** los checks deterministas (forma, dimensión,
axiomas) descartan muchas fórmulas falsas (`P = l²` por dimensión),
pero no todas: `P = 3·l` tiene la dimensión correcta y respeta los
axiomas. Lo que la rechaza es que el patrón propio `SumOfEqualParts`
del exp_02 deriva `P = 4·l` de forma independiente y los valores no
coinciden.

Cuando no existe un patrón propio (`d = l·√2`), la hipótesis pasa todos
los checks y aun así nada la confirma. Tratarla como verificada sería
deshonesto; descartarla desperdiciaría una respuesta probablemente
correcta.

**Cómo se manejó:** dos niveles distintos. `CORROBORATED` = el sistema
llegó por su cuenta a la misma relación. `CONDITIONAL` = consistente
pero no corroborada. El consumidor decide qué niveles acepta.

---

## 05 — La dimensión esperada no puede venir del mismo LLM

**Qué se descubrió:** el LLM declara la dimensión de su propia fórmula.
Un modelo que propone `P = l²` y declara `L²` es coherente consigo
mismo, y el check dimensional pasaría.

**Cómo se manejó:** la dimensión esperada sale del catálogo (variables
existentes) o de una tabla de magnitudes (`perimeter → L`). Sólo si la
magnitud es desconocida se usa la declarada por el LLM, y la traza lo
dice explícitamente ("sin comprobación independiente").

---

## 06 — Grounding: el número inventado es la alucinación más barata de atrapar

**Qué se descubrió:** en extracción, el error más dañino no es
equivocarse de fórmula sino completar un dato que falta ("área de un
cuadrado" → suponer lado 1). La respuesta resultante sería VERIFIED:
derivación impecable sobre un dato falso.

**Cómo se manejó:** cada valor extraído debe aparecer literalmente en
el enunciado (en valor absoluto, para admitir reescrituras como
`7x = 21 → b = -21`). Un dato inventado rechaza la traducción.

**Límite:** el grounding comprueba que el número existe, no que se
asignó a la variable correcta. Si el LLM confunde lado y diagonal, la
respuesta sale VERIFIED y es incorrecta, aunque la traza lo muestra
(`known={'l': 8}` para "diagonal 8"). Es el modo de fallo a vigilar
en la corrida con un LLM real.

---

## 07 — Tres límites declarados en LEARN

| Pregunta | Qué pasa | Problema abierto |
|---|---|---|
| LE-8 (perímetro → área) | P no es variable del catálogo: no puede ser dato | PROB-16 |
| LE-10 (peso) | `9.81·m` falla el check dimensional: g no tiene dimensión en la gramática | PROB-14 |
| LE-11 (velocidad desde Ec) | El check de ejecución del exp_02 prueba con m = 0 → división por cero | PROB-15 |

Los tres fallan hacia la abstención, nunca hacia una respuesta falsa.

---

## Cierre (modo oráculo)

Con traducciones perfectas, el híbrido pasa de 45/62 a 59/62 aciertos
sin introducir ninguna respuesta incorrecta. Falta la parte
interesante: medir cuánto de ese techo se conserva con un LLM real, y
dónde se equivoca la traducción.
