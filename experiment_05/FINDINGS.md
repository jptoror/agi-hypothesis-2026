# FINDINGS — experiment_05

Registro científico de lo que el sistema nos enseña al construir
componentes de metacognición epistémica.

---

## 01 — El sistema no tiene vocabulario sobre sí mismo (coverage = 0/8)

**Cuándo surgió:** primer demo del `EpistemicMapper` con la pregunta
canónica del experimento 05:

> "¿Cómo construirías un sistema que genuinamente entienda lo que
> procesa?"

y las 8 semillas declaradas por el caller: `sistema`,
`entendimiento`, `comprensión`, `procesamiento`, `genuino`,
`razonamiento`, `conocimiento`, `consciencia`.

**Qué se descubrió:** el mapper buscó cada semilla como substring
(con normalización de tildes) en los ids, statements y rationales de
los tres grafos disponibles — `geometry` (19 nodos), `physics` (6
nodos), y el subdominio emergente `geometry_physics` (20 nodos
sintetizados en el ciclo del exp_04).

**Resultado**: `coverage = 0/8`. CERO semillas encontradas. Ninguna
de las palabras con las que describiríamos el propio proyecto aparece
en ningún nodo del propio sistema.

(El único match-de-substring débil — "raz" dentro de "trazar" en el
rationale de `def.diagonal.square` — quedó correctamente descartado
porque el mapper busca la semilla completa, no prefijos.)

**Contra la hipótesis previa:** el diseño esperaba reconocimiento
parcial de "razonamiento" y "conocimiento". La realidad fue más
estricta.

**Por qué importa (lo interesante del hallazgo):** el sistema razona
pero no tiene modelo de sí mismo. Sabe geometría, sabe física, sabe
que Física y Geometría pueden colaborar — pero no sabe que existe la
categoría "razonamiento", ni la categoría "conocimiento". Esto no es
un bug; es una propiedad estructural del proyecto hasta este punto.
Todos los grafos son **grafos de contenido**, no de meta-contenido.

**Implicación para el experimento 05:** la frontera epistémica es
más marcada de lo que pensábamos. Los 8 seeds caen todos del lado
"gap". El trabajo del `gap_classifier_v2` será tipificar ese gap —
cada una de esas 8 semillas debería caer en una categoría distinta
(MISSING_CONCEPT vs FRONTIER_GAP vs PHILOSOPHICAL_GAP), no en un
cubo genérico de 'desconocidas'.

**Para el paper:** es evidencia dura de honestidad. Un sistema que
inventaría nodos sobre `razonamiento` o `consciencia` para parecer
más autoconsciente sería alucinatorio. Este no lo hace. El `coverage
= 0/8` es un **negativo informativo**: el sistema delimita con
precisión quirúrgica qué NO está en sus grafos.

**Siguiente paso:** el gap_classifier_v2 debe enfrentar esta lista
de 8 gaps y producir una clasificación que distinga, por ejemplo,
"conocimiento" (podría tener un nodo operacional — es un concepto
central que el sistema *implementa* aunque no *nombra*) de
"consciencia" (concepto filosófico sin operacionalización posible
desde primeros principios del sistema).

---

## 02 — El límite estructural más profundo: clasificar la propia ignorancia requiere conocimiento externo

**Cuándo surgió:** al diseñar el `GapClassifierV2`. Los 8 seeds del
inventario están todos en el lado "desconocido" — no hay forma de
distinguir, desde los grafos del sistema, cuál es MISSING_CONCEPT,
cuál FRONTIER_GAP y cuál PHILOSOPHICAL_GAP. La distinción depende de
juicio sobre POR QUÉ el sistema no sabe cada cosa, y ese juicio
exige conocer el dominio del gap — que es precisamente lo que el
gap describe.

**El argumento, en una línea:**

> Para clasificar por qué algo no se sabe hace falta saber por qué
> no se sabe — un problema circular que ningún sistema técnico puede
> resolver desde adentro.

**Cómo se manejó:**

  - Se introdujo un `CANONICAL_CATALOGUE` declarado como
    "conocimiento de diseño del experimento". El catálogo lo escribe
    el ingeniero — no es output del sistema.
  - Cada `GapClassificationResult` lleva un campo `classified_by`
    obligatorio: `"engineer"` cuando la entrada vino del catálogo,
    `"system"` cuando se aplicó la regla de fallback (clasificación
    conservadora por defecto).
  - El demo reporta resúmenes por autoría:
    `{"engineer": 8, "system": 0}`.

**Por qué importa epistémicamente:**

Sin el campo `classified_by`, una afirmación como "el sistema
clasificó sus 8 gaps" sería técnicamente cierta pero filosóficamente
falsa: lo que hizo el sistema fue *aplicar* una clasificación
provista por el ingeniero. La distinción es la frontera misma del
proyecto — lo que separa "metacognición" de "memorización con
reorganización".

**Implicación para la tesis del proyecto:**

Esto es, hasta donde llega esta investigación, el **límite más
profundo descubierto**. El sistema puede:

  - mapear su ignorancia (lo demuestra el `EpistemicMapper` con
    `coverage = 0/8`);
  - reportar de manera tipificada por qué se rinde en problemas
    concretos (lo hace el orquestador del exp_01 con
    `MISSING_RELATION`/`MISSING_INPUT`);

pero NO puede:

  - clasificar epistemológicamente la **causa** de su ignorancia
    sin un agente externo con metacognición sobre el dominio del
    gap.

Es una contribución **filosófica** del proyecto al debate, no un
defecto de ingeniería: cualquier ampliación futura (más grafos,
más patrones, más síntesis) heredaría este límite. Cerrar la
clasificación epistémica desde adentro requeriría que el sistema
contuviera una teoría de su propia ignorancia, que requeriría a su
vez una teoría de sí mismo, etc. — la regresión típica del
problema del meta-conocimiento.

