# Repository knowledge base

Design and architecture notes for the serialization-invariance audit. These documents record
**why** the system is built the way it is — the reasoning that will not be recoverable by reading
the source in three months.

For a plain-language tour of the code, start with [code-tour.md](code-tour.md).

## Read in this order

| # | Document | What it covers |
|---|---|---|
| 1 | [research-context.md](research-context.md) | The four papers, the gap we fill, and how each design choice traces back to a claim in the literature |
| 2 | [architecture-overview.md](architecture-overview.md) | The system end to end: module map, data flow, the three modes, the central invariants |
| 3 | [datasets.md](datasets.md) | GraphQA and Erdős loaders, the `GraphInstance` schema, which tasks are included and why others are not |
| 4 | [permutation-design.md](permutation-design.md) | How equivalent serializations are constructed and how "exactly one axis changed" is enforced |
| 5 | [modes-and-prompts.md](modes-and-prompts.md) | The three interaction modes, the fixed code template, the library axis, and the answer contracts |
| 6 | [execution-sandbox.md](execution-sandbox.md) | Running model code safely and recovering the graph it actually built |
| 7 | [scoring-and-classification.md](scoring-and-classification.md) | Answer parsing, type-aware comparison, and the nine-class failure taxonomy |
| 8 | [analysis-and-metrics.md](analysis-and-metrics.md) | Metric definitions, why invariance is per-instance, the tables and figures |
| 9 | [pipeline-and-caching.md](pipeline-and-caching.md) | Stages, configuration, caching, resumability, cost control |
| 10 | [testing.md](testing.md) | What the test suite actually proves, and what it cannot |

Decisions taken with the team, and why: [design-choices.md](design-choices.md).

## Result reports

The main results and the follow-up experiments are in [`../ANALYSIS.md`](../ANALYSIS.md). These
reports go deeper on single questions; their numbers trace to committed tables under `results/`.

| Document | What it covers |
|---|---|
| [results-walkthrough.md](results-walkthrough.md) | How to read the results: accuracy and consistency together, worked examples, tracing a number to its records |
| [error-findings.md](error-findings.md) | Copying-error profiles per model, read from the saved declarations |
| [erdos-m3-graph-type-rerun.md](erdos-m3-graph-type-rerun.md) | The Erdős M3 control rerun with the graph type stated, and what it changed |
| [graph-type-omission-ablation.md](graph-type-omission-ablation.md) | What a model assumes when the prompt omits the graph type |
| [four-model-detection.md](four-model-detection.md) | Permutation-disagreement detection and voting on all four models |
| [duplicate-edge-hint.md](duplicate-edge-hint.md) | A one-sentence prompt hint against duplicate-edge counting, on two models (archived result) |

## The one-paragraph summary

A graph can be written as text in many equivalent ways. We ask whether an LLM that solves graph
problems **by writing code** returns the same answer under equivalent serializations, and if not,
whether the fragility enters when the model **transcribes** the text into a graph object or when it
writes the **solution logic**. We answer this by perturbing one serialization axis at a time
(`relabel`, `order`, `structure`, `syntax`), running three interaction modes on every variant —
the two code modes crossed with two solving libraries — and recovering both the graph each program
*declared* and the graph it *built*, so failures can be attributed to transcription, construction or
logic rather than merely counted.

## Conventions used across these documents

* **Canonical** — the fixed experimental reference, not an isomorphism-invariant canonicalization. Every variant is derived from it.
* **Axis** — one independent dimension of a serialization. Exactly one changes per variant.
* **Instance** — one graph paired with one task and one query, plus its ground truth.
* **Variant** — one serialization of one instance.
* **Record** — one (instance, variant, mode, library, model) result row.
* **M1 / M2 / M3** — the modes `direct`, `code`, `graph_as_code`.
* **Arm** — a (mode, library) pair, e.g. `code/networkx`. Five run per variant.
* **Library** — the solving toolkit, `networkx` or `native`; a field on every record,
  crossed with the two code modes, never part of the mode name.

## Serialization

M1 and M2 always receive the **same** graph text for a given variant; only their solving
instructions differ. M3 receives no text at all. The reference is the **edge-list "adjacency"
wording** for both datasets — decided 2026-09-16, with the reasoning and the rejected alternative in
[datasets.md](datasets.md#4-the-reference-encoding).

All modes are zero-shot: the one-shot worked-example modes were removed, and the fixed code
template took over the job of pinning the program's shape.

## Status

The full experiment ran on four models (Qwen3-8B, DeepSeek-V3.1, Gemma 4 31B, DeepSeek-V4-Flash)
over both datasets, every axis and every arm; results are in [`../ANALYSIS.md`](../ANALYSIS.md).
Generated programs ran in local subprocesses, not in the Docker containers described in
[execution-sandbox.md](execution-sandbox.md#execution-environment). `python scripts/verify.py`
reruns the tests, the pipeline on the stub model, and the analysis from the published records.
