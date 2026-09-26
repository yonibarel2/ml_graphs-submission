# Datasets and the instance schema

How raw benchmarks become the uniform `GraphInstance` records that everything downstream consumes.
Source: [`src/gsi/data/`](../src/gsi/data/).

Benchmarks: GraphQA from *Talk Like a Graph* ([paper](https://arxiv.org/abs/2310.04560),
[generation code](https://github.com/google-research/google-research/tree/master/graphqa)) and
Erdős from G1 ([paper](https://arxiv.org/abs/2505.18499),
[dataset](https://huggingface.co/datasets/PKU-ML/Erdos), [code](https://github.com/PKU-ML/G1)).
The sampled instances are tracked in `data/processed/<config>/instances.jsonl`.

---

## 1. The `GraphInstance` schema

One instance is **one graph paired with one task and one query, plus its ground truth**. Note that
a single graph appears in many instances — once per task — which is why `meta.graph_id` exists
separately from `id`.

| Field | Meaning |
|---|---|
| `id` | unique: `<dataset>-<generator/task>-<n>-<task>` |
| `dataset` | `graphqa` or `erdos`; selects the loader, question template, and configured renderer |
| `task` | task name within that dataset |
| `directed`, `weighted` | graph properties; drive renderer wording and `to_nx` construction |
| `nodes` | canonical node labels, ascending |
| `edges` | canonical edge order; `[u, v]` or `[u, v, w]` when weighted |
| `query_args` | the query in **canonical labels**, e.g. `{"node": 3}` or `{"u": 1, "v": 4}` |
| `answer_type` | one of `bool, int, float, node, node_set, path, edge_set` |
| `ground_truth` | the correct answer in canonical labels |
| `native_prompt` | the dataset's own prompt, when it has one (Erdős); else `None` |
| `meta` | `graph_id`, `n`, `m`, generator, and dataset-specific extras |

`answer_type` is the pivot: it selects the `ANSWER:` format shown to the model, the parser, and the
comparator. Adding a task means picking one of the seven existing types, or adding a type in three
places ([scoring-and-classification.md](scoring-and-classification.md) §5).

`query_args` and `ground_truth` are stored in **canonical labels**. Perturbed labels exist only at
prompt time and are mapped back before scoring — see [permutation-design.md](permutation-design.md) §6.

---

## 2. GraphQA ([`graphqa.py`](../src/gsi/data/graphqa.py))

The original release ships *generation code*, not a downloadable dataset, so we regenerate locally
following the paper's design.

**Graph families** (`GENERATORS`), following Fatemi Appendix A.4 exactly: `er`, `ba`, `sfn`, `sbm`,
`star`, `path`, `complete` — sampled in their proportions (500 each for ER/BA/SFN/SBM, 100 each for
star/path/complete, because those "have less variety"), not cycled evenly.
**Size**: `NODE_RANGE = (5, 20)` nodes, drawn uniformly.
**Parameters**: ER edge probability drawn from [0, 1]; SBM community count drawn from 2 to 10 (capped
at n). Generation and ground truth both use networkx, as they did.

Generation is seeded from the config, and after building each graph we drop self-loops and relabel
to integers `0..n-1` so the canonical labelling is uniform across families.

### Tasks

`FATEMI_TASKS` names the seven tasks defined in their Appendix A.2; `reachability`,
`shortest_path` and `triangle_counting` also exist but are Erdős-style extras and are not in the
GraphQA config.

| Task | `answer_type` |
|---|---|
| `edge_existence` | `bool` |
| `node_degree` | `int` |
| `node_count` | `int` |
| `edge_count` | `int` |
| `connected_nodes` | `node_set` |
| `disconnected_nodes` | `node_set` |
| `cycle_check` | `bool` |
| `reachability` | `bool` |
| `shortest_path` | `int` (hop count) |
| `triangle_counting` | `int` |

Ground truth is computed with networkx, never hand-written. Question wording for the six tasks
shared with CodeGraph follows their templates (*"Is node X connected to node Y?"*, *"List all the
nodes connected to X …"*) so the prompts are comparable.

The one-shot modes and their worked-example pool were removed; the fixed code template replaced
them. See [modes-and-prompts.md](modes-and-prompts.md) §2.

### Query sampling is deliberately balanced

For `edge_existence`, a naive uniform node pair would almost always land on a non-edge in a sparse
graph, so "No" would be correct nearly always and a model could score well by always answering No.
We instead coin-flip between sampling a real edge and a non-edge, and randomize the order of `u`
and `v` so the answer is not inferable from which node was named first.

The result is **balanced but not exactly 50/50** — measured at roughly 62% "Yes" over 60 instances,
because dense families (`complete`, `star` centres) have few or no non-edges and fall back to
sampling an edge. Good enough that a constant answer scores poorly, but if a per-task majority-class
baseline is reported, use the observed rate rather than assuming 50%.

For `shortest_path` we sample only from **connected pairs**, since an unreachable pair has no finite
hop count. If a graph has no valid pair for a task, `sample_query` returns `None` and the instance
is skipped rather than fabricated.

---

## 3. Erdős ([`erdos.py`](../src/gsi/data/erdos.py))

Loaded from HuggingFace `PKU-ML/Erdos`, `test` split: 50 tasks × 100 graphs, 5–34 nodes. This is
the benchmark Herbst et al. measured direct-mode fragility on. Our M1/M2 reference is the
dataset's own edge-list wording (§4); the native prompts are also the source of the graph data and
task wording.

### Three non-obvious loader decisions

**1. Edges are parsed from the prompt text, not from the `edges` column.**
For `maximum_flow` and `traveling_salesman_problem`, the dataset's `edges` column **drops the
weights** that the prompt itself contains — the prompt says `(1, 2, 3)` while the column says
`(1, 2)`. Since the prompt is what the model actually reads, the prompt is authoritative. The
loader parses edges from the prompt and cross-checks against the column, discarding any row where
the two disagree on structure. Using the column would have silently produced unweighted graphs for
weighted tasks, and every max-flow answer would have been wrong for a reason nobody could see.

**2. The prompt is split into preamble and question.**
Erdős prompts have three parts: a task definition, the serialized graph, and the question with an
answer-format sentence. The loader keeps the preamble (it carries the task definition the model
needs) and the question (with the format sentence stripped, since we impose our own `ANSWER:`
contract). The graph portion is discarded — we re-render it from the variant, which is what lets us
perturb it.

**3. Only unambiguous tasks are exposed.** 24 of 50.

### Task selection

Included (24), grouped by `answer_type`:

| Type | Tasks |
|---|---|
| `int` | `triangles`, `degree`, `edge_number`, `node_number`, `connected_component_number`, `strongly_connected_number` |
| `float` | `diameter`, `radius`, `density`, `clustering_coefficient`, `jaccard_coefficient`, `maximum_flow` |
| `bool` | `edge_existence`, `has_cycle`, `is_bipartite`, `is_regular`, `local_connectivity` |
| `node_set` | `neighbor`, `common_neighbor`, `center`, `periphery` |
| `path` | `shortest_path`, `weighted_shortest_path` |
| `edge_set` | `bridges` |

**Excluded**, and why: `topological_sort`, `minimum_spanning_tree`, `bfs`, `dfs`,
`maximal_independent_set`, `min_vertex_cover`, `dominating_set`, `traveling_salesman_problem`,
`hamiltonian_path`, `isomophic_mapping`, `max_weight_matching`, `bipartite_maximum_matching` and
others have **many equally correct answers**. A DAG can have several valid topological orders; a
graph can have several minimum spanning trees of equal weight.

This matters more here than in a normal benchmark. Our central metric asks *"did the model give the
same answer under both serializations?"* — but for these tasks a model could legitimately return a
different-but-equally-valid answer under a relabeling, and we would score it as non-invariant when
nothing is wrong. **Including them would systematically overstate fragility.** They can be
reinstated later behind per-task validity checkers rather than equality (see §5).

`DEFAULT_TASKS` narrows further to 12 for routine runs, spanning every answer type.

### Filtering

`max_prompt_chars` (6,000 in `configs/erdos.yaml`) drops very long prompts. Erdős prompts reach
~12.5k characters, which strains a 7B model's context and inflates cost. Applied identically across
all models so the comparison stays fair.

---

## 4. The reference encoding

**Decided 2026-09-16, with the team present. This is the source of truth; the code implements it.**

| Dataset | Structure | Syntax | |
|---|---|---|---|
| `graphqa` | `edge_list` | `graphqa_nl` | Fatemi's "adjacency" encoder — an edge list in words |
| `erdos` | `edge_list` | `erdos_nl` | the dataset's native prompt |

Set in `DEFAULT_CANONICAL` ([`experiment/config.py`](../src/gsi/experiment/config.py)), overridable
per dataset in the experiment YAML.

**Reference**, here, means the fixed experimental starting point, not an isomorphism-invariant graph
canonicalization. Sorting applies to the reference; perturbations may change labels or order.
M1 and M2 always receive the same graph text for a given variant; M3 receives no text at all, so the
choice does not touch it.

### Why the edge list

**The code-mode evidence points the other way from the direct-mode evidence, and this is a code-mode
audit.** CodeGraph's Table 1 puts adjacency ≥ incident on 4 of 6 tasks, and incident *collapses* on
edge count — 77.0 vs 98.8 — because an adjacency list shows every edge twice and the model
double-counts when it transcribes. Fatemi's own ranking favours incident for few-shot and CoT
prompting but ranks it **worst under zero-shot**, so "best encoding" is prompt-dependent rather than
a property of the encoding. Our modes are zero-shot and two of the three generate code.

**For Erdős the native prompt is Herbst's baseline.** Our renderer reproduces it byte-for-byte on all
2,400 rows of the supported tasks, and that fidelity is exactly what licenses comparing our
direct-mode numbers to theirs. A different reference forfeits the comparison the proposal leans on.

**It is also the form CodeGraph's own sample programs transcribe from**, and it gives both datasets
the same starting point, so a cross-dataset difference is about the data rather than the wording.

### The alternative that was considered and rejected

Incident encoding (an adjacency list in words) for both datasets, on the strength of *Talk Like a
Graph* [2] Table 7, where it has the highest **mean** accuracy across the six basic tasks over all
five prompting methods. It is also easy to generate deterministically.

Rejected because that mean is taken across prompting methods we do not use, and it is dominated by
the few-shot and CoT rows; under zero-shot — our setting — the same paper ranks incident last, and
CodeGraph's code-mode numbers agree. Adopting it would additionally have required an incident
renderer preserving direction and weights (`graphqa_nl` drops weights today), adjacency-list
ordering kinds in every config, and new fidelity checks to replace the ones that pin the edge-list
format.

Recorded here rather than deleted so the question is not reopened from the same evidence.

### What holds either way

* Both encoders are implemented and both reproduce Fatemi's Appendix A.1 examples **byte-for-byte**,
  including two details of "incident" that are easy to get wrong: there is no "nodes" after "among"
  (unlike "adjacency"), and the neighbour noun is singular for a node with exactly one neighbour.
  Pinned by [`tests/test_fatemi_fidelity.py`](../tests/test_fatemi_fidelity.py).
* The incident form remains reachable as the **`structure` variant**, so CodeGraph's
  incident-collapse finding is itself a directly testable structure effect rather than an assumption
  baked into the reference.

[2] Fatemi et al., [*Talk Like a Graph: Encoding Graphs for Large Language Models*](https://arxiv.org/abs/2310.04560),
ICLR 2024, Appendix A.1 and Table 7.

---

## 5. Extending

**A new task in an existing dataset.** Add it to the `TASKS` dict with an `answer_type`, add a
question template, add a ground-truth branch (GraphQA) or confirm the native answer parses (Erdős).
Nothing downstream changes.

**A new dataset.** Implement a loader returning `list[GraphInstance]`, add a `question()` function,
register it in `build_instances` ([`experiment/run.py`](../src/gsi/experiment/run.py)) and
`question_for` ([`prompts/modes.py`](../src/gsi/prompts/modes.py)), and add a `DEFAULT_CANONICAL`
entry. NLGraph (the proposal's stretch goal) was not implemented; its raw format is `n m` on the first
line then edges and queries.

**Ambiguous-answer tasks.** Requires replacing equality with a validity checker in
[`compare.py`](../src/gsi/score/compare.py) — as already done for `path`, which accepts any valid
shortest path rather than one reference — *and* replacing the invariance key with a canonical form
of the answer class. Both are needed; doing only the first would fix accuracy while leaving the
invariance metric wrong.
