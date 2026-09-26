# Results: robustness of LLM-generated graph code

Updated 2026-09-18 from the restored scored records, original responses, and execution logs;
Gemma 4 31B and DeepSeek-V4-Flash added to §1-§4 and §8 on 2026-09-24.
**Main finding:** code generation improves observed robustness over direct answering, but the
benefit depends on model, task interpretation, and graph presentation. Consistency alone is
insufficient: stable wrong answers, repeated crashes, and alternative valid paths require separation.

## 1. What ran and what is available

- Models: **Qwen3-8B / Nscale**, **DeepSeek-V3.1 / Novita**, **Gemma 4 31B / Novita** and
  **DeepSeek-V4-Flash / DeepInfra**, via the Hugging Face router. The last two ran on a teammate's
  machine; their scored records and raw replies come from the team dataset
  (`Yonibarel/graph-serialization-invariance`, revision `8e1c186`; checksums under
  `results/hf_snapshot_yoni/`), and §1-§4 read them exactly as the local runs.
- GraphQA: 100 generated graphs × seven tasks = 700 instances, 5–20 nodes.
- Erdős: 100 instances × 12 tasks = 1,200 instances, 4–34 nodes; 1,179 distinct source files.
- Five conditions: `direct`, `code/native`, `code/networkx`, `graph_as_code/native`,
  `graph_as_code/networkx`. Both code modes were zero-shot with fixed templates.
- NetworkX was **permitted, not required**: “You may use the networkx library.” Native prompts
  prohibited third-party libraries. In ordinary code generation, NetworkX imports appear in
  85.2–96.3% of responses after deduplicating by prompt hash for Qwen3-8B and DeepSeek-V3.1, and
  98.2–99.0% for Gemma 4 31B; DeepSeek-V4-Flash often writes plain Python even when NetworkX is
  allowed (46.4% on GraphQA, 61.2% on Erdős).
- Temperature 0; Qwen used `/no_think`. Programs ran in local subprocesses, not Docker.
- **463,420 scored records:** 178,500 GraphQA and 284,920 Erdős (44,625 and 71,230 per model).
  These are not independent calls.

| Axis | Change | Interpretation |
|---|---|---|
| `relabel` | Node labels, then sorting | Permutation sensitivity relative to sorted identity |
| `order` | Edge order | Permutation sensitivity relative to canonical input |
| `structure` | Adjacency list or reciprocal edge entries | Representation sensitivity |
| `syntax` | Prose/plain text, JSON, NetworkX code | Representation sensitivity |

Qwen3-8B's and DeepSeek-V3.1's records (scored, responses, execution logs, raw replies; 52 files)
are in the [public Hugging Face snapshot](https://huggingface.co/datasets/Dolevabudi/graph-serialization-invariance/tree/ee5b49e8013c1e5eb90bc14c2f7786810af01b77);
Gemma 4 31B's and DeepSeek-V4-Flash's come from the team dataset (§8.7). These large artifacts are
not in Git; `scripts/verify.py` downloads the scored records and regenerates every table from them.
The first Erdős repeat study (`floor_erdos.json`) is not in the snapshot and is tracked here (§5).

The graph-as-code conditions are included in the saved permutation results, but were omitted
from the repeat-baseline study (`scripts/nondeterminism_floor.py`). Their raw non-invariance
below is `100 × (1 − mean(frac_identical))`, averaging task × axis rates over relabel and order.

| Dataset | Model | Arm | Raw non-invariance | Repeat floor | Adjusted effect |
|---|---|---|---:|---|---|
| GraphQA | Qwen3-8B | `graph_as_code/networkx` | 14.3% | Not measured | — |
| GraphQA | Qwen3-8B | `graph_as_code/native` | 0.0% | Not measured | — |
| GraphQA | DeepSeek-V3.1 | `graph_as_code/networkx` | 0.0% | Not measured | — |
| GraphQA | DeepSeek-V3.1 | `graph_as_code/native` | 0.0% | Not measured | — |
| Erdős | Qwen3-8B | `graph_as_code/networkx` | 37.6% | Not measured | — |
| Erdős | Qwen3-8B | `graph_as_code/native` | 4.6% | Not measured | — |
| Erdős | DeepSeek-V3.1 | `graph_as_code/networkx` | 4.5% | Not measured | — |
| Erdős | DeepSeek-V3.1 | `graph_as_code/native` | 13.6% | Not measured | — |
| GraphQA | Gemma 4 31B | `graph_as_code/networkx` | 0.1% | Not measured | — |
| GraphQA | Gemma 4 31B | `graph_as_code/native` | 4.1% | Not measured | — |
| GraphQA | DeepSeek-V4-Flash | `graph_as_code/networkx` | 1.6% | Not measured | — |
| GraphQA | DeepSeek-V4-Flash | `graph_as_code/native` | 0.0% | Not measured | — |
| Erdős | Gemma 4 31B | `graph_as_code/networkx` | 5.1% | Not measured | — |
| Erdős | Gemma 4 31B | `graph_as_code/native` | 5.2% | Not measured | — |
| Erdős | DeepSeek-V4-Flash | `graph_as_code/networkx` | 4.5% | Not measured | — |
| Erdős | DeepSeek-V4-Flash | `graph_as_code/native` | 4.4% | Not measured | — |

Non-invariance includes repeated execution/parsing failures, so it is not strictly an answer-flip
rate. An unmeasured floor is not zero; no adjusted effect is reported. Even where a repeat floor
exists, subtracting it does not establish a causal permutation effect (see section 5).

## 2. Read accuracy and invariance together

**Accuracy below** is record-weighted across all available variants, separately by condition.
It gives context, not an independent-trial count or a causal estimate of serialization effects.

| Dataset / model | Direct | Code/native | Code/NetworkX allowed |
|---|---:|---:|---:|
| GraphQA / Qwen | 81.5% | 93.0% | 89.0% |
| GraphQA / DeepSeek | 81.3% | 84.5% | 86.0% |
| GraphQA / Gemma | 90.9% | 97.2% | 97.0% |
| GraphQA / V4-Flash | 83.8% | 78.5% | 83.2% |
| Erdős / Qwen | 64.7% | 91.2% | 69.1% |
| Erdős / DeepSeek | 95.1% | 99.0% | 99.0% |
| Erdős / Gemma | 98.3% | 99.9% | 99.8% |
| Erdős / V4-Flash | 89.8% | 97.4% | 96.4% |

(GraphQA / Qwen direct was printed as 81.6% until 2026-09-24; it is 7,278/8,925 = 81.5%.)

The following table averages task × axis rates over **relabel and order only**.
Each entry is **I / R**: `frac_identical` / `frac_all_correct`, in percent.
I requires every answer to parse and agree; R requires every tested form to be correct.
For relabel, the reference is sorted identity; for order, it is canonical.

| Dataset / model | Direct I / R | Code/native I / R | Code/NetworkX I / R |
|---|---:|---:|---:|
| GraphQA / Qwen | 76.4 / 69.8 | 94.3 / 93.8 | 88.2 / 84.6 |
| GraphQA / DeepSeek | 89.5 / 73.7 | 97.4 / 84.6 | 96.6 / 84.0 |
| GraphQA / Gemma | 97.0 / 87.5 | 96.3 / 95.3 | 95.1 / 94.6 |
| GraphQA / V4-Flash | 89.5 / 75.7 | 92.9 / 75.0 | 92.5 / 78.6 |
| Erdős / Qwen | 49.5 / 51.1 | 86.4 / 89.3 | 61.6 / 65.1 |
| Erdős / DeepSeek | 83.7 / 87.9 | 93.8 / 98.3 | 92.3 / 96.7 |
| Erdős / Gemma | 92.3 / 95.9 | 95.5 / 99.8 | 95.6 / 99.9 |
| Erdős / V4-Flash | 76.0 / 79.6 | 92.1 / 95.9 | 95.2 / 99.0 |

**Code improves both observed metrics in almost every code-versus-direct comparison, not all.**
Over the sixteen comparisons (four models, two datasets, two library arms), I rises in 14 and R in
15. The exceptions are on GraphQA: Gemma's direct answers are already the most consistent (I 97.0
against 96.3 in plain Python, paired -0.6 [-1.9, 0.6], and 95.1 with NetworkX, **-1.9 [-3.2, -0.6]**,
a significant drop), and DeepSeek-V4-Flash's plain-Python R is 75.0 against 75.7 direct (paired
-0.7 [-3.0, 1.6], within noise). Plain Python has the highest I of the three conditions in five of
the eight dataset/model combinations; Gemma on GraphQA (direct) and Gemma and DeepSeek-V4-Flash on
Erdős (NetworkX) are the others. That does not establish that it wins every task or representation,
nor identify the contribution of serialization separately from response nondeterminism.

