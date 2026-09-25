# Experiment 17 — Propagación de vocabulario entre especialistas

## Hipótesis

El vocabulario es **estructura del nodo**, no inferencia sobre el
token. Cada `KnowledgeNode` declara explícitamente las formas de
superficie por las que puede ser referenciado en lenguaje natural,
y un registry centralizado las indexa cuando los especialistas se
registran. No hay propagación manual, no hay servicios externos,
no hay detección estadística de idioma.

Si la hipótesis es correcta, agregar un nuevo especialista basta
para que sus términos sean reconocibles por el especialista de
lenguaje en la consulta inmediatamente siguiente — sin tocar
código del lenguaje, sin recompilar nada, sin un paso de
"sincronización".

## Decisiones de diseño

1. **Marcador del parser:** `**Términos:**` con lista CSV (en
   bloques `**Definición:**`, `**Teorema:**`, `**Algoritmo:**`,
   `**Axioma:**`).
2. **Normalización mínima:** lowercase + strip + colapso de
   espacios internos. **No** se quitan acentos — "voraz" y
   "vóraz" son palabras distintas; si ambas valen, se declaran
   ambas.
3. **Persistencia:** ninguna. Los grafos cargados son la fuente
   de verdad; el registry se reconstruye a partir de ellos.
4. **Conflictos:** cuando dos especialistas declaran la misma
   forma, `lookup` retorna ambas bindings. La resolución se
   delega al caller con `domain_hint` o vía
   `ClarificationRequest` (mecanismo del exp_08). Sin hint y sin
   resolución, el sistema NO adivina.
5. **Idempotencia:** re-registrar un especialista REEMPLAZA sus
   bindings (no acumula). Soporta hot-reload sin duplicados.

## Componentes

```
experiment_17/
├── README.md
├── vocabulary/
│   ├── bindings.py          VocabularyBinding (frozen)
│   └── registry.py          VocabularyRegistry + DEFAULT_REGISTRY + normalize()
├── tests/
│   ├── test_registry.py         25 tests del registry aislado
│   ├── test_node_extractor.py    8 tests del marcador en parser
│   ├── test_integration.py       7 tests end-to-end con SpecialistFactory
│   └── test_conflict.py          4 tests del flujo de clarificación
└── data/
    └── demo_algorithms.md   3 nodos con `**Términos:**` declarado
```

Cambios en código existente (mínimos, retro-compatibles):

- `experiment_06/document_parser/node_extractor.py` — añade el
  marcador `**Términos:**`. Si está, popula
  `properties["surface_forms"]`. Si no está, queda `[]`.
- `experiment_06/specialist_factory/factory.py` — al construir un
  especialista desde un documento, registra automáticamente sus
  surface forms en el `VocabularyRegistry` inyectado (default:
  `DEFAULT_REGISTRY`).
- `experiment_07/specialist/language_specialist.py` — añade una
  pre-pasada (`_apply_vocabulary_registry`) que precede al
  matcher local de tokens. Usa `lookup_longest_match` para que
  spans largos ganen sobre sueltos.

## Evidencia

- 44/44 tests del exp_17 verde; 186/186 del proyecto verde.
- La consulta `"calculá el coloreado voraz del grafo G"` resuelve
  `coloreado voraz → alg.greedy_coloring` y `grafo G → def.grafo`
  sin trabajo manual de propagación. Trazabilidad completa:
  `surface_form → documento_origen → nodo`.
- Conflicto sobre `set` (declarado por dos especialistas) emite
  `ClarificationRequest` con ambos candidatos cuando no hay hint;
  resuelve a `def.cpp.set` con `domain_hint="cpp"`.

## Lo que NO hay

Por contrato del experimento:

- Cero servicios externos.
- Cero detección de idioma.
- Cero diccionarios o thesauri.
- Cero expansión automática (stemming, sinónimos, plurales
  inferidos). Si una forma vale, se declara.
- Cero ruptura de compatibilidad con documentos sin el marcador
  — los 142 tests anteriores quedan exactamente verde.
