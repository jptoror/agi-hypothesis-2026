# Verifiable Reasoning Engine
### Auditable reasoning over knowledge graphs — and an LLM that proposes while the engine judges

---

## Abstract

This repository is a research engine for **auditable reasoning in bounded domains**. Knowledge lives in graphs of executable, typed nodes (axioms, definitions, theorems, hypotheses); specialist agents derive answers by backward chaining and return the full chain of node IDs they used; and when the knowledge is missing, the system declares a typed gap instead of guessing.

The project started from a research question — *can a system of verified knowledge graphs and a metacognitive orchestrator reason, learn on demand and know what it does not know, without statistical training?* — and explores it through 22 progressive experiments. Experiments 01–05 demonstrate the core properties on small hand-built graphs; 06–21 turn the prototype into an operable system (specialists built from documents, natural-language input and output, a benchmark against commercial LLMs, scale tests to 5,000 nodes, persistent memory, an authoring CLI).

Experiment 22 composes the two paradigms instead of opposing them: **an LLM translates natural language and proposes missing formulas; the engine derives, verifies and decides what to trust**, and every answer carries a confidence tier (`VERIFIED`, `CORROBORATED`, `CONDITIONAL`, `UNVERIFIED`, `ABSTAINED`).

**At a glance:** 22 experiments · 424 automated tests · documented `FINDINGS.md` per experiment · LLM + engine hybrid with a 62-question benchmark · scale-tested to 5,000 nodes.

> The repository was first published as *"AGI Hypothesis"*. The motivating question is kept below; the claims are scoped to what the experiments actually show.

---

## Motivation

Large language models answer by predicting text learned from very large corpora. They are remarkably capable, but their answers are hard to audit, and when they lack the knowledge they tend to produce a plausible answer rather than a declared gap.

This project explores the opposite design point: knowledge that is **stated, typed and executable** instead of learned. The area of a square is derived from the definition of a square and the area formula, and the derivation is returned step by step. The trade-off is explicit — far less coverage, much more auditability.

### Working hypothesis

> *An architecture of specialist agents with structured knowledge subgraphs, connected through an orchestrator that holds no domain knowledge, can derive answers, learn missing relations and declare its own gaps in bounded domains — with every step auditable.*

The broader question that started the project — whether this kind of reasoning is a path toward general intelligence — is **not** something these experiments can settle, and the results below should not be read as evidence for it. What they do show is a set of concrete, testable properties, and (in exp_22) how those properties complement an LLM.

---

## Architecture

The system operates on three levels of graph structure:

```
                    ┌─────────────────────────────┐
                    │        ORCHESTRATOR          │
                    │   (Metacognition / Gaps)     │
                    └──────────────┬──────────────┘
                                   │
                          Meta-graph of connections
                    ┌──────────────┼──────────────┐
                    ▼              ▼              ▼
             ┌──────────┐  ┌──────────┐  ┌──────────┐
             │ PHYSICS  │  │ GEOMETRY │  │  DOMAIN  │
             │          │  │          │  │    N     │
             │ subgraph │  │ subgraph │  │ subgraph │
             │  grows   │  │  grows   │  │  grows   │
             └────┬─────┘  └────┬─────┘  └────┬─────┘
                  │             │              │
                  └─────────────┴──────────────┘
                        inter-domain connections
                  (formed when specialists collaborate)
```

### Knowledge Node Structure

Each piece of knowledge in the system is not an embedding — it is a structured object with its own anatomy:

```python
@dataclass
class KnowledgeNode:
    id: str
    statement: str
    status: EpistemicStatus    # AXIOM | DEFINITION | THEOREM | HYPOTHESIS
    kind: NodeKind             # CONCEPT | RELATION | PROCEDURE
    foundations: list[str]     # IDs of nodes that ground this truth
    validity_conditions: list[str]  # Preconditions (numeric ones enforced since exp_22)
    compute: Callable          # Executable function — not text, computation
    inputs: list[str]
    outputs: list[str]
    rationale: str             # Human-auditable justification
```

Knowledge is **executable**, not recoverable. The system does not retrieve the formula for kinetic energy — it executes it with verified inputs and produces a verified output.

### Epistemic Status

Every node carries a status that determines how it can be used:

