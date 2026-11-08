"""BM25 tokenisation and k1/b on the development folders, chunk level (session A1, A1-DEV).

Usage: a_bm25_dev.py run CONFIG DATA_ROOT OUT_DIR --stage stage1|stage2 [--tokenizer NAME]
       a_bm25_dev.py summarise CONFIG OUT_DIR --log LOG.json --table TABLE.csv [--host LABEL]
       a_bm25_dev.py rows CONFIG OUT_DIR --tokenizer NAME --rows ROWS.csv --files FILES.json
``run`` is the cluster stage (resumable per folder, level and cell); ``summarise`` reads the run
files, applies the selection rule of the configuration and checks the regression control against
``results/tables/e1_dev_sweep.csv``. The logic is in ``ril.analysis.rq1_bm25_dev``.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ril.analysis import rq1_bm25_dev as a1  # noqa: E402 (path set above)
from ril.util.log import get_logger  # noqa: E402 (path set above)

E1_SWEEP = Path(__file__).resolve().parents[1] / "results/tables/e1_dev_sweep.csv"
E1_DEV_CONFIG = (
    Path(__file__).resolve().parents[1] / "configs/experiments/e1_bm25_reproduction.yaml"
)


def _e1_default() -> tuple[float, int, list[str]]:
    with open(E1_SWEEP, encoding="utf-8") as handle:
        row = next(r for r in csv.DictReader(handle) if r["is_default"] == "True")
    cfg = yaml.safe_load(E1_DEV_CONFIG.read_text(encoding="utf-8"))
    folders = [f["folder"] for f in cfg["folders"] if f["role"] == "dev"]
    return float(row["ndcg10_pooled"]), int(row["queries"]), folders


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run")
    run.add_argument("config")
    run.add_argument("data_root")
    run.add_argument("out_dir")
    run.add_argument("--stage", choices=("stage1", "stage2"), required=True)
    run.add_argument("--tokenizer", default=None)
    run.add_argument("--only", default=None, help="one folder name")
    summ = sub.add_parser("summarise")
    summ.add_argument("config")
    summ.add_argument("out_dir")
    summ.add_argument("--log", required=True)
    summ.add_argument("--table", required=True)
    summ.add_argument("--host", default="ada")
    rows_cmd = sub.add_parser("rows")
    rows_cmd.add_argument("config")
    rows_cmd.add_argument("out_dir")
    rows_cmd.add_argument("--tokenizer", required=True)
    rows_cmd.add_argument("--rows", required=True)
    rows_cmd.add_argument("--files", required=True)
    args = ap.parse_args()
    log = get_logger("a1_dev")
    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    if args.cmd == "run":
        cells = a1.stage_cells(cfg, args.stage, args.tokenizer)
        n = a1.run_cells(cfg, args.data_root, args.out_dir, cells, only=args.only)
        log.info("%s: %d run files written", args.stage, n)
        return 0
    if args.cmd == "rows":
        cells = a1.stage_cells(cfg, "stage1") + a1.stage_cells(cfg, "stage2", args.tokenizer)
        unique = list(dict.fromkeys(cells))
        query_rows = a1.query_level_rows(args.out_dir, unique)
        with open(args.rows, "w", newline="", encoding="utf-8") as handle:
            w = csv.DictWriter(handle, fieldnames=list(query_rows[0]))
            w.writeheader()
            w.writerows(query_rows)
        files = a1.run_file_hashes(args.out_dir)
        Path(args.files).write_text(json.dumps(files, indent=1) + "\n", encoding="utf-8")
        log.info("%d query rows, %d run files hashed", len(query_rows), len(files))
        return 0
    seed, draws = int(cfg["seed"]), int(cfg["bootstrap"]["draws"])
    default = ("ref", *a1.DEFAULT_K1_B)
    s1 = a1.stage_cells(cfg, "stage1")
    stage1 = a1.summarise_cells(args.out_dir, s1, default, seed=seed, draws=draws)
    pick1 = a1.choose(stage1, a1.cell_name(default))
    tok = pick1["adopted"].split("_k1_")[0]
    s2 = a1.stage_cells(cfg, "stage2", tok)
    base2 = (tok, *a1.DEFAULT_K1_B)
    stage2 = a1.summarise_cells(args.out_dir, s2, base2, seed=seed, draws=draws)
    pick2 = a1.choose(stage2, a1.cell_name(base2)) if len(stage2) == len(s2) else None
    expected, n_queries, folders = _e1_default()
    record = {
        "experiment": "A1-DEV",
        "date": date.today().isoformat(),
        "config": args.config,
        "config_hash": a1.config_hash(cfg),
        "host": args.host,
        "hardware": next(iter(a1.load_cell(args.out_dir, default)), {}).get("hardware"),
        "regression_e1_dev": a1.regression_check(args.out_dir, folders, expected, n_queries),
        "stage1": {"rows": stage1, "choice": pick1},
        "stage2": {"tokenizer": tok, "rows": stage2, "choice": pick2},
    }
    Path(args.log).write_text(json.dumps(record, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    rows = [{"stage": "stage1", **r} for r in stage1] + [{"stage": "stage2", **r} for r in stage2]
    with open(args.table, "w", newline="", encoding="utf-8") as handle:
        w = csv.DictWriter(handle, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    log.info("regression exact: %s", record["regression_e1_dev"]["exact"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