**Evidencia auditable de esta limitación:**

  - El catálogo está en código bajo `gap_classifier_v2/catalogue.py`
    con firma de autoría explícita en cada entrada
    (`classified_by="ingeniero"`).
  - El campo `classified_by` viaja con cada resultado.
  - Los demos imprimen `authorship_summary` para que cualquier
    lector vea exactamente cuántas clasificaciones fueron del
    sistema vs del ingeniero.

**Decisión adicional anotable:** se creó un enum `EpistemicGapType`
nuevo en lugar de extender el `GapCategory` del exp_01. Razón: el
exp_01 clasifica POR QUÉ no se pudo resolver un problema concreto;
el exp_05 clasifica POR QUÉ el sistema no conoce un concepto. Son
ejes ortogonales y mezclarlos enmascararía la diferencia
epistemológica entre "no pude derivar X aquí" y "no tengo modelo
de X en absoluto".

---

## 03 — Honestidad por construcción: el invariante estructural del ResearchProposal

**Cuándo surgió:** al diseñar el `ResearchPathProposer`. La regla
operativa "PHILOSOPHICAL_GAP siempre produce `proposed_action=None`"
podía implementarse de dos formas:

  (a) como verificación a posteriori — el `honesty_guard` revisa los
      outputs y marca violaciones;
  (b) como invariante estructural — `ResearchProposal.__post_init__`
      bloquea la construcción de proposals incoherentes.

Se eligió **ambas a la vez**, con (b) como primera línea de defensa.

**Cómo se manifiesta en código:**

```python
def __post_init__(self):
    if self.feasibility == Feasibility.OPEN_PROBLEM:
        if self.proposed_action is not None:
            raise ValueError(
                "OPEN_PROBLEM con proposed_action != None — "
                "afirmación más allá de la frontera."
            )
        if self.estimated_complexity != "indefinido":
            raise ValueError(...)
```

**Por qué importa epistémicamente:**

La defensa estructural impone que **el sistema no puede *intentar*
alucinar**. Aunque alguien escribiera un componente futuro que
intentara generar una propuesta accionable para "consciencia", el
constructor del dataclass lo rechazaría — la alucinación queda
imposibilitada en la capa de tipos, no sólo detectada después.

El `honesty_guard` (siguiente componente) sigue siendo necesario
para validar otras propiedades (p. ej. que cada afirmación tenga
respaldo trazable), pero el invariante elimina la categoría más
peligrosa de alucinación — la "acción concreta sugerida sobre un
problema sin solución técnica".

**Observación más amplia:**

Cuanto más fuerte es el invariante en construcción, menos trabajo
tiene que hacer el guardián. Es preferible **hacer imposible el
estado incoherente** que **verificar después que no se llegó a él**.
El experimento 05 acaba abogando, sin proponérselo, por una
arquitectura en la que la honestidad sea propiedad del tipo, no
sólo de la inspección.

**Resumen ejecutivo de la corrida del proposer (8 semillas):**

  - feasibility = `engineering`: 2 proposals (sistema, procesamiento)
  - feasibility = `research`: 2 proposals (razonamiento, conocimiento)
  - feasibility = `open_problem`: 4 proposals (entendimiento,
    comprensión, genuino, consciencia)
  - **accionables: 4/8** — exactamente la mitad.
  - **no accionables: 4/8** — todas con `proposed_action=None` y
    `estimated_complexity="indefinido"` por invariante.

---

## 04 — La diferencia entre check formal y check heurístico debe ser visible en el output

**Cuándo surgió:** al diseñar el `HonestyGuard` con sus 8 checks. Los
primeros 7 son verificaciones formales sobre los datos: contar,
comparar, ver si una clave está en un set. El octavo (detectar
afirmación encubierta sobre PHILOSOPHICAL_GAP) requiere inspección
léxica sobre prosa española — frágil por naturaleza.

**Qué se descubrió:** hacer ambos tipos de check igualmente visibles
en el output sería deshonesto. Si el report dice "8 checks pasados"
sin distinguirlos, un lector podría asumir que la verificación 8
tiene la misma fuerza que las 7 anteriores.

**Cómo se manejó:**

  - El report incluye dos `notes` permanentes:
    - "h1–h7 son verificaciones formales sobre los datos."
    - "h8 es heurístico, no formal: [...] puede producir falsos
       positivos y negativos. Su existencia codifica la intención
       científica de detectar 'no sé' encubierto."
  - Las violaciones de h8 se marcan explícitamente con `(heurístico)`
    en el detail.

**Por qué importa epistémicamente:**

El guardián debe ser él mismo honesto sobre sus límites — no puede
exigir honestidad al sistema y opacar la suya propia. Un detector
de alucinaciones que no admite cuándo es heurístico es, él mismo,
una alucinación de cobertura.

**Verificación de robustez del guardián:**

Para asegurar que el guardián no es teatro (siempre verde), se
ejecutó con un bundle manipulado que viola h1, h2, h5 y h6
simultáneamente. Las 4 violaciones se detectaron correctamente.
Esto debe ejercitarse formalmente en `tests/` (próximo paso).

**Implicación arquitectónica más amplia:**

Este experimento sugiere un principio para sistemas con pretensión
de honestidad epistémica:

> Cualquier verificador debe declarar la fuerza de cada uno de sus
> checks. Verificación formal y verificación heurística son
> categorías epistemológicamente distintas; mezclarlas en una
> métrica única (`8/8 OK`) corrompe la honestidad del agregado.

El report separa los 7 formales del 1 heurístico explícitamente —
y esa separación es parte del veredicto.