Paired improvements in R over direct, in percentage points, with 95% percentile bootstrap intervals:

| Dataset / model | Code/native minus direct | Code/NetworkX minus direct |
|---|---:|---:|
| GraphQA / Qwen | +24.0 [20.8, 27.4] | +14.8 [11.5, 18.0] |
| GraphQA / DeepSeek | +10.9 [9.0, 12.9] | +10.3 [8.0, 12.5] |
| Erdős / Qwen | +38.2 [35.9, 40.5] | +14.0 [11.4, 16.6] |
| Erdős / DeepSeek | +10.4 [8.9, 11.9] | +8.8 [7.2, 10.4] |
| GraphQA / Gemma | +7.9 [6.3, 9.6] | +7.1 [5.5, 8.9] |
| GraphQA / V4-Flash | -0.7 [-3.0, 1.6] | +2.9 [0.3, 5.5] |
| Erdős / Gemma | +3.9 [3.0, 4.9] | +4.0 [3.0, 5.0] |
| Erdős / V4-Flash | +16.3 [14.6, 18.1] | +19.5 [17.8, 21.1] |

Method: 5,000 paired resamples, seed 20260918; cluster by GraphQA graph ID (100) and Erdős
source path (1,179), preserving tasks, variants, and conditions together. These pointwise intervals
reflect graph-sampling uncertainty conditional on the collected responses; they do not include
provider randomness or uncertainty from shared cached programs. Injected conditions are excluded.

Three reasons not to equate I with reliable reasoning:

1. **Stable wrong answers:** DeepSeek GraphQA code/native has 97.4% I but only 84.6% R;
   12.8% are consistently wrong, driven by the interpretation mismatch below.
2. **Valid alternatives:** DeepSeek Erdős shortest-path code/native under order has I=50%,
   R=100%. Different shortest paths can be equally correct. Excluding shortest-path tasks raises
   its mean permutation I from 93.8% to 98.0%; do not label this entire difference a failure.
3. **Repeated failure:** Qwen Erdős code/NetworkX has 38.4% non-invariance, but 479 of 2,400
   instance × permutation-axis groups fail to parse on *every* form. That is 20.0 percentage
   points, or 52% of its non-invariant groups, without any usable answer to “flip.”

## 3. Mode and presentation interact

Similar bars across axes mean similar measured instability, not absence of a perturbation effect.
For Qwen GraphQA, raw task-averaged I makes the interaction especially clear:

| Condition | Relabel | Order | Structure | Syntax |
|---|---:|---:|---:|---:|
| Direct | 75.4% | 77.4% | 68.0% | 72.6% |
| Code/native | 92.7% | 95.8% | **59.7%** | 95.1% |
| Code/NetworkX allowed | 86.9% | 89.6% | 81.3% | **60.7%** |

The better code condition changes with representation. Comparisons across axes are descriptive:
axes have different numbers of forms, and an all-forms-agree criterion becomes stricter with more forms.

### A. “Disconnected nodes” measures two different interpretations

GraphQA ground truth means **non-neighbors**, excluding the queried node. DeepSeek often computes
**nodes unreachable by any path**. These answers coincide on only 11 of the 100 canonical instances.
Inspection of programs confirms BFS/connected-component logic, not merely an inference from scores.

| DeepSeek canonical condition | Matches unreachable-node answer | Benchmark-correct |
|---|---:|---:|
| Code/native | 100/100 | 11/100 |
| Code/NetworkX allowed | 99/100 | 12/100 |
| Injected/native | 100/100 | 11/100 |
| Injected/NetworkX allowed | 100/100 | 11/100 |

For `graphqa-sbm-0000-disconnected_nodes`, the injected NetworkX program uses
`nx.node_connected_component(G, 11)` and returns `[17]`; the benchmark expects
`[0, 2, 3, 5, 6, 7, 8, 13, 14, 15, 17]`.

DeepSeek-V4-Flash reads the task the same way, on every graph: the unreachable-node answer on
100/100 canonical instances in both code arms and both injected arms (11/100 benchmark-correct in
each). Gemma 4 31B does so only sometimes: the unreachable-node answer on 27, 29 and 33 of 100 in
the plain-Python, NetworkX and injected plain-Python arms (84, 82 and 78 benchmark-correct) -- that
is, 16, 18 and 22 misreadings beyond the 11 graphs where the two readings coincide -- and none in
injected NetworkX (11, the coincident graphs; 100 correct). Direct answers are mixed for every model (unreachable-node answer / correct: Qwen 23/67,
DeepSeek-V3.1 79/32, Gemma 39/72, DeepSeek-V4-Flash 84/27).

Across all five conditions, GraphQA accuracy is DeepSeek **85.3%**, Qwen **89.9%**.
Excluding this task gives **96.9% versus 91.2%**, reversing the ranking. For the two newer
models: Gemma 96.4% -> 98.8%, DeepSeek-V4-Flash 81.5% -> 92.7%. This is a diagnostic
sensitivity analysis, not grounds to silently drop the task. A wording intervention is still needed
before claiming that clarification fixes it. Low performance here is not evidence of inability to traverse graphs.

### B. Duplicate-edge presentation breaks counting code, for three of the four models

GraphQA node-degree accuracy, correct answers out of 100 for each representation:

| Model / code condition | Canonical | Adjacency list | Reciprocal edge list |
|---|---:|---:|---:|
| Qwen / native | 99 | 17 | 5 |
| Qwen / NetworkX allowed | 95 | 98 | 97 |
| DeepSeek / native | 100 | 34 | 19 |
| DeepSeek / NetworkX allowed | 100 | 100 | 100 |
| Gemma / native | 100 | 100 | 100 |
| Gemma / NetworkX allowed | 100 | 100 | 100 |
| V4-Flash / native | 100 | 83 | 65 |
| V4-Flash / NetworkX allowed | 100 | 86 | 97 |

The native structure average is **11.0% for Qwen and 26.5% for DeepSeek**. Among the 200
structure records, respectively **176 and 147** return exactly twice the nonzero true degree.
DeepSeek-V4-Flash is affected less (74.0%; 51 of 200 exactly twice) and Gemma not at all (100%,
none): the failure is common but not universal across models.
The inspected programs copy both `(u,v)` and `(v,u)`, then count reciprocal entries separately,
for example by incrementing both endpoint counts. A degree of 3 becomes 6. A simple `nx.Graph` merges
reciprocal entries; the native code often does not.

`declared_ok=True` can coexist with this failure because declaration checks normalize duplicate
edges. The semantic graph was copied correctly under that check; its multiplicity was mishandled
by the solving code. This is strong evidence of representation-dependent program failure.

### C. NetworkX permission introduces model-dependent execution failures

