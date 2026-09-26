# Detection and voting on all four models (2026-09-22, corrected 2026-09-24)

Sections 8.1 and 8.2 of [ANALYSIS.md](../ANALYSIS.md) first measured the permutation-disagreement
detector and the permutation vote on the two models run from this repository. The team's
published dataset supplies the other two; this note is the four-model version, and §8 now reports
all four.

Source: `Yonibarel/graph-serialization-invariance`, revision `22edd1f`, files
`scored/{graphqa,erdos}/{hf-gemma-4-31b,hf-deepseek-v4-flash}.jsonl.gz`, downloaded with a
checksum manifest to `results/hf_snapshot_yoni/` and restored into `results/<dataset>/scored/`.
Complete base runs: 44,625 GraphQA and 71,230 Erdős records per model, the same record sets as the
two local models. Every record's `correct` flag and answer key re-derive exactly from its parsed
answer with this repository's scorer. Revision `8e1c186` (2026-09-23) adds the raw replies, with
the scored records unchanged in content; replaying them through this repository's pipeline
reproduces every field of 231,697 of the 231,710 records, the other 13 being timeouts in the
team's run (ANALYSIS.md §8.7). Regenerate with
`python scripts/permutation_signal.py --config configs/<dataset>.yaml` (all four models). No
inference.

The first version of this note was computed with the detection script before the corrections of
ANALYSIS.md §8.6: the sorted-identity form counted as a relabeling, and recall counted crashes as
caught. The tables below use the corrected script; §4 and §5 change the most.

## 1. The detector, four models

Flag an instance when the canonical answer and its relabel/order variants do not all agree. Code
arms, all permutations. "Silent errors" are the wrong answers that returned an answer at all; a
crash is always flagged but needs no detector.

| Dataset | Model | Arm | Accuracy | Flag rate | Errors caught | Silent errors caught |
|---|---|---|---:|---:|---:|---:|
| Erdős | DeepSeek-V3.1 | native | 0.998 | 8.1% | 2/2 | 1/1 |
| Erdős | DeepSeek-V3.1 | networkx | 0.992 | 10.1% | 10/10 | 4/4 |
| Erdős | Qwen3-8B | networkx | 0.732 | 42.2% | 313/321 (98%) | **10/18 (56%)** |
| Erdős | Qwen3-8B | native | 0.950 | 17.1% | 45/60 (75%) | 40/55 (73%) |
| Erdős | DeepSeek-V4-Flash | native | 0.981 | 9.5% | 17/23 (74%) | **7/13 (54%)** |
| Erdős | DeepSeek-V4-Flash | networkx | 0.992 | 5.5% | 6/9 (67%) | 6/9 (67%) |
| Erdős | Gemma 4 31B | both arms | 1.000 | 5.0% | no errors to catch | — |
| GraphQA | Gemma 4 31B | networkx | 0.974 | 6.7% | 17/18 (94%) | 17/18 (94%) |
| GraphQA | Qwen3-8B | native | 0.974 | 9.1% | 16/18 (89%) | 16/18 (89%) |
| GraphQA | Qwen3-8B | networkx | 0.901 | 16.4% | 53/69 (77%) | 47/63 (75%) |
| GraphQA | Gemma 4 31B | native | 0.977 | 5.1% | 12/16 (75%) | 12/16 (75%) |
| GraphQA | DeepSeek-V4-Flash | native | 0.783 | 9.1% | **40/152 (26%)** | 40/152 (26%) |
| GraphQA | DeepSeek-V4-Flash | networkx | 0.831 | 9.9% | **25/118 (21%)** | 25/118 (21%) |
| GraphQA | DeepSeek-V3.1 | native | 0.871 | 3.4% | **1/90 (1%)** | 1/90 (1%) |

The Erdős DeepSeek-V3.1 rows rest on 2 and 10 errors in 1,200 instances; read them as counts.

## 2. Why it fails where it fails, measured rather than asserted

The split is not by model strength. It is by whether that model's errors are *stable*. Canonical
errors in the GraphQA plain-Python arm, by task:

| Model | Total errors | Concentrated in `disconnected_nodes` | Caught there | Detector recall |
|---|---:|---:|---:|---:|
| DeepSeek-V3.1 | 90 | 89 (99%) | 0 | 1.1% |
| DeepSeek-V4-Flash | 152 | 89 (59%), plus `connected_nodes` 63 | 0 | 26.3% |
| Gemma 4 31B | 16 | 16 (100%) | 12 | 75.0% |
| Qwen3-8B | 18 | 7 (39%) | 7 | 88.9% |

