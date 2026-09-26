# How the implementation works

This document explains the code in `src/gsi/` in plain words. It assumes you have read the
proposal but not the code. Section 1 is the idea, Section 2 walks one example through the whole
pipeline, Section 3 explains each module, Section 4 tells you how to run things, and Section 5 lists
design decisions you should know about.

The design rationale lives in the other documents in this folder ([index](README.md)) — start with
[modes-and-prompts.md](modes-and-prompts.md) and [permutation-design.md](permutation-design.md).

---

## 1. What we are testing, in one paragraph

A graph can be written as text in many equivalent ways (rename the nodes, reorder the edges, use
JSON instead of a sentence, ...). We want to know whether an LLM that solves a graph problem
**by writing code** gives the same answer no matter which equivalent text it receives. If it does
not, we want to know *where* the mistake enters: when the model **copies** the text into a graph in
its program (transcription), when it **builds** a graph out of that copy (construction), or when it
writes the **solution logic**. We ask the model in three ways:

| Mode | What the model gets | What it produces | Why it is there |
|---|---|---|---|
| `direct` (M1) | graph text + question | reasoning ending in `\boxed{answer}` | the known-fragile baseline (Herbst / G1 wording) |
| `code` (M2) | graph text + question + a fixed program template | the filled template; we run it | the thing we are auditing, in CodeGraph's format |
| `graph_as_code` (M3) | the same prompt with the graph text **removed** and the template's first two lines already filled by us | the same template, minus the copying | the **control**: M2 with one line written by us, so no transcription |

The two code modes are each run **twice**: once told it may use `networkx`, once told to use only
plain Python. That is the `library` axis, and it is a separate field on every result row, not part
of the mode name. So one serialization of one instance costs **five API calls**: 1 + 2 + 2.

If M2 flips its answer under a relabeling but M3 does not, the copying step is to blame.

### The template

Both code modes hand the model the same skeleton, and this is the load-bearing piece of the design:

```
# CODE START
nodes = <the nodes of G>
edges = <the edges of G, as (u, v) pairs>

<your code here>
ans = <the computed result, a Python int>
# CODE END
```

Because `nodes` and `edges` are always assigned, always first, always by that name, we can read them
back out of the program and compare them to the graph the model was shown. **That comparison is the
transcription measurement**, and it works whether or not the model used networkx. M3 gets the same
skeleton with those two lines already filled, which makes M2 and M3 a minimal pair differing in
exactly one thing.

The answer slot deliberately says *"the computed result"*, not *"your answer"*, and the prompt adds
*"Compute the result - do not write it directly."* An earlier draft invited `ans = 3` — the model
working it out in prose and typing the number in. Programs that do it anyway are caught and labelled
`no_computation`.

---

## 2. One example, end to end

Take a 5-node undirected graph with edges (1,2), (1,3), (2,3), (3,4), (4,5) and the Erdős task
"What is the degree of node 3 in the graph?" (answer: 3).

**Step 1 - data.** `data/erdos.py` turns the dataset row into a `GraphInstance`:

```
id="erdos-degree-0012", nodes=[1..5], edges=[[1,2],[1,3],[2,3],[3,4],[4,5]],
query_args={"node": 3}, answer_type="int", ground_truth=3,
meta={preamble: "The task is to determine the degree...", question: "...", format_hint: "Your answer should be an integer."}
```

**Step 2 - canonical serialization.** The dataset's native wording, reproduced byte-for-byte:

```
Here is an undirected graph containing nodes from 1 to 5. The edges are: (1, 2), (1, 3), (2, 3), (3, 4), (4, 5).
```

**Step 3 - variants.** From the canonical form we derive variants that change *exactly one thing*.
A `relabel` variant renames the nodes and then **re-sorts** the list (Herbst's convention), so it
still reads tidily; the question is renamed too ("degree of node **1**?"). An `order` variant
shuffles the edge list; `structure` switches to an adjacency list; `syntax` writes the same thing as
JSON or as networkx code. Every variant is asserted to differ from its reference in one axis only.

**Step 4 - prompts.** M2's prompt (CodeGraph's format plus the template):