Qwen Erdős code/NetworkX accuracy is **69.1%**, versus **91.2%** in native; DeepSeek is **99.0%**
in both, Gemma 99.8% against 99.9%, DeepSeek-V4-Flash 96.4% against 97.4%. Qwen pays heavily for
the permission; DeepSeek-V4-Flash loses a point, and 352 of its 514 wrong NetworkX records are
execution failures (Gemma: 18 of 30). Of Qwen's 4,409 wrong NetworkX-condition records, **3,998 (90.7%)** are execution failures.
They include **1,228** generator-indexing errors, **1,195** calls to the unavailable
`nx.number_of_connected_components`, **653** unavailable `Graph.common_neighbors` method calls,
and **220** missing-`nx` imports. The former claim “91% hallucinated APIs” was too broad.

On Qwen's NetworkX-code syntax rung, missing-`nx` NameErrors occur in **190/700 GraphQA (27.1%)**
and **220/1,200 Erdős (18.3%)** records, versus zero on the other inputs in the same ordinary-code
condition. The old 53.7% figure counted programs without an import, including legal plain-Python
solutions. It was not the crash rate. This is a syntax-associated execution failure, not a proven
causal account of why the model omitted the import.

## 4. What the control and failure labels can actually establish

**Transcription is not the dominant measured failure source.** Across ordinary code records,
98.1–99.9% have correct declared graph data, depending on model/dataset (all four models). But
correct answers can hide copying errors: of Qwen's wrong-declaration records, **148/242 on GraphQA
and 252/495 on Erdős** still answer correctly (DeepSeek-V3.1 10/11 and 182/270, Gemma 11/11 and
40/46, DeepSeek-V4-Flash 23/36 and 45/61). These are record counts, with cache reuse; copying is not universally reliable.
Failure shares alone miss such cases because a correct answer is classified `ok` first.

**The injected-graph control changes information, not just copying effort.** It hides the graph
from the model and supplies it only during execution. The M2–M3 gap is therefore not a clean
estimate of transcription cost. A further prompt defect makes some comparisons misleading:

- For Erdős, injected prompts explicitly identify directed graphs but can omit **undirectedness**.
  The neighbor preamble discusses successors for directed graphs, while the removed graph text
  carried the actual undirected designation.
- On canonical `neighbor`, **all eight model × library conditions** return the one-way successors
  interpretation on **100/100** instances. Each scores **28/100**: 16/16 directed, 12/84 undirected.
- All four NetworkX conditions construct `DiGraph` on all 84 undirected instances. This is a concrete
  control-prompt information loss, not evidence that removing transcription hurts reasoning.
- The construction checker largely compares edge sets and can miss graph-type/node-set errors;
  wrong answers from these directedness mismatches can be labelled `logic` with `construction_ok=True`.

**Update 2026-09-22:** the control was rerun with the graph type stated explicitly
(`configs/erdos_m3fix.yaml`). `neighbor` goes from 28/100 to 100/100 in all eight model × library
arms and wrong-direction NetworkX graphs fall to zero, confirming the information loss above. See
[docs/erdos-m3-graph-type-rerun.md](docs/erdos-m3-graph-type-rerun.md), including
the single-program flips and re-asked-prompt changes that are not effects of the fix. The
omission is analysed as a one-word ablation in
[docs/graph-type-omission-ablation.md](docs/graph-type-omission-ablation.md):
where a task's preamble does not state the graph type, models sometimes infer it from nearby
wording -- all four do on `neighbor` -- and a wrongly built graph can still score correct.

**Caching can multiply a single program's success or failure.** Qwen's GraphQA injected/NetworkX
cycle check is wrong on **1,274 records from one cached reply**, which calls `nx.has_cycle`.
On syntax/structure, M3 sees no changed graph text; flat bars can be designed into the control.
Its I is not necessarily 100%: repeated execution failures fail the all-parsed requirement.
Read prompt counts and correctness alongside record counts; do not pool native and NetworkX
failure labels as though construction errors were equally observable.

## 5. Nondeterminism and other measurement limits

**Superseded by §8.0.** Both first-version repeat studies below (`floor_graphqa.json`,
`floor_erdos.json`) are kept as a record of what was measured and why it was rejected; every
floor claim in this document is made against the corrected floor of §8.0 (`floor2_<dataset>.json`).

The saved GraphQA repeat study asks each selected canonical prompt three times, on 150 instances:

| Model | Direct disagreements | Code/native | Code/NetworkX allowed |
|---|---:|---:|---:|
| Qwen | 12/150 (8.0%) | 3/150 (2.0%) | 4/150 (2.7%) |
| DeepSeek | 7/150 (4.7%) | 1/150 (0.7%) | 1/150 (0.7%) |

These demonstrate repeat variability, but **do not justify the old noise-subtracted percentages**:

- The floor treats repeated unparsable answers as stable; the main metric treats them as non-invariant.
- Relabel ordinarily has identity plus three seeds; order has canonical plus up to three variants,
  with no-op removal. The old “three versus two forms” account was incorrect.
- The 150 GraphQA instances cover only 86/100 graphs and no star graphs, due to sorted-ID sampling.
- Canonical repetitions are not the sorted-identity reference for every Erdős relabel comparison.
- The Erdős repeat study (`results/floor_erdos.json`, 150 instances x 3 asks, both models,
  0 dropped): Qwen
  direct 38/150 (25.3%), code/native 4/150 (2.7%), code/NetworkX 6/150 (4.0%); DeepSeek
  direct 19/150 (12.7%), code/native **0/150 (0.0%)**, code/NetworkX 4/150 (2.7%). The raw replies
  were kept in the local response cache, which is not in the repository. These are **raw disagreement rates,
  not a correction**: the objections above about definition mismatch, biased sampling and reference
  choice apply to them equally. Subtracting separately estimated rates is not a validated causal
  decomposition even after matching their definitions.
- An earlier version of this section stated that a 3-ask floor is comparable to `relabel`
  (3 forms) and stricter than `order` (2 forms). That was wrong. In the full configs `relabel` has
  **4** forms per instance (identity + 3 seeds) and `order` has **3** for most instances. A 3-ask
  floor is therefore *less* strict than either axis and **under**-estimates disagreement, so the
  old subtraction overstated the permutation effect rather than being conservative.

Also found: two Qwen GraphQA direct answers containing only `ANSWER` were parsed as empty lists
and wrongly credited; 21 correct code records were labelled `no_computation` but still included
in accuracy. These are small known effects; the reported tables do not correct them.
Alternative shortest paths and float tolerances also separate answer identity from task correctness.

Independent recomputation found no discrepancies in the 1,200 Erdős ground truths under the existing
tolerance. That does not validate every parser or failure label. Broad claims that graph size barely
matters, or that models fail on unrelated instances, are withdrawn: those patterns depend on task
and condition. Generalization is limited to these models/providers and small sampled graphs.

## 6. What to conclude

**Supported:** code improves observed consistency and all-variants correctness versus direct
answering in most aggregate permutation comparisons (I in 14 and R in 15 of 16; not Gemma's
consistency on GraphQA, where direct answering is already the most consistent); presentation
interacts with the code condition; three of the four models show duplicate-counting failures; task interpretation and control-prompt information
loss explain important low scores. Successful transcription does not guarantee a correct program.

**Not established:** a noise-corrected causal permutation effect; universal superiority of native
Python or NetworkX; a pure transcription-cost estimate from M2–M3; or a general model ranking
from pooled accuracy. Do not equate non-invariance with error or invariance with correctness.

These findings set the next steps, and each is reported where it was carried out:

1. **Measurement.** `scripts/audit_results.py` separates stable-correct, stable-wrong,
   valid-but-different, varying-with-errors and unparsed groups per instance (§7). The archived
   outputs were not re-scored, so the small scorer effects of §5 remain in the tables.
2. **The control.** The Erdős control was rerun with the graph type stated in every injected prompt
   (§4, [docs/erdos-m3-graph-type-rerun.md](docs/erdos-m3-graph-type-rerun.md)).
3. **Mitigation.** Detection, voting, canonical labeling and one solver per task are §8
   (instructor feedback specifically encouraged mitigation). The targeted prompt hints (E4) were
   not run in this repository (§8.5).
