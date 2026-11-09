"""Compare a native paired BM25 dev run with the stored operator summary (E-C-CATCHUP).

Usage: c_native_compare.py NATIVE_RESULTS.json REPORTED.json --rows ROWS.csv --table TABLE.csv
       --log LOG.json [--run-files DIR]
The logic is in ``ril.analysis.c1_native_compare``; the native results file is written by
``python -m ril.evaluation.run``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ril.analysis import c1_native_compare as cmp  # noqa: E402 (path set above)
from ril.util.log import get_logger  # noqa: E402 (path set above)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("native")
    parser.add_argument("reported")
    parser.add_argument("--rows", required=True)
    parser.add_argument("--table", required=True)
    parser.add_argument("--log", required=True)
    parser.add_argument("--run-files")
    args = parser.parse_args()
    log = get_logger("c_native_compare")
    result = json.loads(Path(args.native).read_text())
    cells = cmp.compare_cells(result["metrics"], cmp.load_reported(Path(args.reported)))
    rows = cmp.query_rows(result)
    cmp.write_csv(Path(args.rows), rows)
    cmp.write_csv(Path(args.table), cells)
    summary = {
        "config_hash": result["config_hash"],
        "git_hash": result["git_hash"],
        "seed": result["seed"],
        "bootstrap_draws": result["bootstrap_draws"],
        "query_rows": len(rows),
        "verdicts": {
            v: sum(c["verdict"] == v for c in cells) for v in ("agree", "point_only", "differ")
        },
        "paired_delta_check": cmp.paired_deltas(rows),
        "input_hashes": result["input_hashes"],
        "native_rows_sha256": cmp.sha256_file(Path(args.rows)),
        "run_files": cmp.run_file_listing(Path(args.run_files)) if args.run_files else [],
    }
    Path(args.log).write_text(json.dumps(summary, sort_keys=True, indent=2) + "\n")
    log.info("verdicts %s over %d cells, %d query rows", summary["verdicts"], len(cells), len(rows))


if __name__ == "__main__":
    main()
