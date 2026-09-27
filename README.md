# How Invariant is Code Generation to Graph Serialization?

Ram Kedem, Yehonatan Barel, Ido Azoulay, Dolev Abudi — course project, Machine Learning with Graphs.

A graph can be written as text in many equivalent ways. We ask whether an LLM that solves a graph
problem **by writing code** returns the same answer for every equivalent serialization, and when it
does not, where the error enters: copying the graph into the program (transcription), building a
graph from that copy (construction), or the solution logic. Each instance from GraphQA and Erdős is
serialized along four axes (`relabel`, `order`, `structure`, `syntax`) and put to four models in
three modes: direct answer, code, and code with the graph injected by us (the control).

**Main finding:** code generation improves observed robustness over direct answering, but the
benefit depends on model, task interpretation, and graph presentation.

## Where things are

| Path | Contents |
|---|---|
| `src/gsi/` | The pipeline: data, serialization, prompts, model client, sandbox, scoring, analysis |
| `configs/` | Experiment configs (`graphqa.yaml`, `erdos.yaml`) and model endpoints (`models.yaml`) |
| `scripts/` | Entry points (`run.py`, `analyze.py`), one script per follow-up experiment, `verify.py` |
| `data/processed/*/instances.jsonl` | The sampled graphs, tasks and ground truth |
| `results/` | Tables and figures per dataset and per follow-up run, repeat-prompt floors (`floor*.json`), and read-only audits (`review/`) |
| `tests/` | Test suite |

The scored records and raw model replies are published on Hugging Face:
[Dolevabudi/graph-serialization-invariance](https://huggingface.co/datasets/Dolevabudi/graph-serialization-invariance)
(Qwen3-8B, DeepSeek-V3.1) and
[Yonibarel/graph-serialization-invariance](https://huggingface.co/datasets/Yonibarel/graph-serialization-invariance)
(Gemma 4 31B, DeepSeek-V4-Flash).

## Setup and verification

Python 3.10 or later.

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -e ".[erdos,dev]"
python scripts/verify.py
```

`verify.py` makes no paid model calls. It runs the tests, runs the whole pipeline on an offline stub
model, downloads the published records (sha256-checked), reruns the analysis on them, and compares
every regenerated table with the committed one. It takes about 20 minutes.

## Running the pipeline

```bash
python scripts/run.py --config configs/smoke.yaml              # offline stub model, a few minutes
python scripts/analyze.py --config configs/smoke.yaml
```

Real models need an API key in `.env` (see `.env.example`); pass them with `--models`, using the
names in `configs/models.yaml`. Every stage is cached and resumable.
