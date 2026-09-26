# Interaction modes and the prompt contract

The ways a graph problem is put to a model, the exact wording each one uses, why the injected mode
is a *minimal pair* with the code mode, and why the solving library is a separate axis rather than
a fourth mode. Source: [`src/gsi/prompts/modes.py`](../src/gsi/prompts/modes.py).

---

## 1. The three steps a code-generating model performs

When an LLM solves a graph problem by writing code from a serialized graph, it does three separable
things:

**(a) Transcription** — read the text and write the graph down as data in the program.
**(b) Construction** — turn that data into whatever structure it will compute over.
**(c) Solution logic** — choose an algorithm and write code that produces the answer.

A wrong answer can come from any of the three. The mode design and the template are how we tell
them apart; the taxonomy that names them is in
[scoring-and-classification.md](scoring-and-classification.md).

## 2. Three modes, two of them crossed with a library

| Mode | Graph arrives as | Model produces | Transcribes? | Library arm | Wording from |
|---|---|---|---|---|---|
| `direct` (M1) | text | reasoning ending in `\boxed{…}` | — | none | G1 / Herbst |
| `code` (M2) | text | a filled template between `# CODE START` / `# CODE END` | **yes** | networkx \| native | CodeGraph |
| `graph_as_code` (M3) | pre-filled `nodes`, `edges` | the same template, those two lines already filled | **no** | networkx \| native | M2 with the graph text removed |

`library` is a **separate field on every record**, not part of the mode name. It is crossed with the
two code modes, so one variant costs **five calls**: 1 × M1 + 2 × M2 + 2 × M3.

Why a field and not four mode names: the library and the mode are independent dimensions. Folding
them into one string would force every `mode in CODE_MODES` test to enumerate the cross product, and
every analysis to recover the two dimensions by parsing. Keeping them apart means the membership
tests never grow, and `groupby` either includes `library` (to separate the arms) or omits it (to
pool them). See [analysis-and-metrics.md](analysis-and-metrics.md) §2.

> A bug this shape already cost us once: `classify.py` compared `mode == "graph_as_code"` while the
> configs ran `graph_as_code_0shot`, so the branch never fired for the mode actually in use — and the
> test pinned the unused name, so the suite stayed green. That is the failure mode the field
> prevents.

**One-shot modes were removed.** `code_1shot` and `graph_as_code` (the exemplar variants) are gone
along with `prompts/exemplars.py`. The template below does what the worked example did — it fixes
the program's shape — and does it identically in both library arms, which an exemplar could not.
They were removed before any of the reported runs.

