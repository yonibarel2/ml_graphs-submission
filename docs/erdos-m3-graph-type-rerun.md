# Erdős graph-as-code control, rerun with the graph type stated (2026-09-22)

The graph-as-code (M3) control on Erdős was rerun with one sentence added to every undirected
injected prompt. This note records why, what changed, what did not, and what the rerun cannot show.
Run `python scripts/m3fix_compare.py` to regenerate the paired tables under
`results/erdos_m3fix/tables/compare/` (it stops if the two runs do not hold the same M3 records);
standard tables and figures are under `results/erdos_m3fix/`.

## 1. The defect

M3 removes the graph text and injects `nodes`/`edges` at execution. The harness added a note on the
graph type only for directed graphs, so for an undirected graph the M3 prompt stated its type only
if the task's own preamble did. Seven of the twelve Erdős preambles do (`bridges`,
`common_neighbor`, `connected_component_number`, `degree`, `edge_number`, `triangles`, and
`edge_existence`, which describes both cases); four say nothing (`density`, `diameter`, `has_cycle`,
`shortest_path`); and `neighbor` mentions only the directed case ("For directed graph, you should
return the successors of the node").

Misreadings occurred only where the preamble does not state the type. In the NetworkX arm, where the
graph a program builds can be inspected, no recovered graph was directed on undirected input on nine
of the twelve tasks, including three of the four with a silent preamble (`density`, `diameter`,
`shortest_path`). DeepSeek-V3.1's `bridges` and `edge_number` programs and DeepSeek-V4-Flash's
`edge_number` programs build no graph object, so there the direction is not observed. On `neighbor` every model did, on every undirected record, and
the task scored 28/100 in all eight model × library arms (16/16 directed, 12/84 undirected;
ANALYSIS.md §4); DeepSeek-V3.1 also did on `has_cycle` (100% of recovered graphs) and
`edge_existence` (2.1%), and Gemma on `edge_existence` (69.2%). Direct answering and code-from-text
were unaffected: their prompts still carried the graph text.

## 2. The change

`inject_graph_type: true` in `configs/erdos_m3fix.yaml` makes the prompt builder add, for undirected
graphs in M3 only, the sentence

> The graph is undirected: (u, v) and (v, u) denote the same edge.

in the position where directed graphs already had "The graph is directed: (u, v) is an edge from u
to v." Nothing else changed: same 1,200 instances and 14,246 variants (copied from `erdos`; the
`variants` stage rebuilds them byte-identical), same template, same models, same providers,
temperature 0. Directed-graph prompts are byte-identical to
the base run. The flag is off by default, so the original runs stay reproducible. The sentence
changes the prompt hash but not the record id, so every rerun record pairs with the base record.

Scale: 28,492 records per model, 1,772 distinct prompts per model (886 per library arm), of which
150 are directed-graph prompts whose text is unchanged. Two models answered those from a local cache
(Qwen3-8B, DeepSeek-V3.1: 1,622 new calls each); the other two had no local cache and re-asked them
as well (Gemma 4 31B, DeepSeek-V4-Flash: 1,772 each; §4). 6,788 API calls in total. The run log
(`results/erdos_m3fix.log`, Git-ignored) ends each model's LLM stage with:

```
[llm:hf-qwen3-8b-nscale] 28492/28492 done, 26870 from cache, 0 errors
[llm:hf-deepseek-v4-flash] 28492/28492 done, 26720 from cache, 0 errors
[llm:hf-gemma-4-31b] 28492/28492 done, 26720 from cache, 0 errors
[llm:hf-deepseek-v3.1-novita] 28492/28492 done, 26870 from cache, 0 errors
```

## 3. What the fix established

**The neighbor failure was the missing word, not transcription and not reasoning.** `neighbor` goes
from 28/100 to 100/100 in all eight arms. In the NetworkX arm, the share of recovered graphs built
directed on undirected input falls to 0 for every model, from 7.5% (Qwen), 18.6% (DeepSeek-V3.1),
13.3% (Gemma) and 8.8% (DeepSeek-V4-Flash); `directedness.csv` gives the counts of recovered graphs,
which are the denominators. The native arm has no graph object, so there the direction is not
observed.

Two more tasks gain from the sentence, entirely on undirected instances. DeepSeek-V3.1's NetworkX
`has_cycle` goes 53 → 100: its program built a directed graph on every undirected record before and
on none after (undirected instances 36/83 → 83/83). Gemma's `edge_existence` goes 91 → 100 (native)
and 82 → 100 (NetworkX, where wrong-direction graphs fall from 69.2% of recovered graphs to 0).

Task-averaged permutation invariance (I: all forms identical; R: all forms correct) over relabel and
order, and canonical accuracy, base → fixed:

