# Scoring and failure classification

Turning a model's reply into `correct: true/false` plus a failure class. Source:
[`src/gsi/score/`](../src/gsi/score/).

---

## 1. The chain

```
M1: raw reply ──── find_boxed_answer()   last \boxed{…}; else G1's "the [final] answer is" regex
M2/M3: program ─── run it, read `ans`    CodeGraph's contract; no markers or no `ans` -> no answer
   ▼
answer text
   │  parse_value(text, answer_type)      → typed value, or None
   ▼
parsed  (in VARIANT labels)
   │  relabel_answer(..., v.inverse_label_map)
   ▼
parsed_canonical  (in CANONICAL labels)
   │  compare(pred, ground_truth, answer_type, G=...)
   ▼
correct: bool
   │  classify(mode, correct, parsed, exec_result)
   ▼
failure_class
```

Two invariants hold throughout: **comparison always happens in canonical label space**, and
`parsed is None` always means "could not read an answer", never "the model said nothing useful".

## 2. Extraction follows the source pipelines, with no extra leniency

**M1.** `find_boxed_answer` takes the **last** `\boxed{…}` (brace-matched, `\text{}` and `$`
stripped), exactly as G1's `correctness_check.py` does. Its only fallback is G1's own: the text
after *"the [final] answer is"*. Last, not first, because models restate the format before answering.

**M2 / M3.** The answer is the variable `ans` after execution. There is no fallback — CodeGraph's
`exec_py` has none: no `# CODE START`/`# CODE END` markers means no code, no `ans` means no answer,
and printed output is never read. A crash discards `ans`.

Why this cannot bias the study: each contract is applied **identically across every variant and
model within a mode**, and invariance is a comparison between variants of the same instance under
the same mode. Contracts differ *across* modes, which affects only absolute accuracy levels — and
those are now directly comparable to the papers whose contracts they copy.

`parse_value` is tolerant in the same controlled way — `"no, there is none"` → `False`,
`"degree 3"` → `3`, `"nodes 1 and 3"` → `[1, 3]`, `"[]"`/`"none"`/`"empty"` → `[]` — but returns
`None` rather than guessing when the text does not contain the right shape (`"maybe"` for a bool,
`"4.5"` for an int).

## 3. Label remapping

`relabel_answer` maps node labels inside an answer through a mapping, recursing into the structure
per type: `node` is a scalar, `node_set`/`path` are lists, `edge_set` is a list of pairs.
Non-node types (`int`, `float`, `bool`) pass through untouched — a *degree* of 3 must not be
"relabelled" to 7.

This is what makes relabeling variants scorable at all. Under `{0→2, 1→4, …}` the model is asked
about node 2 and answers about node 2; the inverse map turns that back into the canonical node 0
before comparison. Round-tripping is unit-tested for every node-valued type.

## 4. Comparison, per type

| Type | Rule |
|---|---|
| `bool`, `int`, `node` | exact equality |
| `float` | `abs(a−b) ≤ max(1e-2, 1e-2·abs(gt))` — absolute floor plus relative tolerance |
| `node_set` | set equality; order irrelevant |
| `edge_set` | normalized: pairs sorted when undirected, deduplicated |
| `path` | **validity-based**, see below |

The float tolerance needs both terms: purely relative would be unusably strict near zero (common for
`clustering_coefficient` and `jaccard_coefficient`), purely absolute would be too loose for large
`wiener_index`-style values.

**Paths are checked for validity, not identity.** A graph often has several shortest paths of equal
length. Requiring one specific reference would mark correct answers wrong — and, worse, would make
a model look non-invariant when it merely picked a different valid path under a relabeling. So a
path is accepted when it has the same endpoints, every consecutive pair is a real edge, and it has
the same length — or, for weighted graphs, the same **total weight** (`nx.path_weight`), since hop
count is the wrong criterion when edges carry weights.

This is the template for admitting the currently-excluded ambiguous Erdős tasks: replace equality
with a validity checker. Note it is only half the work — see §6.

## 5. Adding an answer type

Three places, all small: `FORMAT_HINT` and `ANS_HINT` in
[`modes.py`](../src/gsi/prompts/modes.py), a branch in `parse_value`, and branches in
`normalize_answer` and `compare`. Then a parametrized case in
[`tests/test_compare.py`](../tests/test_compare.py).

## 6. `normalize_answer` — the invariance key

Distinct from `compare`. It produces a **hashable canonical form** used to ask "were these two
answers the same?", independent of whether either is correct:

* `node_set` → sorted tuple, so `[3, 1]` and `[1, 3]` count as the same answer
* `edge_set` → sorted deduplicated pairs, undirected pairs ordered
* `float` → rounded to 4 dp, so float noise is not read as an answer change
* `path` → tuple in path order, **not** sorted — order is meaningful here

The analysis stores this as `answer_key` and counts distinct keys per instance.