4. **The repeat baseline** was redone with the metric's own definitions (§8.0).

## 7. Reproduction and reading order

(The mitigation phase is §8, appended after this section.)

Start with `tables/accuracy.csv`, then read `invariance.csv` with I and R together. Use `ladder.csv`,
`failures.csv`, and `silent_transcription.csv` for diagnosis; join scored/response/exec rows by
`record_id` to inspect a program. Model-specific tables are under `tables/<model>/`.

Run `python scripts/audit_results.py` from an environment with project dependencies to reproduce
per-instance categories (`per_instance.csv`, written but not tracked: 29 MB), aggregate rates, and
the 5,000-resample paired intervals under `results/review/`. The independent calculation reproduces all **1,520** invariance-table cells of
the four models (760 for the first two). This audit reads stored outputs; it makes no API calls and executes no generated programs.
The other scripts in `results/review/` are read-only audits of the same stored outputs, each with
its JSON beside it: `measurement_audit.py` (parse failures, empty and duplicate answers, M3 records
per task and arm, the repeated-prompt sample; the two local models), `measurement_control_followup.py`
(Erdős source files and duplicate graphs, the 1,179 above; M3 `neighbor` answers and graph-direction
mismatches), `mechanisms_audit.py` (NetworkX use and exception types in the generated code),
`task_patterns.py` (per-task patterns and canonical overlap between models) and `error_patterns.py`
([docs/error-findings.md](docs/error-findings.md)).
Combined tables can be regenerated with `python scripts/analyze.py --config configs/graphqa.yaml`
(and `configs/erdos.yaml`); `--models <name>` writes model-specific exports.
`python scripts/verify.py` does all of this in a scratch copy, starting from the published records
(sha256-checked), and compares every regenerated table with the committed one.

## 8. Mitigation phase: detecting and reducing serialization-induced failures

The mitigation phase defined seven experiments: **E0** re-measure the nondeterminism floor;
**E1** use disagreement across permutations as an error detector; **E2** permutation voting, alone
and with abstention; **E3** canonical labeling of the input; **E4** targeted prompt hints;
**E5** one solver program per task, decoupled from the instance; **E6** program voting.

Success criteria, fixed before any of E1-E5 was run:

1. **Detection is real** if E1 catches ≥70% of wrong answers at ≤15% flag rate on ≥3 of 4 models
   in the native code arm.
2. **Voting is safe** if E2 never lowers code-arm accuracy by more than the floor interval, and
   improves it on ≥2 models.
3. **Canonical labeling is free** if E3's best scheme is within 1 pp of the random-label baseline
   on both datasets (better is a bonus, not required).
4. **A hint is adopted** only if it improves its target failure on ≥3 models with no regression
   on any other axis beyond the floor interval.
5. **Decoupling works** if E5 is within 5 pp of M2 on both datasets.
6. **The recipe is a result** if it reduces the floor-corrected flip rate by ≥50% on ≥3 models
   while accuracy does not drop.

E0, E1, E2, E3, E5 and E6 ran on all four models; E4 (prompt hints) was not run. Qwen3-8B and DeepSeek-V3.1 ran locally; for Gemma 4 31B and
DeepSeek-V4-Flash the base run comes from the team dataset (scored records and raw replies, §8.7),
and E0, E3 and E5 made new calls (2026-09-24, about $1.50). Tables:
`results/<dataset>/tables/{permutation_signal,canonical_labeling,canonical_labeling_invariance,solver_per_task,program_voting}.csv`
and `results/floor2_<dataset>.json`. Everything here is measured against the base run of §1-§5,
and the flip-rate claims against the corrected floor of §8.0. This section was revised on
2026-09-23 after a review of the first write-up and extended to four models on 2026-09-24; §8.6
lists what changed and why.

Two conventions hold throughout. The sorted-identity form (`relabel:identity`) is a *reference*,
never a perturbation: it renames nothing, on GraphQA it is the canonical prompt itself, and on
Erdős it is byte-identical to the `sorted_st` ordering for 1,136 of 1,200 instances. And an
unparsable answer (a crash, a missing `ans`) never counts as agreement, as in §2.

### 8.0 The floor, measured with the metric's definitions (E0)

Section 5 rejected the first floor: it treated unparsable repeats as stable, used 3 asks where
`relabel` has 4 forms, sampled by sorted id and so missed every star graph, and re-asked the
canonical prompt where `relabel` is judged against the sorted-identity reference. E0 redoes it
with an unparsable reply counting as disagreement, k = 4, a stratified sample of 100 instances,
and both reference prompts on Erdős. Instead of subtracting, it reports the observed flip rate on
the same instances next to the floor, with a paired 95% interval on the excess.

GraphQA (relabel / order):

| model | arm | floor | flips | excess over floor |
|---|---|---|---|---|
| Qwen3-8B | direct | 6.0% | 24% / 23% | **+18 [+9,+27] / +17 [+9,+25]** |
| Qwen3-8B | code/networkx | 5.0% | 14% / 13% | **+9 [+3,+15] / +8 [+3,+13]** |
| Qwen3-8B | code/native | 1.0% | 8% / 6% | **+7 [+2,+12] / +5 [+1,+9]** |
| DeepSeek-V3.1 | direct | 7.0% | 14% / 10% | **+7 [+1,+13]** / +3 [-1,+7] |
| DeepSeek-V3.1 | code/networkx | 1.0% | 3% / 1% | +2 [-1,+5] / +0 |
| DeepSeek-V3.1 | code/native | 0.0% | 4% / 3% | **+4 [+0.1,+8]** / +3 [-0.4,+6] |
| Gemma 4 31B | direct | 3.0% | 1% / 2% | -2 [-5,+0.8] / -1 [-4,+2] |
| Gemma 4 31B | code/networkx | 1.0% | 5% / 5% | **+4 [+0.1,+8] / +4 [+0.1,+8]** |
| Gemma 4 31B | code/native | 2.0% | 4% / 2% | +2 [-0.8,+5] / +0 [-3,+3] |
| DeepSeek-V4-Flash | direct | 5.0% | 15% / 12% | **+10 [+3,+17] / +7 [+1,+13]** |
| DeepSeek-V4-Flash | code/networkx | 7.0% | 5% / 7% | -2 [-5,+0.8] / +0 [-6,+6] |
| DeepSeek-V4-Flash | code/native | 4.0% | 7% / 5% | +3 [-0.4,+6] / +1 [-1,+3] |

Bold intervals exclude zero. For Qwen every cell is above its floor; for DeepSeek-V3.1 the excess is
established on relabel in the direct and native arms and is within noise elsewhere at n = 100.
Erdős (relabel is judged against the sorted-identity reference, order against canonical, so the
two references are re-asked separately; n = 95 / 100):

| model | arm | floor (identity / canonical) | flips relabel / order | excess over floor |
|---|---|---|---|---|
| Qwen3-8B | direct | 30.5% / 27.0% | 54% / 48% | **+23 [+14,+33] / +21 [+12,+30]** |
| Qwen3-8B | code/networkx | 28.4% / 27.0% | 39% / 38% | **+11 [+4,+17] / +11 [+5,+17]** |
| Qwen3-8B | code/native | 1.1% / 0.0% | 14% / 8% | **+13 [+5,+20] / +8 [+3,+13]** |
| DeepSeek-V3.1 | direct | 7.4% / 7.0% | 15% / 11% | **+7 [+1,+13] / +4 [+0.1,+8]** |
| DeepSeek-V3.1 | code/networkx | 1.1% / 1.0% | 4% / 5% | +3 [-1,+8] / +4 [-1,+9] |
| DeepSeek-V3.1 | code/native | 0.0% / 1.0% | 4% / 3% | **+4 [+0.2,+8]** / +2 [-1,+5] |
| Gemma 4 31B | direct | 2.1% / 1.0% | 7% / 4% | **+5 [+0.7,+10]** / +3 [-0.4,+6] |
| Gemma 4 31B | code/networkx | 0.0% / 0.0% | 5% / 3% | **+5 [+0.7,+10]** / +3 [-0.4,+6] |
| Gemma 4 31B | code/native | 0.0% / 0.0% | 4% / 2% | **+4 [+0.2,+8]** / +2 [-0.8,+5] |
| DeepSeek-V4-Flash | direct | 12.6% / 14.0% | 21% / 18% | **+8 [+0.3,+17]** / +4 [-2,+10] |
| DeepSeek-V4-Flash | code/networkx | 1.1% / 1.0% | 5% / 4% | **+4 [+0.2,+8]** / +3 [-0.4,+6] |
| DeepSeek-V4-Flash | code/native | 3.2% / 3.0% | 7% / 3% | +4 [-2,+10] / +0 [-4,+4] |

