# Open Problems — agi-hypothesis

Registro de problemas identificados durante la construcción.
Cada problema incluye dónde se detectó, qué impacto tiene,
y qué soluciones son candidatas cuando haya evidencia suficiente.

---

## PROB-01 — Persistencia entre sesiones
**Detectado en:** experiment_02
**Síntoma:** Nodos aprendidos en runtime desaparecen 
             al reiniciar el proceso
**Impacto:** El sistema no acumula conocimiento 
             entre sesiones — cada run empieza desde cero
**Bloqueante para:** Cualquier uso real del sistema
**Soluciones candidatas:**
  - Serialización JSON por especialista (simple, ya viable)
  - SQLite local (sin dependencias externas)
  - Base de datos de grafos como Neo4j (escala)
**Trabajo realizado:**
  - experiment_02/persistence/serialize.py implementa
    dump(graph, path) + load(path, registry) con formato JSON
    estable (schema_version=1).
  - experiment_02/persistence/registry.py implementa
    ComputeRegistry para reconectar funciones ejecutables tras
    deserialización (JSON no serializa callables).
  - experiment_02/tests/test_persistence_roundtrip.py: 6 tests
    verdes que verifican preservación de ids, statuses,
    foundations, validación, y resultados numéricos idénticos
    tras dump → load.
**Pendiente:**
  - Ningún orchestrator del proyecto USA persist/load en su
    ciclo de vida real. Si LearningOrchestrator (exp_02) hace
    consolidación a THEOREM, esa consolidación se pierde al
    reiniciar — el mecanismo está implementado pero NO
    integrado al flujo.
  - SQLite y Neo4j no probados.
**Trabajo realizado adicional (experiment_19):**
  - `experiment_19/persistence/serialization.py` implementa el
    serializer estricto del proyecto (`format_version: "1.0"`,
    `compute_ref` vía `ProcedureRefRegistry`, errores explícitos
    en lugar del fallback `repr` del exp_02).
  - `experiment_19/persistence/manifest.py` añade
    `SystemManifest` + `save_system` + `load_system` que reconstruyen
    el sistema completo: `SpecialistRegistry`, `VocabularyRegistry`
    (reindexado desde los grafos cargados) y todos los grafos.
  - `experiment_19/orchestrator.SessionOrchestrator` integra la
    persistencia al ciclo de vida real del orquestador:
    `process_turn` escribe a disco automáticamente, `resume_session`
    recupera el estado tras un reinicio total del proceso.
  - El integration test verifica un escenario cold-boot: sesión
    creada, persistida, todos los objetos `del`eted + `gc.collect()`,
    sistema reconstruido desde cero, segundo turno con referencia
    anafórica al primer turno resuelta correctamente.
**Pendiente residual:**
  - SQLite/Neo4j sin probarse (in-memory + JSON sigue siendo el
    backend único). El contrato del serializer es estable; un
    backend nuevo sólo tiene que respetar `format_version: "1.0"`.
**Estado:** RESUELTO — capa de persistencia completa integrada al
            orquestador de sesión, verificada por test de
            cold-boot.

---

## PROB-02 — Sesgo geométrico en especialista base
**Detectado en:** experiment_06
**Síntoma:** _FIGURE_TERMS hardcodeado en SubdomainSpecialist
             requiere implicit_figure_kind como workaround
             para dominios no geométricos
**Impacto:** El especialista base asume geometría — 
             otros dominios necesitan workarounds
**Bloqueante para:** Especialistas de dominios arbitrarios
**Soluciones candidatas:**
  - domain_terms como parámetro de constructor
  - DomainContext completamente agnóstico sin figure_kind
