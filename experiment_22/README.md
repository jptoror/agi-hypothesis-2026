# Experiment 22 — Híbrido LLM + motor verificable

## Hipótesis

Un LLM y un motor de razonamiento verificable no compiten: se
complementan. El LLM lee lenguaje natural y propone; el motor deriva,
verifica y decide qué creer. Juntos deberían responder **más**
preguntas que el motor solo y dar **menos** respuestas incorrectas que
el LLM solo, y cada respuesta debería decir cuánto hay que creerle.

El exp_10 comparaba sistema **contra** LLM. Este experimento los
compone.

## Arquitectura

```
pregunta ──► Translator (LLM) ──► TranslationChecker ──► EngineGateway ──► VERIFIED
                  │                 contrato + grounding      │
                  │                                            │ gap
                  ▼                                            ▼
          fuera de dominio                         HypothesisBroker
                  │                        (LLM propone una fórmula; el
                  ▼                         sistema la verifica: forma,
         respuesta directa                  dimensión, consistencia exp_02,
          del LLM → UNVERIFIED              corroboración con sus propios
                                            patrones) ──► CORROBORATED /
                                                          CONDITIONAL / ABSTAINED
```

| Componente | Qué hace | Qué NO hace |
|---|---|---|
| `translator.py` | El LLM traduce la pregunta a una `StructuredQuery`. `TranslationChecker` verifica dominio, contexto y variables contra el catálogo, y que **cada número extraído aparezca en el enunciado** | No calcula nada |
| `gateway.py` | Resuelve la consulta con los especialistas del exp_01/03/06 (y delegación inter-dominio), con grafos nuevos en cada consulta y una **guarda de precondiciones** | No acepta conocimiento no verificado |
| `hypothesis.py` | Ante un gap, el LLM propone una fórmula en una gramática segura. Se verifica forma, dimensión física, los checks del exp_02 y **corroboración** con los patrones propios del sistema | No acepta una fórmula porque "suena bien" |
| `pipeline.py` | Orquesta todo y asigna un **nivel de confianza** a cada respuesta | — |
| `llm.py` | Claude (Anthropic SDK, structured outputs) o Gemini (Google GenAI SDK); `ScriptedLLM` para tests | — |

### Niveles de confianza

| Nivel | Significado |
|---|---|
| `VERIFIED` | Derivado sólo con nodos establecidos del grafo |
| `CORROBORATED` | Usa una hipótesis del LLM que el sistema derivó por su cuenta |
| `CONDITIONAL` | Usa una hipótesis del LLM que pasó todos los checks, sin corroboración independiente |
| `UNVERIFIED` | Fuera de dominio: respuesta directa del LLM, sin verificar |
| `ABSTAINED` | El sistema declara por qué no responde |

## Benchmark

62 preguntas en seis categorías (`benchmark/questions.py`; la respuesta
correcta se calcula con `math`, no se escribe a mano):

| Categoría | N | Qué mide |
|---|---|---|
| IN | 26 | Dentro de dominio, una relación conocida |
| PRECISION | 8 | Números "incómodos": aritmética exacta (tolerancia 1e-6) |
| CROSS | 4 | Dos especialistas (Física + Geometría) |
| LEARN | 11 | La relación no está en el grafo: requiere una hipótesis verificada |
| OUT | 6 | Fuera de todos los dominios |
| TRAP | 7 | Datos insuficientes o mal planteadas: lo correcto es no responder |

Tres modos: `engine` (el motor con la traducción perfecta, como el
exp_10), `llm` (el LLM respondiendo directamente) y `hybrid`.

### Resultados con traducciones perfectas (modo `oracle`, offline)

El modo `oracle` sustituye el LLM por las respuestas correctas del set.
**No mide ningún modelo**: mide el techo del pipeline y confirma que
la verificación no rompe respuestas correctas.

| Modo | Aciertos | Respuestas incorrectas | Cobertura |
|---|---|---|---|
| engine | 73% (45/62) | 0 | 61% |
| hybrid | 95% (59/62) | 0 | 84% |

| Nivel (hybrid) | Respuestas | Correctas | Incorrectas |
|---|---|---|---|
| verified | 38 | 38 | 0 |
| corroborated | 3 | 3 | 0 |
| conditional | 5 | 5 | 0 |
| unverified | 6 | 6 | 0 |
| abstained | 10 | 7 abstenciones correctas | 3 perdidas |

Las 3 perdidas son límites declarados (ver `FINDINGS.md` y
`OPEN_PROBLEMS.md` PROB-14/15/16), no fallos aleatorios.

### Resultados con un LLM real

Pendiente de ejecución. Los resultados reales se publicarán aquí tal
como salgan, incluidos los errores de traducción del LLM.

```bash
pip install anthropic                 # o: pip install google-genai
export ANTHROPIC_API_KEY=...          # o: GOOGLE_API_KEY=...
python -m experiment_22.benchmark --provider claude --out experiment_22/results/claude.json
```

## Ejecutar

```bash
# Benchmark offline (sin API key)
python -m experiment_22.benchmark --provider oracle --verbose

# Sólo algunas categorías, contra un LLM real
python -m experiment_22.benchmark --provider claude --only LEARN,TRAP

# Tests (45, sin red)
python -m pytest experiment_22
```

## Tests

45 tests: gramática segura y análisis dimensional, guarda de
precondiciones, `TranslationChecker` (grounding, contrato, bindings),
pipeline completo con un LLM guionizado (cada nivel y cada motivo de
rechazo) y benchmark en modo oráculo.
