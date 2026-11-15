"""Floor arm of RQ3 (E-RQ3-FLOOR, D169): analysis of stored rows; no call.

Usage (from the work directory):
  rq3_floor_arm.py analyse --floor DIR --rrf DIR --oracle DIR --out-dir OUT [--raw DIR ...]

Each DIR holds ``results/results.jsonl`` and ``log/calls.jsonl`` of one arm. The leakage check and
the prompts use ``rq3_driver.py prepare`` and ``rq3_oracle_arm.py leak-check`` unchanged.
Logic lives in ``ril/analysis/rq3_floor.py``.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ril.util.log import get_logger  # noqa: E402
from ril.util.seed import set_seed  # noqa: E402

log = get_logger("rq3_floor_arm")


def _paths(d: str) -> tuple[str, str]:
    """(results.jsonl, calls.jsonl) of an arm directory: nested (results/, log/) or flat."""
    nested = Path(d) / "results" / "results.jsonl"
    if nested.exists():
        return str(nested), str(Path(d) / "log" / "calls.jsonl")
    return str(Path(d) / "results.jsonl"), str(Path(d) / "calls.jsonl")


def _rows(d: str) -> list[dict[str, Any]]:
    p = Path(_paths(d)[0])
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x]


def _csv(path: Path, rows: list[dict[str, Any]]) -> None:
    keys: list[str] = []
    for r in rows:
        for k in r:
            if k not in keys:
                keys.append(k)
    with path.open("w", newline="", encoding="utf-8") as h:
        w = csv.DictWriter(h, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow({k: (json.dumps(v) if isinstance(v, list) else v) for k, v in r.items()})


def cmd_analyse(a: argparse.Namespace) -> int:
    from ril.agent.providers.holdout import split
    from ril.analysis import rq3_floor as rf
    from ril.analysis import rq3_oracle as ro
    from ril.analysis.rq3_agent_summary import arm_summary

    executable = json.loads(Path(a.subset).read_text(encoding="utf-8"))["executable"]
    _, conf = split(executable, json.loads(Path(a.heldout).read_text(encoding="utf-8")))
    conf = sorted(conf)
    named = {"floor": a.floor, "rrf": a.rrf, "oracle": a.oracle, "raw": a.raw}
    arm_dirs = {k: v for k, v in named.items() if v}
    rows: list[dict[str, Any]] = []
    runs: dict[str, tuple[int, ...]] = {}
    for label, d in arm_dirs.items():
        part = _rows(d)
        if len({str(r["arm"]) for r in part}) != 1:
            raise SystemExit(f"{label}: expected one arm name in {d}")
        for r in part:
            r["arm"] = label
        rows += part
        runs[label] = tuple(sorted({int(r["run"]) for r in part}))
    if runs["floor"] != (0,):
        raise SystemExit(f"floor repeats are {runs['floor']}, expected (0,)")
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    # a partial arm (a stop before the last instance) is analysed on the instances it covers
    covered = {str(r["instance_id"]) for r in rows if r["arm"] == "floor"}
    analysed = [i for i in conf if i in covered]
    if len(analysed) != len(covered):
        raise SystemExit("floor rows outside the confirmatory instances")

    def arms(ids: list[str], label: str) -> list[dict[str, Any]]:
        out_rows: list[dict[str, Any]] = []
        for reading in ("exact", "tolerant"):
            for r in ro.arm_rows(rows, ids, runs, reading, a.seed_analysis):
                out_rows.append({"instance_set": label, **r})
        return out_rows

    tables: dict[str, list[dict[str, Any]]] = {
        "arms": arms(analysed, f"floor-covered ({len(analysed)})")
        + arms(conf, f"all confirmatory ({len(conf)})"),
        "contrasts": rf.floor_contrasts(
            rows, analysed, {k: v for k, v in runs.items() if k != "raw"}, seed=a.seed_analysis
        ),
    }
    tables["instances"] = [
        {"instance_id": i, "covered_by_floor": i in covered, "repo": i.split("__")[0]} for i in conf
    ]
    if a.mdd:
        with open(a.mdd, encoding="utf-8") as h:
            tables["minimum_detectable"] = rf.mdd_for(list(csv.DictReader(h)), 0.4, (1, 2, 3))
    for name, t in tables.items():
        _csv(out / f"rq3_floor_{name}.csv", t)
    summaries = {
        label: arm_summary(
            label,
            *_paths(d),
            runs[label],
        )
        for label, d in arm_dirs.items()
    }
    (out / "floor_summary.json").write_text(
        json.dumps(
            {
                "confirmatory": len(conf),
                "floor_covered": len(analysed),
                "arms": summaries,
                "runs": runs,
            },
            indent=1,
            sort_keys=True,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )
    sys.stdout.write(json.dumps({"confirmatory": len(conf), "tables": sorted(tables)}) + "\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("analyse")
    p.add_argument("--floor", required=True)
    p.add_argument("--rrf", required=True)
    p.add_argument("--oracle", required=True)
    p.add_argument("--raw")
    p.add_argument("--subset", default="results/rq3_exec/executable_instances_v1.json")
    p.add_argument("--heldout", default="results/rq3_driver/heldout_v1.json")
    p.add_argument("--mdd", default="results/rq3_driver/rq3_power_measured_agreement_mdd.csv")
    p.add_argument("--out-dir", required=True)
    p.add_argument("--seed-analysis", type=int, default=0)
    p.set_defaults(fn=cmd_analyse)
    for sp in sub.choices.values():
        sp.add_argument("--seed", type=int, default=0)
    args = ap.parse_args(argv)
    set_seed(args.seed)
    return int(args.fn(args))


if __name__ == "__main__":
    raise SystemExit(main())