**Trabajo realizado:**
  - _FIGURE_TERMS hardcodeado ELIMINADO de
    experiment_04/subdomain_specialist/specialist.py (verificado
    con grep: 0 referencias en el proyecto).
  - domain_terms: list[list[str]] AÑADIDO como parámetro de
    constructor de SubdomainSpecialist y SubdomainAdapter, con
    default vacío. Cada caller declara sus propios términos.
  - Figure renombrada a DomainContext en experiment_01/specialist/
    problem.py (clase Figure ya no existe; verificado con grep:
    0 referencias activas, sólo 2 menciones en docstrings
    históricos).
  - 76 referencias a DomainContext en 26+ archivos del proyecto.
**Pendiente residual:**
  - implicit_figure_kind sigue existiendo como parámetro opcional
    para casos donde el problema declara un kind no reconocido.
    No es un bug, pero documenta que la abstracción aún no es
    100% agnóstica al dominio (PROB-04 del FINDINGS exp_06 ya
    anotaba esto).
**Estado:** RESUELTO SUSTANCIALMENTE — _FIGURE_TERMS eliminado,
            domain_terms como parámetro, Figure renombrada a
            DomainContext. Queda implicit_figure_kind como
            parámetro opcional declarado.

---

## PROB-03 — Contexto ambiguo en lenguaje natural
**Detectado en:** experiment_07 / diseño experiment_08
**Síntoma:** Palabras como "coeficiente" tienen significado
             distinto según el dominio — el especialista
             de lenguaje no puede aprender sin contexto
**Impacto:** El sistema no puede resolver ambigüedad
             lingüística sin información adicional
**Bloqueante para:** Lenguaje natural real como input
**Soluciones candidatas:**
  - Mecanismo de clarificación — el sistema pregunta
    cuando detecta ambigüedad
  - Contexto conversacional acumulado entre turnos
  - Subgrafos de intersección por dominio
    ("español algebraico", "español físico")
**Trabajo realizado:**
  - experiment_08/clarification implementa la primera solución
    candidata: ClarificationResolver con 5 pasos auditables y
    ClarificationRequest estructurado.
  - 13 tests verdes en experiment_08/tests verifican los 3
    veredictos (SUFFICIENT/AMBIGUOUS/UNKNOWN) y la integración
    al pipeline.
  - FINDINGS exp_08 documenta 4 hallazgos epistemológicos.
**Pendiente:**
  - Contexto conversacional acumulado entre turnos NO
    implementado (cada run es independiente).
  - Subgrafos de intersección por dominio NO probados.
**Estado:** RESUELTO PARCIALMENTE en experiment_08 — mecanismo
            de clarificación funciona; las otras dos soluciones
            candidatas siguen pendientes.

---

## PROB-04 — Condiciones de validez en lenguaje natural
**Detectado en:** experiment_06
**Síntoma:** Condiciones como "a ≠ 0" no son evaluables
             por el matcher numérico actual
**Impacto:** Validación de condiciones es permisiva
             para expresiones matemáticas en texto
**Bloqueante para:** Verificación rigurosa de precondiciones
**Soluciones candidatas:**
  - Parser de expresiones matemáticas simples
  - Integración con sympy para evaluación simbólica
  - Campo structured_conditions separado del NL
**Trabajo realizado (experiment_22):**
  - `experiment_22/gateway.py` envuelve cada `compute` con una guarda
    que evalúa las condiciones numéricas simples ('a ≠ 0', 'l >= 0',
    'm >= 0') contra las entradas reales. Una violación es un gap
    declarado, no un `ZeroDivisionError` ni un área de 16 para un lado
    de -4.
  - La misma guarda desactiva los nodos que exigen un triángulo
    rectángulo cuando el contexto es un triángulo genérico: la
    heurística del exp_01 aceptaba cualquier 'triangle*' y aplicaba
    Pitágoras a triángulos no rectángulos.
  - Las condiciones en prosa ("a, b, c son longitudes no negativas")
    siguen sin evaluarse.
**Estado:** PARCIAL — resuelto para condiciones numéricas simples en
            el gateway del exp_22; el razonador del exp_01 no cambia.

---

## PROB-05 — Escala del grafo
**Detectado en:** todos los experimentos
**Síntoma:** Grafos actuales tienen 6-20 nodos —
             validación estructural, no estadística
