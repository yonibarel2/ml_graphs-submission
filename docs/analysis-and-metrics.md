# Metrics and analysis

What we measure, why it is defined that way, and how to read the output. Source:
[`src/gsi/analysis/`](../src/gsi/analysis/).

### Generating tables without overwriting another model

`python scripts/analyze.py --config configs/graphqa.yaml --models <model>` writes
CSVs to `results/graphqa/tables/<model>/`. Selecting multiple models creates a separate
folder for each. This is also the layout produced by `scripts/run_model.sh`.

Omit `--models` to analyze all available scored files and write combined CSVs to
`results/graphqa/tables/`. Filtered runs leave these combined tables untouched; rerun
the unfiltered command to refresh them after more models finish. Figures remain in
`results/graphqa/figs/`, with model names in their filenames. The same layout applies
to Erdős and other experiment configs.

---

## 1. Accuracy — context, not the answer

```
groupby(dataset, task, mode, library, axis, model) → mean(correct), n, n_calls
```

Reported to place our numbers in context. One caveat keeps it from being a matched replication:
CodeGraph's per-encoder results use a one-shot code demonstration and our M2 supplies none — the
template pins the program's shape instead. Treat it as contextual evidence, not a reproduction.

But accuracy **cannot answer the research question**, and this is the point of the whole project.
Consider a model evaluated under two encodings:

| Graph | Encoding A | Encoding B |
|---|---|---|
| G1 | correct | wrong |
| G2 | wrong | correct |

Accuracy is 50% under both. The encodings look equally good. Yet the model's answer flipped on
**every single graph** — it is maximally unstable. Averaging over graphs before comparing encodings
destroys the signal. That is precisely the weakness in prior work
([research-context.md](research-context.md) §2.1), and it forces the next metric.

## 2. `library` is a grouping key, not a mode

Every table keys on `KEYS = [dataset, task, mode, library, axis, model]`. `library` is `-` for
`direct`, which writes no code.

Keeping it as its own column rather than folding it into the mode name is what makes the arms both
separable and poolable: include it in a `groupby` and `code/networkx` and `code/native` are distinct
rows; leave it out and they pool. Neither requires parsing a string, and `mode in CODE_MODES` stays
a two-element test.

**One place pooling is forbidden.** The failure decomposition must never be pooled across `library`:
`construction` is separable only in the networkx arm, so the native arm's `logic` column absorbs
failures the networkx arm reports separately. The two columns do not mean the same thing. See
[scoring-and-classification.md](scoring-and-classification.md) §7.

Figures join the two into one tick label (`code/networkx`) for readability; the data never does.

## 3. Invariance — the headline result

For each axis, group the canonical record with that axis's variants **for the same instance**, then:

```
identical  =  (nunique(answer_key) == 1) AND (every answer parsed)
spread     =  (max − min) / task answer range        [numeric types only]
```

and aggregate:

```
frac_identical    fraction of instances answered identically
mean_spread       mean normalized spread
frac_all_correct  fraction correct on every variant (for reference)
```

Three definitional choices worth understanding:

**"Same", not "correct".** A model answering 7 every time scores `frac_identical = 1.0` even when
the truth is 4. This deliberately separates *consistency* from *accuracy*: a system whose answer
flips under an arbitrary relabeling is unsafe regardless of its average score. `frac_all_correct` is
reported alongside so the two are never conflated.

**An unparsable answer counts as different.** `all_parsed` is required for `identical`. A model that
answers on one variant and rambles on another is not invariant, and treating a missing answer as a
"match" would reward failure.

**Grouping includes the reference form.** Each variant is compared against the reference point, not
just against its siblings — that is what makes the number "invariant to *this perturbation*" rather
than "self-consistent among perturbed forms". For `relabel` the reference is the sorted identity
relabeling (`relabel:identity`, a member of the axis), following Herbst; for every other axis it is
canonical. See [permutation-design.md](permutation-design.md) §4.1.

