"""Tables and run log of pilot E1/E2 from the run records. Thin wrapper.

Usage: e1_tables.py RUN_DIR OUT_DIR --config CONFIG --seed N [--boot N] [--log PATH]
       [--full-dir DIR --full-config CONFIG] [--job-ids TEXT] [--code-commit HASH]
RUN_DIR holds ``chunk/`` and ``units/`` as written by e1_run.py. Writes ``e1_*.csv`` and
``e2_*.csv`` (counts, means and intervals only) and, with --log, a counts-only run log.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ril.analysis.e1_run_log import build_run_log  # noqa: E402
from ril.analysis.e1_tables import (  # noqa: E402
    aggregation_table,
    chunk_query_rows,
    chunk_summary,
    conclusion_table,
    confirm_paired,
    load_chunk_runs,
    load_unit_runs,
    module_effect,
    noise_tables,
    per_folder_counts,
    positive_tables,
    protocol_vs_filter,
    sweep_table,
    unit_query_rows,
    unit_summary,
    write_csv,
)
from ril.evaluation.e1_run import config_hash, load_config  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("run_dir")
    ap.add_argument("out_dir")
    ap.add_argument("--config", required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--boot", type=int, default=2000)
    ap.add_argument("--log", default="")
    ap.add_argument("--full-dir", default="")
    ap.add_argument("--full-config", default="")
    ap.add_argument("--sweep-dir", default="")
    ap.add_argument("--confirm-dir", default="")
    ap.add_argument("--confirm-setting", default="")
    ap.add_argument("--job-ids", default="")
    ap.add_argument("--code-commit", default="")
    args = ap.parse_args()
    out = Path(args.out_dir)
    chunk_runs = load_chunk_runs(args.run_dir)
    unit_runs = load_unit_runs(args.run_dir)
    rows = chunk_query_rows(chunk_runs)
    urows = unit_query_rows(unit_runs)
    s, b = args.seed, args.boot
    write_csv(str(out / "e1_folders.csv"), per_folder_counts(chunk_runs))
    write_csv(str(out / "e1_chunk_summary.csv"), chunk_summary(rows, s, b))
    write_csv(str(out / "e1_protocol_vs_filter.csv"), protocol_vs_filter(rows, s, b))
    write_csv(str(out / "e1_unit_summary.csv"), unit_summary(urows, s, b))
    write_csv(str(out / "e1_module_effect.csv"), module_effect(urows, s, b))
    kinds, noise = positive_tables(unit_runs)
    write_csv(str(out / "e1_positive_kinds.csv"), kinds)
    write_csv(str(out / "e2_positive_noise_classes.csv"), noise)
    tabs = noise_tables(rows, unit_runs, urows, s, b)
    write_csv(str(out / "e2_chunk_label_sets.csv"), tabs["chunk"])
    write_csv(str(out / "e2_unit_label_sets.csv"), tabs["unit"])
    write_csv(str(out / "e2_conclusions.csv"), conclusion_table(rows, unit_runs, urows, s, b))
    full_rows: list[dict[str, object]] = []
    if args.full_dir:
        full_runs = load_chunk_runs(args.full_dir)
        full_rows = chunk_query_rows(full_runs)
        write_csv(str(out / "e1_full_l2_folders.csv"), per_folder_counts(full_runs))
        write_csv(str(out / "e1_full_l2_summary.csv"), chunk_summary(full_rows, s, b))
        write_csv(
            str(out / "e1_full_l2_protocol_vs_filter.csv"), protocol_vs_filter(full_rows, s, b)
        )
    ref = {
        ("full_l2", "L2"): (13.0, 38.8),
        ("verified12", "L2"): (11.9, 46.7),
        ("verified12", "L3"): (22.2, 33.9),
    }
    agg = aggregation_table(
        rows, {"verified12": lambda r: r["role"] == "test"}, ref, s, min(b, 1000)
    )
    if full_rows:
        datasets = sorted({r["dataset"] for r in full_rows})
        sets: dict[str, Callable[[dict[str, Any]], bool]] = {"full_l2": lambda r: True}
        for ds in datasets:
            sets[f"dataset:{ds}"] = lambda r, ds=ds: bool(r["dataset"] == ds)
        agg += aggregation_table(full_rows, sets, ref, s, min(b, 1000))
    write_csv(str(out / "e1_aggregation.csv"), agg)
    if args.sweep_dir:
        write_csv(str(out / "e1_dev_sweep.csv"), sweep_table(args.sweep_dir, (1.5, 0.75), s, b))
    if args.confirm_dir:
        crows = chunk_query_rows(load_chunk_runs(args.confirm_dir))
        cs = chunk_summary(crows, s, b)
        for r in cs:
            r["setting"] = args.confirm_setting
        write_csv(str(out / "e1_confirm_summary.csv"), cs)
        write_csv(str(out / "e1_confirm_paired.csv"), confirm_paired(rows, crows, s, b))
    if args.log:
        cfg = load_config(args.config)
        full_cfg = load_config(args.full_config) if args.full_config else None
        build_run_log(
            args.log,
            config_hash=config_hash(cfg),
            full_config_hash=config_hash(full_cfg) if full_cfg else "",
            seed=s,
            draws=b,
            chunk_runs=chunk_runs,
            unit_runs=unit_runs,
            full_rows=full_rows,
            job_ids=args.job_ids,
            code_commit=args.code_commit,
            unit_failures_dir=args.run_dir,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