```
The task is to determine the degree of a node in the graph. ...
Write a piece of Python code to return the answer in a variable 'ans'. Please enclose the code with
# CODE START and # CODE END.

Fill in the template below and keep its structure. 'nodes' must list every node of G and 'edges'
must list every edge of G as (u, v) pairs. Then write the code that computes the answer from
'nodes' and 'edges'. Compute the result - do not write it directly.

# CODE START
nodes = <the nodes of G>
edges = <the edges of G, as (u, v) pairs>

<your code here>
ans = <the computed result, a Python int>
# CODE END

You may use the networkx library.        <- or "Use only plain Python and its standard library..."

Q: What is the degree of node 3 in the graph?
Here is an undirected graph containing nodes from 1 to 5. The edges are: (1, 2), (1, 3), ...
A:
```

M3's prompt is the same text with the graph description removed and the two declaration lines
replaced by `# 'nodes' and 'edges' are already defined.` Everything else is byte-identical — that
is what makes the pair minimal. M1's prompt is the native text plus G1's sentence asking for
`Therefore, the final answer is: $\boxed{ANSWER}$.`

**Step 5 - the model.** The prompt goes to an OpenAI-compatible endpoint at temperature 0. Replies
are cached by prompt hash. A `stub` model returns canned programs so everything can be tested for free.

**Step 6 - execution (code modes).** The code between the markers runs in a separate process with a
timeout. For M3 we predefine `nodes` and `edges` first. Inside, every networkx graph the program
builds is recorded. When it finishes we read the variable `ans` — nothing else; a missing `ans` or
missing markers is a format failure, and a crash discards `ans`, exactly as CodeGraph's runner does.

We also read `nodes` and `edges` back out of the namespace — **even when the program crashed**,
because the template assigns them before the solving code runs. A program that copied the graph
correctly and then blew up still tells us the copying was fine.

**Step 7 - scoring.** M1: the last `\boxed{}`. Code modes: `ans`. The value is parsed by answer
type, node labels are mapped back to canonical, and it is compared with a type-aware comparator
(sets ignore order, floats have tolerance, paths are accepted when valid and of equal length/weight).

**Step 8 - failure classification.** For code modes:

Nine classes. The template splits the program's work into three visible stages, so a wrong answer
can be charged to one of them:

```
truth --[1]--> declared nodes/edges --[2]--> the graph the code used --[3]--> ans
         transcription           construction                      logic
```

```
program crashed or timed out            -> execution
no code between the markers / no `ans`  -> format
`ans` is a literal (never computed)     -> no_computation   <- checked BEFORE correctness
answer correct                          -> ok
declared graph != the true graph        -> transcription    (construction, in M3)
graph built != the graph declared       -> construction     (networkx arm only)
template ignored, nothing recoverable   -> unverifiable
otherwise                               -> logic
```

`no_computation` sits above the correctness check on purpose: a hardcoded answer that happens to be
right is not a solved task, and counting it `ok` would inflate exactly the number we report.

`construction` needs a graph object to compare against, so it is only separable in the networkx arm.
In the native arm those failures land in `logic` — which is why the two arms' failure decompositions
are **never pooled**.

**Step 9 - analysis.** Per instance: were the answers identical across the canonical/reference form
and every variant of one axis? That fraction is the invariance score. The **transcription ladder**
then reads the transcription-failure share across prose → JSON → networkx code → injected, which
isolates the cost of copying while the model's knowledge of the graph is held constant.

---

## 3. The modules, one by one

```
src/gsi/
  data/        base.py, graphqa.py, erdos.py
  serial/      variant.py (four axes, single-axis guard), render.py (10 renderers), parse.py (tests),
               canonical.py (canonical labeling, used by the E3 mitigation)
  prompts/     modes.py (3 modes, the template, the library arms), solutions.py (stub only)
  llm/         client.py (OpenAI-compatible, cache, retry), stub.py
  exec/        sandbox.py (host), runner.py (guest)
  score/       parse_answer.py, compare.py, classify.py
  experiment/  config.py, run.py
  analysis/    tables.py, figures.py
tests/         179 tests
configs/       models.yaml, smoke.yaml, pilot.yaml, graphqa.yaml, erdos.yaml, erdos_m3fix.yaml
scripts/       run.py, analyze.py, run_model.sh (the pipeline); one script per follow-up
               experiment (see ANALYSIS.md §8); verify.py (reproduce the tables without inference)
```