Both DeepSeek models make the `disconnected_nodes` misreading of ANALYSIS.md §3A on essentially
every graph, and it is identical under every permutation: none of those errors is caught. Gemma
makes the same misreading but on only 16 graphs, and its detector still fires on 12 because those
few are unstable. The detector's blind spot is a property of the *error*, not of the model, and the
four-model table is what turns that from an explanation into a result.

## 3. Abstention

Answer only when the permutations agree:

| Dataset, model, arm | Coverage | Accuracy on answered | Base accuracy |
|---|---:|---:|---:|
| Erdős, DeepSeek-V3.1, native | 91.9% | **100%** | 0.998 |
| Erdős, DeepSeek-V4-Flash, native | 90.5% | 99.4% | 0.981 |
| Erdős, Qwen3-8B, networkx | 57.8% | **98.8%** | 0.732 |
| GraphQA, Qwen3-8B, native | 90.9% | 99.7% | 0.974 |
| GraphQA, Gemma 4 31B, networkx | 93.3% | 99.8% | 0.974 |
| GraphQA, DeepSeek-V4-Flash, native | 90.9% | 82.4% | 0.783 |
| GraphQA, DeepSeek-V3.1, native | 96.6% | 86.8% | 0.871 |

The last two rows are the counterexample again: when the errors are systematic, abstention cannot
make the answers reliable. DeepSeek-V3.1 answers at 86.8% against 87.1% without abstaining;
DeepSeek-V4-Flash gains 4.1 points but is still wrong on 17.6% of what it answers.

## 4. Cost: how many extra calls

Silent-error recall from one extra call (k = 2: the canonical answer plus the first seeded
relabeling) against all permutations, plain-Python arm. A crash is flagged at any k; counting
crashes as caught would add 1, 10 and 5 crashes, all caught, to the three Erdős rows.

| Dataset, model | Caught at k=2 | Flag rate at k=2 | Caught, all | Flag rate, all |
|---|---:|---:|---:|---:|
| Erdős, DeepSeek-V3.1 | 1/1 | 3.9% | 1/1 | 8.1% |
| Erdős, DeepSeek-V4-Flash | 3/13 (23%) | 5.2% | 7/13 (54%) | 9.5% |
| Erdős, Qwen3-8B | 25/55 (45%) | 9.1% | 40/55 (73%) | 17.1% |
| GraphQA, Qwen3-8B | **15/18 (83%)** | 4.4% | 16/18 (89%) | 9.1% |
| GraphQA, Gemma 4 31B | 5/16 (31%) | 1.6% | 12/16 (75%) | 5.1% |

One relabeled call already gives Qwen most of its GraphQA recall and DeepSeek-V3.1 its one silent
Erdős error; Gemma on GraphQA and Qwen and DeepSeek-V4-Flash on Erdős gain substantially from the
full set. The value of the
extra calls depends on the model and dataset, not on model strength.

Relabeling versus reordering, compared at the same k on the same instances (`relabel@matched`,
`order@matched`; 42 code cells with errors, k = 2 to 4): relabeling catches more errors in 20,
as many in 14 and fewer in 8 (Gemma GraphQA native, DeepSeek-V3.1 Erdős NetworkX, DeepSeek-V4-Flash
Erdős in both arms), and flags more instances in 36. It is the more sensitive probe, not a
uniformly better one.

## 5. Voting

Majority over the canonical and permuted answers (ties to the canonical answer) changes accuracy
by -2.4 to +6.4 points across the sixteen code cells. The gain is concentrated where errors are
unstable (Qwen Erdős NetworkX +6.4). Five cells lose, all on GraphQA: four by 0.1-0.3 points, and
DeepSeek-V4-Flash plain Python by 2.4 -- 17 `connected_nodes` instances whose correct canonical
answer is outvoted by the misreading most of their variants make, with no instance gaining. That
is the systematic error of §2 amplified, not noise. Voting is small and not uniformly safe;
abstention is the stronger use of the same calls.

## 6. What this adds to section 8

Section 8 stated that the detector finds unstable errors and not wrong beliefs, on two models.
Four models now support it, and the two that fail are exactly the two whose errors concentrate in
a stably misread task.

The rest of section 8 now also covers all four models: the repeat floor (§8.0), canonical
labeling (§8.3) and the per-task solver (§8.4) with new inference, and program voting (§8.2) from
the programs replayed out of the raw replies. DeepSeek-V4-Flash's `connected_nodes` misreading is
also what makes voting over its programs lose (-2.3).