**Impacto:** No sabemos cómo se comporta el sistema
             con cientos o miles de nodos por especialista
**Bloqueante para:** Uso con dominios de conocimiento reales
**Soluciones candidatas:**
  - Índices sobre outputs para búsqueda O(1)
  - Base de datos de grafos (Neo4j, ArangoDB)
  - Particionamiento del grafo en subgrafos cargados
    bajo demanda
**Trabajo realizado:**
  - experiment_11/scale_test midió las 3 operaciones críticas
    sobre grafos sintéticos de 10/50/100/500/1000/5000 nodos
    con tiempos reales (FINDINGS exp_11).
  - experiment_12 aplicó las dos primeras soluciones candidatas
    (índice de outputs + memoización) — ver PROB-08 y PROB-09.
**Pendiente:**
  - Estructuras de almacenamiento alternativas (Neo4j, SQLite)
    siguen sin probarse — el sistema es in-memory, single-process.
  - Particionamiento del grafo (carga bajo demanda) sin abordar.
**Estado:** PARCIALMENTE RESUELTO — medido en exp_11, optimizado
            in-memory en exp_12. Persistencia/escala distribuida
            siguen pendientes.

---

## PROB-06 — Parser de lenguaje natural limitado
**Detectado en:** experiment_07
**Síntoma:** Token matching estricto — "resolver" no
             matchea "resuelve", sin stemming, sin
             manejo de conjugación
**Impacto:** El sistema solo entiende vocabulario exacto
             declarado en el grafo
**Bloqueante para:** Usuarios reales que escriben libremente
**Soluciones candidatas:**
  - Lematización ligera (sin dependencias pesadas)
  - Vocabulario expandido manualmente en el grafo
  - Especialista de lenguaje que aprende variantes
    como nodos nuevos (exp_08)
**Estado:** Declarado como límite honesto del exp_07

---

## PROB-07 — Import circular en experiment_06
**Detectado en:** verificación de estado del proyecto
**Síntoma:** experiment_06.document_parser ↔ 
             experiment_06.specialist_factory
             import circular que solo aparece con
             unittest discover global
**Impacto:** No afecta funcionalidad actual pero
             bloqueará descubrimiento automático de tests
             a medida que el proyecto escale
**Solución aplicada:** ProcedureSpec se importa bajo
                       TYPE_CHECKING (sólo para anotaciones de
                       tipo, no en runtime); PROCEDURES se
                       importa LAZY dentro de
                       GraphBuilder.__init__ cuando
                       procedures=None. Ambos cambios en
                       experiment_06/document_parser/graph_builder.py
                       (líneas 32-55, 168-176).
**Verificación:** `unittest discover -s . -p "test_*.py"` global
                   pasa los 116 tests sin ImportError.
**Estado:** RESUELTO — verificado contra evidencia en el
            inventario honesto.

---

## PROB-08 — transitive_foundations es recursivo y revienta con N>1000
**Detectado en:** experiment_11/scale_test
**Síntoma:** RecursionError al medir grafos de 1000+ nodos con
             cadena lineal de dependencias. El default de
             sys.setrecursionlimit (1000) se agota porque la
             implementación de KnowledgeGraph.transitive_foundations
             es recursiva pura.
**Impacto:** Cualquier grafo con cadena de dependencias > ~990
             niveles falla — incluyendo grafos reales de gran
             escala donde un teorema dependa de una cadena larga
             de definiciones.
**Solución aplicada:** transitive_foundations reescrito con stack
                       explícito iterativo en
                       experiment_01/knowledge_graph/graph.py.
                       El benchmark del exp_12 valida cadenas de
                       4998 niveles con sys.recursionlimit=1000
                       (default de Python, sin workaround).
**Estado:** RESUELTO en experiment_12 — ver
            experiment_12/FINDINGS.md #04.

---

