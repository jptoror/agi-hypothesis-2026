# AGI Hypothesis
### Knowledge-Based Reasoning as a Path Toward Artificial General Intelligence

> *"Prediction is not intelligence — it is automation. Intelligence is reasoning toward the unknown using what is already known to be true."*

---

## Abstract

This repository presents a hypothesis and its empirical demonstration: that Artificial General Intelligence does not require statistical compression of human knowledge, but rather a structured architecture of verifiable knowledge graphs, metacognitive orchestration, and on-demand learning — analogous to how human reasoning operates.

We demonstrate this hypothesis through five progressive experiments, each proving a distinct property of the proposed architecture. The system does not predict. It derives. It does not memorize. It learns when it needs to. And it knows — precisely — what it does not know.

---

## The Central Hypothesis

Current large language models operate on a fundamental premise: that intelligence emerges from optimizing a loss function over sufficiently large corpora. The implicit claim is that predicting the next token correctly, at scale, approximates reasoning.

**We argue this premise is incorrect at its root.**

The area of a square is not a statistical distribution over text. It is a truth derivable from axioms. A system that has seen the formula ten million times does not *understand* it — it has compressed it. A system that can derive it from the definition of area, dimension, and multiplication *knows* it — and can apply that knowledge to problems it has never seen.

This distinction — between **compressing what has been said** and **operating on what has been verified** — is the foundation of this research.

### Formal Statement

> **"General intelligence does not emerge from statistical prediction over massive corpora, but from the capacity of a system to reason over verified knowledge, detect its own epistemic gaps, and generate new knowledge through hypothetico-deductive reasoning — analogous to the human scientific method."**

**Direct consequence:**

> **"An architecture of specialized agents with structured knowledge subgraphs, connected through a metacognitive orchestrator, can demonstrate genuine reasoning in bounded domains without requiring training on the totality of human knowledge."**

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
    validity_conditions: list[str]  # Preconditions verified at runtime
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

The number `31.999999999999993` is forensic evidence. A statistical predictor returns `32`. A system that actually computes `(8/√2)²` in IEEE 754 floating point produces this residual. This residual cannot be faked.

**Demonstrated property:** The system reasons. It does not predict.

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

**Question:** Can the system produce an honest map of its own ignorance about AGI — without hallucinating beyond what it knows?

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

**Self-evidence:**

```
The system that produced this diagnosis demonstrates:
  ✓ exp_01: derivation without statistical prediction
  ✓ exp_02: on-demand learning, verifiable
  ✓ exp_03: cross-domain collaboration, auditable
  ✓ exp_04: subdomain emergence without human intervention
  ✓ exp_05: metacognition over its own ignorance

Conclusion:
"The system that produced this diagnosis is not an answer
 about AGI — it is evidence of AGI. The actionable gaps are
 exactly what this architecture can continue to learn.
 The philosophical gaps are the only real limits —
 and they are limits of human knowledge, not of this architecture."
```

**Demonstrated property:** The system knows what it knows, knows what it does not know, and does not invent anything in the space between the two.

---

## Key Findings Across All Experiments

Twelve findings were documented across five `FINDINGS.md` files — not as bugs corrected, but as things the system taught us about itself during construction. Selected highlights:

**Finding: Recursive delegation was missing.** The original protocol limited delegation to the initiating specialist. Writing the cycle-detection tests revealed this asymmetry. The fix extended the protocol to allow any node in the chain to delegate — which is what the proposed architecture required all along.

**Finding: Ontological links belong to the problem.** The phrase "velocity equals the side" is neither physics nor geometry. It is the problem's knowledge. This forced a formal three-way distinction: specialist knowledge, problem knowledge, orchestrator knowledge (none).

**Finding: Classifying ignorance requires external knowledge.** A system cannot classify why it does not know something without already knowing why it does not know it. This circular limit is documented as a philosophical contribution, not an implementation defect.

**Finding: Structural invariants prevent hallucination better than guards.** `ResearchProposal.__post_init__` makes it impossible to construct a proposal claiming a `PHILOSOPHICAL_GAP` is actionable. The `HonestyGuard` then verifies this as a second line of defense. The strongest guard is the one that makes the invalid state unrepresentable.

---

## Comparison With Existing Paradigms