**Execution environment.** The API returns code; our pipeline executes it, one local subprocess per
program, and collects the result — see [execution-sandbox.md](execution-sandbox.md#execution-environment).

**Serialization.** M1 and M2 receive the *same* graph text for a given variant; only their solving
instructions differ. That text is the edge-list "adjacency" wording — see
[datasets.md](datasets.md#4-the-reference-encoding) for why, and for the incident alternative that
was rejected. M3 receives no text at all, so the choice does not touch it.

## 3. The template, and why it exists

Both code modes hand the model the same skeleton:

```
# CODE START
nodes = <the nodes of G>
edges = <the edges of G, as (u, v) pairs>

<your code here>
ans = <the computed result, a Python int>
# CODE END
```

Three properties make this the load-bearing piece of the design:

**The transcription becomes readable.** `nodes` and `edges` are always assigned, always first,
always by that name. The harness reads them back out of the namespace and compares them to the
graph the model was shown. That comparison is the transcription measurement, and it needs no
networkx and no inference about what the program meant.

**It survives a crash.** The slots are assigned before the solving code runs, so a program that
transcribed correctly and then raised still tells us the transcription was fine.

**It is the same skeleton in both arms.** A worked example written in networkx would have steered
the native arm toward networkx. A slot named `edges` steers nobody.

**The answer slot names a type, not a value.** An earlier draft read `ans = <your answer>`, which
invites `ans = 3` — the model reasoning it out in prose and typing the number in. The slot now
describes the computation, and the instruction says *"Compute the result - do not write it
directly."* Programs that write a literal anyway are caught and classed `no_computation`; the
detector is in [execution-sandbox.md](execution-sandbox.md) §4.

## 4. M2 and M3 are a minimal pair

M3 receives the identical prompt with two changes: the declaration lines are replaced by a comment
saying the variables already exist, and the graph text is gone.

```
# CODE START                       # CODE START
nodes = <the nodes of G>           # 'nodes' and 'edges' are already defined.
edges = <the edges of G, ...>
                                   
<your code here>                   <your code here>
ans = <the computed result, ...>   ans = <the computed result, ...>
# CODE END                         # CODE END
        M2                                  M3
```

Same task line, same CodeGraph instruction, same library sentence, same `Q: … A:` layout, same `ans`
contract. The only difference is **who fills in `nodes` and `edges`**. That is precisely "with
transcription" versus "without transcription", and nothing else.

This is what fixes an isolation problem the earlier design had. When M2 was free-form and M3
injected variables, M3 imposed a representation that M2 did not — so the two modes differed in the
graph representation *as well as* in transcription, and the gap between them could not be read as
the cost of transcription alone. The template fixes the representation in both arms, turning it from
a confound into a constant.

**Which axes reach M3.** The injected lists carry the variant's labels and its emission order, so
`relabel` and `order` reach M3. `syntax` and `structure` cannot — there is no graph text for them to
change — so M3's prompts for those variants are byte-identical to canonical and the cache
deduplicates them. That is intended: M3 is the control.

**A consequence to keep in view.** For a task whose question names no node — `cycle_check`,
`node_count`, `edge_count`, `has_cycle`, `is_bipartite`, `density`, `diameter` — the M3 prompt
contains nothing instance-specific at all. Every graph and every variant in the dataset collapses to
**one** prompt and therefore one model reply, executed against each graph's injected data. Cheap,
and correct, but it means M3's invariance on those tasks is 1.0 by construction rather than by
measurement, and M3's accuracy there rests on a single reply. The scored rows carry `prompt_hash`
and the tables report `n_calls` beside `n` so this is visible rather than buried
([analysis-and-metrics.md](analysis-and-metrics.md) §8).

## 5. The library axis

| Arm | Sentence appended to the prompt |
|---|---|
| `networkx` | *"You may use the networkx library."* |
| `native` | *"Use only plain Python and its standard library. Do not import networkx or any other third-party library."* |

That sentence is the **only** difference between the two prompts — pinned by
[`tests/test_modes.py`](../tests/test_modes.py).

**Why the axis exists.** Every prior result we build on is a networkx result. CodeGraph's exemplars
are plain Python; Fatemi's ground truth is networkx; our own transcription check began as a
networkx hook. If fragility turns out to be a networkx-specific phenomenon — say, `nx.Graph()`
silently accepting a malformed edge list — that is a fact about a library, not about serialization.
Running both arms is what separates the two.

**What the arms cost.** `construction` is only separable in the networkx arm, because it needs a
graph object to compare the declared data against. The native arm has no such object, so its
construction errors are reported as `logic`. **Never pool the two arms' failure decompositions** —
the columns do not mean the same thing. The tables keep `library` in the key for exactly this
reason.

**Restricting an arm.** `library_tasks` in the experiment YAML limits an arm to named tasks, which
is how the native arm can be kept off tasks where hand-written code has no realistic chance
(max-flow, bridges) and would produce a floor effect rather than a measurement. Unset by default.

## 6. The transcription ladder

The M2 prompt is identical across rungs except for the graph block; the fourth rung removes it:

| Rung | Graph block | Copying effort |
|---|---|---|
| 1 prose | `G describes a graph among nodes 0, 1, … The edges in G are: (0, 4) (1, 6) …` | parse sentences |
| 2 json | `{"directed": false, "nodes": [...], "edges": [[1, 2], ...]}` | parse JSON |
| 3 networkx code | `G = nx.Graph(); G.add_edges_from([(1, 2), ...])` | copy-paste |
| 4 injected (M3) | *(none)* — `nodes`/`edges` pre-filled | none |

Reading the transcription-failure share down the ladder isolates the cost of copying while the
model's knowledge of the graph is held constant across rungs 1–3. The ladder is built from the
`syntax` axis at canonical labels and order, so consecutive rungs differ in the graph text alone.

## 7. Answer contracts, per mode

| Mode | Contract | Extraction | Fallback |
|---|---|---|---|
| M1 | G1's suffix: *"The last line of your response should be of the following format: 'Therefore, the final answer is: $\boxed{ANSWER}$.'"* | last `\boxed{}` | G1's own: text after *"the [final] answer is"* — nothing else |
| M2 / M3 | CodeGraph's: *"return the answer in a variable `ans`"* between `# CODE START` / `# CODE END` | run the program, read `ans` | **none.** No markers → no code; no `ans` → no answer. Printed output is ignored. |

These mirror the source pipelines exactly. CodeGraph's `exec_py` takes the code between the markers
(no fence fallback), appends `print(ans)`, and treats a missing `ans` as a failure. G1's
`correctness_check.py` takes the last `\boxed{}` with the *"the answer is"* regex as the only
fallback. A program that crashes after assigning `ans` gets no answer, as in CodeGraph.

Invariance is compared within a mode and within a library arm, so different contracts across modes
cannot distort it.

## 8. Prompt assembly, with sources

**System message.** M1: `You are a helpful assistant.` Code modes: CodeGraph's Table 6 role text
(*"You are an expert in graph networks and Python programming…"*).

> The M1 system prompt is **ours, not G1's** — G1 sets no system prompt at all. We use a neutral
> one so that M1 and the code modes both have one and the comparison is not confounded by its
> presence. This asymmetry (neutral vs. expert role) is a deliberate fidelity choice: each mode
> keeps its source paper's own framing. Worth stating in the write-up.

**User message, code modes:**
```
<task definition>                 Erdős preamble, or "For this task, please <task> in the undirected graph G."
Write a piece of Python code to return the answer in a variable 'ans'. Please enclose the code
with # CODE START and # CODE END.        [+ directed / weighted notes]

Fill in the template below and keep its structure. <slot instructions>
Compute the result - do not write it directly.

# CODE START ... # CODE END       the template; M3's has the two slots pre-filled

<library sentence>                "You may use the networkx library." | "Use only plain Python ..."

Q: <question, in the variant's labels>
<graph text>                      omitted in M3
A:
```

**User message, M1:** `[preamble]` + graph text + `Question: …` + the dataset's own format sentence
(Erdős carries one; GraphQA gets the equivalent Erdős-style sentence) + the G1 suffix.

The question is rewritten in the variant's labels; scoring maps answers back
([permutation-design.md](permutation-design.md) §6). `prompt_hash` = SHA-256 of system + user,
model-independent, so the two library arms of one variant never collide in the cache.

## 9. What M3 is, and is not

It is a single-turn adaptation. Finkelshtein's Graph-as-Code is a multi-turn loop over a pandas
DataFrame on node-classification graphs too large to serialize; ours is one program on graphs of at
most 34 nodes. Single-turn keeps one prompt hash per record, deterministic and cacheable. The
write-up should say "adapted from", not "reproduces".

Because M3 cannot mis-copy, its residual variation under `order` measures sampling nondeterminism,
not serialization sensitivity. The repeated-prompt floor (`scripts/nondeterminism_floor.py`,
[ANALYSIS.md](../ANALYSIS.md) §8.0) was measured for M1 and M2, not for M3.

## 10. Extension point: mitigation modes

`MODES` and the `_code` / `_direct` builders are the registry; a new mode is one builder and one
tuple entry. The candidates considered before the diagnosis:

| Mode | Idea | Use when |
|---|---|---|
| `M2_verify` | transcribe, assert node/edge counts and degree sequence against the prompt, then solve | transcription-dominated |
| `M2_canon` | canonicalize the serialization deterministically before prompting | transcription-dominated |
| `M2_vote` | majority over k relabelings | logic-dominated |

A free-form arm — the old un-templated M2 — was the other candidate, as a control for whether the
template itself changed the model's behaviour.

None of these became a mode. The mitigation phase ([ANALYSIS.md](../ANALYSIS.md) §8) implemented
canonicalization (E3) and voting (E2, E6) as scripts over the existing modes; `M2_verify` and the
free-form arm were not built.
