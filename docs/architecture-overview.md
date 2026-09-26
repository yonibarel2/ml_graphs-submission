# Architecture overview

How the system fits together, and the invariants that hold across it.

---

## 1. The measurement, in one diagram

```
                        ┌──────────────────────────────┐
   dataset ──[1]──────▶ │ GraphInstance                │   one graph + one task + one query
                        │ nodes, edges, query, truth   │   + its ground truth
                        └──────────────┬───────────────┘
                                       │ [2]
                        ┌──────────────▼───────────────┐
                        │ canonical Variant            │   (label_map, order, structure, syntax)
                        └──────────────┬───────────────┘
                    single-axis transforms (exactly one field each)
        ┌──────────────┬───────────────┼───────────────┬──────────────┐
     relabel         order         structure        syntax        (canonical)
        └──────────────┴───────────────┼───────────────┴──────────────┘
                                       │
                    ┌──────────────────┼──────────────────┐
              render(v)          node_seq/edge_seq   true_edge_set(v)
              graph as text       graph as data       the ground-truth graph
                    │                  │                     │
            ┌───────┴──────┐           │                     │
            ▼              ▼           ▼                     │
        M1 direct        M2 code    M3 graph_as_code         │
                            │  ×  library ∈ {networkx, native}
            │              │           │                     │
            │       [3] LLM (temp 0, cached by prompt hash)   │
            │              │           │                     │
            │       [4] sandboxed execution ─────────────────▶│ compare the graph the
            │              │           │                      │ program declared and built
            ▼              ▼           ▼                      ▼
        [5] parse ANSWER → map labels back → compare → classify failure
                                       │
                        ┌──────────────▼───────────────┐
                        │ accuracy · invariance · gap  │
                        │ failure decomposition        │
                        └──────────────────────────────┘
```

Five API calls per variant: 1 × M1, plus each code mode crossed with each library arm.

The two branches out of a single `Variant` — text for M1/M2, plain `nodes`/`edges` data for M3 — are
what make the transcription control possible. The third branch, `true_edge_set(v)`, is what makes
failure attribution possible.

