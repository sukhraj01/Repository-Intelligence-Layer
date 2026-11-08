"""D100 build inputs: folders from the inventory, shared-folder marking, base-commit table."""

from __future__ import annotations

import csv
from pathlib import Path

from ril.evaluation import eval_build_inputs as ebi

SHA = "a" * 40


def test_folders_config_and_meta(tmp_path: Path) -> None:
    inv = tmp_path / "inv.csv"
    with inv.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["repository", "l2_queries_by_folder"])
        w.writerow(["o/r", "DS/shared=3;Other/solo=1"])
    folders = ebi.folders_of(str(inv), ["o/r"])
    assert folders == [("o/r", "DS", "shared"), ("o/r", "Other", "solo")]
    cfg = ebi.build_config({"seed": 0, "folders": [], "bm25": {"k1": 1.5}}, folders)
    assert [f["role"] for f in cfg["folders"]] == ["test", "test"]
    assert all(f["levels"] == ["L2"] and f["instances_of_repo"] for f in cfg["folders"])
    ids = {
        "LEVEL-2/DS/shared": {"qrels_query_ids": {"o__r-1": 1, "x__y-2": 1, "O__R-3": 1}},
        "LEVEL-2/Other/solo": {"qrels_query_ids": {"o__r-9": 1}},
    }
    tables = {
        "DS": [
            {"instance_id": "o__r-1", "base_commit": SHA, "patch": "p"},
            {"instance_id": "O__R-3", "base_commit": "short", "patch": ""},
        ]
    }
    meta, missing = ebi.build_meta(folders, ids, tables)
    assert sorted(meta) == ["o__r-1"]
    assert {m["instance"]: m["reason"] for m in missing} == {
        "O__R-3": "bad_base_commit",
        "o__r-9": "no_metadata",
    }
