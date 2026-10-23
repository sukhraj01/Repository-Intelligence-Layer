"""L3 positive census (wrapper over ``ril.analysis.l3_census``). Counts only.

Usage:
  x1_census.py meta IDS_ALL.json OUT_META.json PARQUET... --folders DATASET/FOLDER ...
  x1_census.py tables OUT_PREFIX UNITS_DIR [UNITS_DIR ...] [--seed 0]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ril.analysis.e1_tables import write_csv  # noqa: E402
from ril.analysis.l3_census import census, census_meta, load_records  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("stage", choices=["meta", "tables"])
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--folders", nargs="*", default=[])
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    if args.stage == "meta":
        import pyarrow.parquet as pq  # noqa: PLC0415 - local only

        ids_all, out, *parquets = args.paths
        with open(ids_all, encoding="utf-8") as handle:
            listing = json.load(handle)
        wanted = {f: sorted(listing[f"LEVEL-3/{f}"]["qrels_query_ids"]) for f in args.folders}
        cols = ["instance_id", "repo", "base_commit", "patch"]
        tables = [pq.read_table(p, columns=cols).to_pylist() for p in parquets]
        meta = census_meta(wanted, tables)
        with open(out, "w", encoding="utf-8") as handle:
            json.dump(meta, handle)
        sys.stdout.write(
            json.dumps({"wanted": sum(len(v) for v in wanted.values()), "found": len(meta)}) + "\n"
        )
        return 0
    prefix, *dirs = args.paths
    records = [r for d in dirs for r in load_records(d)]
    kinds, novelty = census(records, seed=args.seed)
    write_csv(f"{prefix}_kinds.csv", kinds)
    write_csv(f"{prefix}_novelty.csv", novelty)
    sys.stdout.write(json.dumps({"records": len(records), "rows": len(kinds)}) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