## PROB-09 — backward_chaining escala superpolinomial
**Detectado en:** experiment_11/scale_test
**Síntoma:** Sobre grafos sintéticos con cadena de dependencias,
             el tiempo de specialist.solve() crece con un factor
             ×117000 cuando el tamaño crece ×500 (de 10 a 5000
             nodos). Para N=5000 una consulta tarda ~4.35 s.
**Impacto:** Inviable para uso interactivo con grafos de
             miles de nodos. Para grafos pequeños (<100) el coste
             es sub-milisegundo y aceptable.
**Causa probable:** _scan_relevant_nodes llama a
                    transitive_foundations por cada seed; sin
                    memoización los recorridos se repiten.
                    Adicionalmente, find_relations_producing
                    itera el grafo entero (sin índice por
                    output_variable).
**Soluciones aplicadas:**
  - Índice _output_index {variable → list[node_id]} construido
    incrementalmente en KnowledgeGraph.add() — find_relations_producing
    pasa de O(N) a O(1) amortizado.
  - Memoización persistente _foundations_cache invalidada en
    add()/remove() — primera llamada a transitive_foundations(X)
    en O(N), siguientes en O(K) (lectura del cache).
  - transitive_foundations iterativo (resuelve PROB-08
    simultáneamente).
**Resultados medidos (exp_12 vs exp_11, mismo run):**
  - find_relations_producing en N=500: 0.037 ms → 0.0003 ms
    (×148 más rápido)
  - transitive_foundations en N=500: 0.115 ms → 0.0005 ms
    (×213 más rápido)
  - backward_chaining en N=500: 32.9 ms → 3.67 ms (×9.0)
  - backward_chaining en N=5000: ~4350 ms → 425 ms (×~10)
  - Factor de crecimiento entre N=10 y N=5000:
    de ×117000 (cuadrático) a ×23225 (~O(N log N))
**Estado:** RESUELTO SUSTANCIALMENTE en experiment_12 — ver
            experiment_12/FINDINGS.md #05.
**Deuda residual:** la degradación que queda viene del propio
                    GeometrySpecialist (_scan_relevant_nodes,
                    recursión por cada input pendiente, ranking
                    de candidatos). Optimizar ESO requiere
                    cambios en experiment_01/specialist/specialist.py
                    fuera del alcance del exp_12. Para los grafos
                    actuales del proyecto (≤30 nodos) y hasta
                    N=5000 el rendimiento es aceptable.

---

## PROB-10 — Axiomas pueden quedar con fundamentos espurios y validate() no lo detecta
**Detectado en:** experiment_13/specialist_factory (especialista de colas)
**Síntoma:** El nodo `ax.fifo` del documento data_structures_queue.md
             se extrae con 3 fundamentos asignados automáticamente
             (def.cola, def.cola.frente, def.cola.fondo). El
             documento NO declara `**Depende de:**` para el axioma;
             los fundamentos vienen de la heurística "opción iii"
             del NodeExtractor del exp_06 (hermanos previos en la
             misma sección). graph.validate() acepta el grafo sin
             reportar nada.
**Impacto epistemológico:** Un axioma se acepta sin demostración —
                           tener fundamentos contradice su naturaleza.
                           El razonador puede seguir funcionando
                           correctamente porque los fundamentos
                           espurios no rompen ningún check, pero la
                           cadena de transitive_foundations queda
                           mal formada conceptualmente.