The comparison uses `answer_key` (from `normalize_answer`), so `[3, 1]` and `[1, 3]` are the same
answer for a node set but `[1, 2, 3]` and `[3, 2, 1]` differ for a path, where order is meaningful.
See [scoring-and-classification.md](scoring-and-classification.md) §6.

`mean_spread` complements the binary check for numeric answers: answering 4 then 5 is a near-miss,
answering 4 then 40 is not, and `frac_identical` cannot tell them apart. Normalizing by the task's
observed answer range makes tasks with different scales comparable, with a floor of 1.0 so a
constant-answer task cannot divide by zero.

## 4. The gap — the localization result

```
gap  =  frac_identical(code) − frac_identical(graph_as_code)      within one library arm
```

per `(dataset, task, axis, library, model)`. The pivot is taken **inside** `library`, so the two
modes being differenced differ in transcription alone — which is the entire point of M3 being a
minimal pair of M2. Differencing across arms would mix the transcription effect with a library
effect and mean nothing.

* **Negative** → M2 less consistent than M3 → fragility enters at **transcription**.
* **≈ Zero** → transcription is not the problem; instability is in the **solution logic**.

**Only interpretable on `relabel` and `order`.** On `syntax` and `structure`, M3 is invariant by
construction (no text reaches it), so a gap there is an artifact, not a finding. See
[modes-and-prompts.md](modes-and-prompts.md) §4.

## 5. The transcription ladder — the cleaner localization result

```
rung 1 prose  →  rung 2 json  →  rung 3 networkx code  →  rung 4 injected (M3)
```

For each rung, per `(dataset, mode, model)`: accuracy and the share of records in each failure class.
Rungs 1–3 are the M2 `syntax` variants at canonical labels and order, so consecutive rungs differ in
the graph text alone while the model's knowledge of the graph is held constant; rung 4 removes the
text. Reading the `transcription` share down the ladder isolates the cost of copying **without the
"can see the graph / cannot" confound** that the plain M2−M3 gap carries. This is the table to lead
with for localization; the gap becomes a consistency check.

## 6. Failure decomposition — the mechanism

Among code-mode records that are **not** `ok`, the share of each of the nine failure classes per
`(dataset, mode, library, axis, model)`, with `n_failures` as the denominator so small cells are
visible.

Read alongside the gap: the gap says *how much* the transcription step costs, the decomposition says
*what goes wrong*, now split three ways —

```
transcription   the graph was copied wrong
construction    copied right, built wrong        (networkx arm only)
logic           right graph, wrong answer
```

Structural expectations that double as harness checks:

* `graph_as_code` rows must contain **no** `transcription` — unreachable there by design.
* `code/native` rows must contain **no** `construction` — not separable without a graph object.
* A non-trivial `no_computation` rate means the model is answering in its head and typing the
  number into the template. That is a compliance problem with the prompt, not a reasoning result,
  and it invalidates the affected cells rather than lowering them.
* A high `unverifiable` rate should now be rare, since the template verifies transcription without
  networkx. If it is not rare, the models are ignoring the template and the template needs
  rewording before any of these numbers are worth reading.

## 7. Silent transcription

```
groupby(dataset, mode, library, axis, model, correct) → rate(wrong graph)
```

using `declared_ok`, falling back to `graph_match` for programs that ignored the template.
How often a program worked from the **wrong graph** — split by whether the answer was still right.

The `correct=True` rows are the interesting ones: the model mistranscribed and got away with it,
because the corrupted part of the graph did not affect the query. This measures how much
transcription damage the task simply fails to expose — a caveat on any claim that transcription is
reliable, and a reason to prefer tasks that read more of the graph.

## 8. `n` versus `n_calls` — read this before quoting any number

Every accuracy and invariance cell carries both:

* **`n`** — scored records.
* **`n_calls`** — the distinct model responses behind them.