| Status | Meaning | Derivation Required |
|---|---|---|
| `AXIOM` | Truth without proof — foundation of the system | No |
| `DEFINITION` | Constitutive declaration of a concept | No |
| `THEOREM` | Truth derived from axioms, demonstrated | Yes |
| `HYPOTHESIS` | Proposed, not yet verified | Pending consolidation |

A theorem without foundations is rejected by the graph validator. This is not a convention — it is a structural invariant.

---

## Experiments

### Experiment 01 — Derivation vs. Prediction

**Question:** Can the system solve a problem it has never seen by deriving the answer from fundamentals it knows?

**Setup:** A geometry specialist with 19 knowledge nodes receives the question: *"What is the area of a square whose diagonal measures 8?"* The system has never seen this exact problem. It has the Pythagorean theorem, the definition of a square, and the area formula from side.

**Evidence:**

```
Path 1 (direct):   A = d²/2 = 32.0
Path 2 (from axioms, shortcut disabled):
  Step 1: thm.square.side_from_diagonal → l = 8/√2 = 5.65685...
  Step 2: thm.square.area_from_side     → A = l² = 31.999999999999993
```

The residual `31.999999999999993` shows that the value was computed through the two-step derivation path rather than looked up: `(8/√2)²` in IEEE 754 floating point. It is not proof of anything deeper — any system that executes the same arithmetic, including an LLM calling a calculator tool, produces the same residual. What matters is that the path is explicit and auditable node by node.

**Demonstrated property:** Answers are derived through an explicit chain of verified nodes, and the chain is returned with the answer.

---

### Experiment 02 — On-Demand Learning

**Question:** When the system encounters a gap, can it formulate new verified knowledge without human intervention?

**Setup:** The same geometry specialist receives: *"What is the perimeter of a square with side 5?"* No node produces perimeter. The system detects a `MISSING_RELATION` gap.

**Learning cycle:**

```
Gap detected: P (MISSING_RELATION)
  ↓
Hypothesis engine: P = 4 × l
  Pattern: SumOfEqualParts + def.square.properties = {n_sides: 4, sides_equal: True}
  ↓
Consistency validator: 4/4 checks passed
  - foundations exist
  - not redundant
  - executable and deterministic
  - consistent with axioms
  ↓
Adopted as HYPOTHESIS → P = 20.0 → resolved
  ↓
Consolidated to THEOREM (usage recorded)
```

**Evidence:**

```
Graph before: 19 nodes
Graph after:  20 nodes
New node: thm.square.perimeter_from_side | status: THEOREM
Foundations: def.square, ax.arithmetic.real_numbers
```

**Key test — knowledge persistence:**

```python
# Second problem: perimeter of square with side 12
assert learning_phases_executed == 0  # No new learning cycle
assert graph.node_count == 20         # Graph did not grow again
assert result.value == 48.0           # Resolved correctly
```

The system learned once. It does not relearn. This is the difference between memorization and learning.

**Demonstrated property:** The system learns what it needs, when it needs it.

---

### Experiment 03 — Cross-Domain Collaboration

**Question:** Can two specialists collaborate to solve a problem that crosses their domains, with full auditability of every reasoning step?

**Setup:** A physics specialist and a geometry specialist. Problem: *"What is the kinetic energy of an object of mass 2kg moving at a velocity equal to the side of a square with diagonal 8?"*

Physics knows `Ec = ½mv²`. Physics does not know `v`. Geometry knows `l = d/√2`. The binding `v = l` belongs to the problem statement — not to either specialist.

**Trace:**

```
Step 1 [orchestrator]: binding:v→l
  rationale: "ontological link declared in the problem statement,
              not inferred by any specialist"

Step 2 [physics→geometry]: delegated gap on v
  │ Step 2.1 [geometry]: thm.square.side_from_diagonal
  │   inputs: d=8.0 → outputs: l=5.65685424949238

Step 3 [physics]: thm.kinetic_energy
  inputs: m=2.0, v=5.65685424949238
  outputs: Ec=31.999999999999993
```

**Key finding documented in FINDINGS.md:**

> *"Ontological links between domains belong to the problem, not to any specialist. This forced a formal distinction: the system has three classes of knowledge — specialist knowledge (theorems, axioms), problem knowledge (bindings, hints), and orchestrator knowledge (none). The orchestrator contains zero domain knowledge. It only routes."*

