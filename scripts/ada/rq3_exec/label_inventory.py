# ruff: noqa: T201  (standalone cluster helper; stdlib only, prints one JSON line)
"""Which Verified instances carry L2 / L3 labels and a stored unit record (read-only listing).

Usage: python3 label_inventory.py RAW_DATA_ROOT UNIT_DIR [UNIT_DIR ...] > inventory.json
Query ids of a folder are the ids in its qrels with a positive score (the loader drops queries
without qrels, ``ril/evaluation/core_bench.py``).
"""

import json
import os
import sys


def qrel_ids(path: str) -> set[str]:
    out: set[str] = set()
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                row = json.loads(line)
                if float(row.get("score", 1)) > 0:
                    out.add(str(row["query_id"]))
    return out


def main() -> None:
    root, unit_dirs = sys.argv[1], sys.argv[2:]
    levels: dict[str, set[str]] = {"L2": set(), "L3": set()}
    for level, name in (("L2", "LEVEL-2"), ("L3", "LEVEL-3")):
        base = os.path.join(root, name, "SWE-bench_Verified")
        for folder in sorted(os.listdir(base)):
            levels[level] |= qrel_ids(os.path.join(base, folder, "qrels.jsonl"))
    units: set[str] = set()
    for d in unit_dirs:
        units |= {f[:-5] for f in os.listdir(d) if f.endswith(".json")}
    print(
        json.dumps(
            {
                "l2": sorted(levels["L2"]),
                "l3": sorted(levels["L3"]),
                "unit_records": sorted(units),
            }
        )
    )


main()