### 3.1 `data/`
* **`graphqa.py`** — regenerates GraphQA-style graphs (six families, 5–20 nodes) and ten tasks with
  networkx ground truth. Canonical text is Fatemi's "adjacency" encoder (an edge list in words),
  the best-performing encoding under code generation per CodeGraph; question wording for the six
  shared tasks follows CodeGraph's templates.
* **`erdos.py`** — loads the HuggingFace test split, keeps the 24 unambiguous tasks, parses edges
  from the prompt text (the `edges` column drops capacities for `maximum_flow`), and splits each
  prompt into preamble / question / format sentence. The canonical rendering reproduces the native
  prompt byte-for-byte on all 2,400 rows.

### 3.2 `serial/`
* **`variant.py`** — a serialization is `(label_map, order, structure, syntax)`. `relabel` renames
  then sorts (Herbst); each relabeling is checked against a sorted identity reference that is
  emitted as `relabel:identity`. `order` is compared as a rule when one is named, as positions
  otherwise. No-op variants are dropped. `sort: false` gives the position-preserving ablation.
* **`render.py`** — one renderer per (syntax, structure): plain, json, networkx_code, graphqa_nl,
  erdos_nl × edge_list, adj_list.

### 3.3 `prompts/`
* **`modes.py`** — the three modes, the shared code template, the two library sentences, and the
  wording copied from the papers: CodeGraph's Table 6 role and instruction for code modes; G1's
  `\boxed{}` suffix for direct mode; Erdős-style format sentences. `MODES` is the registry;
  `build_prompt(mode, inst, variant, library)` is the single entry point. A mitigation mode is one
  builder plus one entry.
* **`solutions.py`** — reference solution expressions per task, used **only** by the stub so it can
  emit a program that really computes the right answer. Models are never shown a solution. This is
  what survived of the deleted `exemplars.py`.

### 3.4 `llm/`
* **`client.py`** — `ModelSpec` + `LLMClient.complete()`: cache lookup by prompt hash → API call at
  temperature 0 → retry with backoff → atomic cache write. Identical prompts in flight are
  serialized so they are billed once. `extract_code()` takes the text between `# CODE START` and
  `# CODE END`, case-insensitively, and nothing else.
* **`stub.py`** — canned programs and boxed answers with deterministic failure behaviours.

### 3.5 `exec/`
* **`sandbox.py`** — subprocess, timeout, process-group kill, graph matching, per-key in-flight lock
  and atomic cache writes (identical executions run once).
* **`runner.py`** — rlimits, the networkx hook, `nodes`/`edges` injection for inject modes, `exec`,
  then `ans` from the namespace and the declared `nodes`/`edges` **even on a crash**; sidecar always
  written. `sandbox.py` adds the static checks (`ans_is_literal`, `reads_graph_vars`) and the two
  comparisons (`declared_ok`, `construction_ok`).