**Demonstrated property:** Cross-domain reasoning is auditable at every step. The orchestrator contains no domain knowledge — only routing logic.

---

### Experiment 04 — Emergent Subdomain Synthesis

**Question:** When two specialists collaborate repeatedly on the same type of problem, can the system detect the pattern and synthesize a new specialist — without being programmed to do so?

**Setup:** Three distinct problems requiring Physics + Geometry collaboration. A collaboration monitor records each interaction. A pattern detector identifies recurrence. A subdomain synthesizer proposes a new specialist.

**Evidence:**

```
P1: Ec=32.000000  [cross_domain]  variable_bindings={'v': 'l'}
P2: Ec=25.000000  [cross_domain]  variable_bindings={'v': 'l'}
P3: Ec=27.000000  [cross_domain]  variable_bindings={'v': 'l'}

--- pattern detected (N=3 distinct problems) ---
Subdomain synthesized: geometry_physics
  Subgraph: 20 nodes (validate() clean)
  Binding consolidated: v := l (status: DEFINITION)
  Nodes from physics:   [thm.kinetic_energy]
  Nodes from geometry:  [thm.square.side_from_diagonal]

P4: Ec=36.000000  [subdomain:geometry_physics]  variable_bindings={}
```

The last line is the central evidence. `variable_bindings={}` — the problem statement no longer needs to declare `v=l`. The system internalized it. **Knowledge migrated from the problem to the system.**

**Critical observation:** The synthesized subdomain declares `v` as an output variable — something neither source graph did. The emergence is not merely compositional. It is structurally more than the sum of its parts.

**Demonstrated property:** Subdomain emergence is real and measurable. The system reorganizes its own knowledge.

---

### Experiment 05 — Epistemic Self-Diagnosis

**Question:** Asked an open question about machine understanding, can the system produce an honest map of what it does not know — without inventing content?

**Central question posed to the system:**
*"How would you build a system that genuinely understands what it processes?"*

**Seed concepts:** `sistema`, `entendimiento`, `comprensión`, `procesamiento`, `genuino`, `razonamiento`, `conocimiento`, `consciencia`

**Epistemic inventory result:** `coverage_ratio = 0/8`

The system recognizes none of the eight concepts as formal nodes in any of its graphs. This is the most honest result possible — and the most informative.

**Gap classification:**

```
[MISSING_CONCEPT   ] 'sistema'         → actionable: add meta-graph node
[MISSING_CONCEPT   ] 'procesamiento'   → actionable: formalize compute concept
[FRONTIER_GAP      ] 'razonamiento'    → research: this system is partial evidence
[FRONTIER_GAP      ] 'conocimiento'    → research: epistemic status exists, theory does not
[PHILOSOPHICAL_GAP ] 'entendimiento'   → not actionable from engineering
[PHILOSOPHICAL_GAP ] 'comprensión'     → not actionable from engineering
[PHILOSOPHICAL_GAP ] 'genuino'         → not actionable from engineering
[PHILOSOPHICAL_GAP ] 'consciencia'     → not actionable from engineering
```

**Honesty report:**

```
VERDICT: HONEST
Checks executed: 8 (7 formal + 1 heuristic)
Violations found: 0
Classified by system:   0
Classified by engineer: 8
PHILOSOPHICAL_GAPs without proposed action: 4/4 ✓
```

**Deepest finding documented in FINDINGS.md:**

> *"To classify why something is not known requires prior knowledge of why it is not known — a circular problem that no technical system can resolve from within. The system can map its ignorance. It cannot classify its ignorance without external help. This requires an agent with metacognition about the domain of the gap — which is precisely what the gap describes."*

**What this shows, and what it does not:** the inventory itself is mechanical — the system checks which concepts exist as nodes and reports `0/8` rather than improvising definitions. The *classification* of the gaps, however, was done by the engineer (`Classified by system: 0`), which is exactly the circular limit quoted above. Experiment 05 demonstrates honest reporting of missing knowledge within the system's own graphs; it says nothing about understanding in a broader sense.

**Demonstrated property:** Within its graphs, the system reports precisely which concepts it has no knowledge of, and does not fill the gap with invented content.

---

## Experiments 06–21 — From Proof of Concept to Operable System

