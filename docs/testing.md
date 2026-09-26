# Testing strategy

What the 179 tests actually prove, and — as important — what they cannot. Source:
[`tests/`](../tests/).

```bash
pytest -q          # a few minutes, no network, no API calls
```

---

## 1. What is worth testing here

This is a measurement instrument, so the tests target the properties the *conclusions* depend on,
not code coverage. Four failure modes would silently invalidate results:

1. a "variant" that changes more than one axis → attribution is meaningless;
2. a renderer that misrepresents the graph → we measure a different graph than we think;
3. a misclassified failure → the localization claim is wrong;
4. M2 and M3 drifting apart, or the two library arms differing by more than their one sentence →
   the minimal-pair argument collapses and the gap measures something else.

Each has a dedicated test file.

## 2. `test_variants.py` — the single-axis guarantee

Parametrized over six graph families × two canonical forms × every axis.

**Round trip.** `parse(render(v)) == true_edge_set(v)` for every variant. Every rendering can be
read back to exactly the graph it claims to describe — this is what rules out a renderer that
silently drops or duplicates edges under some ordering.

**Single axis.** `axes_differing(v, canon) == {v.axis}` for every generated variant. The same
assertion runs in production inside `make_variants`, so a violation cannot reach a result.

**Inverse relabeling.** Mapping a variant's edges back through the inverse label map recovers the
canonical edge set — the property scoring depends on.

**Permutation properties.** A relabel is a genuine permutation of the label set, reproducible from
its seed, different across seeds, and **position-preserving** (edge `i` in the variant is edge `i`
of canonical with labels substituted). That last assertion pins the design decision in
[permutation-design.md](permutation-design.md) §4.1 so it cannot be undone by accident.

**Ordering semantics.** Each kind has the property it claims: `sorted_st` sorts, `s_sorted_t_shuffled`
leaves the source column sorted, `t_sorted_s_shuffled` the target column, `shuffle_all` is a genuine
permutation of the same multiset. Adjacency-list orderings change the rendering while leaving the
edge set identical, and requesting an edge-list ordering on an adjacency list raises.

## 3. `test_sandbox.py` — the failure taxonomy, executably specified

One fixture program per outcome, all template-shaped, each run through the real sandbox:

| Fixture | Expected |
|---|---|
| correct program | `ok`, `declared_ok=True`, `construction_ok=True` |
| edge missing from the declaration | `transcription` |
| correct declaration, built from a truncated list | `construction` |
| right graph, wrong formula | `logic` |
| `ans = 3` — **and 3 is correct** | `no_computation`, not `ok` |
| `ans = 0` then `ans += 1` | not a literal; `ok` |
| raises after a correct declaration | `execution`, **`declared_ok` still True** |
| `while True` | `execution`, timed out, bounded wall time |
| off-template, no networkx | `unverifiable` |
| off-template, with networkx | still localized via the recovered graph |
| native arm, correct | `ok`, no graph recovered, transcription still verified |
| native arm, wrong on a correct declaration | `logic` — construction is not separable there |
| native arm, bad declaration | `transcription` |
| M3 with a relabeled graph | `ok` — injection carries the perturbation |
| M3 overwriting the injected `edges` | `construction`, **not** `transcription` |
| prints instead of assigning `ans` | `format` |
| `DiGraph` on undirected task | `ok` with `directedness_mismatch` |
| builds three graphs | correct one chosen by Jaccard |
| string node labels | normalized, `declared_ok=True` |
| `ans` as a set / bool | formatted as `[1, 2, 3]` / `Yes` |
| same code twice | second call `cached=True` |

These are the specification. If the classification rules change, this is where the change is pinned.

The two rows in bold type are the ones worth remembering. A crash that still yields a transcription
verdict is what makes `execution` failures informative instead of opaque. And a correct-but-literal
`ans` classified as `no_computation` rather than `ok` is the guard on the number the whole project
reports.

## 3b. `test_modes.py` — the prompt contract

The template and the minimal pair are architecture, so they are asserted rather than trusted:

* the template has both declaration slots and a free logic slot; M3's differs **only** in those
  slots — the tails are compared for byte equality
* the answer slot never says `<your answer>`, and the prompt always carries *"Compute the result -
  do not write it directly"*
* M2 contains the graph text, M3 does not, and every other component appears in both
* M3's prompt hash is **identical** across syntax variants while M2's is not — the property the
  response cache relies on
* the two library prompts differ by exactly one sentence, checked by substituting each library
  sentence for a placeholder and comparing the results
* `library` never appears in `mode`; the two arms produce distinct prompt ids and distinct hashes,
  so they cannot collide in a sink or a cache
* `direct` rejects a library, and a code mode rejects a missing or unknown one

## 4. `test_compare.py` — parsing and comparison

Parametrized cases for `find_answer_line` (markdown decoration, multiple markers taking the last,
the last-line fallback, empty input) and `parse_value` across all seven types including the
rejection cases (`"maybe"` for a bool, `"4.5"` for an int → `None`).

