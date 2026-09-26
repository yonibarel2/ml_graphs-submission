# How to review the experiment results

This guide was written on 2026-09-18 for the first two models (DeepSeek-V3.1 and Qwen3-8B),
from Hugging Face revision `ee5b49e8013c1e5eb90bc14c2f7786810af01b77`. The combined CSVs now also
include Gemma 4 31B and DeepSeek-V4-Flash; [ANALYSIS.md](../ANALYSIS.md) reports all four. The
reading method below applies unchanged.

## 1. Understand the experiment before reading the numbers

The question is whether an LLM solving a graph problem gives equivalent answers when
the same graph is written differently, and which parts of its generated program fail.
This is evaluation of existing models, not training.

* **GraphQA:** 100 generated graphs, each with seven tasks: 700 graph–task instances.
* **Erdős:** 100 instances for each of 12 tasks: 1,200 graph–task instances.
* **Models (this guide):** DeepSeek-V3.1 on Novita and Qwen3-8B on Nscale.
* **Total:** 231,710 scored records for these two; cached replies mean these are not independent
  API calls.

| Condition | What the model receives and does |
|---|---|
| `direct` | Reads graph text and answers directly |
| `code/native` | Reads graph text and generates plain Python |
| `code/networkx` | Reads graph text and generates Python with NetworkX allowed |
| `graph_as_code/native` | Generates generic solving code; graph data is supplied at execution |
| `graph_as_code/networkx` | Same injected-data control, with NetworkX allowed |

`relabel` changes node labels; `order` changes edge order. These are the permutation
tests. `structure` changes edge-list/adjacency-list or duplicated-edge presentation;
`syntax` changes prose/plain text/JSON/code wording. These test representation sensitivity.
The graph's meaning is intended to remain unchanged.

For more detail, read [modes and prompts](modes-and-prompts.md) and
[permutation design](permutation-design.md).

## 2. Look at accuracy and consistency together

Start with the [Qwen Erdős invariance plot](../results/erdos/figs/invariance_erdos_hf-qwen3-8b-nscale.png),
then the [DeepSeek Erdős plot](../results/erdos/figs/invariance_erdos_hf-deepseek-v3.1-novita.png).
Focus first on `relabel` and `order`. Higher bars mean more instances produced the
same parsed answer across the tested forms.

Next read the [Erdős accuracy table](../results/erdos/tables/accuracy.csv) and
[GraphQA accuracy table](../results/graphqa/tables/accuracy.csv), filtering by `model`,
`task`, `mode`, and `library`.

Accuracy across all available variant records, recalculated from those tables:

| Dataset / model | Direct | Plain Python | NetworkX |
|---|---:|---:|---:|
| GraphQA / Qwen | 81.5% | 93.0% | 89.0% |
| GraphQA / DeepSeek | 81.3% | 84.5% | 86.0% |
| Erdős / Qwen | 64.7% | 91.2% | 69.1% |
| Erdős / DeepSeek | 95.1% | 99.0% | 99.0% |

These are record-weighted accuracy summaries, not invariance scores or averages over
independent model calls. Task composition matters, particularly on GraphQA (see below).

Keep these columns distinct:

| Column | Meaning |
|---|---|
| `accuracy` | Fraction of scored answers that are correct |
| `frac_identical` | Fraction of instances whose answers all parse and agree across tested forms |
| `frac_all_correct` | Fraction of instances correct on every tested form |
| `n` | Scored record count in an accuracy cell |
| `n_calls` | Distinct prompt hashes within an accuracy cell; not additive across cells |

A consistently wrong answer can have perfect invariance. Repeated parsing failures
count against invariance even if the failures are identical. Thus `1 - frac_identical`
is not exclusively a rate of answers changing.

## 3. Inspect three concrete examples

### Representation can break code that normally works