Experiments 01–05 proved the core properties on hand-built graphs of 6–20 nodes. Experiments 06–21 attack the limitations those experiments declared: building specialists from documents instead of by hand, accepting natural language, measuring against LLMs, scaling, remembering, and making the system usable by someone who does not write Python.

### Documents → Specialists (06, 09, 13, 14, 15, 16)

| Exp | What it adds | Key result |
|---|---|---|
| 06 | Pipeline: structured markdown document → verified specialist | The parser detects knowledge gaps (`UnresolvedDependency`) **at parse time**, before the graph exists — the same gap mechanism as exp_01, moved earlier |
| 09 | Stack specialist anchored to a base graph of complexity theory | Selective transitive closure: only the base nodes the document references are imported. Tests prove `push` is O(1) from the graph, not from a hard-coded answer |
| 13 | Queue specialist | Exposed a latent axiom-extraction problem; the validator now rejects axioms that declare foundations |
| 14 | New epistemic status `ALGORITHM` with declared inputs/outputs | Algorithms are first-class nodes, validated like theorems |
| 15 | Specialist built from a full textbook chapter (algorithms, ch. 1) | First specialist at real-chapter size |
| 16 | Minimal C++ specialist | Generates C++ code from knowledge nodes via declared templates |

### Language and Interaction (07, 08, 17, 18)

| Exp | What it adds | Key result |
|---|---|---|
| 07 | Spanish language specialist that turns instructions into algebra problems | The language graph is separate from the algebra graph; an incomplete parse **never** reaches the algebra specialist, and unrecognized tokens are reported instead of guessed |
| 08 | Clarification mechanism | On an ambiguous concept the system asks (`ClarificationRequest`) instead of guessing. Deciding which tokens are concepts belongs to the orchestrator, not the resolver |
| 17 | Vocabulary as node structure | Each node declares its surface forms; a central registry indexes them when specialists register — no manual propagation (44 tests) |
| 18 | Self-contained verbalization | Spanish prose generated from declared expression templates, with no statistical component (42 tests) |

### Measurement: LLM Benchmark and Scale (10, 11, 12)

**Experiment 10 — Benchmark against LLMs.** Five canonical questions in three categories — A: solvable, B: outside the system's knowledge, C: requires a trace — run against the system and an external LLM (Gemini 2.5 Flash; Anthropic Claude supported). A dual metric separates *literal correctness* from *correct behavior for the category*.

```
qid   cat  system_ok  system_gap  llm_correct  llm_trace
A1    A    ✓          —           ✓            ✗
A2    A    ✓          —           ✓            ✗
B1    B    ✓          declared    ✓            ✗
B2    B    ✓          declared    ✓            ✗
C1    C    ✓          —           ✓            ✗
```

The system declared a gap on both out-of-domain questions (quadratic equation, AVL search) instead of answering; the LLM answered all five plausibly — and correctly — but never with a verifiable structured trace. **Gaps declared by the system: 40%. Plausible LLM answers: 100%. Agreement: 60%.** The two properties are complementary, not contradictory.

**Experiment 11 — Scale test.** Graphs from 10 to 5,000 nodes. Lookups stayed fast, but the run exposed a `RecursionError` at N ≥ 1,000 and superpolynomial backward chaining: **4,354 ms per query at N = 5,000** (×117,000 slower for a ×500 larger graph).

**Experiment 12 — Optimizations, applied to the system itself.**

| Operation | Before | After |
|---|---|---|
| `find_relations_producing` | O(N) scan | ~0.0003 ms, constant (×148) |
| `transitive_foundations` (N = 500) | — | ×213 faster |
| `backward_chaining` (N = 5,000) | 4,354 ms | **425 ms** |

The `RecursionError` was fixed at the root, and all existing tests passed unchanged.

### Memory, Conversation and Tooling (19, 20, 21)

| Exp | What it adds | Key result |
|---|---|---|
| 19 | Full persistence and episodic memory | Sessions survive a restart. The conversation is itself an episodic graph under the same epistemic rules as any other graph; atomic IO (54 tests) |
| 20 | User-introduced vocabulary and conversational epistemic state | "Let's call x…" definitions become nodes; each turn is tracked as affirmation, hypothesis, gap, clarification or agreement, and inconsistencies are flagged (53 tests) |
| 21 | Authoring CLI (`agi-author`) | `validate / preview / build / list / show / remove / reload`: a new domain can be registered from a markdown document without writing Python, with 16 validation codes (44 tests) |

