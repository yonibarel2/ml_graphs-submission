# Permutation architecture: how equivalent serializations are constructed

This document explains how the project builds "equivalent serializations" of a graph and why it is
built that way. It is the design rationale behind [`src/gsi/serial/variant.py`](../src/gsi/serial/variant.py)
and [`src/gsi/serial/render.py`](../src/gsi/serial/render.py).

For the pipeline as a whole see [code-tour.md](code-tour.md).

---

## 1. The problem this architecture solves

The research question is whether an LLM writing code returns the **same answer** when the **same
graph** is written in an equivalent way, and if not, where the fragility enters.

That question is only answerable if each perturbation is *attributable*. "Equivalent serialization"
describes an infinite space: any node names, any edge order, any format. If we produced a handful of
alternative texts by hand and accuracy dropped, we could not say what caused the drop. This is
precisely the weakness we identify in prior work (CodeGraph varies node labels, phrasing and syntax
all at once, so an observed drop cannot be attributed to any single cause).

So the architecture has one overriding requirement:

> **Every non-canonical serialization must differ from the canonical one along exactly one axis,
> and that property must be machine-checkable rather than assumed.**

Everything below follows from that requirement.

---

## 2. The four axes

We adopt the decomposition of Herbst et al. (*Lost in Serialization*) — **node labeling, edge
encoding, syntax** — for two reasons. First, the proposal frames our contribution as applying
their controlled perturbations to *executed code*, so reusing their axes is what makes the
composition meaningful. Second, it supports comparison with their direct-mode findings, subject
to differences in models and prompts.

We split their "edge encoding" into two axes, because it bundles two independently variable things:
the order in which edges are presented, and the data structure used to present them.

| Axis | What varies | Variants implemented |
|---|---|---|
| `relabel` | the symbol each node is displayed as | random permutation, N seeds |
| `order` | the sequence in which nodes/edges are emitted | edge list: `sorted_st`, `s_sorted_t_shuffled`, `t_sorted_s_shuffled`, `shuffle_all`; adjacency list: `lines_shuffled`, `neighbors_shuffled`, `shuffle_all` |
| `structure` | the data structure | `edge_list` ↔ `adj_list`; undirected edges listed once or in both directions (`replicated`) |
| `syntax` | the surface format | `plain`, `json`, `networkx_code`, `graphqa_nl`, `erdos_nl` |

---

## 3. Central decision: a serialization is a structured object, not a string

**Variants are never produced by editing text.** A `Variant` is a record of four independent
fields, and text is generated from it only at the end, by a renderer:

| Field | Role |
|---|---|
| `label_map` | canonical node label → displayed symbol |
| `node_seq`, `edge_seq` | the **order** nodes and edges are emitted in (in displayed labels) |
| `params.structure`, `params.replicated` | edge list vs adjacency list; edges once or twice |
| `params.syntax` | surface format |

Because the serialization is structured, *"exactly one axis changed"* becomes a computable
predicate rather than a claim we hope is true:

```python
def axes_differing(v, canon) -> set[str]:          # variant.py
    diff = set()
    if v.label_map != canon.label_map:                        diff.add("relabel")
    if _canonical_order(v) != _canonical_order(canon):        diff.add("order")
    if (v.params["structure"], v.params["replicated"]) != ... diff.add("structure")
    if v.params["syntax"] != canon.params["syntax"]:          diff.add("syntax")
    return diff
```

and `make_variants()` **asserts** it on every variant it produces:

```python
assert diff == {v.axis}, f"{v.variant_id}: differs in {diff}"
```

If a transform or renderer ever leaks a second change, data generation crashes rather than silently
emitting a result nobody could interpret. Had variants been built by string manipulation, this
guarantee could not even be stated.

Two subtleties. Order is compared **after mapping labels back through the inverse label map**,
otherwise every relabeling would look like an order change too. And when a variant names an
ordering rule (`sorted_st`, `shuffle_all`, …) the rule itself is compared rather than the positions
— that is what lets a sorted relabeling count as "same order" as the sorted identity reference
(§4.1). The reference is per axis: relabelings are checked against `relabel:identity`, everything
else against canonical. A candidate whose serialization is identical to its reference is dropped as
a no-op rather than scored.

---

## 4. The transforms, and the reasoning behind each

