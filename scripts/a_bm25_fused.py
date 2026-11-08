"""A BM25 variant inside RRF(BM25, dense) on the development folders (session A1, E-A1-FUSED).

Usage: a_bm25_fused.py run CONFIG DATA_ROOT ENC_ROOT OUT_DIR
       a_bm25_fused.py summarise CONFIG OUT_DIR STORED_DIR --log LOG.json --table TABLE.csv
                                 --rows ROWS.csv --files FILES.json [--host LABEL]
``run`` reads the stored encoded chunk and query vectors (no encoding); ``summarise`` writes the
paired-difference table, the query-level rows and the run-file hashes, and checks the control cell
against the stored chunk ranks. The logic is in ``ril.analysis.rq1_bm25_fused``.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import date
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ril.analysis import rq1_bm25_fused as fused  # noqa: E402 (path set above)
from ril.analysis.rq1_bm25_dev import cell_name  # noqa: E402 (path set above)
from ril.util.log import get_logger  # noqa: E402 (path set above)


def _write_csv(path: str, rows: list[dict[str, object]]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as handle:
        w = csv.DictWriter(handle, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run")
    for name in ("config", "data_root", "enc_root", "out_dir"):
        run.add_argument(name)
    summ = sub.add_parser("summarise")
    for name in ("config", "out_dir", "stored_dir"):
        summ.add_argument(name)
    for name in ("log", "table", "rows", "files"):
        summ.add_argument(f"--{name}", required=True)
    summ.add_argument("--host", default="ada")
    args = ap.parse_args()
    log = get_logger("a1_fused")
    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    if args.cmd == "run":
        n = fused.run_all(cfg, args.data_root, args.enc_root, args.out_dir)
        log.info("%d run files written", n)
        return 0
    runs = fused.load_runs(args.out_dir)
    rows = fused.query_rows(runs)
    table = fused.difference_table(
        rows, cfg, seed=int(cfg["seed"]), draws=int(cfg["bootstrap"]["draws"])
    )
    control = cell_name(fused.cells_of(cfg)[0])
    regression = fused.regression_against_stored(runs, cfg, args.stored_dir, control)
    files = [
        {
            "path": p.name,
            "bytes": p.stat().st_size,
            "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
        }
        for p in sorted(Path(args.out_dir).glob("*.json"))
    ]
    record = {
        "experiment": "E-A1-FUSED",
        "date": date.today().isoformat(),
        "config": args.config,
        "config_hash": hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest()[:12],
        "host": args.host,
        "hardware": runs[0]["hardware"] if runs else None,
        "regression_vs_stored_chunk_ranks": regression,
        "differences": table,
    }
    Path(args.log).write_text(json.dumps(record, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    Path(args.files).write_text(json.dumps(files, indent=1) + "\n", encoding="utf-8")
    _write_csv(args.table, table)
    _write_csv(args.rows, rows)
    log.info("regression exact: %s (%d checked)", regression["exact"], regression["checked"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