### 3.6 `score/`
* **`parse_answer.py`** — `find_boxed_answer` (last `\boxed{}`, else G1's "the answer is" regex) and
  `parse_value` per type.
* **`compare.py` / `classify.py`** — label remapping, type-aware comparison, the decision tree.

### 3.7 `experiment/` and `analysis/`
* `run.py` — stages `data, variants, llm, exec, score`, all resumable; `--estimate` for cost.
* `run.py` — `cfg.arms_for(mode, task)` expands `modes × libraries` into the (mode, library) pairs to
  run; `library` is `None` for `direct`.
* `tables.py` — `accuracy`, `invariance` (relabel grouped against the identity reference), `ladder`,
  `failures`, `gap` (M2 − M3 **within** a library arm), `silent_transcription`. All key on
  `[dataset, task, mode, library, axis, model]`, and every cell reports `n_calls` beside `n`, because
  the response cache can back a hundred rows with a single reply. `figures.py` draws each.

---

## 4. How to run

```bash
pip install -e ".[erdos,dev]"               # inside a virtual environment
cp .env.example .env                        # fill HF_TOKEN for the models that were run

pytest -q
python scripts/verify.py                                               # everything below, checked
python scripts/run.py --config configs/smoke.yaml                      # stub, a few minutes
python scripts/run.py --config configs/smoke.yaml --models hf-qwen3-8b-nscale --limit 30
python scripts/analyze.py --config configs/smoke.yaml
```

`--estimate` reports the call count of a config without calling a model, but it rebuilds
`data/processed/<config>/instances.jsonl` (for Erdős, from the Hugging Face dataset), so run it on a
scratch copy if the committed instances must stay untouched.

Config keys (`configs/erdos.yaml` is the reference):

```yaml
datasets:
  erdos:
    tasks: [...]
    n_per_task: 100
    max_prompt_chars: 6000
    variants:
      relabel:   {seeds: 3}            # sort: false -> positional ablation
      order:     {kinds: [sorted_st, s_sorted_t_shuffled, shuffle_all], seeds: 1}
      structure: {toggle: true, replicated: true}
      syntax:    {kinds: [json, networkx_code]}   # the ladder rungs
modes: [direct, code, graph_as_code]
libraries: [networkx, native]                     # crossed with the code modes -> 5 calls per variant
# library_tasks: {native: [degree, edge_number]}  # optional: restrict an arm to some tasks
models: [hf-qwen3-8b-nscale, hf-deepseek-v3.1-novita, hf-gemma-4-31b, hf-deepseek-v4-flash]
exec: {timeout: 20, mem_mb: 1024, workers: 4}
```

---

## 5. Design decisions you should know about

1. **M2 is CodeGraph, plus a fixed template.** Role text, instruction, `Q:/A:` layout, markers and
   the `ans` variable are CodeGraph's. The template is ours, and it is what makes transcription
   observable without assuming the model used networkx.
2. **M3 is M2 with `nodes`/`edges` pre-filled.** Same prompt, same template, same contract. The only
   difference is who writes those two lines. Single-turn — an adaptation of Finkelshtein's
   multi-turn mode, not a reproduction.
3. **`library` is a field, not a mode.** `networkx` vs `native` is crossed with the two code modes
   and stored as its own column on every record. Folding it into the mode name would force every
   `mode in CODE_MODES` test to enumerate a cross product, and every analysis to recover two
   dimensions by parsing a string. It also has to be in the record id, or the two arms of one
   variant would collide in the JSONL sink.
4. **One-shot was removed, not disabled.** `code_1shot`, `graph_as_code` (the exemplar variants) and
   `exemplars.py` are deleted. The template does what the worked example did — it fixes the
   program's shape — and does it identically in both library arms, which an exemplar could not.
   They were removed before the reported runs.
5. **Contracts are copied from the source pipelines, with their fallbacks and no others.** M1: last
   `\boxed{}`, else "the answer is" (G1). Code modes: `ans` only (CodeGraph). Printed output is never
   read. Invariance is compared within a mode and within a library arm, so per-mode contracts cannot
   bias it.
6. **Relabel then sort**, compared against a sorted identity reference (Herbst footnote 3). The
   position-preserving version is an ablation.
7. **GraphQA starts from the edge-list text** (Fatemi's "adjacency"), the best code-mode encoding in
   CodeGraph; the adjacency-list "incident" form is the `structure` variant.
8. **All scoring happens in canonical label space**; paths are accepted on validity and equal
   length/weight; `format` means "no parsable answer" in every mode.
9. **The M1 system prompt is ours, not G1's.** G1 sets none at all. We use a neutral
   `"You are a helpful assistant."` so that M1 and the code modes both have one. The asymmetry with
   the code modes' expert role is deliberate — each mode keeps its source paper's framing — and is
   worth a sentence in the write-up.
