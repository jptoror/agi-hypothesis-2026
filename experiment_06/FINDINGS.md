# FINDINGS — experiment_06

Registro científico de lo que el sistema nos enseña al construir el
pipeline documento → especialista verificado.

---

## 01 — El parser detecta gaps de conocimiento ANTES de construir el grafo

**Cuándo surgió:** al diseñar `node_extractor.py` con la verificación
de dependencias (`UnresolvedDependency`).

**Qué se descubrió:** el mismo mecanismo de detección de gaps que el
razonador usa en tiempo de ejecución (exp_01: `MISSING_RELATION`,
`MISSING_INPUT`) opera ahora en tiempo de PARSING. Cuando un
`**Depende de:**` referencia un id que no existe en el documento, el
parser produce un `UnresolvedDependency` — análogo al
`MISSING_RELATION` del exp_01 pero detectado antes de construir el
grafo, no durante el razonamiento sobre él.

**Por qué importa:** un sistema que solo detecta gaps en tiempo de
razonamiento descubre la ignorancia tarde — cuando ya intentaba usar
conocimiento inexistente. Detectar gaps en tiempo de parsing es una
forma de metacognición sobre el material de entrada: "el documento
afirma cosas sobre referencias que no contiene". Esa propiedad
existía implícitamente en el exp_01 (gap classifier sobre la
resolución); aquí se hace explícita en el pipeline de construcción.

**Implicación arquitectónica:** la detección de gaps no es propia del
razonador — es una propiedad del sistema entero. Cualquier fase del
pipeline que manipule referencias entre nodos puede aplicar el mismo
patrón: `set(referencias) - set(disponibles) = gaps`. El parser, el
sintetizador (exp_04), el clasificador epistémico (exp_05) y el
guardián de honestidad (exp_05) son todos casos del mismo mecanismo
aplicado en momentos distintos del ciclo de vida.

---

## 02 — El SubdomainSpecialist del exp_04 resultó ser arquitectónicamente genérico

**Cuándo surgió:** al implementar `SpecialistFactory` y enfrentar la
decisión de "¿especialista nuevo o reutilizar uno existente?".

**Qué se descubrió:** el `SubdomainSpecialist` que construimos en el
exp_04 para subdominios emergentes (sintetizados desde patrones de
colaboración) sirve sin modificaciones para subdominios extraídos
desde documentos. Las dos propiedades clave que lo hacen reutilizable:

  - `_conditions_apply` híbrido: evalúa condiciones numéricas (`m >= 0`)
    e ignora prosa libre que no encaja en el matcher. Esto permite que
    convivan condiciones rigurosas y prosa matemática como `a ≠ 0`
    (que NO es numérica para el matcher: no hay `<op> <número>`).
  - `_scan_relevant_nodes` sin sesgo geométrico: siembra desde los
    productores del target y cierra transitivamente. No asume nada
    sobre el dominio.

**Por qué importa:** la arquitectura de especialistas que construimos
en el exp_04 — pensada para una necesidad específica — resultó ser un
componente reutilizable para cualquier subdominio cuyos nodos vengan
de fuera del razonador clásico. La emergencia de subdominios (exp_04)
y la construcción desde documentos (exp_06) son CASOS DEL MISMO
PATRÓN: "tomar un grafo construido por algún proceso externo y
montarle un especialista encima".

**Implicación para el paper:** existe una unidad arquitectónica entre
los componentes que parecían ad-hoc. El `SubdomainSpecialist` es la
abstracción correcta de "especialista que opera sobre un grafo
heterogéneo cuya forma fija desconoce a priori". Cualquier futuro
modo de origen del grafo (importación desde otra base de datos,
generación por reglas, etc.) puede reutilizarlo.

---

## 03 — La procedencia del conocimiento es propiedad del nodo, no del proceso

**Cuándo surgió:** al implementar `count_manual_nodes` y el assert
`nodes_constructed_manually == 0`.

**Qué se descubrió:** la única forma honesta de afirmar "este grafo
no contiene nodos construidos a mano" es marcar la procedencia en el
propio nodo, no rastrear el proceso de construcción. Marcar
`extracted_from_document=True` en `properties` durante el build hace
que cualquier auditor posterior pueda contar instantáneamente: "este
nodo vino del pipeline de parsing; este otro no". La afirmación se
verifica por inspección del estado, no por confianza en el código que
lo construyó.

**Por qué importa epistémicamente:** "el código que construye el
grafo es seguro" es una afirmación frágil — depende de leer el
código y confiar. "Cada nodo declara su procedencia" es una
afirmación verificable — depende solo de inspeccionar el grafo.
La diferencia es exactamente la del exp_05: defensa estructural
versus auditoría a posteriori. La marca en `properties` es la
defensa estructural; el assert del test es la auditoría.

