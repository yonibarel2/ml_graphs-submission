"""Publish the experiment's results to a private HuggingFace dataset repo, for the team.

    python scripts/upload_results.py <user-or-org>/<repo-name> [--public] [--with-cache]

Needs a token with **write** permission in HF_WRITE_TOKEN (or HF_TOKEN). The inference token
used for the runs has only `inference.serverless.write` and cannot create or push to a repo:
make one at https://huggingface.co/settings/tokens with "Write access to contents/settings of
all repos".

The repo is created **private** unless --public is passed. Results are pre-publication research
data; team members are added at
https://huggingface.co/datasets/<repo>/settings -> Collaborators.

What goes up, by default (~15 MB):
  tables/    the six analysis CSVs per dataset -- the actual results
  figs/      the five charts per dataset per model
  scored/    one row per (instance, variant, mode, library, model), gzipped: the analysis input
  data/      instances.jsonl per dataset -- which graphs and queries were sampled
  README.md  what the run was, which models/providers, how to read the files

With --with-cache it also uploads the raw replies as one tar.gz per model (~250 MB each), so a
teammate can re-score without paying for inference again.
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATASETS = ("graphqa", "erdos")


def gzip_to(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    with src.open("rb") as f, gzip.open(dst, "wb", compresslevel=6) as g:
        shutil.copyfileobj(f, g)


def readme(models: list[str]) -> str:
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                         capture_output=True, text=True).stdout.strip() or "unknown"
    lines = [
        "---", "license: mit", "tags: [graph-reasoning, llm-evaluation, serialization-invariance]",
        "---", "",
        "# Serialization-invariance audit of LLM graph code generation",
        "",
        "Does an LLM that solves a graph problem **by writing code** return the same answer under",
        "equivalent serializations of the same graph -- and if not, does the fragility enter when it",
        "**transcribes** the graph into its program, when it **constructs** a structure from that",
        "copy, or in the **solution logic**?",
        "",
        f"Produced by [`ml_graphs`]( https://github.com/ramramk/ml_graphs ) at commit `{rev}`.",
        "",
        "## Design",
        "",
        "Each instance (one graph + one task + one query) is rendered into several **equivalent**",
        "serializations differing in exactly one axis: `relabel`, `order`, `structure`, `syntax`.",
        "Every variant is put to the model in three modes, two of them crossed with a solving library:",
        "",
        "| mode | graph arrives as | transcribes? | library arms |",
        "|---|---|---|---|",
        "| `direct` (M1) | text | -- | none |",
        "| `code` (M2) | text + a fixed program template | **yes** | networkx, native |",
        "| `graph_as_code` (M3) | `nodes`/`edges` pre-filled by the harness | **no** | networkx, native |",
        "",
        "M2 and M3 are a minimal pair: the same template, differing only in who fills the two",
        "declaration lines. The M2-M3 difference is therefore the cost of transcription alone.",
        "",
        "## Models",
        "",
    ]
    for m in models:
        lines.append(f"* `{m}`")
    lines += [
        "",
        "Both served through HuggingFace Inference Providers at temperature 0. The provider is part",
        "of the identity: the same Qwen3-8B degenerated on 29% of prompts on one provider and 0% on",
        "another (see the repo's `docs/pipeline-and-caching.md`).",
        "",
        "## Files",
        "",
        "```",
        "tables/<dataset>/accuracy.csv             mean(correct) per dataset x task x mode x library x axis x model",
        "                 invariance.csv           frac_identical -- the headline metric, per instance then aggregated",
        "                 gap.csv                  M2 - M3 invariance, within a library arm = the cost of transcription",
        "                 ladder.csv               failure shares across prose -> json -> networkx code -> injected",
        "                 failures.csv             failure-class decomposition among code-mode failures",
        "                 silent_transcription.csv wrong graph, right answer",
        "tables/<dataset>/<model>/*.csv            model-specific exports from analysis with --models",
        "figs/<dataset>/*.png                      the same, plotted, one file per model",
        "scored/<dataset>/<model>.jsonl.gz         one row per record: every intermediate + the verdict",
        "data/<dataset>/instances.jsonl            which graphs, tasks and queries were sampled",
        "```",
        "",
        "### Reading `scored/`",
        "",
        "One row per `(instance, variant, mode, library, model)`. Beyond `correct` and",
        "`failure_class` it carries the diagnostics that make attribution possible:",
        "",
        "| field | meaning |",
        "|---|---|",
        "| `declared_ok` | the `nodes`/`edges` the model wrote == the graph it was shown (transcription) |",
        "| `construction_ok` | the graph the program built == what it declared (networkx arm only) |",
        "| `ans_is_literal` | `ans` was written down, not computed |",
        "| `finish_reason` | `length` = the reply was cut off; exclude these before quoting invariance |",
        "| `n_calls` (tables) | **distinct model replies** behind a cell |",
        "",
        "> **`n` is not `n_calls`.** M3's prompt contains no graph text, so for a task whose question",
        "> names no node (`cycle_check`, `node_count`, `density`, ...) *every* instance and variant",
        "> collapses to one reply, executed against every graph. Such a cell can hold 1,000 rows backed",
        "> by a single model decision -- read `n_calls` before quoting it.",
        "",
        "## Failure classes",
        "",
        "`ok` `wrong` `execution` `format` `transcription` `construction` `logic` `no_computation`",
        "`unverifiable` -- defined in the repo's `docs/scoring-and-classification.md`.",
        "`construction` is separable in the networkx arm only, so **never pool the failure",
        "decomposition across `library`**.",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("repo", help="e.g. Dolevabudi/graph-serialization-invariance")
    ap.add_argument("--public", action="store_true", help="default is private")
    ap.add_argument("--with-cache", action="store_true", help="also upload raw replies (~250 MB per model)")
    args = ap.parse_args()

    token = os.environ.get("HF_WRITE_TOKEN") or os.environ.get("HF_TOKEN")
    if not token:
        print("set HF_WRITE_TOKEN (a token with write access to repo contents)", file=sys.stderr)
        return 2

    from huggingface_hub import HfApi
    api = HfApi(token=token)

    models = sorted({p.stem for d in DATASETS for p in (ROOT / "results" / d / "scored").glob("*.jsonl")})
    if not models:
        print("no scored results found -- has the run finished?", file=sys.stderr)
        return 2

    with tempfile.TemporaryDirectory() as tmp:
        staging = Path(tmp)
        for d in DATASETS:
            base = ROOT / "results" / d
            if not base.exists():
                continue
            for sub in ("tables", "figs"):
                if (base / sub).exists():
                    shutil.copytree(base / sub, staging / sub / d)
            for p in (base / "scored").glob("*.jsonl"):
                gzip_to(p, staging / "scored" / d / (p.name + ".gz"))
            inst = ROOT / "data" / "processed" / d / "instances.jsonl"
            if inst.exists():
                (staging / "data" / d).mkdir(parents=True, exist_ok=True)
                shutil.copy(inst, staging / "data" / d / "instances.jsonl")
            if args.with_cache:
                for m in models:
                    cache = ROOT / "results" / "cache" / m
                    if not cache.exists():
                        continue
                    out = staging / "raw_replies" / f"{m}.tar.gz"
                    out.parent.mkdir(parents=True, exist_ok=True)
                    if not out.exists():
                        print(f"  packing {m} raw replies ...", flush=True)
                        with tarfile.open(out, "w:gz") as tf:
                            tf.add(cache, arcname=m)
        (staging / "README.md").write_text(readme(models))

        n = sum(1 for _ in staging.rglob("*") if _.is_file())
        mb = sum(p.stat().st_size for p in staging.rglob("*") if p.is_file()) / 2**20
        print(f"staged {n} files, {mb:.0f} MB -> {args.repo} ({'public' if args.public else 'private'})")

        api.create_repo(args.repo, repo_type="dataset", private=not args.public, exist_ok=True)
        api.upload_folder(folder_path=str(staging), repo_id=args.repo, repo_type="dataset",
                          commit_message="Results: two models, two datasets, all axes and arms")
    print(f"\nhttps://huggingface.co/datasets/{args.repo}")
    if not args.public:
        print("private -- add the team under Settings -> Collaborators")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
