"""D100 selection: the recorded list is exactly what the rule gives on the inventory."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from ril.analysis import eval_repo_selection as sel

ROOT = Path(__file__).resolve().parents[2]
INVENTORY = ROOT / "results/tables/eval_repo_inventory.csv"
CONFIG = ROOT / "configs/experiments/eval_repos_v1.json"


def _write(path: Path, rows: list[tuple[str, str, str, int]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["repository", "set_group", "language_class", "l2_queries"])
        w.writerows(rows)


def test_filters_and_order(tmp_path: Path) -> None:
    rows = [(f"o/r{i}", "other", "python", 5 + i) for i in range(20)]
    rows += [
        ("o/dev", "dev", "python", 50),
        ("o/ver", "verified", "python", 50),
        ("o/mixed", "other", "mixed", 50),
        ("o/low", "other", "python", 4),
    ]
    p = tmp_path / "inv.csv"
    _write(p, rows)
    s = sel.select(p)
    assert s.eligible == 20
    names = [n for n, _ in s.primary + s.reserve]
    assert not {"o/dev", "o/ver", "o/mixed", "o/low"} & set(names)
    assert len(names) == 16 and len(set(names)) == 16
    assert [sel.order_key(n) for n in names] == sorted(sel.order_key(n) for n in names)


def test_recorded_config_matches_rule() -> None:
    s = sel.select(INVENTORY)
    doc = json.loads(CONFIG.read_text(encoding="utf-8"))
    assert s.eligible == doc["eligible"] == 67
    assert [(d["repository"], d["l2_queries"]) for d in doc["evaluation"]] == s.primary
    assert [(d["repository"], d["l2_queries"]) for d in doc["reserve"]] == s.reserve
    assert doc["inventory_sha256"] == sel.sha256_file(INVENTORY)