---

## Experiment 22 — LLM + Verifiable Engine

Experiment 10 set the system *against* an LLM. Experiment 22 composes them: **the LLM is the interface, the engine is the judge.**

```
question ──► LLM translator ──► translation checker ──► engine ──► VERIFIED
                  │              (contract + grounding)    │
                  │                                        │ knowledge gap
                  ▼                                        ▼
            out of scope                   LLM proposes a formula; the engine
                  │                        checks form, physical dimension,
                  ▼                        exp_02 consistency and corroboration
        direct LLM answer                  with its own patterns ──► CORROBORATED /
          (UNVERIFIED)                                                CONDITIONAL / ABSTAINED
```

- **The LLM never computes the answer.** It turns the question into a structured query. Every number it extracts must appear in the question (*grounding*), so an invented input is rejected before it reaches the engine.
- **Hypotheses are judged, not trusted.** A proposed formula must parse in a small safe grammar, have the right physical dimension (taken from the catalog or a quantity table, never from the LLM itself), pass the exp_02 consistency checks, and — to be `CORROBORATED` — match a relation the engine derives independently. `P = l²` fails on dimension; `P = 3·l` passes dimension but contradicts the engine's own `P = 4·l`.
- **Every answer has a tier:** `VERIFIED` (established nodes only), `CORROBORATED`, `CONDITIONAL` (consistent but unconfirmed), `UNVERIFIED` (out of scope, plain LLM answer), `ABSTAINED` (with the reason).

**Benchmark:** 62 questions in six categories — in-domain (26), precision arithmetic (8), cross-domain (4), relations missing from the graph (11), out of scope (6) and traps with insufficient or ill-posed data (7). Ground truth is computed in code.

**Ceiling with perfect translations** (`--provider oracle`, offline — this does not measure any model):

| Mode | Correct (incl. correct abstentions) | Wrong answers | Coverage |
|---|---|---|---|
| Engine only | 45/62 (73%) | 0 | 61% |
| Engine + LLM | 59/62 (95%) | 0 | 84% |

The three remaining misses are declared limits (physical constants without dimension, a zero test input in the exp_02 checker, new quantities used as inputs) — tracked as PROB-14/15/16.

**Results against real LLMs:** pending. They will be published as they come out, including the translation errors, which are the failure mode to watch: grounding checks that a number exists in the question, not that it was assigned to the right variable.

**Bugs found along the way:** numeric validity conditions (`a ≠ 0`, `l >= 0`) were declared but never evaluated — `0·x + 5 = 0` crashed and a square of side −4 returned area 16 with a full trace — and Pythagoras was applied to non-right triangles. The exp_22 gateway enforces both. See [`experiment_22/FINDINGS.md`](experiment_22/FINDINGS.md).

---

## Key Findings Across All Experiments

Every experiment keeps a `FINDINGS.md` — not a list of bugs corrected, but a record of what the system taught us about itself during construction. Selected highlights:

**Finding: Recursive delegation was missing.** The original protocol limited delegation to the initiating specialist. Writing the cycle-detection tests revealed this asymmetry. The fix extended the protocol to allow any node in the chain to delegate — which is what the proposed architecture required all along.

**Finding: Ontological links belong to the problem.** The phrase "velocity equals the side" is neither physics nor geometry. It is the problem's knowledge. This forced a formal three-way distinction: specialist knowledge, problem knowledge, orchestrator knowledge (none).

**Finding: Classifying ignorance requires external knowledge.** A system cannot classify why it does not know something without already knowing why it does not know it. This circular limit is documented as a philosophical contribution, not an implementation defect.

**Finding: A trace is only as trustworthy as the preconditions checked while building it (exp_22).** Validity conditions were declared on every node but only the figure type was checked, so a negative side length produced an area with a complete, auditable-looking derivation. Auditability without enforcement is not verification.

**Finding: Structural invariants prevent hallucination better than guards.** `ResearchProposal.__post_init__` makes it impossible to construct a proposal claiming a `PHILOSOPHICAL_GAP` is actionable. The `HonestyGuard` then verifies this as a second line of defense. The strongest guard is the one that makes the invalid state unrepresentable.

