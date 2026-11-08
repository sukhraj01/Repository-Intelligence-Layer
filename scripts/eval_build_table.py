"""Write results/tables/eval_repo_build_measured.csv from the build logs (D100).

--cache-stats cs.json --verify verify.json --encode encode_run.json
Deterministic. Reads the selection, the inventory (for the estimates) and three log files.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--selection", default=str(ROOT / "configs/experiments/eval_repos_v1.json"))
    p.add_argument("--inventory", default=str(ROOT / "results/tables/eval_repo_inventory.csv"))
    p.add_argument("--cache-stats", required=True)
    p.add_argument("--verify", required=True)
    p.add_argument("--encode", required=True)
    p.add_argument("--out", default=str(ROOT / "results/tables/eval_repo_build_measured.csv"))
    p.add_argument("--repository", action="append", default=None, help="built repositories")
    p.add_argument("--seed", type=int, default=0)
    a = p.parse_args(argv)

    from ril.analysis import eval_build_table as ebt

    sel = json.loads(Path(a.selection).read_text(encoding="utf-8"))
    built = a.repository or [e["repository"] for e in sel["evaluation"]]
    by_name = {e["repository"]: e for e in sel["evaluation"] + sel["reserve"]}
    with open(a.inventory, encoding="utf-8", newline="") as fh:
        inventory = {r["repository"]: r for r in csv.DictReader(fh)}
    run = json.loads(Path(a.encode).read_text(encoding="utf-8"))["runs"][0]
    rows = ebt.build_rows(
        [by_name[r] for r in built],
        inventory,
        json.loads(Path(a.cache_stats).read_text(encoding="utf-8")),
        json.loads(Path(a.verify).read_text(encoding="utf-8")),
        run["stores"],
    )
    ebt.write_csv(rows, a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
