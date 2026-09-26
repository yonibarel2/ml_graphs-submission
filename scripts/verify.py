"""Check the repository end to end: the tests, the pipeline, and that the committed result tables
follow from the published records. No paid model calls.

    python scripts/verify.py [--skip-tests] [--keep DIR]

Everything runs in a scratch copy of the configs, scripts and instances; the committed files are
never written to.

1. Runs the test suite.
2. Runs the whole pipeline (data, variants, llm, exec, score, analysis) on configs/smoke.yaml with
   the offline stub model, and checks that every stage completes and every failure class occurs.
3. Downloads the scored records of the four models from the two Hugging Face datasets, at pinned
   revisions, and checks each file's sha256 against the values below (the published LFS object ids).
4. Reruns the analysis scripts on those records.
5. Compares every CSV they write with the committed one.

Not covered, because they need model replies that are not in the scored records or new calls:
program_voting.csv and solver_per_task.csv, canonical_labeling.csv (the accuracy half of E3),
results/floor*.json, results/erdos_m3fix/, the archived results/mitigation_*/ and the per-question
notes under results/review/.

Takes about 20 minutes. Needs network access to huggingface.co (public datasets, no token) and about 20 MB of downloads.
Exit status 0 only if every check passes.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATASETS = ("graphqa", "erdos")
FAILURE_CLASSES = {"ok", "wrong", "execution", "format", "no_computation", "transcription",
                   "construction", "logic", "unverifiable"}

# DeepSeek-V3.1 and Qwen3-8B ran locally and were published by one teammate; Gemma 4 31B and
# DeepSeek-V4-Flash ran on another teammate's machine (ANALYSIS.md, "Models").
SOURCES = {
    "Dolevabudi/graph-serialization-invariance": {
        "revision": "ee5b49e8013c1e5eb90bc14c2f7786810af01b77",
        "files": {
            "scored/graphqa/hf-deepseek-v3.1-novita.jsonl.gz": "95aaf7d8c5e476385b76caf4f0810169f4f5bcfef4a76ee80bc40c0130ca8421",
            "scored/graphqa/hf-qwen3-8b-nscale.jsonl.gz": "12760accae2429c6ca8df4fb8ab8cf5653ef2a7cd077e7e36d94758e0e8917f8",
            "scored/erdos/hf-deepseek-v3.1-novita.jsonl.gz": "6e38e2a98da496e5f1c370eb16db0331438399f5ec1438765865106e93402eb7",
            "scored/erdos/hf-qwen3-8b-nscale.jsonl.gz": "da60b6a2c85bddae038e5d4619e6dbb9c9a939c34b50ff7ba5deffd937f2d570",
        },
    },
    "Yonibarel/graph-serialization-invariance": {
        "revision": "8e1c18632a132d5e13ee95164f75651bcf1730e9",
        "files": {
            "scored/graphqa/hf-deepseek-v4-flash.jsonl.gz": "84336f261d6e4ec7517c53644009b7c28a22bebdb738ea653b507d8b667bfac5",
            "scored/graphqa/hf-gemma-4-31b.jsonl.gz": "1c6a7bd1a01233f7694717077c0cb5e7cfd712aa45edd6c34f4651c4317a49b9",
            "scored/erdos/hf-deepseek-v4-flash.jsonl.gz": "410371e18877e127f3bafefec07b1c0489f07955f1a63c65b74210d3c59a6d26",
            "scored/erdos/hf-gemma-4-31b.jsonl.gz": "c74ea319620d888f6b3c72eda76c8b7707499c4830eebac028436954f943139a",
        },
    },
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def run(cmd: list[str], cwd: Path) -> bool:
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src") + os.pathsep + os.environ.get("PYTHONPATH", "")}
    print("$", " ".join(Path(c).name if c == cmd[0] else c for c in cmd), flush=True)
    proc = subprocess.run(cmd, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if proc.returncode != 0:
        print(proc.stdout[-4000:])
        print(f"FAILED (exit {proc.returncode})")
    elif cmd[1:3] == ["-m", "pytest"]:
        print("  " + proc.stdout.strip().splitlines()[-1])
    return proc.returncode == 0


def smoke(work: Path) -> bool:
    """The stub model's behaviours are chosen so that every failure class occurs."""
    cfg = str(work / "configs" / "smoke.yaml")
    if not (run([sys.executable, "scripts/run.py", "--config", cfg], work)
            and run([sys.executable, "scripts/analyze.py", "--config", cfg], work)):
        return False
    with (work / "results" / "smoke" / "scored" / "stub.jsonl").open() as f:
        rows = [json.loads(line) for line in f]
    seen = {r["failure_class"] for r in rows}
    tables = sorted(p.stem for p in (work / "results" / "smoke" / "tables").glob("*.csv"))
    print(f"  {len(rows)} records scored, {len(seen & FAILURE_CLASSES)}/9 failure classes seen, "
          f"tables: {', '.join(tables)}")
    if FAILURE_CLASSES - seen:
        print(f"  missing classes: {sorted(FAILURE_CLASSES - seen)}")
    return bool(rows) and seen >= FAILURE_CLASSES and len(tables) == 6