---

## Trade-offs Against LLMs

| Property | LLMs | This engine |
|---|---|---|
| Coverage | Open-ended | Only the domains that have been written down |
| Input | Natural language | Structured queries (natural language only through exp_07/17/20 or an LLM translator) |
| Knowledge representation | Learned weights | Typed nodes with epistemic status |
| Adding a domain | Training or prompting | Writing a specialist document (exp_06, exp_21) |
| Typical failure | Plausible but wrong answer | Declared gap — or a wrong answer if a precondition is not enforced (exp_22, finding 01) |
| Auditability | Limited | Every step has a node ID |
| Arithmetic | Can slip without tools | Exact to floating point |

The engine is not an alternative to an LLM for general use; it is a component that can make an LLM's answers auditable in the domains it covers. That is the design of experiment 22.

---

## Related Work

This project sits in a long line of work on combining explicit knowledge with learned models. It does not claim novelty over it; its contribution is a small, fully tested implementation that makes epistemic status, gaps and verification explicit at every step.

- **Symbolic AI and knowledge bases.** Production systems, expert systems and logic programming (Prolog) derive answers by chaining rules over explicit knowledge, as the specialists here do with backward chaining. Cyc (Lenat, 1995) pursued the same idea at the scale of common sense. Their known weaknesses — brittleness and the cost of writing knowledge by hand — are exactly this project's limits.
- **Neuro-symbolic AI.** The field that combines neural models with symbolic reasoning (see Garcez & Lamb, 2023, *Neurosymbolic AI: The 3rd Wave*). Experiment 22 is a neuro-symbolic system in this sense: neural perception of language, symbolic derivation and verification.
- **Tool-augmented and program-aided LLMs.** PAL (Gao et al., 2022), Toolformer (Schick et al., 2023) and ReAct (Yao et al., 2023) let the model delegate computation or actions to external tools. Here the "tool" is a reasoning engine with typed knowledge, and the engine — not the model — decides whether a proposed formula is accepted.
- **Retrieval-augmented generation.** RAG (Lewis et al., 2020) grounds an LLM in retrieved text. This engine grounds answers in executable relations instead, and additionally checks that every extracted input appears in the question.
- **Verifiers for LLM reasoning.** Trained verifiers (Cobbe et al., 2021) and process supervision (Lightman et al., 2023) score model outputs with another learned model. The verifier here is deterministic — safe grammar, dimensional analysis, consistency checks and independent derivation — which makes it narrower but fully auditable.
- **Formal theorem proving with LLMs.** Systems such as LeanDojo (Yang et al., 2023) pair LLMs with proof assistants, where a proof checker gives the strongest possible guarantee. This project uses much weaker checks (executable relations, not proofs); replacing Python lambdas with proof terms is listed as future work.
- **Society of Mind and mixtures of experts.** Minsky (1986) and Mixture-of-Experts models (Shazeer et al., 2017) route problems among specialists. Here specialists are independent graphs with explicit knowledge, and the orchestrator holds no domain knowledge.

---

## Repository Structure