M1 and M2 receive the same graph text for every variant; M3 receives none. The reference encoding
is the edge-list "adjacency" wording for both datasets — see
[the reference encoding](datasets.md#4-the-reference-encoding). It does not affect the structure
above: the reference is one point, and every transform is defined relative to it.

## 2. Module map

M2/M3 programs run in local subprocesses; see
[execution environment](execution-sandbox.md#execution-environment).

```
src/gsi/
  data/        base.py       GraphInstance dataclass + JSONL helpers
               graphqa.py    generate GraphQA-style graphs, 10 tasks, ground truth via networkx
               erdos.py      load HuggingFace PKU-ML/Erdos, 24 unambiguous tasks
  serial/      variant.py    Variant, the four single-axis transforms, axes_differing, to_nx
               render.py     10 renderers, one per (syntax, structure) pair
               parse.py      text -> edge set; tests only
               canonical.py  exact canonical labeling of a (graph, query) pair; used by E3
  prompts/     modes.py      three modes, the fixed code template, the library arms
               solutions.py  reference solution expressions; used only by the stub
  llm/         client.py     OpenAI-compatible client, retry, disk cache
               stub.py       canned-response model for zero-cost pipeline testing
  exec/        sandbox.py    host side: subprocess, timeout, graph matching, static checks
               runner.py     guest side: rlimits, nx hook, execute, recover nodes/edges, sidecar
  score/       parse_answer.py  ANSWER line -> typed value
               compare.py       label remapping, normalization, type-aware comparison
               classify.py      the failure decision tree
  experiment/  config.py     YAML -> ExperimentConfig, per-dataset overrides
               run.py        the five stages, threading, resumability, --estimate
  analysis/    tables.py     accuracy / invariance / ladder / failures / gap / silent_transcription
               figures.py    heatmap and bar charts
```

**Dependency direction** is strictly downward: `serial` depends on `data`; `prompts` on both;
`llm`, `exec`, `score` on those; `experiment` orchestrates everything; `analysis` reads only the
scored JSONL. `exec/runner.py` is the one deliberate exception — it imports **nothing** from `gsi`
because it runs inside an isolated subprocess (see [execution-sandbox.md](execution-sandbox.md)).

## 3. The modes

| | M1 `direct` | M2 `code` | M3 `graph_as_code` |
|---|---|---|---|
| Receives graph as | text | text | pre-filled `nodes`, `edges` |
| Produces | reasoning + `\boxed{…}` | the filled template, answer in `ans` | the same template, two lines already filled |
| Executed? | no | yes | yes |
| Performs transcription | — | **yes** | **no** |
| Performs solution logic | yes | yes | yes |
| Library arms | none | networkx, native | networkx, native |
| Axes that can reach it | all four | all four | `relabel`, `order` only |
| Role | known-fragile baseline | the subject of the audit (CodeGraph's format) | the transcription-free control: M2 with one line filled in by us |

M2 and M3 differ in exactly one thing — who writes `nodes = […]` and `edges = […]` — so their
difference is the cost of transcription and nothing else. The shared template is what guarantees
that: before it existed, M3 imposed a graph representation that free-form M2 did not, and the gap
between them mixed transcription with representation.

`library` is a **separate field**, crossed with the two code modes rather than baked into their
names, so `mode in CODE_MODES` never has to enumerate a cross product. See
[modes-and-prompts.md](modes-and-prompts.md) §2.

Because M3 cannot be affected by `syntax` or `structure` (there is no text for them to change), its
prompts for those variants are byte-identical to canonical and the cache deduplicates them. The
`syntax` rungs of M2 plus M3 form the **transcription ladder** (prose → JSON → networkx code →
injected); see [modes-and-prompts.md](modes-and-prompts.md) §6.

## 4. Invariants the system maintains

These are enforced in code, not merely intended:

1. **Single axis.** Every variant differs from its reference along exactly one axis — canonical for
   most axes, the sorted identity relabeling for the relabel axis (Herbst's convention).
   `assert axes_differing(v, ref) == {v.axis}` in `make_variants`.
2. **Canonical label space.** All correctness comparison happens after mapping node-valued answers
   back through the inverse label map. A relabeling never changes what counts as correct.
3. **Determinism.** Every random draw is seeded from `(instance_id, axis, kind, seed)`. Regenerating
   data is byte-identical; verified by MD5 on both dataset configs.
4. **Idempotence.** Re-running any stage performs no new work. LLM calls are cached by prompt hash,
   executions by code hash, and every JSONL sink skips record ids it already holds.
5. **No silent no-ops.** A transform that produces text identical to canonical is discarded, never
   scored as "the model answered consistently".
6. **One template, both modes and both arms.** The code prompt's skeleton is generated by a single
   function, so M2 and M3 cannot drift apart and the two library arms differ by exactly one
   sentence. Pinned by [`tests/test_modes.py`](../tests/test_modes.py).

## 5. Where state lives

```
data/processed/<config>/instances.jsonl    tracked in git — pins the sample against upstream drift
data/processed/<config>/variants.jsonl     ignored — deterministic function of instances
results/cache/<model>/<prompt_hash>.json   raw LLM replies, shared across configs
results/cache/exec/<hash>.json             execution results
results/<config>/responses/<model>.jsonl   per-run response log
results/<config>/exec/<model>.jsonl        per-run execution log
results/<config>/scored/<model>.jsonl      one row per (instance, variant, mode, library, model)
results/<config>/tables/*.csv, figs/*.png  analysis output
```

Everything is plain JSONL. No database, no binary formats — the intermediate state stays greppable,
diffable, and inspectable by hand, which matters when debugging what a model actually did.

## 6. Design principles

**Structured objects over string manipulation.** A serialization is a record with four fields, not
a string. This is what turns "exactly one thing changed" from a hope into an assertion.

**Attribution over aggregation.** Every measurement is taken per instance and aggregated only at
the end. Averaging early is the specific failure mode we are correcting in prior work.

**Recover what actually happened.** Rather than inferring why a program failed, the harness reads
the graph the program *declared* and the graph it *built*, and compares both against the truth.
Diagnosis rests on observation, not inference — and the declaration is read even when the program
crashed.

**Cheap to re-run.** Two cache layers plus resumable sinks mean a crashed run resumes and a
re-analysis costs nothing. With a fixed API budget and four people sharing it, this is a
correctness property, not a convenience.

**Fail loudly at generation time.** Assertions fire while building data, where a bug is cheap to
fix, rather than surfacing as an inexplicable number after money has been spent.

## 7. Reading order for the rest

[datasets.md](datasets.md) → [permutation-design.md](permutation-design.md) →
[modes-and-prompts.md](modes-and-prompts.md) → [execution-sandbox.md](execution-sandbox.md) →
[scoring-and-classification.md](scoring-and-classification.md) →
[analysis-and-metrics.md](analysis-and-metrics.md) → [pipeline-and-caching.md](pipeline-and-caching.md)
