# What a model assumes when the serialization omits the graph type (2026-09-22)

A one-sentence ablation on four models. For an undirected graph, the Erdős graph-as-code (M3) prompt
stated the graph type only if the task's own preamble did (seven of twelve do;
docs/erdos-m3-graph-type-rerun.md §1); the rerun (`configs/erdos_m3fix.yaml`) states it
explicitly for every undirected graph. Same model, task, graph and template, with one fact present
or absent. Tables:
`results/erdos_m3fix/tables/ablation/`, regenerate with `python scripts/graph_type_ablation.py`.
No inference and no program execution.

## 1. The finding: where the preamble does not state the type, the model fills it in

The omission did **not** produce a uniform directed default. The misreading appears only where the
retained preamble does not assert that the graph is undirected, and how often depends on what the
preamble says instead. Measured on all four models, canonical undirected instances, from the graph
the sandbox recovers in the NetworkX arm (`latent_misreading.csv`); every share is over recovered
graphs, and a program that builds no graph object tells us nothing about direction:

| What the retained preamble says | Tasks | Recovered graphs that are a DiGraph |
|---|---|---|
| asserts undirected ("guaranteed to be undirected", "count the edge only once") | bridges, common_neighbor, connected_component_number, degree, edge_number, triangles | **0%**, all four models (not observed for DeepSeek-V3.1 `bridges` and `edge_number` or DeepSeek-V4-Flash `edge_number`: no graph recovered) |
| says nothing about graph type | density, diameter, shortest_path | **0%**, all four models |
| | has_cycle | DeepSeek-V3.1 **100%** (one program); other three 0% |
| mentions both ("For an undirected graph… For a directed graph…") | edge_existence | Gemma **69.5%**; DeepSeek-V3.1 1.3% (1 of 77 recovered); the other two 0% |
| mentions only directed ("For directed graph, you should return the successors") | neighbor | **100%, all four models** |

How much evidence each row carries depends on how many programs stand behind it. `neighbor` asks
about a node, so its prompts differ per instance: all 26 distinct programs per model built a
DiGraph, on all four models. Gemma's `edge_existence` misreading is 53 of its 77 distinct programs.
DeepSeek-V3.1's `has_cycle` names no node, so one program served all 83 undirected instances: that
row is a single generation, not 83 observations.

The `neighbor` preamble names "directed" only to define a *conditional* behaviour for a case that
does not apply. Every model reads it as the graph's type, on every undirected instance. Where the
preamble asserts the type, no model gets it wrong. Where the text is silent or describes both
cases, most programs are right and the exceptions are model-specific.

The programs state the inference in their own comments. With the word omitted, DeepSeek's
`has_cycle` program opens `# Create a directed graph from the edges` and calls
`nx.is_directed_acyclic_graph`; with the word restored, the same prompt yields
`# Create an undirected graph` and `nx.find_cycle`.

So a model does not default to directed. (It cannot check the edge list either: M3 hides the graph.)
On `neighbor` it takes the only type language in the prompt as the graph's type, although that
language is conditional and belongs to a different clause; elsewhere the evidence is one model at a
time.

## 2. A wrongly built graph can still score correct

In the NetworkX arm the sandbox recovers the graph the program built, so the misreading is
observable independently of the answer. Among undirected instances in the base run:

| Model | Task | Built a DiGraph | Still correct | Latent errors | Surfaced errors |
|---|---|---:|---:|---:|---:|
| Qwen3-8B | neighbor | 100% of 84 | 14.3% | 12 | 72 |
| DeepSeek-V3.1 | neighbor | 100% of 84 | 14.3% | 12 | 72 |
| DeepSeek-V4-Flash | neighbor | 100% of 84 | 14.3% | 12 | 72 |
| Gemma 4 31B | neighbor | 100% of 84 | 14.3% | 12 | 72 |
| DeepSeek-V3.1 | has_cycle | 100% of 83 | 43.4% | 36 | 47 |
| Gemma 4 31B | edge_existence | 69.5% of 95 | 72.7% among those | 48 | 18 |
| DeepSeek-V3.1 | edge_existence | 1 of 77 recovered (1.3%) | 1 of 1 | 1 | 0 |

Every model misread every one of the 84 `neighbor` instances, and the task noticed on 72 of them.
The remaining 12 are **latent errors**: a correct answer computed from a graph that does not match
the input, scored `ok`. Gemma's `edge_existence` is the clearest case, with 48 latent against 18
surfaced: nearly three quarters of its wrongly built graphs never showed up in the score. (These
are canonical instances. The share of Gemma's recovered graphs that are a DiGraph is 69.5% here and
69.2% over all forms in the rerun report.)

This is the construction-level analogue of the silent transcription result
(docs/error-findings.md §3), and it is why answer accuracy cannot be used to argue that a
model understood the serialization it was given.

## 3. Recovery

With the type stated, no recovered NetworkX graph is directed on undirected input, for any model: 0
of 1,123 recovered graphs for Qwen3-8B and for Gemma, 0 of 813 for DeepSeek-V4-Flash and 0 of 797
for DeepSeek-V3.1, whose remaining programs build no graph object (`recovery.csv`). `neighbor` is
100/100 everywhere. The native arm has no graph to inspect; there the evidence is the answers alone.

## 4. What moved for other reasons, and is excluded

`task_sensitivity.csv` also shows movements that are not direction effects. They are diagnosed in
docs/erdos-m3-graph-type-rerun.md §4 and must not be read as ablation results: `bridges`
and `diameter` flip on a single generated program because their M3 prompt is identical across all
instances; DeepSeek-V4-Flash's `density` and `edge_number` changes are re-asked directed prompts
under provider nondeterminism; Qwen's `triangles` dip is a program rewrite on an unrelated task.
Gemma's `edge_existence` gain (0.91 → 1.00 native, 0.82 → 1.00 NetworkX) is a direction effect: its
NetworkX programs built a DiGraph on 69.5% of undirected canonical instances before and on none
after, and the whole gain is on undirected instances.

## 5. Limits

- The built-graph evidence exists only in the NetworkX arm; the native arm has no graph object to
  recover, so its numbers rest on answer correctness alone.
- Base-run records for Gemma 4 31B and DeepSeek-V4-Flash come from the team's published dataset
  (`Yonibarel/graph-serialization-invariance`, revision `22edd1f`; revision `8e1c186` carries the
  same scored files plus the raw replies, ANALYSIS.md §8.7), downloaded with a checksum
  manifest to `results/hf_snapshot_yoni/` and restored into `results/erdos/scored/`. All four
  models therefore contribute per-record evidence.
- Single generations. A task whose M3 prompt names no node (`has_cycle`, `bridges`, `diameter`, ...)
  is decided by one program per graph type, so its row is one draw; repeated generations would be
  needed to say how often a model makes that choice.
- One dataset. GraphQA states "undirected graph G" in its own template, so it has no equivalent
  omission to ablate.

## 6. Why this belongs in the paper

It is a controlled, four-model answer to a question the audit otherwise only raises: serialization
is not just how a graph is written, it is also what is left unwritten. An omitted property is
filled in from surrounding text, the filled-in value can be wrong, and the error is invisible on
any task whose answer is insensitive to it. That connects the measurement half of the study to the
localization half without needing a new experiment.