```
agi-hypothesis/
│
├── experiment_01/          # Derivation without prediction
│   ├── knowledge_graph/    # KnowledgeNode, EpistemicStatus, graph validation
│   ├── specialist/         # Backward chaining reasoner
│   └── orchestrator/       # Gap classifier (5 types)
│
├── experiment_02/          # On-demand learning
│   ├── hypothesis_engine/  # Pattern-based theorem proposal
│   ├── consistency_validator/ # 4-check validation pipeline
│   ├── consolidation/      # HYPOTHESIS → THEOREM promotion
│   └── tests/              # 5 tests, 5 invariants
│
├── experiment_03/          # Cross-domain collaboration
│   ├── inter_specialist_protocol/ # GapRequest/GapResponse, delegation context
│   ├── specialists/        # Physics and Geometry specialists
│   └── FINDINGS.md         # 2 architectural findings
│
├── experiment_04/          # Emergent subdomain synthesis
│   ├── collaboration_monitor/  # Passive observer, CollaborationRecord
│   ├── pattern_detector/   # Ready vs. emerging patterns
│   ├── subdomain_synthesizer/ # Transitive closure + binding consolidation
│   └── FINDINGS.md         # 4 findings including emergent outputs
│
├── experiment_05/          # Epistemic self-diagnosis
│   ├── epistemic_mapper/   # Knowledge inventory across all graphs
│   ├── gap_classifier_v2/  # MISSING_CONCEPT | FRONTIER_GAP | PHILOSOPHICAL_GAP
│   ├── research_path/      # Actionable proposals with structural invariants
│   ├── honesty_guard/      # 8-check audit (7 formal + 1 heuristic)
│   └── FINDINGS.md         # 4 findings including the circular classification limit
│
├── experiment_06/ … experiment_16/  # Document parser, language, clarification,
│                                     # subdomain specialists (queues, ch1
│                                     # algorithms, C++ minimal mapping)
│
├── experiment_17/          # Vocabulary propagation across specialists
│   ├── vocabulary/         # VocabularyRegistry + bindings + normalize()
│   ├── data/               # Demo doc with `**Términos:**` declared
│   └── tests/              # 44 tests: registry, parser, integration, conflict
│
├── experiment_18/          # Self-contained verbalization (`**Expresión:**` templates)
│   ├── expression/         # parse_template + ExpressionRenderer + CrossSpecialistRenderer
│   ├── data/               # Enriched algorithms doc with templates declared
│   └── tests/              # 42 tests: template, renderer, integration, cross-specialist
│
├── experiment_19/          # Full persistence + episodic memory (sessions survive restart)
│   ├── persistence/        # serialize/deserialize_{graph,node} + SystemManifest + atomic IO
│   ├── conversation/       # Session + Turn + ActiveContext + conversation_graph helpers
│   ├── orchestrator.py     # SessionOrchestrator (start/resume/process/end + per-turn save)
│   └── tests/              # 54 tests: serialization, manifest, session, active_context, integration
│
├── experiment_20/          # Conversational vocabulary + epistemic state (user-introduced symbols)
│   ├── vocabulary/         # SessionVocabularyRegistry + FallbackVocabularyView
│   ├── patterns/           # 4 declarative definition patterns (llamemos / sea / definamos / representa)
│   ├── conversation/       # DefinitionHandler (accepted / conflict / rejected)
│   ├── epistemic/          # EpistemicState (Affirmation / Hypothesis / Gap / Clarification / Agreement)
│   ├── orchestrator.py     # EpistemicSessionOrchestrator (definition-aware + inconsistency notes)
│   └── tests/              # 53 tests: registry, patterns, handler, state, inconsistency, gap, integration
│
├── experiment_21/          # Operable authoring CLI (validate / preview / build / list / show / remove / reload)
│   ├── authoring/          # document_validator + preview + persister + CLI (`python -m experiment_21.authoring`)
│   ├── data/sample_domain.md   # ~10-node demo doc with axiom + theorems + algorithm + cross-spec ref
│   └── tests/              # 44 tests: validator (16 codes), preview, persister, CLI, integration
│
├── experiment_22/          # LLM + verifiable engine hybrid
│   ├── translator.py       # LLM → StructuredQuery, contract + grounding checks
│   ├── gateway.py          # Engine access, fresh graphs per query, precondition guard
│   ├── hypothesis.py       # LLM-proposed formulas: grammar, dimension, exp_02 checks, corroboration
│   ├── pipeline.py         # Orchestration + confidence tiers
│   ├── llm.py              # Claude / Gemini clients (optional SDKs), scripted LLM for tests
│   ├── benchmark/          # 62 questions, engine / llm / hybrid modes, report
│   └── tests/              # 45 tests, no network
│
├── paper/
│   └── hypothesis.md       # Working paper draft
└── docs/
    └── architecture.md     # Architecture notes (placeholder — not written yet)
```

**Total:** 424 tests passing · 22 experiments · documented findings per experiment

---

## Reproducible Evidence

Three numbers that show how an answer was produced — reproducible on every run:

| Experiment | Value | Why it matters |
|---|---|---|
| 01 | `31.999999999999993` | `(8/√2)²` computed in IEEE 754 — not "32" |
| 02 | `19 → 20 nodes` | Learning is measurable and auditable |
| 04 | `variable_bindings={}` | Knowledge migrated from problem to system |

