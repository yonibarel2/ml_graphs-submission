# Mitigation: a one-sentence fix for duplicate-edge counting

**Archived result.** This experiment ran on 2026-09-18/19 on the `mitigation-dedup` branch of the
development repository (`ramramk/ml_graphs`, commit `e0b0444`) and was later removed from the main
line together with its prompt-hint code. Its report and result tables are kept here unchanged
because the paper cites them; the configs, the hint's code and `scripts/mitigation_compare.py`
are not part of this repository, so it cannot be rerun from here, and `scripts/verify.py` does not
check it. Its repeat-disagreement floor is the first one ([ANALYSIS.md](../ANALYSIS.md) §5), not
the corrected floor of §8.0.

The proposal says "if the audit's findings allow, we will
attempt a mitigation guided by the diagnosis". This run targets the representation failure diagnosed in
[ANALYSIS.md](../ANALYSIS.md) §3B: when an undirected edge is listed as both `(u,v)` and `(v,u)`, native-Python
code counts it twice.

**Bottom line.** The hint removes the duplicate-edge failure in both models. Applied to the whole GraphQA
dataset, it makes DeepSeek slightly more robust on almost every axis (NetworkX syntax −2.3 points), but it
makes Qwen *less* robust to relabelling, edge order and syntax (6–13 points). A one-sentence fix helps the
strong model and trades one fragility for another in the 8B model.

**Setup.** Same 100 GraphQA graphs, same queries, same models (Qwen3-8B / nscale, DeepSeek-V3.1 / Novita),
same code template, both code arms (native, NetworkX). The only change is one sentence added to every prompt:

> An edge may be listed in both directions; (u, v) and (v, u) are the same edge and must be counted once.

Run first on the structure axis (7 tasks × 3 forms: canonical, adjacency list, reciprocal edges), then on
**all of GraphQA** (all 4 axes, 17,850 records per model). Baseline = the original run, paired record by
record (`scripts/mitigation_compare.py`). About 32k calls, about $9.

## Targeted result

`node_degree`, native code, correct out of 100 (before → after):

| Model | Canonical | Adjacency | Reciprocal | Doubled answers (adj / recip) |
|---|---|---|---|---|
| DeepSeek | 100 → 100 | 34 → **100** | 19 → **100** | 66 / 81 → 0 / 0 |
| Qwen | 99 → **86** | 17 → **87** | 5 → **87** | 82 / 94 → 9 / 10 |

Structure-axis invariance (native code, all 7 tasks): DeepSeek I 86.0 → 99.3%, Qwen I 59.7 → 81.0%.

## Whole dataset

A prompt change has to hold on all the data, not only on the forms it targets. Invariance I (% of instances
whose answer is identical on all variants of the axis), before → after:

| Model / arm | Relabel | Order | Structure | Syntax | Accuracy, all records |
|---|---|---|---|---|---|
| DeepSeek / native | 97.0 → 98.7 | 97.8 → 98.8 | 86.0 → **99.3** | 96.7 → 99.4 | 84.5 → 87.0 |
| DeepSeek / NetworkX | 96.7 → 98.7 | 96.5 → 99.0 | 97.1 → 98.6 | 95.7 → 93.4 | 86.0 → 86.6 |
| Qwen / native | 92.7 → **79.6** | 95.8 → **88.7** | 59.7 → **81.0** | 95.1 → **88.0** | 93.0 → 92.5 |
| Qwen / NetworkX | 86.9 → **80.6** | 89.6 → **82.1** | 81.3 → 77.0 | 60.7 → **49.3** | 89.0 → **84.4** |

On ANALYSIS.md's headline permutation metric (relabel + order), DeepSeek improves (native 97.4 → 98.8,
NetworkX 96.6 → 98.9) and Qwen degrades (native 94.3 → 84.1, NetworkX 88.2 → 81.3). All-variants-correct (R)
moves the same way. The Qwen drops are several times the 1–3% repeat-disagreement floor and their 95%
intervals exclude zero (`results/mitigation_dedup_full/tables/axis_invariance.csv`).

**Qwen side effects.** The hint over-corrects: 13 canonical degree answers are now doubled. Other tasks move
both ways: `connected_nodes` +13 points, `disconnected_nodes` −19 (the code forgets to exclude the query
node), `cycle_check` −15 with NetworkX. The small model's code is sensitive to *any* prompt change.

## Caveats

- 95% intervals (in the CSVs) are a paired bootstrap over graphs, conditional on the collected responses.
  The repeat baseline shows 1–3% disagreement for code, so deltas of a few points are not conclusive.
- The baseline was run earlier on another machine (Linux); these runs used Windows. Program execution is
  deterministic, but provider-side drift cannot be ruled out.
- During the full run the PC slept for 40 minutes; the 4 programs it interrupted were recorded as timeouts.
  They were removed and rerun, so the final run has no timeouts.

## Diagnostic note (not a mitigation)

To confirm the "disconnected nodes" misreading in ANALYSIS.md §3A, one clarifying sentence ("A node is connected
to another node only if there is an edge directly between them.") was added on that task alone. DeepSeek goes
from 11–12/100 to 100/100, so its low score was a misread question, not a reasoning failure. This belongs in the
analysis, not the mitigation: it is task-specific and unrelated to representation
(`results/mitigation_disconnected/tables/`).

## Files

- Tables: `results/mitigation_dedup/tables/` (structure axis), `results/mitigation_dedup_full/tables/`
  (whole dataset), `results/mitigation_disconnected/tables/` (the diagnostic note above).
- Configs, the hint's code and the comparison script: branch `mitigation-dedup` of the development
  repository, commit `e0b0444`.