What the floors are made of matters as much as their size (`disagreed_with_unparsable` in the
JSON). Qwen's direct floor on Erdős, **27-31%**, is genuine: the model gives different answers to
an identical prompt on almost a third of instances, and only 2-3 of those 27-29 disagreements
involve an unparsable reply. Its permutation effect (+21 to +23 pp) sits on top of that. Qwen's
NetworkX floor on Erdős (27-28%) is not variation at all: 26 of 27 and 27 of 27 disagreements
involve an unparsable reply -- the same program crashing on every repeat, which the metric counts
as disagreement. Qwen's `code/native` floor is 0-1% while its flip rate is 8-14%: for that arm
essentially all of the measured instability is the permutation. DeepSeek-V3.1's code arms are within
noise on Erdős at n = 100 except native/relabel; its effects are small in absolute terms (3-5 pp)
and this sample cannot resolve them -- underpowered, not null.

The two newer models look like DeepSeek-V3.1, not like Qwen. Gemma's floors are 0-3% and its
excess is +4 to +5 points wherever it clears zero (every Erdős relabel cell, GraphQA NetworkX),
with lower bounds of +0.1 to +0.7: real but small. DeepSeek-V4-Flash's direct answers carry the
largest newer-model effect (+10 on GraphQA relabel, +8 on Erdős relabel) on top of an Erdős direct
floor of 12.6-14.0% that, like Qwen's, is genuine disagreement (none of those 26 involves an
unparsable reply); its code arms are within noise except Erdős NetworkX relabel (+4).

### 8.1 Detect: disagreement across permutations predicts a wrong answer (E1)

For each instance, compare the canonical answer with its relabel and order variants; flag the
instance if they do not all agree. No new inference: this reads the base run. A crash on the
canonical form is always flagged and always wrong, but it needs no detector, so the table gives
recall twice: on all errors, and on the *silent* errors that returned an answer.

| dataset | model | arm | flag rate | errors caught | silent errors caught | P(wrong \| flagged) | P(wrong \| not flagged) |
|---|---|---|---|---|---|---|---|
| GraphQA | Qwen | code/native | 9.1% | 16/18 (89%) | 16/18 (89%) | 25% | 0.3% |
| GraphQA | Qwen | code/networkx | 16.4% | 53/69 (77%) | 47/63 (75%) | 46% | 2.7% |
| Erdős | Qwen | code/native | 17.1% | 45/60 (75%) | 40/55 (73%) | 22% | 1.5% |
| Erdős | Qwen | code/networkx | 42.2% | 313/321 (98%) | 10/18 (56%) | 62% | 1.2% |
| Erdős | DeepSeek-V3.1 | code/native | 8.1% | 2/2 | 1/1 | 2.1% | 0.0% |
| Erdős | DeepSeek-V3.1 | code/networkx | 10.1% | 10/10 | 4/4 | 8.3% | 0.0% |
| GraphQA | DeepSeek-V3.1 | code/native | 3.4% | 1/90 (1%) | 1/90 (1%) | 4.2% | 13.2% |
| GraphQA | DeepSeek-V3.1 | code/networkx | 4.9% | 11/99 (11%) | 1/89 (1%) | 32% | 13.2% |
| GraphQA | Gemma | code/native | 5.1% | 12/16 (75%) | 12/16 (75%) | 33% | 0.6% |
| GraphQA | Gemma | code/networkx | 6.7% | 17/18 (94%) | 17/18 (94%) | 36% | 0.2% |
| Erdős | Gemma | both arms | 5.0% | no errors | — | 0% | 0% |
| GraphQA | V4-Flash | code/native | 9.1% | 40/152 (26%) | 40/152 (26%) | 62.5% | 17.6% |
| GraphQA | V4-Flash | code/networkx | 9.9% | 25/118 (21%) | 25/118 (21%) | 36% | 14.7% |
| Erdős | V4-Flash | code/native | 9.5% | 17/23 (74%) | 7/13 (54%) | 15% | 0.6% |
| Erdős | V4-Flash | code/networkx | 5.5% | 6/9 | 6/9 | 9.1% | 0.3% |

Where errors are silent and unstable the detector works: Qwen's GraphQA and plain-Python Erdős
errors are caught at 73-89% while flagging 9-17% of instances. Its apparent 98% on Erdős/NetworkX
is mostly crashes; on the 18 silent errors it is 56%. DeepSeek-V3.1's Erdős code arms make only 2 and
10 errors in 1,200 instances, so "all caught" there is a count, not a rate to generalize. Gemma's
errors behave like Qwen's (75-94% caught on GraphQA; none to catch on Erdős); DeepSeek-V4-Flash's
GraphQA errors like DeepSeek-V3.1's (21-26%), and on Erdős it catches 7 of its 13 silent
plain-Python errors.

Ablations (`permutation_signal.csv`). **One extra call** (k = 2, the first seeded relabeling)
already catches 15/18 of Qwen's GraphQA plain-Python errors at a 4.4% flag rate (all
permutations: 16/18 at 9.1%; every one of them silent) and DeepSeek-V3.1's one silent Erdős
plain-Python error at 3.9%, but only 2 of the 4 silent errors of its NetworkX arm at 4.8%; on
Erdős plain Python Qwen needs more (25/55 silent errors at k = 2, 40/55 with all); for the newer
models see docs/four-model-detection.md §4. **Relabeling versus
reordering**, compared at the same k on the same instances (`relabel@matched`, `order@matched`;
42 code cells with errors, four models): relabeling catches more errors in 20 cells, as many in 14
and fewer in 8 (Gemma GraphQA native, DeepSeek-V3.1 Erdős NetworkX, DeepSeek-V4-Flash Erdős in both
arms), and flags more instances in 36. It is the more sensitive probe, not a uniformly better one.

The failure of the detector is as informative as its success. DeepSeek-V3.1's GraphQA errors are
*systematic* -- the `disconnected_nodes` misreading of §3A is made identically on every variant --
so permutation cannot expose them: 13% wrong among the *unflagged*. DeepSeek-V4-Flash repeats the
same misreading on every graph (and misreads `connected_nodes` on 63), with 14.7-17.6% wrong among
its unflagged instances; Gemma makes the misreading on only 16 graphs, unstably, and 12 are
caught. Disagreement detects unstable errors, not wrong beliefs.

### 8.2 Improve at inference time: vote, or abstain (E2, E6)

**Answer voting.** Majority over the canonical + permuted answers; ties go to the canonical answer:

| | canonical | vote | Δ |
|---|---|---|---|
| Qwen, Erdős, code/networkx | 0.732 | 0.797 | +6.4 |
| Qwen, GraphQA, direct | 0.851 | 0.887 | +3.6 |
| DeepSeek-V3.1, Erdős, direct | 0.963 | 0.988 | +2.5 |
| Qwen, Erdős, code/native | 0.950 | 0.960 | +1.0 |
| DeepSeek-V3.1, GraphQA, code/native | 0.871 | 0.869 | -0.3 |
| DeepSeek-V3.1, GraphQA, direct | 0.804 | 0.786 | -1.9 |
| V4-Flash, Erdős, direct | 0.915 | 0.940 | +2.5 |
| Gemma, GraphQA, direct | 0.901 | 0.890 | -1.1 |
| V4-Flash, GraphQA, code/native | 0.783 | 0.759 | -2.4 |

