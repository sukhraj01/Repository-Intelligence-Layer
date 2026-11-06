"""Gold in the assembled context (E-ASSEMBLY): measurement, tables and the tokenizer ratio.

Usage:
  assembly_run.py measure CONFIG E3_CACHE DENSE_ROOT REPO_CACHE WORK_DIR OUT_DIR [--seed N]
  assembly_run.py tables  OUT_DIR TABLE_PREFIX [--seed N]
  assembly_run.py cap_tables OUT_DIR TABLE_PREFIX [--seed N]
  assembly_run.py ratio   REPO_DIR REPO_ID TOKENIZER_JSON OUT_JSON [--name NAME] [--seed N]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import yaml  # noqa: E402

from ril.util.log import get_logger  # noqa: E402
from ril.util.seed import set_seed  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("stage", choices=["measure", "tables", "cap_tables", "ratio"])
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--only")
    ap.add_argument("--name", help="name recorded for the real tokenizer (ratio)")
    ap.add_argument("--limit", type=int)
    args = ap.parse_args()
    set_seed(args.seed)
    log = get_logger("assembly")
    if args.stage == "measure":
        from ril.assembly.measure import run_measure

        cfg = yaml.safe_load(Path(args.paths[0]).read_text(encoding="utf-8"))
        cache, dense, repos, work, out = args.paths[1:6]
        counts = run_measure(cfg, cache, dense, repos, work, out, only=args.only, limit=args.limit)
        log.info("%s", {k: v for k, v in counts.items() if k != "failures"})
        Path(out, "failures.json").write_text(json.dumps(counts["failures"], indent=1))
        return 0
    if args.stage == "tables":
        from ril.analysis.assembly_tables import coverage_rows, load_rows, summary_rows
        from ril.analysis.x2_tables import write_csv

        out_dir, prefix = args.paths[:2]
        rows, coverage = load_rows(out_dir)
        write_csv(f"{prefix}_summary.csv", summary_rows(rows, args.seed))  # type: ignore[arg-type]
        write_csv(f"{prefix}_coverage.csv", coverage_rows(coverage, rows))  # type: ignore[arg-type]
        write_csv(f"{prefix}_query_rows.csv", rows)
        log.info("%d query rows -> %s_*.csv", len(rows), prefix)
        return 0
    if args.stage == "cap_tables":
        from ril.analysis.assembly_tables import (
            cap_selection_rows,
            coverage_rows,
            load_rows,
            paired_rows,
            summary_rows,
        )
        from ril.analysis.x2_tables import write_csv

        out_dir, prefix = args.paths[:2]
        rows, coverage = load_rows(out_dir)
        write_csv(f"{prefix}_summary.csv", summary_rows(rows, args.seed))  # type: ignore[arg-type]
        write_csv(f"{prefix}_coverage.csv", coverage_rows(coverage, rows))  # type: ignore[arg-type]
        write_csv(f"{prefix}_selection.csv", cap_selection_rows(rows))  # type: ignore[arg-type]
        write_csv(f"{prefix}_paired.csv", paired_rows(rows, seed=args.seed))  # type: ignore[arg-type]
        write_csv(f"{prefix}_query_rows.csv", rows)
        log.info("%d query rows -> %s_*.csv", len(rows), prefix)
        return 0
    from ril.assembly.measure import snapshot_units
    from ril.assembly.tokens import ApproxTokenizer, HFTokenizer, ratio_against

    repo_dir, repo_id, tok_json, out_json = args.paths[:4]
    texts = [u.source for u in snapshot_units(repo_dir, repo_id)]
    real = HFTokenizer(tok_json, args.name or Path(tok_json).parent.name)
    result = ratio_against(ApproxTokenizer(), real, texts, seed=args.seed)
    Path(out_json).write_text(json.dumps(result, sort_keys=True, indent=1), encoding="utf-8")
    log.info("%s", result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
