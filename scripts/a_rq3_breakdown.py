"""Retrieval-versus-reasoning breakdown and token cost of the graded agent runs (E-RQ3-BREAKDOWN).

Usage: a_rq3_breakdown.py --out-dir results/rq3_breakdown [--repo owner/name=PATH ...]
Reads the stored rows of the four registered arms, their context file lists, the gold files and
the floor contrasts; writes ``breakdown.csv``, ``attempt_cost.csv``, ``summary.json`` and, with
``--repo``, ``repo_python_tokens.csv`` (approximate tokens of each checkout's Python code). No model
call. The logic is in ``ril.analysis.rq3_breakdown``.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ril.analysis import rq3_breakdown as bd  # noqa: E402 (path set above)

DRIVER = ROOT / "results/rq3_driver"
TRAINED = DRIVER / "trained_runs/gemini-3.8-flash"
ARMS = {  # report name: (rows, context file list)
    "untrained": (DRIVER / "untrained_runs/gemini-3.8-flash/rrf_runs0-2/results.jsonl", "rrf"),
    "raw": (TRAINED / "tr_mined_raw_u100_s100_runs0-2/results/results.jsonl", "raw"),
    "filter_bm25": (
        TRAINED / "tr_mined_filter_bm25_u100_s100_runs0-2/results/results.jsonl",
        "filter",
    ),
    "subsample": (TRAINED / "tr_mined_sub_u100_s100_runs0-2/results/results.jsonl", "sub"),
}
ORACLE = ROOT / "results/rq3_oracle"
FLOOR = ROOT / "results/rq3_floor/pooled/rq3_floor_contrasts.csv"


def _jsonl(path: Path) -> list[dict[str, object]]:
    with open(path, encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _floor_means() -> dict[str, float]:
    """Own-k means on the floor's instances: untrained (k 3), oracle (k 2), floor (k 1)."""
    with open(FLOOR, encoding="utf-8") as handle:
        rows = [r for r in csv.DictReader(handle) if r["k_form"].startswith("own k")]
    by = {r["first"]: r for r in rows}
    return {
        "instances": int(by["rrf"]["n_pairs"]),
        "untrained": float(by["rrf"]["mean_a"]),
        "oracle": float(by["oracle"]["mean_a"]),
        "floor": float(by["rrf"]["mean_b"]),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--repo", action="append", default=[], help="owner/name=PATH")
    args = ap.parse_args()
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    instances = [
        line.strip()
        for line in (DRIVER / "ids_confirmatory.txt").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    gold_doc = json.loads((ORACLE / "oracle_gold_files.json").read_text(encoding="utf-8"))
    gold = {i: v["modified"] for i, v in gold_doc["instances"].items()}
    arms, costs = {}, {}
    for name, (rows_path, files_key) in ARMS.items():
        rows = _jsonl(rows_path)
        files = json.loads((ORACLE / f"files_{files_key}.json").read_text(encoding="utf-8"))
        arms[name] = bd.breakdown(rows, instances, gold, files["files"])
        costs[name] = bd.attempt_cost(rows, instances)
    with open(out / "breakdown.csv", "w", newline="", encoding="utf-8") as handle:
        w = csv.writer(handle)
        w.writerow(
            [
                "arm",
                "gold_class",
                "instances",
                "runs",
                "resolved",
                "resolved_share",
                *bd.OUTCOMES,
                "failed_share_all_gold_present",
                "failed_share_no_gold_present",
            ]
        )
        for name, a in arms.items():
            for c in bd.CLASSES:
                k = a["classes"][c]
                w.writerow(
                    [
                        name,
                        c,
                        k["instances"],
                        k["runs"],
                        k["resolved"],
                        round(k["resolved_share"], 4),
                        *(k["outcomes"].get(o, 0) for o in bd.OUTCOMES),
                        round(a["failed_share_all_gold_present"], 4),
                        round(a["failed_share_no_gold_present"], 4),
                    ]
                )
    with open(out / "attempt_cost.csv", "w", newline="", encoding="utf-8") as handle:
        w = csv.writer(handle)
        w.writerow(
            [
                "arm",
                "runs",
                "calls",
                "prompt_tokens",
                "output_tokens",
                "tokens_per_run",
                "usd",
                "usd_per_run",
            ]
        )
        for name, c in costs.items():
            w.writerow(
                [
                    name,
                    c["runs"],
                    c["calls"],
                    c["prompt_tokens"],
                    c["output_tokens"],
                    round(c["tokens_per_run"], 1),
                    round(c["usd"], 4),
                    round(c["usd_per_run"], 5),
                ]
            )
    fm = _floor_means()
    summary = {
        "experiment": "E-RQ3-BREAKDOWN",
        "instances": len(instances),
        "arms": arms,
        "expected_retrieval_gain": {
            n: bd.expected_retrieval_gain(arms[n], arms["untrained"])
            for n in ("raw", "filter_bm25", "subsample")
        },
        "attempt_cost": costs,
        "floor_gap": {
            **fm,
            "share_closed_by_untrained_context": round(
                bd.gap_closed(fm["untrained"], fm["floor"], fm["oracle"]), 4
            ),
        },
    }
    (out / "summary.json").write_text(
        json.dumps(summary, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    if args.repo:
        with open(out / "repo_python_tokens.csv", "w", newline="", encoding="utf-8") as handle:
            w = csv.writer(handle)
            w.writerow(["repo", "commit", "python_files", "approx_tokens", "pct_of_8000_budget"])
            for spec in args.repo:
                repo, _, path = spec.partition("=")
                commit = subprocess.run(
                    ["git", "-C", path, "rev-parse", "--short", "HEAD"],
                    check=True,
                    capture_output=True,
                    text=True,
                ).stdout.strip()
                t = bd.python_tokens(path)
                w.writerow(
                    [
                        repo,
                        commit,
                        t["python_files"],
                        t["approx_tokens"],
                        round(100 * 8000 / t["approx_tokens"], 2),
                    ]
                )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