def download(work: Path) -> bool:
    from huggingface_hub import hf_hub_download

    ok = True
    for repo, src in SOURCES.items():
        for name, expected in src["files"].items():
            path = Path(hf_hub_download(repo, name, repo_type="dataset", revision=src["revision"]))
            got = sha256(path)
            status = "ok" if got == expected else f"MISMATCH (got {got})"
            print(f"  {repo.split('/')[0]:10s} {name:48s} sha256 {status}")
            ok &= got == expected
            _, dataset, fname = name.split("/")
            dst = work / "results" / dataset / "scored" / fname.removesuffix(".gz")
            dst.parent.mkdir(parents=True, exist_ok=True)
            with gzip.open(path, "rb") as f, dst.open("wb") as g:
                shutil.copyfileobj(f, g)
    return ok


def compare(new: Path, old: Path) -> str | None:
    """None if the two CSVs hold the same rows (floats to 1e-9 relative), else what differs.
    Row order is ignored: permutation_signal.csv, for one, lists models in the order they were run."""
    if not old.exists():
        return "no committed file"
    a, b = pd.read_csv(new), pd.read_csv(old)
    if list(a.columns) != list(b.columns):
        return f"columns differ: {list(a.columns)} vs {list(b.columns)}"
    if len(a) != len(b):
        return f"{len(a)} rows vs {len(b)} committed"
    keys = [c for c in a.columns if not pd.api.types.is_float_dtype(a[c])]
    a = a.sort_values(keys, na_position="first", kind="stable").reset_index(drop=True)
    b = b.sort_values(keys, na_position="first", kind="stable").reset_index(drop=True)
    try:
        pd.testing.assert_frame_equal(a, b, check_exact=False, rtol=1e-9, atol=1e-12, check_dtype=False)
    except AssertionError as e:
        return str(e).splitlines()[0] + " " + " ".join(str(e).split())[-200:]
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--skip-tests", action="store_true")
    ap.add_argument("--keep", type=Path, help="work in this directory and keep it, instead of a temporary one")
    args = ap.parse_args()
    py = sys.executable
    failures: list[str] = []

    if not args.skip_tests:
        print("\n== 1. test suite")
        if not run([py, "-m", "pytest", "-q"], ROOT):
            failures.append("pytest")

    work = args.keep.resolve() if args.keep else Path(tempfile.mkdtemp(prefix="gsi-verify-"))
    try:
        for sub in ("configs", "scripts"):
            shutil.copytree(ROOT / sub, work / sub, dirs_exist_ok=True)
        for d in DATASETS:
            (work / "data" / "processed" / d).mkdir(parents=True, exist_ok=True)
            shutil.copy(ROOT / "data" / "processed" / d / "instances.jsonl", work / "data" / "processed" / d)

        print("\n== 2. whole pipeline, offline stub model")
        if not smoke(work):
            failures.append("pipeline")

        print("\n== 3. published records")
        if not download(work):
            failures.append("sha256")

        print(f"\n== 4. analysis, rerun in {work}")
        steps = []
        for d in DATASETS:
            cfg = str(work / "configs" / f"{d}.yaml")
            models = sorted(p.stem for p in (work / "results" / d / "scored").glob("*.jsonl"))
            steps += [
                [py, "scripts/run.py", "--config", cfg, "--stages", "variants"],
                [py, "scripts/analyze.py", "--config", cfg],
                [py, "scripts/analyze.py", "--config", cfg, "--models", *models],
                [py, "scripts/permutation_signal.py", "--config", cfg],
                [py, "scripts/canonical_labeling.py", "--config", cfg, "--invariance-only"],
            ]
        steps.append([py, "scripts/audit_results.py"])
        for cmd in steps:
            if not run(cmd, work):
                failures.append(" ".join(cmd[1:3]))

        print("\n== 5. regenerated tables vs committed")
        new_tables = [p for d in DATASETS for p in sorted((work / "results" / d / "tables").rglob("*.csv"))]
        new_tables.append(work / "results" / "review" / "paired_intervals.csv")  # per_instance.csv is not tracked
        for new in new_tables:
            rel = new.relative_to(work)
            diff = compare(new, ROOT / rel)
            print(f"  {'ok  ' if diff is None else 'DIFF'} {rel.as_posix()}" + ("" if diff is None else f"\n       {diff}"))
            if diff is not None:
                failures.append(rel.as_posix())
        print(f"  {len(new_tables)} tables compared")
    finally:
        if not args.keep:
            shutil.rmtree(work, ignore_errors=True)

    print("\n== result:", "all checks passed" if not failures else f"{len(failures)} failed: {', '.join(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
