"""Write configs/experiments/eval_repos_v1.json from the inventory table (D100).

--inventory results/tables/eval_repo_inventory.csv --out configs/experiments/eval_repos_v1.json
Deterministic; no randomness. ``--seed`` is accepted for the log and must stay 0 (the key is fixed).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--inventory", default=str(ROOT / "results/tables/eval_repo_inventory.csv"))
    p.add_argument("--out", default=str(ROOT / "configs/experiments/eval_repos_v1.json"))
    p.add_argument("--seed", type=int, default=0)
    a = p.parse_args(argv)
    if a.seed != 0:
        p.error("the key is sha256('0:<repository>'); --seed must be 0")

    from ril.analysis import eval_repo_selection as sel

    inv = Path(a.inventory)
    s = sel.select(inv)
    doc = {
        "decision": "D100",
        "rule": sel.RULE_TEXT,
        "key": f'sha256("{sel.KEY_PREFIX}<repository>")',
        "floor_l2_queries": sel.FLOOR_L2_QUERIES,
        "eligible": s.eligible,
        "inventory_sha256": sel.sha256_file(inv),
        "evaluation": [{"repository": r, "l2_queries": n} for r, n in s.primary],
        "reserve": [{"repository": r, "l2_queries": n} for r, n in s.reserve],
    }
    Path(a.out).write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