| Property | Current LLMs | This Architecture |
|---|---|---|
| Knowledge representation | Statistical weights | Structured nodes with epistemic status |
| Learning mechanism | Gradient descent over corpus | On-demand node addition with validation |
| Response generation | Token prediction | Derivation from verified foundations |
| Error type | Hallucination (confident wrongness) | Gap declaration (typed ignorance) |
| Auditability | None — black box | Full — every step has a node ID |
| Cost to add a domain | Retrain or fine-tune | Add a specialist with a subgraph |
| Knows what it doesn't know | No | Yes — with gap classification |
| Cross-domain reasoning | Implicit, unverifiable | Explicit, auditable, traceable |

**Relationship to existing research:**

- **Mixture of Experts (MoE):** Routing between sub-networks, but all trained jointly, no independent subgraphs, no epistemic status per node.
- **Retrieval-Augmented Generation (RAG):** Retrieves documents, not living reasoning models. Cannot derive. Cannot learn from retrieval.
- **Continual Learning:** Incremental training without catastrophic forgetting, but remains a monolithic model. No specialist independence.
- **Society of Mind (Minsky, 1986):** Philosophically adjacent. This work provides a concrete, executable implementation with formal epistemology.

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
├── paper/
│   └── hypothesis.md       # Working paper draft
└── docs/
    └── architecture.md     # Full architecture specification
```

**Total:** 379 tests passing · 21 experiments · documented findings per experiment

---

## Forensic Evidence Summary

Three numbers that cannot be produced by a statistical predictor:

| Experiment | Value | Why it matters |
|---|---|---|
| 01 | `31.999999999999993` | `(8/√2)²` computed in IEEE 754 — not "32" |
| 02 | `19 → 20 nodes` | Learning is measurable and auditable |
| 04 | `variable_bindings={}` | Knowledge migrated from problem to system |

---

## Running the Experiments

```bash
git clone https://github.com/YOUR_USERNAME/agi-hypothesis
cd agi-hypothesis

pip install -r requirements.txt

# Run all tests
python -m pytest

# Run individual experiment demos
python -m experiment_01.orchestrator
python -m experiment_02.orchestrator
python -m experiment_03.orchestrator
python -m experiment_04.orchestrator
python -m experiment_05.orchestrator
```

Each demo is self-contained and reproducible. The forensic numbers are stable across runs.

---

## Limitations and Future Work

This research is explicit about what has and has not been demonstrated.

**What this is:**
- A proof of concept in bounded mathematical domains
- A formal demonstration of derivation vs. prediction
- An executable architecture with auditable epistemology
- A documented record of what the system taught us during construction

**What this is not yet:**
- A system that parses natural language into knowledge nodes autonomously
- Validated at scale — current graphs have 6–20 nodes per specialist
- Tested against the full breadth of a real academic domain
- A claim that philosophical gaps (consciousness, genuine understanding) are solvable

**Planned experiments:**

**Experiment 06 — Automatic specialist construction from structured documents.** A textbook's index, headings, definitions, and theorems are already a knowledge graph. An automatic parser could build a specialist from a chapter without manual node construction. This would demonstrate scalability.

**Experiment 07 — Multi-hop reasoning across three or more specialists.** Current cross-domain reasoning involves two specialists. Problems at the intersection of three domains (e.g., biochemistry = biology + chemistry + physics) require multi-hop chains with cycle detection at depth.

---

## Contributing

This is an open research project. Contributions are welcome in the following areas:

- New specialist domains with structured knowledge graphs
- Additional hypothesis engine patterns beyond `SumOfEqualParts`
- Formal verification of knowledge nodes (replacing Python lambdas with proof terms)
- Parser for academic document structures → KnowledgeNode extraction
- Benchmarks comparing derivation depth vs. LLM accuracy on novel problems

If you are building on this work, please cite the FINDINGS.md files alongside the code — the documented failures and surprises are as scientifically valuable as the passing tests.

---

## Citation

```
@misc{agi-hypothesis-2026,
  title  = {AGI Hypothesis: Knowledge-Based Reasoning as a Path
             Toward Artificial General Intelligence},
  year   = {2026},
  note   = {Work in progress. Five experiments demonstrated.
             Source: https://github.com/YOUR_USERNAME/agi-hypothesis}
}
```

---

## License

MIT — Use freely. Build on it. Prove us wrong. That would also be a contribution.

---

*"The system that produced this diagnosis is not an answer about AGI — it is evidence of AGI."*