On the sixteen code cells the change is -2.4 to +6.4 points: gains where errors are unstable,
nothing -- or a loss -- where they are systematic. DeepSeek-V4-Flash's GraphQA plain-Python arm
loses 2.4 points, all of it one task: on 17 `connected_nodes` instances a correct canonical answer
is outvoted by the misreading most of its variants make, and no instance gains. It is not safe on
direct answering either: on GraphQA DeepSeek-V3.1 loses 1.9 points and Gemma 1.1 (8 instances
lost, 6 of them `disconnected_nodes`, none gained). **Abstaining when the permutations disagree** is the stronger use of the same
calls: Qwen's weaker code arm (Erdős/networkx, 73.2%) answers 57.8% of instances at **98.8%**;
DeepSeek-V3.1's Erdős native arm answers 91.9% at 100%; Qwen's GraphQA native arm 90.9% at 99.7%;
Gemma's GraphQA NetworkX arm 93.3% at 99.8%; DeepSeek-V4-Flash's Erdős native arm 90.5% at 99.4%. Where
errors are systematic it cannot make the answers reliable: on GraphQA plain Python DeepSeek-V3.1
answers 96.6% at 86.8% (87.1% without abstaining) and DeepSeek-V4-Flash 90.9% at 82.4% (78.3%),
so 13-18% of what they answer is still wrong. Cost is k× calls.

**Program voting (E6).** Each variant's program is run on the canonical graph -- its declarations
removed, the canonical edges injected in the canonical order, written in the labels that program
expects -- and the outputs vote (ties to the canonical program's answer). The programs are not
rewritten; node answers are mapped back by the scorer. 300 instances per dataset:

| | programs agree | two parsable answers differ | programs with no answer | canonical → vote |
|---|---|---|---|---|
| Qwen, GraphQA, native | 92.0% | 8.0% | 0.0% | 0.970 → 0.997 |
| Qwen, GraphQA, networkx | 83.7% | 10.7% | 2.2% | 0.897 → 0.923 |
| DeepSeek-V3.1, GraphQA, native | 96.3% | 3.7% | 0.0% | 0.877 → 0.873 |
| DeepSeek-V3.1, GraphQA, networkx | 96.0% | 1.0% | 0.8% | 0.860 → 0.880 |
| Qwen, Erdős, native | 88.3% | 10.3% | 0.2% | 0.960 → 0.960 |
| Qwen, Erdős, networkx | 63.3% | 3.0% | 25.6% | 0.743 → 0.797 |
| DeepSeek-V3.1, Erdős, native | 99.7% | 0.3% | 0.0% | 1.000 → 1.000 |
| DeepSeek-V3.1, Erdős, networkx | 97.7% | 0.7% | 0.3% | 0.993 → 1.000 |
| Gemma, GraphQA, native | 94.7% | 4.7% | 0.1% | 0.980 → 0.973 |
| Gemma, GraphQA, networkx | 94.3% | 5.7% | 0.0% | 0.973 → 0.967 |
| Gemma, Erdős, native | 100% | 0.0% | 0.0% | 1.000 → 1.000 |
| Gemma, Erdős, networkx | 99.7% | 0.0% | 0.1% | 1.000 → 1.000 |
| V4-Flash, GraphQA, native | 91.0% | 9.0% | 0.0% | 0.790 → 0.767 |
| V4-Flash, GraphQA, networkx | 90.7% | 9.3% | 0.0% | 0.857 → 0.850 |
| V4-Flash, Erdős, native | 96.3% | 0.3% | 0.6% | 0.973 → 0.990 |
| V4-Flash, Erdős, networkx | 99.0% | 1.0% | 0.0% | 0.993 → 0.993 |

Programs written for different serializations of one instance return different answers on the
same graph for 0-10.7% of instances; the low agreement of Qwen/Erdős/NetworkX is crashes (25.6%
of its programs return nothing), not disagreement. Voting over programs moves accuracy by -2.3 to
+5.3 points. The -2.3 is DeepSeek-V4-Flash on GraphQA `connected_nodes`: most of its programs
return every reachable node instead of the neighbours, and on 7 instances that majority outvotes a
correct canonical program (none the other way). Like answer voting, it amplifies whatever most of
the programs believe. Agreement on one graph does not show two programs equivalent on every graph, and a
relabeled program still sees the variant's labels, so label-dependent tie-breaking remains part
of what is measured.

### 8.3 Improve the input: canonical labeling (E3)

Every instance's graph is relabeled by a structure-derived rule, rendered once, and run through
every arm -- 400 GraphQA and 150 Erdős instances -- then paired per instance against (i) the
dataset's native labels and (ii) the mean of the base run's random relabelings.

The first run used two heuristics (degree + Weisfeiler-Lehman colour; BFS from the minimum) and
claimed that the relabel axis vanished by construction. It did not: both broke the remaining ties
by the input label. Rendered on every instance (`canonical_labeling_invariance.csv`, no
inference), only 71% / 76% of GraphQA relabelings and 53% / 57% of Erdős relabelings produce the
canonical form's prompt, and only 25-58% of instances do so for all of their relabelings. The
exact scheme (`gsi.serial.canonical`: the same low-degree-first colour order, remaining ties
resolved by searching for the lexicographically smallest edge list, the question's nodes part of
the form, undirected edges written low-high) renders **every** relabeling (2,799 GraphQA, 4,799
Erdős) and every reordering (1,926, 3,524) to the canonical form's prompt. Both axes vanish,
verified rather than assumed.

Accuracy of the exact scheme, direct and code arms (M3 excluded: it sees no graph text):

| | vs native labels | vs random relabelings |
|---|---|---|
| GraphQA, Qwen | native **-3.0 [-5.4,-0.6]**; networkx **+4.2 [+1.6,+6.9]**; direct -0.8 | native **-2.0 [-4.1,-0.02]**; networkx **+3.6 [+1.0,+6.2]**; direct **+4.0 [+0.9,+7.1]** |
| GraphQA, DeepSeek-V3.1 | -0.8 to +1.0; networkx **+1.0 [+0.02,+2.0]** | **+0.8 to +2.3**, every interval above zero |
| Erdős, Qwen and DeepSeek-V3.1 | -2.0 to +2.0, none significant | -2.0 to +2.4, none significant |
| GraphQA, Gemma | -1.2 to +0.8, none significant | native **+1.2 [+0.2,+2.3]**; networkx +1.2; direct +0.6 |
| GraphQA, V4-Flash | -1.2 to +0.5, none significant | native -1.2; networkx -0.7; direct **+3.3 [+1.3,+5.2]** |
| Erdős, newer models | -0.7 to +0.7, none significant | -0.4 to +1.1; V4-Flash direct **+3.8 [+0.2,+7.4]** |

Bold intervals exclude zero. Against random labels the canonical form is significantly better in
seven of twelve GraphQA cells and one of twelve Erdős cells (n = 150), and significantly worse in
one. That loss, Qwen's
GraphQA plain-Python arm, is one task: `disconnected_nodes` falls from 54 to 42 of 57 (14 of the
new errors are logic errors), the task whose wording §3A shows to be ambiguous; on the other six
tasks the canonical form and the native labels score the same, 334 of 343 each. By the plan's
pre-registered criterion (within 1 pp of random labels on both datasets) it passes for
DeepSeek-V3.1 and Gemma and fails for Qwen (-2.0 in two cells: GraphQA plain Python, significant,
and Erdős NetworkX, not) and, narrowly, DeepSeek-V4-Flash (-1.2 on GraphQA plain Python, not
significant). For the two newer models the canonical form is never significantly worse than
random labels and is better in three cells. **Verdict:** adopt it. It closes the relabel and order
axes exactly; its one significant cost is on an already ambiguous task, and only those three of 24
cells are more than 1 pp below random labels. The heuristic rows stay in
`canonical_labeling.csv` (schemes `degree_wl`, `bfs_min`, unchanged) as measurements of those
heuristics, not of a canonical labeling.

### 8.4 Improve the program's scope: one solver per task (E5)

One `solve(nodes, edges, ...)` per (task, library), with no graph in the prompt, executed on every
variant of every instance. Invariance of the prompt is 1.0 by construction. Eight of the twelve
Erdős tasks mix directed and undirected graphs; for those the solver takes a `directed` argument
and is called with each graph's type (§8.6: the first version gave it no way to know). The prompt
also carries the generic instruction to leave the answer in `ans`, which conflicts with asking for a
function that returns it; the harness therefore removes a program's own call of `solve` and returns
`ans` from a `solve` that sets it without a `return` (17 Qwen programs, one line each; §8.6).

| | solver acc | per-instance M2 acc | Δ | tasks with no answer | solver invariance |
|---|---|---|---|---|---|
| DeepSeek-V3.1, GraphQA, native / networkx | 0.873 / 0.749 | 0.871 / 0.859 | +0.1 / -11 | 0 of 7 | 1.000 |
| Gemma, GraphQA, native / networkx | 0.873 / 0.873 | 0.977 / 0.974 | -10.4 / -10.1 | 0 of 7 | 1.000 |
| V4-Flash, GraphQA, native / networkx | 0.749 / 0.730 | 0.783 / 0.831 | -3.4 / -10.1 | 0 of 7 | 1.000 |
| Qwen, GraphQA, native / networkx | 1.000 / 0.857 | 0.974 / 0.901 | +2.6 / -4.4 | 0 / 1 of 7 | 1.000 / 0.857 |
| DeepSeek-V3.1, Erdős, native / networkx | 0.991 / 1.000 | 0.998 / 0.992 | -0.7 / +0.8 | 0 of 12 | 0.95 / 0.96 |
| Gemma, Erdős, native / networkx | 1.000 / 1.000 | 1.000 / 1.000 | 0.0 / 0.0 | 0 of 12 | 0.96 / 0.96 |
| V4-Flash, Erdős, native / networkx | 0.992 / 1.000 | 0.981 / 0.992 | +1.2 / +0.7 | 0 of 12 | 0.95 / 0.96 |
| Qwen, Erdős, native / networkx | 0.970 / 0.667 | 0.950 / 0.732 | +2.0 / -6.6 | 0 / 4 of 12 | 0.96 / 0.624 |

For the three stronger models, one solver per task is free on Erdős: within 1.2 points of
per-instance code, in both arms, once the solver is told the graph type. On GraphQA the cost
arrives as whole tasks read the other way: DeepSeek-V3.1's NetworkX `connected_nodes` solver
(0.13, against 1.00 per instance), Gemma's `disconnected_nodes` solver (0.11 in both arms, against
0.84 / 0.82) and DeepSeek-V4-Flash's `connected_nodes` solver (0.13 / 0.00, against 0.37 / 0.71).
Both DeepSeek models already misread `disconnected_nodes` per instance (0.11), so their solvers
lose nothing there. Qwen's plain-Python solvers match its per-instance code arm for arm (+2.6 and
+2.0) but not task for task: its `disconnected_nodes` solver takes the benchmark's reading (1.00
against 0.93) and its Erdős `neighbor` solver is right everywhere (against 0.62), while its Erdős
`has_cycle` solver searches for directed cycles in a two-way adjacency list, so every undirected
edge counts as a cycle (0.64 against 1.00). With NetworkX its solvers call functions that do not
exist (`nx.has_cycle`; on Erdős also `G.common_neighbors` and `nx.number_of_connected_components`)
or index a generator, so one GraphQA and four Erdős NetworkX solvers return no answer on any
graph; the arms lose 4.4 and 6.6 points net (two of the dead Erdős tasks,
`connected_component_number` and `diameter`, score 0 per instance too). Decoupling converts
per-instance flakiness into per-task risk; because a task's solver is a single program, it is also
the only mitigation here that can be *validated by hand* before use.

