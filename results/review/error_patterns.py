"""Inspect saved code-mode errors without executing generated programs."""
import json
from collections import Counter, defaultdict
from pathlib import Path

from gsi.data.base import GraphInstance
from gsi.serial.variant import canonical, relabel, normalize_edges, norm_label

ROOT = Path(__file__).resolve().parents[2]


def rows(path):
    with path.open(encoding="utf-8") as stream:
        yield from map(json.loads, stream)


report = {}
for dataset in ("graphqa", "erdos"):
    instances = {r["id"]: GraphInstance.from_dict(r)
                 for r in rows(ROOT / "data/processed" / dataset / "instances.jsonl")}
    base = ROOT / "results" / dataset
    for path in sorted((base / "scored").glob("*.jsonl")):
        scored = {r["record_id"]: r for r in rows(path) if r["mode"] == "code"}
        counts = defaultdict(Counter)
        wrong = {}
        for rid, r in scored.items():
            key = r["library"] + "/" + r["axis"]
            c = counts[key]
            c["n"] += 1
            c["wrong_answer"] += not r["correct"]
            c["class/" + r["failure_class"]] += 1
            if r["declared_ok"] is False:
                c["wrong_declaration"] += 1
                c["wrong_declaration_correct_answer"] += r["correct"]
                wrong[rid] = r
        details = []
        for ex in rows(base / "exec" / path.name):
            rid = ex["record_id"]
            if rid not in wrong:
                continue
            r = wrong[rid]
            inst = instances[r["instance_id"]]
            v = canonical(inst, structure="edge_list", syntax="plain")
            if r["axis"] == "relabel" and r["params"]["seed"] != "identity":
                v = relabel(v, r["params"]["seed"])
            expected = normalize_edges(v.edge_seq, v.directed)
            actual = normalize_edges(ex["declared_edges"] or [], v.directed)
            nodes_expected = set(map(norm_label, v.node_seq))
            nodes_actual = set(map(norm_label, ex["declared_nodes"] or []))
            missing, extra = sorted(expected - actual), sorted(actual - expected)
            missing_nodes, extra_nodes = sorted(nodes_expected - nodes_actual), sorted(nodes_actual - nodes_expected)
            assert missing or extra or missing_nodes or extra_nodes, rid
            details.append(dict(record_id=rid, instance_id=r["instance_id"], task=r["task"],
                library=r["library"], axis=r["axis"], params=r["params"], prompt_hash=r["prompt_hash"],
                correct=r["correct"], failure_class=r["failure_class"], n=len(v.node_seq),
                m=len(expected), declaration_unavailable=ex["declared_nodes"] is None or ex["declared_edges"] is None,
                missing_edges=missing, extra_edges=extra,
                missing_nodes=missing_nodes, extra_nodes=extra_nodes))
        assert len(details) == len(wrong)
        groups = {}
        for library in ("native", "networkx"):
            for axes in (("canonical", "order", "relabel", "structure", "syntax"), ("order", "relabel")):
                chosen = [d for d in details if d["library"] == library and d["axis"] in axes]
                key = library + ("/all" if len(axes) == 5 else "/permutations")
                kinds = Counter()
                for d in chosen:
                    if d["declaration_unavailable"]:
                        kinds["declaration_unavailable"] += 1
                        continue
                    if d["missing_nodes"] or d["extra_nodes"]:
                        kinds["node_set_mismatch"] += 1
                    if d["missing_edges"] and not d["extra_edges"]:
                        kinds["edges_missing_only"] += 1
                    elif d["extra_edges"] and not d["missing_edges"]:
                        kinds["edges_extra_only"] += 1
                    elif d["extra_edges"] and d["missing_edges"]:
                        kinds["edges_missing_and_extra"] += 1
                    else:
                        kinds["edges_match"] += 1
                    if len(d["missing_edges"]) + len(d["extra_edges"]) == 1:
                        kinds["one_edge_difference"] += 1
                groups[key] = dict(n=len(chosen), correct=sum(d["correct"] for d in chosen),
                    unique_prompts=len({d["prompt_hash"] for d in chosen}),
                    unique_instances=len({d["instance_id"] for d in chosen}),
                    kinds=dict(kinds), tasks=dict(Counter(d["task"] for d in chosen)),
                    top_instances=Counter(d["instance_id"] for d in chosen).most_common(8))
        report[dataset + "/" + path.stem] = dict(counts=dict(counts), groups=groups, details=details)
        print(dataset, path.stem, json.dumps(groups), flush=True)

(ROOT / "results/review/error_patterns.json").write_text(
    json.dumps(report, indent=2), encoding="utf-8")
