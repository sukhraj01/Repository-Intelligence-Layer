"""Tables of pilot M from its records (counts and intervals only). Thin wrapper.

Usage: m_tables.py RECORDS.json OUT_DIR --seed N [--boot N]
Writes m_match.csv, m_categories.csv, m_categories_by_folder.csv, m_kinds.csv,
m_reach_exclusions.csv, m_family_incidence.csv and m_reach.csv.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ril.analysis.reach_tables import (  # noqa: E402
    BOOTSTRAP_DRAWS,
    category_folder_rows,
    category_rows,
    exclusion_rows,
    incidence_rows,
    kind_rows,
    match_rows,
    reach_rows,
    write_rows,
)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("records")
    ap.add_argument("out_dir")
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument(
        "--reference",
        default="results/logs/s3_codeunit_chunk_mapping_2026-10-17.json",
        help="the first label sample's per-folder counts",
    )
    ap.add_argument("--boot", type=int, default=BOOTSTRAP_DRAWS)
    args = ap.parse_args()
    doc = json.loads(Path(args.records).read_text(encoding="utf-8"))
    inst = doc["instances"]
    out = Path(args.out_dir)
    write_rows(str(out / "m_match.csv"), match_rows(inst))
    write_rows(str(out / "m_categories.csv"), category_rows(inst))
    reference = json.loads(Path(args.reference).read_text(encoding="utf-8"))["per_folder"]
    write_rows(str(out / "m_categories_by_folder.csv"), category_folder_rows(inst, reference))
    write_rows(str(out / "m_kinds.csv"), kind_rows(inst))
    write_rows(str(out / "m_reach_exclusions.csv"), exclusion_rows(inst))
    write_rows(str(out / "m_family_incidence.csv"), incidence_rows(inst))
    reach = reach_rows(inst, seed=args.seed, draws=args.boot)
    reach += reach_rows(
        inst, seed=args.seed, draws=args.boot, label="sensitivity_several_locations"
    )
    write_rows(str(out / "m_reach.csv"), reach)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
