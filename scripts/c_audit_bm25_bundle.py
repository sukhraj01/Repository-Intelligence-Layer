"""Audit the recovered, fixed dev-v1 BM25 bundle without rerunning retrieval."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import sys
from collections import Counter
from pathlib import Path
from zipfile import ZipFile

import yaml

from ril.evaluation.stats import clustered_mean_ci, clustered_paired_diff_ci

SOURCE = "dcc19574386fc66c578bb42c872e38f9e95d0201"
CONFIG_HASH = "ce0c977b4f6a93cd5c0615846170090e7389ebc341825fa4bc4f2f69d8b75452"
CONFIG_SHA = "451a81484271bfe5366ce499b069a650b44733cbdbfe98730c3d07f079d53e37"
REVISION = "23da5d97a8a4495d4bd6d5616aa86d5a12a60699"
EXPECTED = {
    "runs/dev-v1/bm25/results.json",
    "runs/dev-v1/bm25/config.yaml",
    "runs/dev-v1/bm25/hardware.json",
    "runs/dev-v1/bm25/latency_log.csv",
    "runs/dev-v1/bm25/throughput_log.csv",
    "runs/dev-v1/bm25-log.json",
    "configs/dev-v1-bm25.yaml",
    "dataset-plan.json",
    "dataset-manifest.json",
    "raw/provenance.json",
}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def audit(path: Path) -> dict[str, object]:
    with ZipFile(path) as bundle:
        names = bundle.namelist()
        require(
            len(names) == len(set(names)) and set(names) == EXPECTED | {"BUNDLE_MANIFEST.json"},
            "ZIP membership or duplicate member differs",
        )
        require(bundle.testzip() is None, "ZIP CRC check failed")
        files = {name: bundle.read(name) for name in EXPECTED}
        manifest = json.loads(bundle.read("BUNDLE_MANIFEST.json"))
    require(
        manifest.get("version") == "ril-bm25-recovery/v1"
        and manifest.get("source_commit") == SOURCE
        and manifest.get("config_hash") == CONFIG_HASH
        and set(manifest.get("files", {})) == EXPECTED,
        "bundle identity differs",
    )
    for name, data in files.items():
        item = manifest["files"][name]
        require(
            item.get("sha256") == digest(data)
            and item.get("bytes") == len(data)
            and item.get("source") in {"checkpoint", "native"},
            f"bundle member identity differs: {name}",
        )

    config = yaml.safe_load(files["configs/dev-v1-bm25.yaml"])
    require(
        digest(files["configs/dev-v1-bm25.yaml"]) == CONFIG_SHA,
        "original config raw checksum differs",
    )
    require(
        config == yaml.safe_load(files["runs/dev-v1/bm25/config.yaml"]),
        "saved config semantics differ",
    )
    semantic_hash = digest(
        json.dumps({"version": "retrieval-eval/v1", "config": config}, sort_keys=True).encode()
    )
    require(
        semantic_hash == CONFIG_HASH
        and config["seed"] == 0
        and config["bootstrap_draws"] == 2000
        and config["rewrite"] is True
        and config["retriever"] == {"kind": "bm25", "k1": 1.5, "b": 0.75},
        "registered config differs",
    )
    results = json.loads(files["runs/dev-v1/bm25/results.json"])
    require(results == json.loads(files["runs/dev-v1/bm25-log.json"]), "sibling result log differs")
    require(
        results["version"] == "retrieval-eval/v1"
        and results["git_hash"] == SOURCE
        and results["config_hash"] == CONFIG_HASH
        and results["seed"] == 0
        and results["bootstrap_draws"] == 2000
        and results["role"] == "dev"
        and results["split"] == config["split"]
        and results["retriever"] == config["retriever"],
        "result identity differs",
    )
    hardware = json.loads(files["runs/dev-v1/bm25/hardware.json"])
    require(
        hardware["commit"] == SOURCE
        and hardware["config_hash"] == CONFIG_HASH
        and hardware["host"] == "colab"
        and hardware["gpu_name"] == "none"
        and hardware["torch"] == "not imported",
        "hardware identity differs",
    )

    plan = json.loads(files["dataset-plan.json"])
    source_manifest = json.loads(files["dataset-manifest.json"])
    provenance = json.loads(files["raw/provenance.json"])
    require(
        plan["dataset"] == "zhangfw123/CORE-Bench"
        and plan["revision"] == REVISION
        and len(plan["files"]) == 36
        and len(source_manifest["files"]) == 36,
        "staging plan differs",
    )
    identity = {key: plan[key] for key in ("version", "dataset", "revision", "files")}
    sorted_manifest = {
        **source_manifest,
        "files": sorted(source_manifest["files"], key=lambda x: x["path"]),
    }
    require(
        sorted_manifest == identity and provenance["identity"] == identity,
        "staging identities differ",
    )
    manifest_hash = digest(
        json.dumps(source_manifest, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    )
    require(plan["manifest_sha256"] == manifest_hash, "staging manifest hash differs")
    planned = {item["path"]: item for item in plan["files"]}
    completed = provenance["completed"]
    require(set(planned) == set(completed), "staged file completion differs")
    for name, item in planned.items():
        actual = completed[name]
        require(
            actual["path"] == name
            and actual["bytes"] == item["bytes"]
            and (item["sha256"] is None or actual["sha256"] == item["sha256"])
            and (item["git_blob_sha1"] is None or actual["git_blob_sha1"] == item["git_blob_sha1"]),
            f"staged file identity differs: {name}",
        )

    rows = results["query_rows"]
    groups: dict[tuple[str, str, str, str], dict[str, dict[str, dict[str, object]]]] = {}
    for row in rows:
        key = (row["level"], row["dataset"], row["folder"], row["repo"])
        condition = row["condition"]
        require(condition in {"original", "rewrite"}, "unknown query condition")
        by_condition = groups.setdefault(key, {"original": {}, "rewrite": {}})[condition]
        query_id = row["query_id"]
        require(query_id not in by_condition, "duplicate query identity")
        for metric in ("ndcg10", "recall100"):
            require(math.isfinite(row[metric]) and 0 <= row[metric] <= 1, "invalid query metric")
        by_condition[query_id] = row
    require(len(groups) == 9 and len(rows) == 1360, "folder or query count differs")
    level_counts: Counter[str] = Counter()
    for key, pair in groups.items():
        require(
            pair["original"].keys() == pair["rewrite"].keys(),
            f"original/Rewrite query IDs differ: {key}",
        )
        for query_id in pair["original"]:
            a, b = pair["original"][query_id], pair["rewrite"][query_id]
            require(
                a["anchors_original"] == b["anchors_original"]
                and a["anchors_lost"] == b["anchors_lost"],
                "paired anchor metadata differs",
            )
        level_counts[key[0]] += len(pair["original"])
    require(level_counts == {"L2": 442, "L3": 238}, "level query counts differ")

    input_hashes = results["input_hashes"]
    input_keys = {(x["level"], x["repo"]) for x in input_hashes}
    require(
        len(input_hashes) == 9
        and len(input_keys) == 9
        and input_keys == {(x[0], x[3]) for x in groups},
        "input hash membership differs",
    )
    for level, dataset, folder, repo in groups:
        for relative in (
            f"data/LEVEL-{level[1:]}/{dataset}/{folder}/corpus.jsonl",
            f"data/LEVEL-{level[1:]}/{dataset}/{folder}/qrels.jsonl",
            f"data/LEVEL-{level[1:]}/{dataset}/{folder}/queries.jsonl",
            f"data/Rewrite-LEVEL-{level[1:]}/{dataset}/{folder}/queries.jsonl",
        ):
            require(relative in planned, f"planned folder input missing: {relative}")
        item = next(x for x in input_hashes if (x["level"], x["repo"]) == (level, repo))
        require(
            all(
                len(item[k]) == 64
                for k in ("corpus_sha256", "labels_sha256", "original_sha256", "rewrite_sha256")
            )
            and item["original_sha256"] != item["rewrite_sha256"],
            "loaded input identity absent or conditions identical",
        )

    prior = json.loads(Path("results/logs/c1_colab_bm25_dev_v1_2026-10-31.json").read_text())
    require(
        results["metrics"] == prior["reported_cli_summary"]["metrics"],
        "native metrics differ from earlier stdout record",
    )
    computed = []
    for metric_row in results["metrics"]:
        level, condition, metric = (metric_row[k] for k in ("level", "condition", "metric"))
        subset = [row for row in rows if row["level"] == level]
        if condition == "rewrite_minus_original":
            original = {
                (r["dataset"], r["folder"], r["query_id"]): r
                for r in subset
                if r["condition"] == "original"
            }
            rewrite = {
                (r["dataset"], r["folder"], r["query_id"]): r
                for r in subset
                if r["condition"] == "rewrite"
            }
            keys = sorted(original)
            values = clustered_paired_diff_ci(
                [rewrite[k][metric] for k in keys],
                [original[k][metric] for k in keys],
                [original[k]["repo"] for k in keys],
                draws=2000,
                seed=0,
            )
            n, repositories = len(keys), len({original[k]["repo"] for k in keys})
        else:
            selected = [r for r in subset if r["condition"] == condition]
            values = clustered_mean_ci(
                [r[metric] for r in selected], [r["repo"] for r in selected], draws=2000, seed=0
            )
            n, repositories = len(selected), len({r["repo"] for r in selected})
        require(
            metric_row["n"] == n
            and metric_row["repositories"] == repositories
            and all(
                math.isclose(value, metric_row[field], rel_tol=0, abs_tol=1e-12)
                for value, field in zip(values, ("mean", "low", "high"), strict=True)
            ),
            f"bootstrap recomputation differs: {level} {condition} {metric}",
        )
        computed.append(metric_row)
    require(len(computed) == 12, "metric row count differs")
    with Path("results/tables/c1_colab_bm25_dev_v1_2026-10-31.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        prior_csv = list(csv.DictReader(handle))
    require(len(prior_csv) == len(computed), "prior metric CSV row count differs")
    for prior_row, metric_row in zip(prior_csv, computed, strict=True):
        require(
            all(
                prior_row[k] == str(metric_row[k])
                for k in (
                    "level",
                    "condition",
                    "metric",
                    "n",
                    "repositories",
                    "mean",
                    "low",
                    "high",
                )
            ),
            "prior metric CSV differs",
        )

    for kind, expected_n in (("latency", 18), ("throughput", 9)):
        path_in_zip = f"runs/dev-v1/bm25/{kind}_log.csv"
        csv_rows = list(csv.DictReader(io.StringIO(files[path_in_zip].decode())))
        embedded = results[f"{kind}_rows"]
        require(len(csv_rows) == len(embedded) == expected_n, f"{kind} row count differs")
        for csv_row, row in zip(csv_rows, embedded, strict=True):
            require(
                set(csv_row) == set(row) and all(csv_row[k] == str(v) for k, v in row.items()),
                f"{kind} CSV differs from embedded row",
            )
            require(
                row["commit"] == SOURCE
                and row["config_hash"] == CONFIG_HASH
                and row["host"] == "colab"
                and row["gpu_name"] == "none",
                f"{kind} environment differs",
            )
            if kind == "latency":
                require(
                    row["stage"] == "bm25"
                    and row["cache_state"] == "warm"
                    and row["warmup_n"] == 1
                    and row["n"] == row["n_queries"] * 3
                    and 0 <= row["p50_ms"] <= row["p95_ms"] <= row["p99_ms"],
                    "latency measurement differs",
                )
            else:
                require(
                    row["stage"] == "bm25_index"
                    and row["seconds"] > 0
                    and row["units"] > 0
                    and math.isclose(
                        row["units_per_s"], row["units"] / row["seconds"], rel_tol=1e-12
                    ),
                    "throughput measurement differs",
                )
    observed_latency = {row["query_set_id"]: row for row in results["latency_rows"]}
    observed_throughput = {row["workload_id"]: row for row in results["throughput_rows"]}
    require(
        len(observed_latency) == 18 and len(observed_throughput) == 9,
        "duplicate timing workload identity",
    )
    for level, dataset, folder, repo in groups:
        workload = f"{config['split']}:{level}:{dataset}:{folder}"
        require(workload in observed_throughput, "missing index throughput workload")
        inputs = next(x for x in input_hashes if (x["level"], x["repo"]) == (level, repo))
        for condition in ("original", "rewrite"):
            query_set = f"{workload}:{condition}:{inputs[condition + '_sha256'][:12]}"
            require(
                query_set in observed_latency
                and observed_latency[query_set]["n_queries"]
                == len(groups[(level, dataset, folder, repo)][condition]),
                "missing or miscounted query timing workload",
            )

    return {
        "status": "artifact_and_row_audit_passed",
        "zip_sha256": digest(path.read_bytes()),
        "zip_bytes": path.stat().st_size,
        "source_commit": SOURCE,
        "config_hash": CONFIG_HASH,
        "dataset_revision": REVISION,
        "manifest_sha256": manifest_hash,
        "native_files": len(files),
        "checkpoint_files": sum(v["source"] == "checkpoint" for v in manifest["files"].values()),
        "staged_files": len(completed),
        "folder_level_pairs": len(groups),
        "query_rows": len(rows),
        "paired_queries_by_level": dict(level_counts),
        "metrics_recomputed": len(computed),
        "latency_rows": len(results["latency_rows"]),
        "throughput_rows": len(results["throughput_rows"]),
        "hardware": hardware,
        "limits": [
            "Raw corpus, qrels and candidate lists are not in the ZIP; loaded-input hashes and "
            "the original/Rewrite shared-candidate contract cannot be independently rederived.",
            "Per-query latency samples are not in the ZIP; saved percentile rows and their CSV "
            "copies agree, but latency percentiles cannot be independently recomputed.",
            "Colab execution and the earlier waited-child peak RSS are operator supplied; "
            "the ZIP contains saved hardware and timing rows, not an independent host trace.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    args = parser.parse_args()
    sys.stdout.write(json.dumps(audit(args.bundle), indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