**Causa raíz dual:**
  1. NodeExtractor aplica la heurística de hermanos previos sin
     distinguir el EpistemicStatus del nodo (graph_builder no
     diferencia axioma/definición/teorema al asignar foundations
     por defecto).
  2. graph.validate() sólo verifica el caso simétrico ("teorema
     SIN fundamentos"), no el caso "axioma CON fundamentos".
**Soluciones aplicadas (ambas en experiment_13):**
  1. graph.validate() ampliado para detectar axiomas con foundations
     no vacíos. Cambio en
     experiment_01/knowledge_graph/graph.py.
  2. NodeExtractor distingue por EpistemicStatus al asignar
     foundations por defecto: AXIOM sin marcador `**Depende de:**`
     recibe foundations=[] siempre, sin pasar por la heurística de
     hermano previo. DEFINITION/THEOREM siguen heredando de
     hermanos previos como antes. Cambio en
     experiment_06/document_parser/node_extractor.py.
**Verificación:**
  - El especialista de colas (exp_13) se registra correctamente:
    ax.fifo.foundations == [] tras el parse, validate() limpio,
    20 nodos en grafo final.
  - Los teoremas que SÍ dependen de ax.fifo lo declaran con
    `**Depende de:**` en el documento — esa referencia se preserva
    intacta. El fix sólo afecta al fallback heurístico, no al
    marcador explícito.
  - 116/116 tests del proyecto en verde. Tests específicos del fix:
    test_extractor_skips_axiom_heuristic.py (5 asserts) +
    test_validate_rejects_axiom_with_foundations.py (4 asserts) +
    test_queue_specialist_exposes_axiom_problem.py reescrito (6
    asserts) verifican el comportamiento desde tres ángulos
    distintos.
**Estado:** RESUELTO en experiment_13.

---

## PROB-11 — Propagación de vocabulario entre especialistas
**Detectado en:** revisión de cierre tras experiment_16
**Síntoma:** Los términos técnicos que un especialista declaraba
             en sus nodos (ej. `alg.greedy_coloring`) no eran
             reconocibles por el especialista de lenguaje en
             consultas posteriores. El único vocabulario que el
             LanguageSpecialist matcheaba era el codificado
             explícitamente en su propio grafo (exp_07) — agregar
             un nuevo especialista no propagaba sus términos.
**Impacto:** El sistema crecía en capacidad de razonamiento por
             dominio (exp_15, exp_16) pero no en capacidad de
             entrada — nuevos dominios eran "mudos" para el
             lenguaje hasta que alguien tipeara sus formas
             manualmente en otro grafo. Eso rompe el principio
             de adquisición sin trabajo manual.
**Causa raíz:** Faltaba un canal estructural para que cada nodo
                declare las formas de superficie por las que puede
                ser referenciado, y un índice centralizado que las
                exponga al pipeline de lenguaje.
**Solución aplicada (experiment_17):**
  - `experiment_17/vocabulary/registry.py` —
    `VocabularyRegistry`: índice forma_normalizada → bindings,
    con idempotencia por specialist_id, longest-match sobre
    secuencias de tokens, y conflictos expuestos al caller (no
    resueltos por mayoría).
  - `experiment_06/document_parser/node_extractor.py` —
    marcador `**Términos:**` con normalización mínima
    (lowercase + colapso de espacios; acentos preservados).
  - `experiment_06/specialist_factory/factory.py` — registro
    automático de surface forms al construir un especialista
    desde un documento.
  - `experiment_07/specialist/language_specialist.py` —
    pre-pasada `_apply_vocabulary_registry` que precede al
    matcher local de tokens y consume spans declarados.
  - Conflictos ambiguous → `ClarificationRequest` (mecanismo
    del exp_08 reusado). Hint `domain_hint="<specialist_id>"`
    desambigua sin clarificación.
**Verificación:**
  - 44 tests nuevos en experiment_17/tests/ (registry, parser,
    integración end-to-end, conflicto + clarificación).
  - Demo end-to-end: `"calculá el coloreado voraz del grafo G"`
    resuelve `coloreado voraz → alg.greedy_coloring` y
    `grafo G → def.grafo` sin trabajo manual de propagación.
    Trazabilidad surface_form → documento_origen → nodo
    preservada en `VocabularyBinding.source_document`.
  - 186/186 tests del proyecto verdes (142 anteriores + 44
    nuevos). Backward-compat: documentos sin `**Términos:**`
    funcionan idéntico — el campo
    `properties["surface_forms"]` queda como `[]`.
**Estado:** RESUELTO en experiment_17.

---

## PROB-12 — Vocabulario y estado epistémico conversacional
**Detectado en:** scoping de experiment_19
**Síntoma:** La sesión persistente del exp_19 mantiene
             `active_bindings` (anáfora) y `conversation_graph`
             (episodios), pero el usuario aún no puede:
             - introducir vocabulario nuevo durante la conversación
               (p. ej. `"llamemos H a este subgrafo"` → registrar H
               como surface form en la sesión).
             - declarar hipótesis efímeras que aún no son nodos del
               grafo semántico ("supongamos que el grafo es plano").
             El estado epistémico de la conversación queda
             implícito en los `Turn` (parsed_problem, trace) pero no
             tiene un tipo dedicado.
**Impacto:** Una conversación rica con bautismos dinámicos
             ("llamemos a esto X") no se puede expresar; el
             especialista tiene que recibir todo nodo a través de
             un documento. Eso es contradictorio con la tesis de
             "memoria episódica indistinguible estructuralmente de
             la semántica" — la episódica de exp_19 sólo registra
             refs a la semántica.
**Soluciones candidatas:**
  - Marcador conversacional `**Bautismo:**` parseable que el
    SessionOrchestrator extiende: el usuario escribe
    `"llamemos H a {ref}"` y el orquestador agrega el surface form
    al VocabularyRegistry de la sesión (scope local, no global).
  - Tipo `EpistemicHypothesis` ligado al turno que lo introdujo;
    el conversation_graph lo aloja con `promotion_candidate=False`.
**Bloqueante para:** Conversaciones con vocabulario dinámico y
                     razonamiento bajo supuestos.
**Trabajo realizado (experiment_20):**
  - `experiment_20/patterns/definition_patterns.py` declara 4
    patrones de bautismo (`llamemos`, `sea = / igual a`,
    `definamos como`, `representa`). Match exacto, primer
    patrón declarado gana en empates.
  - `experiment_20/conversation/definition_handler.py` procesa
    cada match: crea `conv:def.{symbol}` con foundations
    resueltas (locales en `foundations`, externas en
    `properties["external_foundations"]`). Status: DEFINITION si
    resuelve foundations, HYPOTHESIS si no.
  - `experiment_20/vocabulary/session_registry.py` mantiene un
    `SessionVocabularyRegistry` ligado al conversation_graph;
    `FallbackVocabularyView` da la fachada al LanguageSpecialist
    con la política "local gana sobre global".
  - `experiment_20/epistemic/state.py` introduce
    `Affirmation`/`Hypothesis`/`DeclaredGap`/`ClarificationRecord`/
    `Agreement` como tipos JSON-nativos, con
    `EpistemicState.detect_inconsistency` (comparación EXACTA, no
    estadística) y `find_resolved_gap` (match exacto de concept).
  - `experiment_20/orchestrator.py:EpistemicSessionOrchestrator`
    extiende al del exp_19 (sin mutar exp_19): rutea entradas que
    matchean un patrón al DefinitionHandler, las demás al flujo
    normal con FallbackVocabularyView, y registra
    Affirmation/Gap/Hypothesis/Agreement turn a turn.
  - Redefinición del mismo símbolo en la misma sesión → emite
    `ClarificationRequest` (reuso del exp_08). El grafo NO se
    modifica hasta resolución.
**Verificación:**
  - 53 tests nuevos en experiment_20/tests/ (registry, patterns,
    handler, epistemic state, inconsistency, gap resolution,
    integration con restart entre T2 y T3).
  - 335/335 tests del proyecto verdes (282 anteriores + 53).
    Sesiones persistidas con exp_19 (sin `epistemic_state`) se
    cargan con estado vacío sin romperse.
**Estado:** RESUELTO en experiment_20.

---

## PROB-13 — Consolidación de memoria episódica a semántica
**Detectado en:** scoping de experiment_19
**Síntoma:** Un nodo del conversation_graph que aparece repetidas
             veces a lo largo de turnos (porque el usuario lo
             referencia o lo refina) podría ser un candidato a
             promoverse a un nodo del grafo semántico de algún
             especialista. Hoy, el campo `promotion_candidate: bool`
             está reservado en cada nodo conversacional pero nadie
             lo setea ni lo consume — no hay política de promoción.
**Impacto:** El sistema acumula memoria episódica pero NO aprende
             estructuralmente de ella. Una hipótesis que el usuario
             validó tres veces en tres sesiones distintas sigue
             siendo episódica, no se consolida.
**Causa raíz:** Falta el componente que recorra `conversation_graph`
                buscando candidatos (criterios DECLARATIVOS:
                frecuencia explícita, validación explícita del
                usuario, etc., sin estadística inferida).
**Soluciones candidatas:**
  - Política de promoción declarativa: el usuario marca un nodo
    como "consolidado" → migra al grafo del especialista
    correspondiente con `EpistemicStatus.HYPOTHESIS` o `THEOREM`.
  - Detector de patrones explícitos (no estadístico): el mismo
    `node_id` aparece como foundation de N episodios → candidato.
    N es declarado, no aprendido.
**Preparación ya realizada (experiment_19):**
  - `properties["promotion_candidate"]: bool = False` reservado en
    cada nodo del conversation_graph via
    `ensure_promotion_candidate_field`.
  - El serializer preserva el campo en round-trip
    (test_session.py::test_promotion_candidate_survives_round_trip).
  - Helpers `set_promotion_candidate` / `is_promotion_candidate`
    expuestos en `experiment_19.conversation`.
**Bloqueante para:** Aprendizaje conversacional (un sistema que
                     acumula conocimiento al hablar, sin
                     reentrenamiento).
**Estado:** ABIERTO — scope para experiment_21/22. El campo
            reservado evita migración de datos cuando la
            funcionalidad se implemente.

---

## PROB-14 — Constantes físicas sin dimensión
**Detectado en:** experiment_22 (pregunta LE-10)
**Síntoma:** La hipótesis `W = 9.81 · m` es físicamente correcta, pero
             el check dimensional la rechaza: 9.81 es un número sin
             dimensión en la gramática, así que la expresión tiene
             dimensión M y un peso es M·L·T⁻².
**Impacto:** Toda relación que dependa de una constante física (g, G,
             c) se rechaza. El error es conservador (abstención, no
             respuesta falsa), pero reduce la cobertura.
**Soluciones candidatas:**
  - Constantes declaradas como nodos AXIOM con valor y dimensión
    (`const.g = 9.81 L·T⁻²`), citables como variables por la hipótesis.
**Estado:** ABIERTO

---

## PROB-15 — El check de ejecución del exp_02 prueba con entradas cero
**Detectado en:** experiment_22 (pregunta LE-11)
**Síntoma:** `ConsistencyValidator` ejecuta el compute con todas las
             entradas a 0.0. Una relación correcta con división
             (`v = sqrt(2·Ec/m)`) lanza ZeroDivisionError y se rechaza.
**Impacto:** Se rechazan hipótesis válidas cuyo dominio excluye el cero.
**Soluciones candidatas:**
  - Casos de prueba derivados de las condiciones de validez de la
    hipótesis (`m > 0` → probar con m positivo).
  - Distinguir "indefinido en un punto" de "incorrecto".
**Estado:** ABIERTO

---

## PROB-16 — Magnitudes nuevas sólo como salida, nunca como entrada
**Detectado en:** experiment_22 (pregunta LE-8)
**Síntoma:** "Un cuadrado tiene perímetro 20, ¿cuál es su área?" se
             rechaza en la traducción: P no es una variable del
             catálogo, así que no puede ser un dato conocido.
**Impacto:** El sistema puede aprender P = 4·l, pero no usar P como
             punto de partida en la misma pregunta.
**Soluciones candidatas:**
  - Admitir variables nuevas en `known` cuando la magnitud tiene
    dimensión conocida, y dejar que el broker proponga el eslabón
    inverso.
**Estado:** ABIERTO