| Model | Arm | Canonical acc. | I | R |
|---|---|---:|---:|---:|
| Qwen3-8B | native | 0.938 → 0.992 | 0.954 → 0.948 | 0.936 → 0.987 |
| Qwen3-8B | networkx | 0.607 → 0.667 | 0.624 → 0.624 | 0.607 → 0.667 |
| DeepSeek-V3.1 | native | 0.848 → 1.000 | 0.864 → 0.956 | 0.843 → 1.000 |
| DeepSeek-V3.1 | networkx | 0.901 → 0.907 | 0.955 → 0.862 | 0.899 → 0.901 |
| Gemma 4 31B | native | 0.932 → 1.000 | 0.948 → 0.956 | 0.928 → 1.000 |
| Gemma 4 31B | networkx | 0.925 → 1.000 | 0.949 → 0.958 | 0.922 → 1.000 |
| DeepSeek-V4-Flash | native | 0.932 → 0.906 | 0.956 → 0.873 | 0.932 → 0.906 |
| DeepSeek-V4-Flash | networkx | 0.938 → 0.991 | 0.955 → 0.958 | 0.936 → 0.991 |

Where the numbers come from. The base-run values for Gemma 4 31B and DeepSeek-V4-Flash, here and in
the per-task figures below, are in their tracked per-model tables (`results/erdos/tables/<model>/`).
Statements that need their base-run records -- the directed/undirected splits, the share of
wrong-direction graphs (Gemma's 69.2% on `edge_existence`), and their paired deltas -- use the
scored records published in the team dataset (`Yonibarel/graph-serialization-invariance`, revision
`22edd1f`; revision `8e1c186` carries the same scored files plus the raw replies, ANALYSIS.md
§8.7), downloaded with a checksum manifest to `results/hf_snapshot_yoni/` and restored into
`results/erdos/scored/`. With them, `scripts/m3fix_compare.py` compares all four models; without
them it compares Qwen3-8B and DeepSeek-V3.1 only.

Paired deltas in accuracy, averaged per instance over its forms first, with 95% bootstrap intervals
over instances: DeepSeek-V3.1 native +15.2 [13.2, 17.3] points, networkx +0.6 [−1.9, 3.1]; Qwen
native +5.5 [4.1, 7.0], networkx +6.0 [4.7, 7.4]; Gemma native +6.7 [5.4, 8.2], networkx +7.5 [6.0,
9.0]; DeepSeek-V4-Flash native −2.7 [−4.8, −0.5], networkx +5.3 [3.9, 6.8].

These are not all effects of the sentence. Split by task, in points of the overall delta: `neighbor`
contributes +6.0 to every arm, and the other contributions of the sentence are DeepSeek-V3.1's
`has_cycle` (+3.9, NetworkX) and Gemma's `edge_existence` (+0.7 native, +1.5 NetworkX). The rest are
single-program flips and re-asked prompts (§4). DeepSeek-V3.1's native +15.2 is +6.0 from
`neighbor`, **+8.3 from `bridges`**, whose one program failed in the base run and not in the rerun,
and +0.9 from `diameter`: most of it is not the fix. Its NetworkX +0.6 nets +6.0 and +3.9 against
−8.3 (`bridges`) and −0.9 (`diameter`). DeepSeek-V4-Flash's native −2.7 is +6.0 from `neighbor`
against −8.3 from `bridges` and −0.3 from `density`. Gemma and DeepSeek-V4-Flash also differ between
the runs in provider draws on their re-asked directed prompts (§4, §5). Qwen's NetworkX arm remains
dominated by execution failures on unavailable APIs, which the sentence does not address; its
`common_neighbor`, `connected_component_number`, `diameter` and `has_cycle` cells are 0/100 before
and after.

**The repaired M2–M3 comparison.** With the defect removed, M3 matches or exceeds code-from-text
(M2) on every task for Gemma and for DeepSeek-V3.1 native. Every remaining deficit is one of three
things: a single-program task (DeepSeek-V3.1 NetworkX `bridges` and `diameter`, DeepSeek-V4-Flash
native `bridges`, and two cells unchanged by the fix: DeepSeek-V4-Flash native `edge_number`, 91,
and Qwen's native `has_cycle`, 97); a program generated afresh (§4: DeepSeek-V4-Flash's re-asked
directed prompts, Qwen's `triangles`); or a Qwen NetworkX execution failure (`common_neighbor`,
`has_cycle`). The M2–M3 gap is still a diagnostic comparison, not a transcription cost: M3 also
hides the graph from the model.

## 4. What moved for other reasons

Three kinds of change in the tables are not effects of the sentence, and the report must say so.

**One program decides 100 graphs.** For tasks whose question names no node, the M3 prompt is
identical across all instances, so one reply serves the whole task (`n_calls` = 1 for `bridges`
and `connected_component_number`; 2 for `density`, `diameter`, `edge_number`, `has_cycle`, one per
graph type). `bridges` flips 0 → 100 (DeepSeek-V3.1 native), 100 → 0 (DeepSeek-V3.1 networkx) and
100 → 0 (DeepSeek-V4-Flash native): in each 0 the single generated program declares
`nonlocal time` in a module-level function, where `time` is a global and `nonlocal` has nothing
to bind to: a `SyntaxError` on every graph. DeepSeek-V3.1's `diameter` moves 89 → 100 (native) and 100 → 89 (networkx) because one of
the two programs uses the two-BFS heuristic, which is exact only on trees. These are coin flips on a
single generation and say nothing about serialization; they are why M3 accuracy on these tasks
should be read with `n_calls`, and why a per-task solver study (ANALYSIS.md §8, E5)
needs repeated generations.

**Re-asked directed prompts.** Gemma and DeepSeek-V4-Flash had no local response cache, so all 150
of their distinct directed-graph prompts (75 per library arm) were sent again although their text is
unchanged. Apart from `bridges` above, every DeepSeek-V4-Flash regression is on directed graphs:
`density` native 100 → 96 (the new program divides by n² instead of n(n−1)) and `edge_number`
networkx 100 → 91 (the new program merges (u, v) with (v, u) on a directed graph). This is provider
nondeterminism at temperature 0 on identical text, the phenomenon the repeat floor measures
(ANALYSIS.md §8.0), and it bounds what a single rerun can claim for those two models. The mirror
error shows in the NetworkX arm: on directed input, 30 of DeepSeek-V4-Flash's 640 recovered graphs
before and 49 of 639 after are undirected, all from `degree` programs. Most still score correct (28
of 30 before, 39 of 49 after), so these are mostly latent errors; across all forms the directed
`degree` records' accuracy moves from 74.0% to 71.4%.

**Rewritten programs on undirected prompts.** Qwen `triangles` native drops 100 → 93: for the
query-node-7 prompt Qwen rewrote a correct neighbourhood-pair counter into a wrong de-duplication.
The sentence is irrelevant to triangle counting: once the prompt text changes, the program is
generated afresh, and this one generation came out wrong.

## 5. What this rerun does not establish

- A noise-corrected effect for Gemma and DeepSeek-V4-Flash: their base and fixed runs differ in
  provider draws on the unchanged prompts as well as in the sentence. Their neighbor result
  (28 → 100, all eight arms, one mechanism) is robust to that; their small cell changes are not.
- That the construction checker now catches graph-type errors. `directedness_mismatch` is only
  observable in the NetworkX arm; the native arm has no graph object to inspect.
- Anything about M3's consistency on tasks with one prompt per task, for the reason in §4.
- How the fix would do on another generation. Every interval here resamples instances, conditional
  on the programs the models wrote in these two runs; a task decided by one or two programs can
  swing by 100 points on a different generation. A claim about the expected improvement needs
  repeated generations in both conditions.

## 6. What to use in the paper

Report the base M3 run as the "prompt information loss" ablation (four models, one omitted word, a
misreading shared by every model on `neighbor`), and the fixed run as the M3 control. Quote the
neighbor and directedness results as the effect of the fix; quote the bridges/diameter flips as the
single-program caveat; attribute the DeepSeek-V4-Flash regressions to re-asked prompts, not to the
sentence. Do not quote a model's overall paired delta as the effect of the fix: DeepSeek-V3.1's
native +15.2 is mostly the `bridges` flip; the sentence's own contribution is the per-task split in
§3.

## Files

- Config `configs/erdos_m3fix.yaml`; data `data/processed/erdos_m3fix/`: `instances.jsonl` is
  tracked (a copy of `erdos`); `variants.jsonl` is Git-ignored and rebuilt by the `variants` stage
  (see the config for the commands).
- Records `results/erdos_m3fix/{responses,exec,scored}/<model>.jsonl` (Git-ignored, as for `erdos`).
  Unlike the base run's, they are not in the published Hugging Face datasets, so the tables below
  cannot be regenerated without rerunning, and `scripts/verify.py` does not check them.
- Tables `results/erdos_m3fix/tables/`, figures `results/erdos_m3fix/figs/`, paired comparison
  `results/erdos_m3fix/tables/compare/`. The printed comparison (`results/erdos_m3fix/compare.txt`)
  and the run log (`results/erdos_m3fix.log`) are local and Git-ignored; §2 quotes the log lines
  the call counts come from.
- Code: `inject_graph_type` in `src/gsi/prompts/modes.py`, `src/gsi/experiment/config.py`,
  `src/gsi/experiment/run.py`; test in `tests/test_modes.py`; `scripts/m3fix_compare.py`.
