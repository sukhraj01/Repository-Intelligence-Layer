"""Unit-level BM25 variants on the development set (D119). Thin wrapper.

Usage:
  rq1_unit_bm25.py eval E1_CONFIG DATA_ROOT REPO_CACHE CACHE_DIR DENSE_ROOT WORK_DIR OUT_DIR
                   [--shard I K] [--limit N]
  rq1_unit_bm25.py tables ROOT DATE EVAL_DIR [LADDER_SUMMARY_CSV]
Writes scores and counts only (no text).
"""

from __future__ import annotations

import argparse
import csv
import glob
import hashlib
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ril.util.log import get_logger  # noqa: E402
from ril.util.seed import set_seed  # noqa: E402


def _write(path: str, rows: list[dict[str, object]]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def _sha(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("stage", choices=["eval", "tables"])
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--shard", nargs=2, type=int, default=[0, 1])
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    set_seed(args.seed)
    log = get_logger("unit_bm25")
    if args.stage == "eval":
        from ril.evaluation.unit_bm25 import run_unit_bm25

        e1, data_root, repo_cache, cache_dir, dense_root, work, out = args.paths
        fails = run_unit_bm25(
            e1,
            data_root,
            repo_cache,
            cache_dir,
            dense_root,
            work,
            out,
            shard=(args.shard[0], args.shard[1]),
            limit=args.limit,
        )
        log.info("failures: %d", len(fails))
        return 0 if not fails else 2
    from ril.analysis import rq1_unit_bm25 as ub
    from ril.analysis.e3_tables import load_eval_dir

    root, date, eval_dir, *rest = args.paths
    tab = load_eval_dir(eval_dir)
    ub.check_keys(tab)
    tables = os.path.join(root, "results", "tables")
    ladder_path = rest[0] if rest else os.path.join(tables, "rq1_ladder_cre_summary.csv")
    with open(ladder_path, encoding="utf-8", newline="") as fh:
        ladder = list(csv.DictReader(fh))
    for r in ladder:
        for k in ("mean", "n"):
            r[k] = float(r[k])  # type: ignore[assignment]
    values = ub.value_rows(tab, args.seed)
    compare = ub.compare_rows(tab, args.seed)
    regression = ub.regression_rows(tab, ladder)
    from ril.analysis.rq1_ladder import query_rows

    qrows = query_rows(tab, "unit_bm25")
    outs = {
        "summary": values,
        "compare": compare,
        "regression": regression,
        "query_rows": qrows,
    }
    record: dict[str, object] = {
        "version": "unit-bm25-tables/v1",
        "date": date,
        "seed": args.seed,
        "best_cell": ub.best_cell(tab),
        "sizes": ub.sizes(tab),
        "ladder_summary_sha256": _sha(ladder_path),
        "eval_files": {
            os.path.basename(p): _sha(p) for p in sorted(glob.glob(os.path.join(eval_dir, "*.npz")))
        },
        "outputs": {},
    }
    for name, rows in outs.items():
        path = os.path.join(tables, f"unit_bm25_{name}.csv")
        _write(path, rows)
        record["outputs"][name] = {"path": os.path.relpath(path, root), "sha256": _sha(path)}  # type: ignore[index]
    checks = [
        json.load(open(p, encoding="utf-8"))
        for p in sorted(glob.glob(os.path.join(eval_dir, "checks_s*.json")))
    ]
    record["control_checks"] = {
        "levels_checked": sum(len(c["checks"]) for c in checks),
        "levels_reproduced": sum(1 for c in checks for r in c["checks"] if r["reproduces"]),
        "failures": [f for c in checks for f in c["failures"]],
    }
    ub.dump(os.path.join(root, "results", "logs", f"unit_bm25_run_files_{date}.json"), record)
    log.info(
        "best cell %s; regression %s", record["best_cell"], [r["reproduces"] for r in regression]
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
