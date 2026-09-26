# The execution sandbox

Running model-written code, and — the part that matters — recovering the graph it actually built.
Source: [`src/gsi/exec/sandbox.py`](../src/gsi/exec/sandbox.py) (host) and
[`src/gsi/exec/runner.py`](../src/gsi/exec/runner.py) (guest).

---

## Execution environment

Every reported M2 and M3 program ran locally, one subprocess per program (§2). A containerized
runner — a fixed **Linux Docker image with pinned Python, NetworkX, and dependency versions**, with
execution state reset per program — was designed as the next step for isolation (§5) but was not
built.

The API returns code; **our pipeline executes it** and captures answers, errors, and graph metadata.
M2 fills the template's `nodes` / `edges` slots and then writes the solving code; M3 gets those two
slots pre-filled by the harness and writes only the solving code. Both use the same runtime and
resource limits, and each runs once per library arm.

**Prior work:** [3] executes pandas queries over a preloaded graph table and feeds their outputs
back to the model in an iterative loop; its paper does not specify Docker
([Appendices E–F](https://arxiv.org/pdf/2509.18487#page=20)). Beyond our original references,
[EvalPlus](https://github.com/evalplus/evalplus#-quick-start) documents generation followed by
execution in Docker. These support the approach without implying identical experimental setups.

**Implementation status:** the sections below describe the subprocess runner that produced every
reported result; §5 lists what a container runner would add.

## 1. Two jobs, only one of them obvious

The obvious job is running untrusted-ish code without hanging the pipeline.

The job that makes the research question answerable is the second one: **recover what graph the
program was working with** and compare it to the truth. Without that, a wrong answer is just wrong.
With it, we can say whether the model copied the graph wrong (transcription), built the wrong
structure from a correct copy (construction), or had the right graph and reasoned badly (logic).
This is the mechanism behind the entire localization claim, and it is the thing prior work could
not do.

Two independent recoveries run on every program:

| Signal | Source | Available in |
|---|---|---|
| `declared_ok` | the template's `nodes` / `edges`, read back out of the namespace | both library arms |
| `construction_ok` | the networkx graph the program built, compared to what it declared | the networkx arm only |

`declared_ok` is the primary one and it is library-independent, which is why the template
([modes-and-prompts.md](modes-and-prompts.md) §3) replaced the networkx hook as the transcription
instrument. The hook remains, as the construction check and as a fallback for programs that ignore
the template.

## 2. Host / guest split

`runner.py` executes inside the subprocess and **imports nothing from `gsi`**. It receives a plain
`variant.json` and writes a plain `sidecar.json`. Consequences: the child starts with `python -I`
(isolated mode — no user site-packages, no `PYTHONPATH` inheritance) without needing our package
importable, and a model program that shadows a module name cannot disturb the harness.

```
sandbox.run(code, variant, mode, timeout=20, mem_mb=1024, cache_dir=...)
  ├─ tmpdir/code.py, tmpdir/variant.json
  ├─ Popen([python, -I, runner.py, tmpdir, mode], start_new_session=True, env=minimal)
  ├─ on TimeoutExpired: os.killpg(...)          ← kills the whole process group
  ├─ read tmpdir/sidecar.json
  ├─ normalize graphs, pick best match, set graph_match
  ├─ compare declared nodes/edges to the truth   → declared_ok
  ├─ compare the chosen graph to the declaration → construction_ok
  └─ static-analyse the source                   → ans_is_literal, reads_graph_vars
```

`start_new_session=True` plus `killpg` matters: a program that spawns children (or a runaway
`multiprocessing` pool) would otherwise leave orphans holding CPU after the parent is killed.

## 3. Recovering the model's graph

The mechanism is a monkey-patch installed before the model's code runs:

```python
for cls in (nx.Graph, nx.DiGraph):
    orig = cls.__init__
    def __init__(self, *a, **k):
        orig(self, *a, **k); registry.append(self)
    cls.__init__ = __init__
```

Patching `__init__` rather than scanning the namespace afterwards is what makes this robust. It
catches graphs built **inside functions**, assigned to any variable name, or never assigned at all
(`nx.Graph(edges).number_of_edges()`), and — because `DiGraph`, `MultiGraph` and `MultiDiGraph`
subclass through these constructors — every graph type. A namespace scan would miss all of those.

### The four awkward cases, and how each is handled

**Multiple graphs.** Models often build a scratch copy, or a subgraph. All registered graphs are
normalized and the one with the **highest edge-set Jaccard similarity** to the truth is chosen;
the count is recorded so an anomalous run is visible.

**Label type drift.** A program may use `"3"` where we use `3`. `norm_label` casts through float
when possible, so `3`, `3.0` and `"3"` normalize identically. Without this, correct programs would
be misclassified as transcription failures purely over typing.

**Directedness mismatch.** A model may build a `DiGraph` for an undirected task, adding both
directions. Edges are normalized as unordered pairs when the task is undirected, so such a program
still matches; `directedness_mismatch` is flagged for reporting rather than penalized.

**No networkx graph at all.** A program using a `dict` adjacency — or any program in the native arm,
by instruction — registers nothing. This used to mean `unverifiable`. It no longer does: the
template's `declared_ok` still gives a transcription verdict. What is lost is `construction_ok`
alone, and only for that program. `unverifiable` is still **reported as a rate**, never folded into
transcription or logic, but it should now be rare.

### M3 injection

For the inject mode the harness predefines two plain variables in the program's namespace before
execution — `nodes` (a list of labels) and `edges` (a list of `(u, v)` or `(u, v, w)` tuples), both
in the variant's labels and emission order — and nothing else. The model's program builds whatever
it wants from them.

Because the data is ours, `declared_ok` for M3 normally just echoes our injection. When it comes
back **false**, the model overwrote correct data, which is a construction error and not a
transcription one; the classifier says so explicitly rather than leaving it to a short-circuit.

### Recovery beyond networkx — resolved by the template

The hook only ever saw networkx graphs, so a program that kept the graph in a plain list or dict —
what CodeGraph's own sample programs do, and what the whole native arm does by instruction — was
invisible to it and landed in `unverifiable`. That was an open problem.

The template resolves it. `nodes` and `edges` are ordinary Python lists read straight out of the
namespace, so transcription is verifiable in both arms with no assumption about how the model went
on to represent the graph. `unverifiable` now requires the model to ignore the template slots
**and** build no networkx graph.

What remains library-dependent is `construction`, which genuinely needs an object to compare
against. In the native arm it is `None` and those failures are reported as `logic`. This is a real
limit of the design, not an oversight: the arms are never pooled
([scoring-and-classification.md](scoring-and-classification.md) §7).

## 4. Robustness details

**The answer is the variable `ans`, read from the namespace after execution** — CodeGraph's
contract. Printed output is captured for diagnosis but never consulted for the answer. If the
program raised, `ans` is discarded even if it had been assigned, matching CodeGraph's `exec_py`,
which appends `print(ans)` at the end and therefore gets nothing from a program that crashed.

**`nodes` and `edges` are read back even when the program raised.** `ans` is discarded on a crash,
but the declaration is not: the template assigns those two names *before* the solving code runs, so
a program that transcribed the graph correctly and then crashed still tells us the transcription
was fine. Without this, every crash would be an unexplained `execution` and the transcription
signal would be lost for exactly the runs most likely to have gone wrong.

**`ans_is_literal` is a static check on the source, not a runtime one.** `ast.parse` finds every
assignment to `ans`; the flag is true only when all of them are literal constants, **none of them
sits inside a compound statement**, and nothing ever mutates `ans` — by augmented assignment, by
a method call such as `ans.append(...)`, or by item assignment `ans[k] = v`. So `ans = 3` is a literal,
while `ans = 0` followed by `ans += 1` in a loop is not, and neither is `ans = False` at top level
with `ans = True` inside a branch. The second exclusion was learned the hard way: the first
detector lacked it, and the pilot's 24 `no_computation` records were *all* that cycle-check shape
— literal values, but the program chose between them. A literal is only hardcoding when nothing in
the program can change which one runs. `reads_graph_vars` (does the program ever read `nodes` or
`edges`?) is recorded alongside as a template-compliance diagnostic, but nothing is classified on
it: a program can ignore the slots and still compute the answer honestly.

**The sidecar is written in `finally`.** Whatever happens — exception, `SystemExit`, a model
calling `sys.exit(1)` — the sidecar exists, with stdout, stderr and the recovered graphs.

**stdout is captured, not inherited.** `contextlib.redirect_stdout` keeps model chatter out of our
logs and gives us the exact text to parse.

**Resource limits** (`RLIMIT_AS`, `RLIMIT_DATA`, `RLIMIT_CPU`) are best-effort, wrapped in
`try/except`: macOS enforces address-space limits inconsistently. The wall-clock timeout is the
reliable backstop; the rlimits are defence in depth.

**Edge dumps are truncated** at 20,000 edges with a `truncated` flag, so a pathological program
cannot write a gigabyte sidecar.

## 5. Isolation, and what a container runner would add

The existing subprocess runner is **not a security boundary**: it has no filesystem or network
isolation. Its minimal environment, `python -I`, temporary directory, and process-group timeout
handling help with accidental failures. The process-group cleanup uses Unix-specific APIs.

A container runner would need to disable network access, exclude credentials and host repository
mounts, run as a non-root user, and enforce time, memory, process-count, and output limits, with
grading kept outside the container and the reference graph hidden from M2 (only M3 receives `G`).
It involves container lifecycle, input/output transfer, cleanup, and isolation checks, not just
replacing the subprocess command, and its limits would be calibrated against correct solutions and
then fixed across M2/M3 runs.

## 6. Caching

Keyed on SHA-256 of `(CACHE_VERSION, inject, code, node_seq, edge_seq, directed, weighted)` — the
code **and** the graph it runs against, since the same program on a different variant is a different
execution. Re-running the exec stage costs nothing; re-scoring never re-executes.

`CACHE_VERSION` is bumped whenever `ExecutionResult` gains a field, so old entries are not served
missing the new one. It is at **3** (declaration recovery and the static checks). Identical
executions are also serialized behind a per-key lock and written through `atomic_write_text`, after
a real bug in which M3's syntax variants — which share both code and data — raced to write the same
cache file and produced torn JSON.

A container runner would also have to add the image/runtime version, runner version, and
execution limits to the cache key, so that environment changes cannot reuse stale execution results.

## 7. `ExecutionResult`

| Field | Use |
|---|---|
| `ans` | **the answer** — the formatted value of the variable `ans`, or null |
| `stdout` | diagnosis only |
| `stderr`, `exception` | diagnosis; last 4,000 chars kept |
| `exit_code`, `timed_out`, `wall_s` | → `execution` failure class |
| `declared_nodes`, `declared_edges` | what the model wrote in the template slots; read even on a crash |
| `declared_ok` | **the transcription verdict**; library-independent |
| `construction_ok` | declared graph vs. the graph actually built; networkx arm only |
| `ans_is_literal` | → `no_computation`; true only if `ans` is never computed |
| `reads_graph_vars` | template-compliance diagnostic; not classified on |
| `graphs[]` | per graph: class, directed, n, m, normalized edges, Jaccard |
| `chosen_idx`, `graph_match` | the recovered graph vs. the truth; the fallback verdict |
| `directedness_mismatch` | reported, not penalized |

## 8. What the tests pin down

[`tests/test_sandbox.py`](../tests/test_sandbox.py) runs one fixture program per outcome, all of
them template-shaped:

* the three-way localization — correct → `ok`; an edge missing from the declaration →
  `transcription`; a correct declaration built from a truncated list → `construction`; the right
  graph with a wrong formula → `logic`
* `ans = 3` → `no_computation` **even though the answer is right**; `ans = 0` with `ans += 1` →
  not a literal
* a crash after a correct declaration → `execution`, with `declared_ok` still true
* `while True` → `execution` via timeout, with bounded wall time
* off-template with no networkx → `unverifiable`; off-template *with* networkx → still localized
  through the recovered graph
* the native arm — transcription still separates, construction folds into `logic`
* the inject mode — data arrives in the variant's labels; overwriting it → `construction`, not
  `transcription`
* `DiGraph` on an undirected task → matched with the flag set; three graphs built → the right one
  chosen; string labels → normalized equal; the exec cache returning `cached=True` on the second call

These fixtures are the executable specification of the failure taxonomy. If the classification rules
change, they are where the change gets pinned.