Comparators are tested per type, plus two properties that matter structurally: **path validity with
ties** (a different but equally valid shortest path is accepted; a wrong-length or invalid one is
not) and **relabel round-tripping** for every node-valued type.

## 5. `test_erdos.py` — loader parsing, without the network

Uses a hand-written prompt fixture, so it runs offline. Pins: prompt splitting into
preamble/question with the answer-format sentence stripped; query-node extraction; that the
native edge-list rendering **appears verbatim in the native prompt**; that a relabel propagates into the
question text; that **weights are read from the prompt rather than the `edges` column** (the
`maximum_flow` bug, [datasets.md](datasets.md) §3); and that unsupported tasks are skipped.

This is what pins the Erdős reference to Herbst's baseline. `test_fatemi_fidelity.py` does the
same job for GraphQA, holding **both** encoders byte-identical to Fatemi's Appendix A.1 — the
incident one included, since it is the `structure` variant.

## 6. `test_e2e_stub.py` — the pipeline, end to end

Runs all five stages with the stub model in a temp directory: 12 instances × 5 variants × 5 arms =
300 records, asserting the expected count, that `library` is set on exactly the code-mode rows and
null on `direct`, that multiple failure classes occur, and that the analysis tables build with the
expected axes — including that the M2−M3 gap is computed **inside** each library arm and never
across them.

Then it **runs the whole pipeline a second time** and asserts the responses file is byte-identical,
no new cache entries appeared, and the scored count is unchanged. This is the idempotence guarantee
from [pipeline-and-caching.md](pipeline-and-caching.md) §3 — the property that makes it safe to
re-run a partially-completed expensive job.

## 6b. The follow-up scripts

Each mitigation or review script that produces a reported table has its own file, loading the
script by path and pinning the definitions its numbers depend on: `test_canonical.py` (the exact
canonical labeling gives every relabeling the same labels), `test_canonical_labeling.py` (E3),
`test_permutation_signal.py` (E1/E2: the sorted identity is not a relabeling; recall on answered
errors excludes crashes), `test_program_voting.py` (E6: only the declarations are stripped; ties do
not depend on execution order), `test_solver_per_task.py` (E5: graph type passed to mixed-type
solvers), `test_m3fix_compare.py` and `test_graph_type_ablation.py` (the rerun comparisons use the
same records on both sides and stop on an unfinished rerun), and `test_analyze.py` (per-model
analysis never overwrites another model's or the combined tables).

## 7. What the tests do not cover

**Real model output — now piloted, still not unit-tested.** Every test uses the stub, which fills
the template by construction. The 2026-09-17 pilot ran two real models through the full pipeline
on 20 instances and confirmed the template holds (`declared_ok` readable on 96–100% of code-arm
records in every arm). It also found a detector bug the stub could not have exposed: the stub's
programs never put `ans = True` inside a loop, so the false-positive `no_computation` pattern had
no fixture. It does now (`test_literal_under_control_flow_is_computed_not_hardcoded`). The
lesson generalizes — **the stub only emits shapes we thought of** — and is the reason the pilot
stays a mandatory step before any full run
([pipeline-and-caching.md](pipeline-and-caching.md) §6).

**Provider integration.** No test hits an API. Auth, rate limits, retry behaviour under real 429s
and model-id validity are unverified.

**Statistical correctness.** Tables are checked for shape and expected keys, not for numerical
correctness against a hand-computed reference. A subtly wrong `mean_spread` normalization would pass.
Outside the suite, `scripts/audit_results.py` recomputes the invariance cells independently
([ANALYSIS.md](../ANALYSIS.md) §7), and `scripts/verify.py` checks that the committed tables follow
from the published records.

**Packaging.** The suite runs against the working tree. It did **not** catch the missing
`src/gsi/data/` package, because the files existed locally and were merely never committed — a
fresh-clone smoke test would have. `scripts/verify.py` runs from a scratch copy but still imports
this working tree's `src/`, so it would not catch it either.

**Sandbox escape.** No adversarial tests; the sandbox is explicitly not a security boundary
([execution-sandbox.md](execution-sandbox.md) §5).

## 8. Adding tests

New serialization axis → extend the parametrization in `test_variants.py`; the round-trip and
single-axis assertions apply automatically. New failure class → add a fixture program to
`test_sandbox.py`. New answer type → add parse and compare cases to `test_compare.py`. New dataset →
follow `test_erdos.py`: a fixture row, offline, asserting the canonical rendering matches the source.
New mode or library arm → add a case to `test_modes.py` asserting what it shares with its siblings,
not just what it changes.

**One lesson from a real bug.** `classify.py` tested `mode == "graph_as_code"` while the configs ran
`graph_as_code_0shot`; the branch never fired, and the suite stayed green because the test exercised
the *disabled* name. A test that pins a name nothing runs proves nothing. Where a test names a mode
or a library, prefer the registry constant, and make at least one test assert that the set of arms
actually executed is the set the config asked for — which `test_e2e_stub.py` now does.