All examples use the star graph `graphqa-star-0004-node_degree` from
`data/processed/graphqa/instances.jsonl`: nodes `[0,1,2,3,4]`, edges `[[0,1],[0,2],[0,3],[0,4]]`,
question "What is the degree of node 0?", ground truth `4`. Canonical serialization for GraphQA is
`(identity labels, sorted, edge_list, graphqa_nl)` — Fatemi's "adjacency" encoder; see
[datasets.md](datasets.md#4-the-reference-encoding) for why this and not the incident form. The
example below is shown in the adjacency-list *structure variant* because its line-per-node layout
makes the ordering perturbations easiest to see.

```
G describes a graph among nodes 0, 1, 2, 3, and 4.
In this graph:
Node 0 is connected to nodes 1, 2, 3, 4.
Node 1 is connected to nodes 0.
...
```

### 4.1 `relabel` — relabel, then sort (Herbst's convention)

```
canonical:  label_map {0:0, 1:1, 2:2, 3:3, 4:4}   edge_seq [[0,1],[0,2],[0,3],[0,4]]
relabel s0: label_map {0:2, 1:4, 2:3, 3:1, 4:0}   edge_seq [[2,0],[2,1],[2,3],[2,4]]   (sorted by new labels)
```

Herbst et al. state (footnote 3): *"After relabeling, we lexicographically sort edges to factor out
the impact of shuffled edge-list."* We do the same. After the symbols are swapped, `node_seq` and
`edge_seq` are re-sorted, so a relabeled text reads as tidily as the original and the only thing a
reader sees changing is the labels.

This forces a subtlety in what "order" means. In canonical label space the sorted-after-relabel
sequence is *not* the canonical sequence, so a positional comparison would report an order change.
Order is therefore treated as a **rule** whenever one is named (`params.ordering`, e.g. `sorted_st`)
and as positions only for the unnamed native order. Every relabeling is then compared against a
**sorted identity reference** — emitted as the variant `relabel:identity`, a member of the relabel
axis — rather than against canonical. For GraphQA the identity reference coincides with canonical
(already sorted); for Erdős, whose native order is a BFS, it is the sorted form, exactly Herbst's
`edge_list, sort (s,t)` baseline.

The earlier position-preserving definition (swap symbols, keep positions, so the text looks
unsorted) is retained as `relabel: {sort: false}` for an ablation; the reported runs did not use it.

### 4.2 `order` — permutes positions only

`reorder()` never touches `label_map`; it only permutes `node_seq` and/or `edge_seq`.

Herbst's four orderings presuppose edges are `(source, target)` pairs in a flat list. For an
**adjacency list** there is no "target column" to sort by, so `t_sorted_s_shuffled` is undefined
there. Rather than silently doing something arbitrary, adjacency lists get their own
two-dimensional ordering — which *lines* appear in what order, and which *neighbours* within a
line — and requesting an edge-list ordering on an adjacency list raises `ValueError`.

```
lines_shuffled:      node_seq [4, 2, 0, 3, 1]   edge_seq unchanged
    "Node 4 is connected to nodes 0. / Node 2 is connected to nodes 0. / Node 0 is connected to nodes 1, 2, 3, 4. ..."

neighbors_shuffled:  node_seq unchanged          edge_seq [[0,3],[0,2],[0,4],[0,1]]
    "Node 0 is connected to nodes 3, 2, 4, 1. ..."
```

### 4.3 `structure` — same content, different container

Toggles `edge_list` ↔ `adj_list`, or sets `replicated`. All four record fields except
`params.structure` are untouched:

```
In an undirected graph, (i,j) means that node i and node j are connected with an undirected edge.
G describes a graph among nodes 0, 1, 2, 3, and 4.
The edges in G are: (0, 1) (0, 2) (0, 3) (0, 4).
```

`replicated` is offered **only for undirected edge lists**, because an adjacency list inherently
lists every undirected edge from both endpoints — replication is not a free choice there.

### 4.4 `syntax` — same content and order, different notation

```json
{"directed": false, "adjacency": {"0": [1, 2, 3, 4], "1": [0], "2": [0], "3": [0], "4": [0]}}
```

**PyG (`edge_index`) is deliberately omitted.** Its representation always stores both directions of
an undirected edge, so adding it would change syntax *and* replication — two axes. It could be
reinstated as an explicitly-labelled two-axis variant, but not as a clean syntax perturbation.

---

## 5. Determinism

Every random draw is seeded from *what is being perturbed*, never from a global RNG:

```python
def _rng(*parts):
    return random.Random(int(sha256("instance_id|axis|kind|seed".encode()).hexdigest()[:16], 16))
```

Consequences:

* Regeneration is byte-identical (verified: matching MD5s for both the GraphQA and Erdős configs).
* Adding a task, or changing loop order, does not disturb any existing variant.
* `relabel(seed=0)` on one graph is independent of every other graph, so no accidental correlation
  across instances.

This is why `variants.jsonl` is not tracked in git while `instances.jsonl` is — variants are a pure
deterministic function of the instances.

---

## 6. Two guards that protect the measurement

**No-op variants are dropped, not counted.** Applying `sorted_st` to an already-sorted canonical
edge list yields identical text. Scoring that as "the model answered identically" would be free
credit inflating the invariance score. `make_variants` detects `axes_differing == ∅` and discards
the variant.

**The perturbation must reach the question and the answer.** A relabeling is not only a change to
the graph text. In the example the question becomes *"What is the degree of node **2**?"* — the
query node is renamed too, or we would be asking about a different node than the ground truth
describes. Symmetrically, when a model answers `2`, scoring maps it back through the inverse label
map before comparison. **All correctness comparison happens in canonical label space.**

---

## 7. How a variant reaches each of the three modes

The same `Variant` object serves three different consumers, which is what makes the transcription
control possible:

| Consumer | Built by | Used for |
|---|---|---|
| prompt text | `render(v)` | M1 `direct`, M2 `code` |
| plain `nodes` / `edges` lists | `v.node_seq`, `v.edge_seq` | M3 `graph_as_code`, injected into the program's namespace |
| the normalized true edge set | `true_edge_set(v)` | checking the graph M2's program declared and built |

M3 is injected with the **same two plain lists the template asks M2 to write**, in the variant's
labels and emission order — not with a pre-built `networkx` object. That is deliberate: a live `G`
would impose a representation on M3 that M2 does not have, and the two modes would then differ in
representation as well as in transcription. Injecting the lists keeps them a minimal pair, and keeps
M3 identical in both library arms. (`to_nx(v)` still exists, but only for computing ground truth and
comparisons on our side.)

Relabeling and edge ordering are carried into the injected lists. But **syntax and structure cannot
reach M3 at all** — there is no text for them to affect.

That asymmetry is intentional, and it is the localization instrument:

* M2 performs transcription **and** solution logic; all four axes reach it.
* M3 performs solution logic only; only `relabel` and `order` reach it.
* `frac_identical(M2) − frac_identical(M3)` on a shared axis, **within one library arm**, therefore
  measures **how much invariance the transcription step costs**. The library is held fixed across
  the difference; it is a crossed factor, not a fifth serialization axis.

A useful side effect: M3's prompt for a syntax variant is byte-identical to its canonical prompt,
so the response cache deduplicates them. This is why M3 collapses from 8,925 prompts to 231 unique
API calls per arm on the GraphQA config.

The same effect has a sharper edge for tasks whose **question** also names no node (`cycle_check`,
`node_count`, `has_cycle`, `density`, …): there the M3 prompt is identical across every instance in
the dataset too, so one reply is executed against every graph. M3's invariance on those tasks is
then 1.0 by construction rather than by measurement. The tables report `n_calls` beside `n` so this
is visible — see [analysis-and-metrics.md](analysis-and-metrics.md) §8.

`true_edge_set(v)` normalizes labels (`"3"` and `3` compare equal) and, for undirected graphs,
sorts each pair — so a program that builds the right graph is credited regardless of how it happened
to order or type its nodes.

---

## 8. Resolved tension: relabeling and sortedness

An earlier version preserved positions when relabeling, so a relabeled text read
`nodes 2, 4, 3, 1, and 0` while canonical read `nodes 0, 1, 2, 3, and 4`. Formally single-axis, but
a model saw both new names *and* an unusually unsorted presentation, so a measured drop could not be
attributed to label identity alone.

Reading Herbst et al. closely resolved it: they relabel **and then sort**, comparing across
relabelings that are all sorted. Adopting that convention (§4.1) removes the presentation confound
and makes our relabel axis directly comparable to theirs. The position-preserving definition
survives as the `sort: false` ablation; running both would tell whether any relabel effect is about
label identity or about tidiness, but the reported runs used only the sorted form.

---

## 9. Code map

| File | Responsibility |
|---|---|
| [`serial/variant.py`](../src/gsi/serial/variant.py) | `Variant`, `canonical()`, the four transforms, `axes_differing()`, `make_variants()`, `to_nx()`, `true_edge_set()` |
| [`serial/render.py`](../src/gsi/serial/render.py) | ten renderers, one per (syntax, structure) pair |
| [`serial/parse.py`](../src/gsi/serial/parse.py) | text → edge set; used only by tests |
| [`tests/test_variants.py`](../tests/test_variants.py) | round-trip, single-axis guard, permutation and ordering properties |

**Verification.** For every canonical form × every axis, the tests assert
`parse(render(v)) == true_edge_set(v)` — every rendering can be read back to the correct graph — plus
`axes_differing(v, canon) == {v.axis}`, that the inverse label map recovers the canonical edge set,
that a relabel is a genuine permutation reproducible from its seed, and that each ordering kind has
the property it claims (e.g. `s_sorted_t_shuffled` really does leave the source column sorted).

---

## 10. Configuration

Axes are requested per dataset in the experiment YAML. The M1/M2 reference is an edge list on both
datasets; `configs/erdos.yaml` requests:

```yaml
variants:
  relabel:   {seeds: 3}                 # sort: false -> the position-preserving ablation
  order:     {kinds: [sorted_st, s_sorted_t_shuffled, shuffle_all], seeds: 1}
  structure: {toggle: true, replicated: true}
  syntax:    {kinds: [json, networkx_code]}   # also the rungs of the transcription ladder
```

Both datasets start from an **edge list**, so they share Herbst's edge-list ordering
kinds; the `structure` toggle produces the adjacency-list form (GraphQA's "incident" encoder) as a
variant. Erdős's reference is its **native prompt serialization**, which our renderer reproduces
byte-for-byte on all 2,400 rows — the baseline Herbst et al. measured against, so our perturbations
start from the same point theirs did.