Solver invariance below 1.0 has three causes. On Erdős every model's `shortest_path` solver
returns different, equally short paths on about half the instances (every form correct). The two
DeepSeek models' plain-Python `diameter` program is right on 89-91% of graphs and its answer
changes with the labels (for DeepSeek-V3.1 also with the edge order). And a task with no answer
fails the all-parsed rule on every instance, which puts Qwen's NetworkX values at about 6/7 on
GraphQA (the tasks have slightly different instance counts) and 8/12 less the ties on Erdős.

### 8.5 What the mitigation phase establishes

1. **Serialization sensitivity is usable as a signal, for unstable errors.** Where errors are
   unstable -- Qwen's GraphQA arms and Erdős plain Python, Gemma on GraphQA -- the detector catches
   73-94% of silent errors at a 5-17% flag rate, and one extra relabeled call often gives most of
   that; on Qwen's Erdős NetworkX arm, whose errors are mostly crashes, it catches 10 of the 18
   silent ones. On those five arms abstaining on disagreement gives 97.3-99.8% accuracy at 83-95%
   coverage, and on Qwen's Erdős NetworkX arm 98.8% at 58%. It cannot detect systematic
   misreadings (both DeepSeek models on GraphQA), and says so by construction.
2. **Canonical labeling is nearly free; voting is not.** Canonical labeling closes the relabel and
   order axes exactly with one rendering per instance (-2.0 to +4.0 pp against random labels over
   four models; three of 24 cells are more than 1 pp below, and the one significant loss is Qwen's
   ambiguous `disconnected_nodes`). Answer voting (-2.4 to +6.4 pp on code arms) and program
   voting (-2.3 to +5.3 pp) cost k calls per instance, help where errors are unstable, and amplify
   a model's majority misreading where they are not.
3. **One solver per task is a trade, not a fix.** Its prompt is invariant by construction and its
   program nearly so over the tasks it answers (0.94-1.00: `shortest_path` ties and two `diameter`
   programs). It is free on Erdős for the three stronger models, and in Qwen's plain-Python arms
   only on balance; a single bad program sinks a whole task -- a task read the other way on GraphQA
   (3-11 points for the three stronger models), a NetworkX function that does not exist or a wrong
   cycle test for Qwen -- so it needs per-task validation.
4. **The residual is systematic error**, untouched by every lever here. Reducing it is a question
   about the prompt's semantics (§3A), not about serialization.

The detector's blind spot holds on four models as a property of the error, not the model: both
DeepSeek models put 59-99% of their GraphQA plain-Python errors into `disconnected_nodes`,
misread identically under every permutation, and those are the two cells where recall collapses
(1/90 and 40/152); Gemma misreads the same task on 16 graphs, unstably, and 12 are caught
([docs/four-model-detection.md](docs/four-model-detection.md)).

**Against the pre-registered criteria** (start of §8):

- (1) Detection -- at least 70% of wrong answers caught at a flag rate of at most 15% on three of
  the four models, plain-Python arm -- is **not met** on GraphQA: Qwen and Gemma pass, both
  DeepSeek models fail. On Erdős the three models that make errors reach it only if crashes count
  as caught: DeepSeek-V3.1 (2 of 2 at 8.1%) and DeepSeek-V4-Flash (17 of 23, 74%, at 9.5%) with
  all permutations, Qwen only with a probe chosen afterwards (70% with three relabelings at 14%).
  On silent errors only DeepSeek-V3.1's single one qualifies.