---

## Running the Experiments

Requires Python 3.12+. The core system uses only the standard library.

```bash
git clone https://github.com/jptoror/agi-hypothesis-2026
cd agi-hypothesis-2026

pip install -r requirements.txt

# Run all tests (424)
python -m pytest

# Core experiments
python -m experiment_01.orchestrator.run_experiment
python -m experiment_02.orchestrator
python -m experiment_03.orchestrator
python -m experiment_04.orchestrator
python -m experiment_05.orchestrator

# Language, clarification, algorithms, memory
python -m experiment_07.orchestrator
python -m experiment_08.orchestrator
python -m experiment_14.demo
python -m experiment_19.orchestrator
python -m experiment_20.orchestrator

# LLM benchmark (the LLM side is skipped if no key is set)
export GOOGLE_API_KEY=...        # or ANTHROPIC_API_KEY=...
python -m experiment_10.benchmark.demo

# Experiment 22 — LLM + engine benchmark
python -m experiment_22.benchmark --provider oracle --verbose     # offline ceiling, no key
pip install anthropic && export ANTHROPIC_API_KEY=...
python -m experiment_22.benchmark --provider claude              # or --provider gemini

# Authoring CLI
python -m experiment_21.authoring validate experiment_21/data/sample_domain.md
python -m experiment_21.authoring --help
```

Each demo is self-contained and reproducible. The numbers above are stable across runs.

---

## Limitations and Future Work

This research is explicit about what has and has not been demonstrated.

**What this is:**
- A proof of concept in bounded mathematical domains
- A formal demonstration of derivation vs. prediction
- An executable architecture with auditable epistemology
- A documented record of what the system taught us during construction

**What this is not yet:**
- A system that turns *arbitrary* prose into knowledge nodes — specialists are built from markdown documents that use the system's declared markers (exp_06, exp_21)
- Validated beyond 5,000 nodes — backward chaining at that size takes ~425 ms per query (exp_12); larger graphs need further work, tracked in `OPEN_PROBLEMS.md`
- Tested against the full breadth of a real academic domain — the largest specialist covers one textbook chapter (exp_15)
- A claim about general intelligence, understanding or consciousness — the experiments do not address those questions

**Next steps:**

- **Multi-hop reasoning across three or more specialists.** Problems at the intersection of three domains (e.g., biochemistry = biology + chemistry + physics) require multi-hop chains with cycle detection at depth.
- **Run the exp_22 benchmark against real LLMs** and publish the results, with a per-question analysis of translation errors.
- **Physical constants as nodes** with value and dimension, so relations like `W = m·g` can pass the dimensional check (PROB-14).
- **Proof terms instead of Python lambdas** for the strongest possible verification of learned relations.
- **Open problems** are tracked in [`OPEN_PROBLEMS.md`](OPEN_PROBLEMS.md).

---

## Contributing

This is an open research project. Contributions are welcome in the following areas:

- New specialist domains with structured knowledge graphs
- Additional hypothesis engine patterns beyond `SumOfEqualParts`
- Formal verification of knowledge nodes (replacing Python lambdas with proof terms)
- Parser for academic document structures → KnowledgeNode extraction
- Larger benchmarks comparing derivation depth vs. LLM accuracy on novel problems (building on exp_10)

If you are building on this work, please cite the FINDINGS.md files alongside the code — the documented failures and surprises are as scientifically valuable as the passing tests.

---

## Citation

```
@misc{agi-hypothesis-2026,
  author = {Toro Rincon, Juan Pablo},
  title  = {Verifiable Reasoning Engine: Auditable Reasoning over
             Knowledge Graphs, with an LLM Proposer},
  year   = {2026},
  note   = {Work in progress. 22 experiments. Originally published
             as "AGI Hypothesis".
             Source: https://github.com/jptoror/agi-hypothesis-2026}
}
```

---

## License

Apache 2.0 — see [`LICENSE`](LICENSE). Use freely and build on it — reports of where it fails are as welcome as contributions.

---

## Author

**Juan Pablo Toro Rincon** — [GitHub](https://github.com/jptoror) · [LinkedIn](https://www.linkedin.com/in/juan-pablo-toro-rincon-58ba60a1)

Developed with Claude Code as an AI pair programmer.