They diverge wherever the response cache collapsed prompts, and for one case the divergence is
extreme. **M3's prompt contains no graph text.** For a task whose question also names no node —
`cycle_check`, `node_count`, `edge_count`, `has_cycle`, `is_bipartite`, `density`, `diameter` — the
M3 prompt is byte-identical for *every graph and every variant in the dataset*. One reply is then
executed against a hundred different injected graphs.

In the smoke run this shows up plainly:

```
task         mode           library   axis      accuracy   n  n_calls
cycle_check  graph_as_code  networkx  relabel       0.00  20        1
node_degree  graph_as_code  networkx  relabel       0.85  20       11
```

That is the cache working exactly as designed, and it is why M3 costs almost nothing. But it means:

* M3's `frac_identical` on such a task is **1.0 by construction**, not by measurement — the model
  was never re-asked, so it could not have answered differently.
* M3's accuracy there rests on a **single** model decision, however large `n` is.
* The M2−M3 gap on those tasks therefore equals M2's own fragility, and adds no information.

None of this is a defect to fix — M3 is the control, and a control that cannot vary is a good
control. It is a reporting hazard, which is why `n_calls` is in the table rather than in a footnote.

## 9. Figures

| Figure | Shows |
|---|---|
| `accuracy_<dataset>_<model>.png` | heatmap, rows `task / arm`, columns axes |
| `invariance_<dataset>_<model>.png` | grouped bars, `frac_identical` by axis and arm — **the main result** |
| `ladder_<dataset>_<model>.png` | stacked failure shares per rung with accuracy overlaid — **the localization result** |
| `gap_..._<dataset>_<model>.png` | bars per `task × library`, coloured by axis — the M2−M3 consistency check |
| `failures_<dataset>_<model>.png` | stacked bars of failure-class shares, per arm |

An *arm* is a `(mode, library)` pair, shown as `code/networkx`. Ordering is fixed (`canonical,
relabel, order, structure, syntax`; `direct, code, graph_as_code`; and the class order
`transcription, construction, logic, no_computation, execution, format, unverifiable`) so figures
are comparable across models and datasets at a glance.

## 10. Reading the smoke-run figures

A smoke run (`configs/smoke.yaml`, stub model) writes **stub output** to `results/smoke/`, which is
not tracked. The numbers are artifacts of the stub's
hardcoded behaviour mix (45% correct, 12% wrong logic, 10% dropped edge, 6% bad construction, …) and
mean nothing about any model. They exist to prove the analysis code runs end to end. Every stub gap
bar is negative only because the stub injects `drop_edge` into M2 alone.

What the stub run *does* establish: all nine failure classes are reachable, both library arms
produce runnable programs, and `n_calls` correctly exposes the M3 collapse.

## 11. Uncertainty, noise, and what the tables do not provide

**Confidence intervals are computed outside the tables.** The tables in this module are point
estimates. With 100 graphs per task, a `frac_identical` of 0.85 has meaningful uncertainty, so the
reported comparisons use paired bootstrap intervals over graphs from `scripts/audit_results.py`
(`results/review/paired_intervals.csv`, [ANALYSIS.md](../ANALYSIS.md) §2) and the follow-up
scripts.

**The nondeterminism floor.** A provider-hosted model at temperature 0 is not guaranteed
deterministic, so some measured non-invariance is sampling noise, not serialization sensitivity.
`scripts/nondeterminism_floor.py` re-asks the reference prompts with this metric's own definitions
and reports the permutation flip rate next to the floor ([ANALYSIS.md](../ANALYSIS.md) §8.0).
M3's variance under `order` is a partial read on the same quantity.

**No graph-size breakdown.** `meta.n` (graph size) is stored on every instance, but the tables are
not sliced by size.

**No pairwise-agreement metric.** `frac_identical` requires *all* variants of an axis to agree, so an
axis with five variants is held to a stricter standard than one with two. Comparisons across axes
with different variant counts are therefore descriptive only.