- (2) Voting safety turns on how "the floor interval" is read. Against each arm's measured floor,
  DeepSeek-V3.1's GraphQA plain-Python arm loses 0.3 points (2 of 700 instances) where the floor
  is 0 of 100: a failure by the point estimate, not by the floor's 95% upper bound (3.6%). Every
  other code-arm loss is within its arm's floor, including the largest, V4-Flash's 2.4 points
  against 4.0% -- but that one is systematic, not noise (§8.2). Voting gains on three models.
- (3) Canonical labeling passes for DeepSeek-V3.1 and Gemma, not for Qwen or, narrowly,
  DeepSeek-V4-Flash (§8.3).
- (5) Decoupling (within 5 pp of per-instance code) is met by no model in both arms on both
  datasets: the three stronger models pass on Erdős and fail on GraphQA in at least one arm (one
  misread task each), Qwen passes on GraphQA and fails in its Erdős NetworkX arm (-6.6) (§8.4).
- (4) and (6), the hints and the combined recipe, were not run.

Not established: E4's hints, beyond a duplicate-edge hint run separately on two models (archived
in [docs/duplicate-edge-hint.md](docs/duplicate-edge-hint.md)); anything about a
different generation of the same prompts (every experiment except E0 uses one draw per prompt,
and E5 one draw per task); and detection rates where a model makes almost no errors
(DeepSeek-V3.1 on Erdős: 2 and 10; DeepSeek-V4-Flash on Erdős NetworkX: 9; Gemma on Erdős: none).

### 8.6 Corrections to the first write-up (2026-09-23, 2026-09-24)

A review of the first version of this section found errors in its code and in its reading of the
tables. Each is fixed in the scripts, rerun, and reflected above; nothing in §1-§5 was affected.

- **The sorted-identity form was treated as a relabeling** in detection (E1/E2) and program voting
  (E6). It renames nothing and duplicates the canonical (GraphQA) or `sorted_st` (Erdős) prompt.
  The all-permutation detection rows do not change; the relabel-only rows do. The claim that one
  extra call catches only 39% of Qwen's GraphQA errors ("Qwen needs the full set") came from that
  duplicate; a real relabeling catches 15/18.
- **Detector recall counted crashes as caught.** Silent-error recall is now reported beside it
  (Qwen/Erdős/NetworkX: 97.5% overall, 55.6% on the 18 silent errors), with counts.
- **"Relabeling is the better probe in every cell"** compared four relabel forms against three
  order forms. At equal k it catches more errors in 11 of 24 cells and fewer in 2 (two models;
  on four, 20 of 42 and fewer in 8, §8.1).
- **A transcription error:** P(wrong | not flagged) for Qwen/Erdős/NetworkX was printed as 25%;
  the table always said 1.2%.
- **E6 rewrote constants that merely equalled the query label** (`degree[u] += 1` became `+= 3`
  when the question named node 1). 32 of 898 Qwen GraphQA plain-Python relabel programs changed
  answer, every one through such a collision. Programs are now run unchanged on the canonical
  graph in their own labels, and vote ties no longer depend on execution order. Agreement rose
  from 62-96% to 63-100%.
- **E3's "canonical" labelings were heuristics.** Both broke ties by the input label, so only
  53-76% of relabelings rendered to the same prompt (25-58% of instances in full). E3 is rerun
  with an exact canonical labeling (§8.3); its accuracy result is mixed rather than free
  everywhere, and the heuristics' +3.3 pp for Qwen on Erdős is not reproduced (+0.7, n.s.).
- **E5's invariance was attributed to order-dependent algorithms** for both models; for Qwen it is
  crashed tasks.
- **The floor's composition**: the Qwen NetworkX floor is repeated crashes, now stated.

Found while extending the phase to four models (2026-09-24):

- **E5 gave one solver per task no way to know the graph type.** Eight of the twelve Erdős tasks
  mix directed and undirected graphs, but the solver prompt was built from the task's first
  instance (undirected) and `solve(nodes, edges, ...)` carried no graph type. E5 measured that gap
  instead of the cost of decoupling: `density` was right on undirected graphs and wrong on almost
  every directed one for all four models, and three models' `neighbor` solvers read the
  preamble's "For directed graph, return the successors" as the graph type. The solver now takes
  a `directed` argument for those eight tasks and is called with each graph's type; every other
  prompt is byte-identical. DeepSeek-V3.1's Erdős solver goes from 0.913 / 0.914 (-8.5 / -7.8
  against per-instance code) to 0.991 / 1.000, Qwen's from 0.277 / 0.423 to 0.348 / 0.417 (0.970 /
  0.667 after the next fix). GraphQA (one graph type per task) is unchanged.
- **E5 scored 16 Qwen solvers as answering nothing because of the prompt, not the model.** The
  solver prompt asks for a function that returns the answer but also carries the generic
  instruction to leave the answer in `ans`, and Qwen obeyed the latter in two ways. Five programs
  end with their own `ans = solve(nodes, edges, directed, node)`, which ran before the harness's
  call and raised a `NameError` wherever it names an argument (`directed`, `node`, `u`, `v`)
  rather than the injected `nodes` and `edges`; the graph-type fix added two of these (Erdős
  `has_cycle`, whose earlier `ans = solve(nodes, edges)` had worked, and a new NetworkX
  `shortest_path` program). Twelve set `ans` inside `solve` and never return it, so the harness
  received `None`, scored as an empty or unparsable answer. The harness now removes a program's
  own module-level calls of `solve` and returns `ans` from a `solve` that sets it and has no
  `return` of its own: one line in each of 17 programs (those 16, and `cycle_check`, whose own call
  happened to work). No program of the other models is changed, and none of the 152 has any other
  module-level statement. Qwen's solvers go from
  0.724 / 0.583 to 1.000 / 0.857 on GraphQA and from 0.348 / 0.417 to 0.970 / 0.667 on Erdős
  (tasks without an answer: 1 / 1 to 0 / 1, and 4 / 6 to 0 / 4); what remains is the model's
  own error -- NetworkX functions that do not exist, a generator indexed like a list, a cycle test
  that counts every undirected edge. `cycle_check` gives the same answers on all 1,274 of its
  records. The re-execution used the cached programs; no new calls. Because the harness changed and
  the prompts did not, a resumed run would have kept an older checkout's records; each E5 record
  now stores the hash of the code it executed, and a rerun re-executes every record whose code or
  prompt differs. The committed records were migrated that way, from the execution cache, with
  every answer unchanged.
- **The floor's output depended on dict order** in its last digits; the keys are now sorted and
  reruns are byte-identical.
- **`task_patterns.py` compared whichever two models came first** in its canonical-overlap audit;
  with four models present it now compares every pair.

### 8.7 Where the newer models' records come from

Gemma 4 31B and DeepSeek-V4-Flash were not run from this checkout. Their scored records in §1-§4
come from the team dataset (`Yonibarel/graph-serialization-invariance`); revision `8e1c186` adds the raw API
replies (65,624 per model, exactly the prompts of the scored records;
`results/hf_snapshot_yoni/8e1c1863.../manifest.json`) and leaves the scored records unchanged in
content. The mitigation phase needs more than scores -- E6 runs the generated programs, E0 re-asks
prompts -- so the base run was replayed from those replies through this repository's pipeline,
with every API key blank so that nothing could be re-asked. The replay reproduces every field of
231,697 of the 231,710 records. The other 13 (GraphQA: Gemma 5, DeepSeek-V4-Flash 8, seven of
them one node_degree instance's M3/NetworkX programs) timed out in the team's run and finish
with the correct answer on replay. The tables keep the published records, so those 13 count as
execution failures, as they did in the team's run -- at most 8 of 44,625 records per model.

The replies were merged into the local cache. E1 and E2 read the published records and E6 runs the
replayed programs, all without new calls. E0 (repeats), E3 (canonical prompts) and E5 (solvers) are new
inference for the two models, about $1.50 in total.
