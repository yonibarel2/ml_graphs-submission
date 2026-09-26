# Research context: the gap, and how the design answers it

This document connects the implementation to the literature. Every non-obvious engineering choice
in this repository exists to answer a specific weakness in prior work; this is the record of which
choice answers which weakness.

---

## 1. The four papers

| Key | Paper | What it established | What it left open |
|---|---|---|---|
| `fatemi` | Talk like a Graph (ICLR 2024) | Encoding performance depends on task and prompting method; Incident has the highest mean accuracy across the six basic tasks under all five prompting methods in Table 7 | Only direct prompting; no code execution |
| `herbst` | Lost in Serialization (AAAI GCLR 2026) | Decomposes serialization into node labeling / edge encoding / syntax; >1.5M inferences showing reindexing, edge reordering and format changes alter outputs | Only direct answering. NetworkX/PyG code appears as *text the model reads*, never as a program that runs |
| `finkelshtein` | Actions Speak Louder than Prompts (ICLR 2026) | Across 14 datasets, **code generation is the strongest interaction mode** | Always evaluated under **one fixed serialization**; robustness never tested |
| `cai` | CodeGraph (2024) | Runs LLM-written code under several GraphQA encoders; reports a narrower accuracy spread under code than under CoT | Three specific limitations, below |

## 2. The gap, stated precisely

Two literatures do not meet:

* Herbst asks *"is it invariant?"* — but only of **direct answering**.
* Finkelshtein establishes *"code is strongest"* — but only under **one serialization**.

Nobody has asked whether the field's recommended best practice survives re-serializing the graph.

CodeGraph is the sole work that runs generated code under more than one encoding, and it leaves the
question open for three reasons. Each maps directly onto a component of this implementation:

### 2.1 It is aggregate

CodeGraph reports **average accuracy per encoder**. Two encoders can post identical averages while
the model's answer flips on every individual graph — right on graph A and wrong on B under one
encoding, the reverse under another. Averaging first destroys exactly the signal we want.

> **Design response:** invariance is computed **per instance and only then aggregated**. See
> [analysis-and-metrics.md](analysis-and-metrics.md) §2. The `frac_identical` metric groups by
> `(instance, mode, model, axis)` and asks whether the answers were all identical, before any mean
> is taken.

### 2.2 The perturbation is uncontrolled

GraphQA's encoders change node labels, phrasing and syntax simultaneously, and never vary edge
order. An observed drop cannot be attributed to any single cause.

> **Design response:** a serialization is a structured 4-field object, and every variant changes
> **exactly one field**, enforced by a runtime assertion rather than by convention. See
> [permutation-design.md](permutation-design.md) §3.

### 2.3 It is undiagnosed

When code mode fails, nothing distinguishes a mistranscribed graph from wrong solution logic from a
crash.

> **Design response, in three parts.** First, a fixed template makes the graph the program
> *declared* readable, so transcription is checked directly and without assuming the model used
> networkx ([modes-and-prompts.md](modes-and-prompts.md) §3). Second, the sandbox also recovers
> the graph the program actually *built*, which separates a bad copy from a bad construction
> ([execution-sandbox.md](execution-sandbox.md) §3). Third, the **M3 `graph_as_code` control**
> removes the transcription step entirely, so the M2−M3 difference isolates its cost
> ([modes-and-prompts.md](modes-and-prompts.md) §4). Together these turn "wrong" into one of
> `transcription`, `construction` or `logic`.

## 3. Serialization

M1 and M2 receive the **same** graph text for each variant: the edge-list "adjacency" wording, for
both datasets. The evidence does cut both ways — Fatemi's Table 7 favours incident on mean accuracy
across prompting methods, while CodeGraph's Table 1 favours adjacency specifically under code
generation, where incident collapses on edge count. We follow the code-mode evidence because this is
a code-mode audit, and because for Erdős the edge list is the native prompt and therefore Herbst's
baseline. See [datasets.md](datasets.md#4-the-reference-encoding), which also records the
incident alternative and why it was rejected.

## 4. Why the perturbation axes are Herbst's

The proposal frames the contribution as *composing two lines of work*: applying Herbst's controlled
single-axis perturbations to Finkelshtein's executed-code modes. Reusing Herbst's decomposition is
what makes that composition meaningful rather than a fresh, incomparable study.

Herbst's direct-mode results provide context, but our models and prompts differ from theirs. A discrepancy alone does not establish a harness bug or a failed replication.

We split their "edge encoding" into `order` and `structure` because it bundles two independently
variable things. See [permutation-design.md](permutation-design.md) §2.

## 5. What we claim, and what we do not

**We can claim:**
* whether executed code returns identical answers under single-axis equivalent serializations,
  measured per instance;
* when it does not, the distribution of failures over transcription / construction / logic /
  execution / format;
* how much of the fragility the transcription step accounts for (the M2−M3 gap, taken inside one
  library arm);
* whether any of it is specific to `networkx` rather than to code generation in general (the
  library axis).

**We cannot claim, with the current design:**
* that `construction` and `logic` are separable in the **native** arm — there is no graph object to
  recover there, so construction errors are reported as logic. The two arms' decompositions are
  never pooled for this reason;
* anything about M3's *consistency* on tasks whose question names no node. M3's prompt is then
  identical across every instance and every variant, so one reply serves all of them and its
  invariance is 1.0 by construction. `n_calls` in every table is what keeps this honest;
* that any fragility generalizes beyond the tasks and graph sizes sampled (GraphQA graphs are
  5–20 nodes, the Erdős sample 4–34; both are small);
* that a *provider-hosted* model's answer changes are caused by our perturbation rather than by
  sampling nondeterminism — temperature 0 is not a determinism guarantee over an API. The
  repeated-prompt floor ([ANALYSIS.md](../ANALYSIS.md) §8.0) is reported next to the permutation
  flip rate, but subtracting one from the other is not a causal estimate (§5 there);
* that the relabeling effect is purely about label identity rather than partly about presentation
  tidiness — the position-preserving ablation that would separate them was not run
  ([permutation-design.md](permutation-design.md) §8).

## 6. The grader's requirement

Course feedback on the proposal added three constraints beyond it, and this is how each was met:

1. **Multiple models and multiple datasets** are required to draw empirical conclusions: two
   datasets (GraphQA, Erdős) and four models.
2. **Ablations where possible:** the `library` arm (networkx vs plain Python), crossed with the code
   modes and run on every instance rather than as a side study; the nondeterminism floor
   ([ANALYSIS.md](../ANALYSIS.md) §8.0); and a one-sentence graph-type ablation
   ([graph-type-omission-ablation.md](graph-type-omission-ablation.md)). Relabel seed count,
   graph-size buckets and the position-preserving relabeling were not varied.
3. **Attempt a mitigation** once the fault is diagnosed: detection, voting, canonical labeling and
   one solver per task, chosen after the failure analysis ([ANALYSIS.md](../ANALYSIS.md) §8).

## References

**Execution environment:** [3]'s Graph-as-Code mode iteratively executes pandas expressions over
a preloaded table and returns outputs to the model; it does not specify Docker
([Appendices E–F](https://arxiv.org/pdf/2509.18487#page=20)). Our M2/M3 programs ran in local
subprocesses; a Docker design is described but was not used. Outside our original references,
[EvalPlus](https://github.com/evalplus/evalplus#-quick-start) provides an explicit Docker execution
workflow. See [execution-sandbox.md](execution-sandbox.md#execution-environment).

Full entries in [`../project proposal/references.bib`](../project%20proposal/references.bib).