**This is where admitting ambiguous tasks gets subtle.** Two equally valid topological sorts produce
different keys and would register as non-invariant. Fixing `compare` alone would make accuracy right
while leaving the headline invariance metric wrong. Both `compare` **and** `normalize_answer` need a
task-appropriate notion of equivalence.

## 7. The failure taxonomy

Nine classes: `ok`, `wrong`, `execution`, `format`, `transcription`, `construction`, `logic`,
`no_computation`, `unverifiable`.

The template ([modes-and-prompts.md](modes-and-prompts.md) §3) makes a code-mode program's work
visible in three stages, so a wrong answer can be charged to one of them rather than lumped into
"wrong":

```
truth ──[1]──▶ declared nodes/edges ──[2]──▶ the graph the code used ──[3]──▶ ans

 [1] transcription   the model copied the graph wrong
 [2] construction    it declared the graph correctly, then built something else from it
 [3] logic           it had the right graph and still got the answer wrong
```

`no_computation` sits outside the chain: the program wrote `ans` as a literal, so it never entered
the chain at all.

```
M1 direct:
    correct                              → ok
    parsed is None                       → format
    otherwise                            → wrong

M2 / M3 (code modes):
    timed out or exit_code != 0          → execution
    no code between the markers          → format
    no `ans`, or it does not parse       → format
    `ans` is a literal                   → no_computation   ← checked BEFORE correctness
    correct                              → ok
    declared graph != truth              → transcription    (construction, in an inject mode)
    graph used != declared graph         → construction
    template slots unreadable:
        recovered networkx graph != truth  → transcription  ← fallback via the nx hook
        no networkx graph either           → unverifiable
    otherwise                            → logic
```

### Why the order is what it is

**`execution` before `format`** — a crashed program has no meaningful output; calling it a format
failure would hide the real cause.

**`no_computation` before `correct`** — a program that writes `ans = 3` has not solved anything. If
3 happens to be right, counting it `ok` would let a model score on M2 without ever writing graph
code, inflating exactly the number this project measures. This is the failure the template invites
and must therefore detect: see [execution-sandbox.md](execution-sandbox.md) §4 for how a literal is
told apart from an accumulator (`ans = 0` followed by `ans += 1` is not a literal).

**`correct` before the transcription check** — a program can build the wrong graph and still return
the right answer (dropping an edge irrelevant to the query). Such a case is `ok`, because the
*answer* was right. But it is not discarded: the `silent_transcription` table reports precisely
these — how often a wrong graph went unpunished. That rate matters, because it measures how much
transcription damage the task simply fails to expose. In the full runs it is large: of Qwen3-8B's
wrong-declaration records, 148 of 242 on GraphQA and 252 of 495 on Erdős still answer correctly
([ANALYSIS.md](../ANALYSIS.md) §4).

**A bad declaration means `construction` in an inject mode** — M3's `nodes`/`edges` are supplied by
the harness, so a mismatch means the model *overwrote correct data*. That is construction, not
transcription; transcription is unreachable for M3 by construction, and the classifier makes that
structural rather than hoping.

**`construction` is networkx-only.** It needs a graph object to compare the declared data against.
The native arm has none, so its construction errors land in `logic`. **Never pool the failure
decomposition across `library`** — the `logic` column means different things in the two arms. The
tables keep `library` in the grouping key for this reason.

**`unverifiable` is separate from `logic`** — merging them would silently inflate the logic share
for programs that ignore the template *and* avoid networkx. It is reported as its own rate so the
reader can judge how much of the decomposition is observed rather than assumed. It is now rare:
the template gives a second, library-independent way to verify transcription, so `unverifiable`
requires the model to ignore the slots *and* build no graph.

## 8. `ScoredRecord`

One row per `(instance, variant, mode, library, model)`, carrying the grouping keys (`dataset`,
`task`, `graph_id`, `axis`, `params`, **`library`**), the answer at each stage of the chain
(`answer_line`, `parsed`, `parsed_canonical`, `answer_key`), the verdicts (`correct`,
`failure_class`), and execution diagnostics (`declared_ok`, `construction_ok`, `ans_is_literal`,
`reads_graph_vars`, `graph_match`, `n_graphs`, `timed_out`, `exit_code`, `directedness_mismatch`).

`library` is `null` for `direct`, which writes no code. It is a **field rather than part of the mode
name** so that the arms can be pooled or separated by a groupby instead of by string surgery — see
[modes-and-prompts.md](modes-and-prompts.md) §2.

The row also carries **`prompt_hash`**. Rows sharing one came from a single model call: the response
cache collapses identical prompts, and for M3 on a task whose question names no node that is every
graph and every variant at once. The tables report `n_calls` beside `n` so a cell backed by one
reply cannot be read as a hundred trials.

Keeping every intermediate stage — not just the verdict — is deliberate: when a number looks wrong,
the row itself shows whether the model, the parser, the remapper or the comparator caused it,
without re-running anything.