**Generalización del patrón:** este patrón se aplica a cualquier
sistema que quiera permitir múltiples orígenes de conocimiento
(extraído de documentos, sintetizado de patrones, escrito a mano,
importado de otro sistema) sin perder trazabilidad. Una propiedad
`source` o `extracted_from_*` en cada nodo permite políticas de
ese tipo: "el especialista X solo confía en nodos extraídos de
documentos verificados", "el especialista Y prefiere nodos
sintetizados sobre los importados", etc.

---

## 04 — Acoplamiento ligero entre exp_04 y exp_06 vía `implicit_figure_kind`

**Cuándo surgió:** al ejecutar el demo del `SpecialistFactory` con
`Figure(kind="linear_equation", ...)`.

**Qué se descubrió:** el `SubdomainSpecialist` del exp_04 evalúa
condiciones de figura geométrica con una heurística que solo conoce
`square`, `triangle`, `triangle.right`, `quadrilateral` (los términos
de los grafos de los exp_01 a exp_05). Cuando el problema declara
`kind="linear_equation"` — un tipo no geométrico — la heurística no
casa con ninguna condición de prosa (no hay condiciones de figura en
los nodos extraídos), lo que en este caso particular funciona porque
el verificador es permisivo, pero requirió pasar
`implicit_figure_kind="linear_equation"` al `SpecialistFactory` para
documentar la intención.

**Por qué importa:** el `SubdomainSpecialist` arrastra una decisión
del exp_04 (la lista hardcodeada `_FIGURE_TERMS`) que es
geometría-específica. Reutilizar el componente en exp_06 funciona
pero el acoplamiento queda visible. Es un caso clásico del problema
de "componente reutilizable con suposiciones contextuales": la
abstracción es genérica en su mecanismo (verificación híbrida
numérico+prosa) pero específica en su catálogo de prosa
(figuras geométricas).

**Cómo se manejó:** se documenta como acoplamiento conocido. El
`implicit_figure_kind` permite al caller declarar el "tipo ontológico
de figura del subdominio" — para grafos no geométricos como el de
álgebra, basta declarar el slug y el verificador no rechaza nada.

**Refactor pendiente (no aplicado):** mover `_FIGURE_TERMS` a una
configuración del `SubdomainSpecialist` (parámetro de constructor en
vez de constante de módulo) permitiría que cada subdominio aporte su
propio diccionario de términos de prosa. Lo dejamos anotado como
deuda técnica visible — no es bloqueante para ninguno de los
experimentos actuales.

---

## 05 — Documento estructurado, no NL libre

**Cuándo surgió:** al diseñar la convención de marcadores
(`**Definición:**`, `**Id:**`, etc.).

**Qué se descubrió y se declaró desde el principio:** el experimento
demuestra que un documento ESTRUCTURADO en Markdown puede convertirse
en un especialista — NO que cualquier documento en lenguaje natural
puede. La estructura es la convención de marcadores; la libertad es
la prosa entre ellos. Esa frontera es deliberada: cruzarla
introduciría un componente que tendría que adivinar (LLM o NLP
suave), y eso contradice la hipótesis central del proyecto.

**Por qué importa:** establecer límites del experimento es parte de
la honestidad científica. El parser no "lee" álgebra — reconoce una
notación de libro de texto. Quien escriba un documento siguiendo la
convención obtiene un especialista; quien escriba prosa libre, no.
Esto está en la línea del exp_05: el sistema declara qué puede y qué
no puede.

**Limitación residual declarada:** el `**Id:**` obligatorio es una
carga para el autor humano. Un futuro experimento podría explorar
generación de ids desde el enunciado (heurística sobre el sujeto
nominativo), pero eso introduce una capa de adivinación. La decisión
actual — id explícito — es la más honesta.

---

## Cierre del exp_06

**Resumen ejecutivo:**

  - Documento `algebra_ch3.md` (escrito como capítulo real de
    libro de texto, ~85 líneas).
  - Pipeline de 3 fases (`StructureExtractor` →
    `NodeExtractor` → `GraphBuilder`) procesa el documento.
  - 5 nodos extraídos, 0 errores, `graph.validate()` OK.
  - 0 nodos construidos a mano (verificado por inspección de
    `properties['extracted_from_document']`).
  - Especialista registrado en la `SpecialistRegistry` con
    nombre `algebra_ch3`.
  - Resuelve `3x + 6 = 0` en 1 paso usando el nodo
    `thm.solucion_general` extraído del documento. Resultado:
    `x = -2.0` exacto.
  - 3 tests verdes en la suite del experimento.