Open the [Qwen GraphQA accuracy heatmap](../results/graphqa/figs/accuracy_graphqa_hf-qwen3-8b-nscale.png).
Find `node_degree / code/native`: accuracy falls from about 99% on canonical input
to 11% on structure variants. This is a useful starting point for tracing how
duplicated edge presentation can induce double counting.

### The GraphQA model ranking is sensitive to task interpretation

The `disconnected_nodes` question says "not connected," but its ground truth means
not directly adjacent. A connected-component interpretation instead asks which nodes
are unreachable by any path.

The restored DeepSeek records confirm this distinction. On the 100 canonical instances:

| Condition | Matches unreachable-node answer | Correct under benchmark definition |
|---|---:|---:|
| `code/native` | 100/100 | 11/100 |
| `code/networkx` | 99/100 | 12/100 |
| `graph_as_code/native` | 100/100 | 11/100 |
| `graph_as_code/networkx` | 100/100 | 11/100 |

For example, the injected NetworkX program for
`graphqa-sbm-0000-disconnected_nodes::canonical` calls
`nx.node_connected_component(G, 11)` and returns nodes outside that component.
Its answer is `[17]`; the benchmark expects
`[0, 2, 3, 5, 6, 7, 8, 13, 14, 15, 17]`.

Across all five conditions, DeepSeek's GraphQA accuracy is 85.3%, versus Qwen's 89.9%.
Excluding this task gives DeepSeek 96.9%, versus Qwen 91.2%. This is a diagnostic
sensitivity analysis, not a proposal to silently remove the task. Investigate wording
and report the distinction before interpreting the overall model ranking.

### Different shortest paths can both be correct

In [Erdős invariance.csv](../results/erdos/tables/invariance.csv), filter DeepSeek,
`shortest_path`, `code/native`, `order`. `frac_identical` is 0.50, while
`frac_all_correct` is 1.00. The model can select different equally short paths.
This is answer-identity sensitivity without a loss of task correctness.

## 4. Trace a result back to its evidence

Within each `results/<dataset>/` folder, `tables/` contains combined summaries and
`tables/<model>/` model-specific ones. The per-record files are not in Git; download them from the
Hugging Face datasets (see the [README](../README.md)) into the same folder:

* `scored/<model>.jsonl` contains answers, correctness, variant metadata, and failure labels.
* `responses/<model>.jsonl` contains the original model reply and generated code.
* `exec/<model>.jsonl` contains execution output and graph diagnostics.

Join records by `record_id`. Pick one instance and compare its canonical and perturbed
records within the same model and condition. JSONL has one JSON object per line;
filter by instance/task rather than opening the entire file in an editor.

Use `ladder.csv`, `failures.csv`, and `silent_transcription.csv` for diagnosis.
`failures.csv` reports shares **among failures**; the ladder uses shares **among records**.
Keep native and NetworkX failure decompositions separate because construction errors
are not equally observable in the two conditions.

## 5. Read the interpretation with these qualifications

[ANALYSIS.md](../ANALYSIS.md) contains the updated interpretation and review findings.
Keep these qualifications in mind when discussing the results:

* **Nondeterminism correction:** the first repeat baseline and the main metric handle
  unparsable answers differently, and their comparison counts do not match; its sample also
  omits some GraphQA graphs. The corrected baseline is ANALYSIS.md §8.0. Subtraction is still
  not an established causal estimate.
* **Injected-data control:** removing graph text changes graph visibility as well as
  transcription. Its gap from ordinary code generation is not purely copying cost.
* **Caching:** a single generic program can be reused across many graphs. Read
  `n_calls` before treating an apparent success or failure as many model decisions.
* **Answer parsing:** some uninformative node-set answers parse as empty lists (two Qwen
  GraphQA direct answers, ANALYSIS.md §5); the reported tables do not correct them.

The main observations are that plain-Python code generation improves
raw consistency over direct answering in the aggregate comparisons, NetworkX's
benefit depends strongly on the model, and representation and task wording can each
cause large performance changes. Keep answer consistency, correctness, and repeated-
prompt variability separate when explaining these findings.
