# Pipeline, configuration and caching

How a run is orchestrated, and why the caching design is a correctness property rather than a
convenience. Source: [`src/gsi/experiment/`](../src/gsi/experiment/).

---

## 1. Five stages

```
data      dataset          → GraphInstance      data/processed/<cfg>/instances.jsonl
variants  instance         → canonical + variants  data/processed/<cfg>/variants.jsonl
llm       (variant, mode)  → prompt → reply     results/<cfg>/responses/<model>.jsonl
exec      code             → sandboxed run      results/<cfg>/exec/<model>.jsonl
score     reply + exec     → correct, class     results/<cfg>/scored/<model>.jsonl
```

Selectable with `--stages`, which exists because the stages have different resource profiles.
`llm` is network-bound and costs money; `exec` is CPU-bound and free; `score` is pure computation.
So you can fetch replies once and re-score repeatedly while iterating on a comparator, or run `llm`
on one machine and `exec` on another.

```bash
python scripts/run.py --config configs/erdos.yaml --models hf-qwen3-8b-nscale --stages llm
python scripts/run.py --config configs/erdos.yaml --models hf-qwen3-8b-nscale --stages exec,score
python scripts/analyze.py --config configs/erdos.yaml
```

## 2. Configuration

The example below is `configs/graphqa.yaml`, abridged. It uses the decided reference encoding — an
edge list for both datasets ([the reference encoding](datasets.md#4-the-reference-encoding)).

```yaml
name: graphqa                    # names the data/ and results/ subtrees
datasets:
  graphqa:
    n_graphs: 100
    variants:                    # per-dataset override of the global block
      relabel:   {seeds: 3}
      order:     {kinds: [s_sorted_t_shuffled, t_sorted_s_shuffled, shuffle_all], seeds: 1}
      structure: {toggle: true, replicated: true}
      syntax:    {kinds: [plain, json, networkx_code]}
modes: [direct, code, graph_as_code]
libraries: [networkx, native]              # crossed with the code modes -> 5 calls per variant
# library_tasks: {native: [...]}           # optional: restrict an arm to a subset of tasks
models: [hf-qwen3-8b-nscale, hf-deepseek-v3.1-novita, hf-gemma-4-31b, hf-deepseek-v4-flash]  # --models overrides
exec: {timeout: 20, mem_mb: 1024, workers: 4}
```

**`libraries` is a separate key, not more mode names.** `cfg.arms_for(mode, task)` expands
`modes × libraries` into the (mode, library) pairs to run, yielding `None` for `direct`, which writes
no code. `library_tasks` narrows an arm to named tasks — the way to keep the native arm off tasks
where hand-written code has no realistic chance (max-flow, bridges) and would measure a floor effect
rather than fragility. Unset by default.

**Why `variants` can be overridden per dataset:** valid ordering kinds depend on the structure a
dataset starts from. Both references are edge lists, so both use Herbst's edge-list kinds
(`sorted_st`, `s_sorted_t_shuffled`, `t_sorted_s_shuffled`, `shuffle_all`); the adjacency-list kinds
(`lines_shuffled`, `neighbors_shuffled`) apply to the `structure` variant. Requesting a kind that
does not match the configured structure raises rather than silently doing something arbitrary.

Model definitions live separately in `configs/models.yaml` so experiment configs stay portable:

```yaml
hf-deepseek-v3:
  base_url: https://router.huggingface.co/v1
  api_key_env: HF_TOKEN
  model: deepseek-ai/DeepSeek-V3
hf-qwen3-8b:
  base_url: https://router.huggingface.co/v1
  api_key_env: HF_TOKEN
  model: Qwen/Qwen3-8B:featherless-ai
  extra: {extra_body: {chat_template_kwargs: {enable_thinking: false}}}
stub:
  provider: stub
```

Every provider is OpenAI-compatible, so DeepSeek's own API, OpenRouter, HuggingFace Inference
Providers and a rented GPU running `vllm serve` are all just different `base_url` values behind one
client class. Keys come from `.env` at the repo root (gitignored; `load_dotenv` never overwrites an
existing environment variable).

### HuggingFace Inference Providers — what was learned setting it up (2026-09-16)

One HF token reaches many third-party providers through `router.huggingface.co/v1`. Facts that
cost an afternoon and are not obvious from the docs:

* **The router picks the provider; a `:provider` suffix pins it.** `Qwen/Qwen2.5-7B-Instruct` is
  listed as served but the router answered *"not supported by any provider you have enabled"* —
  it is live only on `featherless-ai`, which the unsuffixed request would not route to. With the
  explicit suffix it works.
* **Qwen3 models think by default** and spend the whole `max_tokens` budget in a
  `reasoning_content` field, returning **empty `content`** with `finish_reason="length"`. Our client
  reads `content`, so every reply would have been a `format` failure. Two providers, two switches:
  `featherless-ai` honours `chat_template_kwargs: {enable_thinking: false}` through `extra_body`;
  `nscale` ignores that and needs Qwen3's `/no_think` soft switch in the prompt text. The second is
  sent through `ModelSpec.user_suffix`, appended at call time only, so the `Prompt`, its hash and
  the response log keep the shared model-independent text. What remains is an empty
  `<think>\n\n</think>` block (`reasoning_chars = 2` on every reply) — harmless.
* **The same model loops on one provider and not on the other.** Qwen3-8B on featherless
  degenerated on **29%** of the full GraphQA set (`the the the…`, or one edge pair repeated to
  4,096 tokens; 3% in the pilot, whose graphs were sparser), and those calls ate 68% of the wall
  time. The identical 40 prompts on nscale with `/no_think`: 0 loops. Greedy decoding at
  temperature 0 sits on a knife-edge for this model and the two inference engines fall on
  different sides of it. **`hf-qwen3-8b-nscale` is the entry to use**; `hf-qwen3-8b` (featherless)
  is kept, with its 5,400 cached replies, as a documented failure mode.
* **Providers cap concurrency differently.** featherless: a hard 10 concurrent requests per user
  (`429 concurrency_limit_exceeded`). nscale: 16 workers with no 429s and 263 calls/min. deepinfra:
  no 429s at 32 but latency climbs, so it is queuing.
* **`usage` now records `finish_reason`, `reasoning_chars` and `served_model`** so a truncated or
  thinking reply is visible in the response log rather than surfacing later as an inexplicable
  `format` failure.
* **Cost reporting differs by provider.** `deepinfra` (DeepSeek-V3) and `together` (Llama) return
  `usage.estimated_cost` per call, so their spend is exact; `featherless-ai` returns none and has to
  be estimated from tokens at the provider's list price. Rates observed / assumed:

  | Model | Provider | $/M input | $/M output | Source |
  |---|---|---|---|---|
  | DeepSeek-V3 | deepinfra | 0.32 | 0.89 | solved from 19 reported costs, residual ~1e-19 |
  | Qwen3-8B | featherless-ai | 0.117 | 0.455 | featherless price list (not reported per call) — **loops on 29% of prompts; do not use** |
  | Qwen3-8B | nscale | — | — | not reported per call |
  | Llama-3.1-8B | together | ~0.05 | ~0.08 | reported per call |

* **Credits.** A free HF account gets **$0.10/month**; PRO gets $2. Beyond that the API keeps
  working only after purchasing credits (pay-as-you-go, billed at the provider's rate with no HF
  markup). The full run is far beyond free credits — see §5. Spend is visible at
  `huggingface.co/settings/inference-providers/overview`, not through the API.

## 3. Caching, in three layers

**Execution deployment:** M2/M3 programs ran in local subprocesses; the container design in
[execution-sandbox.md](execution-sandbox.md#execution-environment) was not used for the reported
runs. The API stage is separate.

**Layer 1 — LLM responses**, keyed on SHA-256 of `system + user`, stored under
`results/cache/<model>/<hash>.json`. Model-independent by construction, so identical prompts are
never re-billed within a model — and this is what makes M3 collapse from 14,246 Erdős prompts to 886
unique calls, since its syntax and structure variants produce byte-identical prompts.

**Layer 2 — executions**, keyed on `(mode, code, graph)`. Re-running `exec` costs nothing;
re-scoring never re-executes.

A move to containers would have to add the image/runtime version, runner version and limits to
this key, so that a changed environment cannot reuse stale results.

**Layer 3 — record ids.** Each JSONL sink loads the ids it already contains and skips them, under a
lock for thread safety. Rows are appended and flushed per record, so a `Ctrl-C` or a crash loses at
most the in-flight call.

The three layers are complementary: caches survive across configs and runs, the sink guard makes a
single run resumable. Together they mean **a re-run costs nothing and an interrupted run resumes**.
With a fixed budget shared by four people, that is what makes it safe to scale up incrementally
rather than betting a full run on untested code.

## 4. Concurrency and retries

One `ThreadPoolExecutor` per model sized by `max_concurrency` (per-provider rate limits differ).
Retries use exponential backoff with jitter on `429`, `5xx`, connection errors and timeouts;
non-retryable status codes raise immediately rather than burning the retry budget. A failed record
is logged and skipped, not fatal — one bad prompt should not lose 20,000 completed ones.

The `exec` stage uses its own CPU-sized pool, independent of API concurrency.

## 5. Cost control

`--estimate` builds data and variants, then reports prompt counts and rough token volume per mode
**without making a single API call**:

```
config graphqa: 700 instances, 8925 variants
  direct                    8925 prompts,    8160 unique, ~1.50M input tokens
  code/networkx             8925 prompts,    8160 unique, ~2.83M input tokens
  code/native               8925 prompts,    8160 unique, ~2.98M input tokens
  graph_as_code/networkx    8925 prompts,     231 unique, ~0.05M input tokens
  graph_as_code/native      8925 prompts,     231 unique, ~0.06M input tokens
  per model: 24942 API calls, ~7.42M input tokens (+ outputs); x 2 models = 49884 calls
```

The gap between "prompts" and "unique" is cache deduplication made visible — and for M3 it is
dramatic: 8,925 prompts collapse to 231 calls, because M3 shows no graph text, so every `syntax` and
`structure` variant of an instance is the same prompt, and for a task whose question names no node
every *instance* is the same prompt too. The scored rows carry `prompt_hash` and the tables report
`n_calls` so this stays visible in the results
([analysis-and-metrics.md](analysis-and-metrics.md) §8). `--limit N` caps new
prompts per model for eyeballing real output before committing to a full run.

### Estimated cost and time (pilot, 2026-09-17)

Per-call averages from the pilot, scaled by the unique-call counts above. These estimates planned
the full run:

| Model | $/M in | $/M out | avg $/call (code arm) | **full run, both datasets** | median latency | **wall time at concurrency 4 / 16** |
|---|---|---|---|---|---|---|
| DeepSeek-V3 (deepinfra) | 0.32 | 0.89 | ~0.00044 | **≈ $28** | 20 s | **≈ 95 h / 31 h** (32: ≈ 23 h) |
| Qwen3-8B (featherless) | 0.117 | 0.455 | ~0.00024 | ≈ $17 | 7 s, 47 s when looping | ≈ 35 h at its cap of 8–10, 29% unusable |
| **Qwen3-8B (nscale)** | — | — | — | not reported per call | **3.1 s** | **≈ 4 h at 16** (263 calls/min measured) |

So roughly **$45 for both models on both datasets** — well beyond a free HF account's $0.10/month
of credit, so the run required purchased credits. And **wall time, not money, was the binding
constraint** for DeepSeek. Measured on 64 uncached calls per level, with zero retries: 11.5
calls/min at concurrency 4, 35.5 at 16, 48.6 at 32 — with median latency rising from 17 s to
23 s at 32, so the provider is queuing and returns diminish; 16 became the default. The models
run as separate processes, and the run is resumable at every stage, so it can be done in pieces
without loss. Featherless does not report cost
per call, so the Qwen figure is list price × measured tokens; deepinfra does, and its rate was
solved from 444 reported costs with a residual of ~1e-19.

## 6. Recommended workflow

1. `--estimate` — know the cost.
2. `--models stub` — full pipeline, zero API calls, confirms the config is valid.
3. **`configs/pilot.yaml`** — the full pipeline on a slice of both datasets (20 instances, 140
   variants, 444 unique calls per model) with real models; **read the raw programs by eye**. This
   is the step that catches prompt-compliance problems the stub cannot simulate.
4. Full `--stages llm`, then `exec,score`, then `analyze.py`.

Step 3 is not optional, and the first pilot (2026-09-16/17, DeepSeek-V3 and Qwen3-8B via the HF
router) is the proof: it found three things the stub could never have shown.

* **`no_computation` was firing on false positives — 25 of 25.** Two shapes. The common
  cycle-check shape is `ans = False` at top level and `ans = True` inside a loop: both literals,
  but the program decides which one runs. And the bridges shape is `ans = []` at top level grown
  by `ans.append(...)` inside a DFS: a literal start, mutated in place. The detector now treats a
  literal nested in any compound statement, or one mutated by a method call or item assignment,
  as computed ([execution-sandbox.md](execution-sandbox.md) §4). After the fix: zero
  `no_computation` on either model, and one real `transcription` failure that had been hiding
  underneath.
* **The graph text changes the program, not just the transcription.** On the `networkx_code`
  rung — where the graph is shown as `import networkx as nx / G = nx.Graph() / …` — DeepSeek-V3
  omitted `import networkx` from its own program in **16 of 20** records (16 of 120 elsewhere),
  and every one of those failed with `NameError`. It sees the import in the prompt and leaves it
  out of the code. That is a serialization effect on the solving code itself, it lands in
  `execution` rather than `transcription`, and it is why the ladder reports every class per rung
  rather than accuracy alone.
* **Qwen3-8B in non-thinking mode degenerates on some prompts at temperature 0** — the reply
  opens *"Okay, I have to be honest about the code…"* and repeats until `max_tokens`. It is
  deterministic, reproduces exactly, and neither `presence_penalty` nor `repetition_penalty`
  breaks it; only Qwen's recommended sampling (`temperature 0.7`) does, and only sometimes. About
  3 of 444 prompts. Qwen2.5-7B-Instruct answers all of them cleanly at temperature 0. This is a
  model defect, not a serialization effect, and it would masquerade as non-invariance because it
  hits some variants of an instance and not others. Every scored row now carries `finish_reason`
  so such records can be flagged or excluded explicitly.
* **An isolated node becomes `(17,)`.** On the adjacency-list `structure` variant both models
  sometimes transcribe *"Node 17 is not connected to any node"* as a one-element tuple in `edges`,
  which crashes on unpacking. It is classed `execution` with `declared_ok = None`, since a
  malformed pair is not a readable declaration. Three records in the pilot; a transcription
  artefact that the strict reader declines to guess at.
* **`nx.has_cycle` does not exist.** Qwen3-8B hallucinated it in its M3 cycle-check program —
  and because the M3 cycle-check prompt is instance-independent, that *one* reply became 21
  `execution` records across 3 graphs × 7 variants. DeepSeek-V3 did not; its M3 arms scored
  1.000 in both libraries. `n_calls` in the tables is what makes this
  legible ([analysis-and-metrics.md](analysis-and-metrics.md) §8).

What the pilot confirmed, which had been the largest untested assumption in the design: **both
models fill the template.** `declared_ok` was readable on 96–100% of code-arm records in every
arm, the native arm obeyed the library instruction (BFS with `deque`, no networkx), and
`construction_ok` separated in the networkx arm exactly as specified.

## 7. What is tracked in git

| Path | Tracked | Why |
|---|---|---|
| `data/processed/*/instances.jsonl` | **yes** | pins which graphs and tasks were sampled, so an upstream change to the HuggingFace Erdős dataset cannot silently alter results |
| `data/processed/*/variants.jsonl` | no | deterministic function of instances; 26 of 29 MB |
| `results/cache/**`, `responses/`, `exec/`, `scored/` | no | large, regenerable, machine-specific |
| `results/*/tables/`, `results/*/figs/`, `results/review/` | **yes** | the reported results; `scripts/verify.py` regenerates the tables from the published records |
| `.env` | no | secrets |

Regeneration was verified byte-identical (matching MD5s) for both dataset configs, which is what
justifies not tracking the derived files.

⚠️ **A gitignore lesson worth keeping.** An early rule was `data/` with no leading slash. Git
matches such patterns **at any depth**, so it silently excluded `src/gsi/data/` — the dataset
loaders — from a commit. The pushed tree imported three modules it did not contain, and local tests
passed the whole time because the files existed on disk. Always anchor directory ignores
(`/data/`, or a specific subpath) and verify a fresh clone actually runs.

## 8. The stub model

`provider: stub` returns canned programs with deterministic failure behaviours selected from the
prompt hash (`correct`, `wrong_logic`, `drop_edge`, `crash`, `timeout`, `no_nx`, `bad_format`), in a
weighted mix that exercises every failure class. A single behaviour can be forced for targeted
testing.

It exists so the entire pipeline — prompting, execution, graph recovery, scoring, classification,
tables, figures — is exercised for free before any budget is spent, and so the end-to-end test
(`tests/test_e2e_stub.py`) and `scripts/verify.py` need no model API. Its numbers are meaningless as results; see
[analysis-and-metrics.md](analysis-and-metrics.md) §10.
