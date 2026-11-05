"""Evaluation-repository inventory (E-EVAL-REPOS): splitting, classes, estimates, flags."""

from __future__ import annotations

from pathlib import Path

import pytest

from ril.analysis import eval_repo_inventory as inv

IDS = {
    "LEVEL-2/SWE-bench_Verified/a__alpha": {
        "queries_ids": ["a__alpha-1", "a__alpha-2"],
        "qrels_query_ids": {"a__alpha-1": 3, "a__alpha-2": 4},
    },
    "LEVEL-3/SWE-bench_Verified/a__alpha": {
        "queries_ids": ["a__alpha-1"],
        "qrels_query_ids": {"a__alpha-1": 30},
    },
    "LEVEL-2/Other/shared": {
        "queries_ids": ["x__one-5", "x__one-6", "y__two-7"],
        "qrels_query_ids": {"x__one-5": 1, "x__one-6": 2, "y__two-7": 3},
    },
    "LEVEL-2/Other/c__gamma": {"queries_ids": ["c__gamma-9"], "qrels_query_ids": {"c__gamma-9": 1}},
    "Rewrite-LEVEL-2/Other/c__gamma": {"queries_ids": ["c__gamma-9"], "qrels_query_ids": {}},
}
ROWS = {
    "LEVEL-2/SWE-bench_Verified/a__alpha": 1000,
    "LEVEL-2/Other/shared": 600,
    "LEVEL-2/Other/c__gamma": 500,
}
STORE = {
    "a__alpha": {
        "unit_records": 2,
        "dense": 2,
        "units": [100, 140],
        "seconds": [10.0, 14.0],
        "distinct_unit_texts": 250,
    }
}
SURVEY = {
    "stores": STORE,
    "bare_clones": {"a__alpha": {"py_files_at_head": 60}},
    "language": {
        "LEVEL-2/SWE-bench_Verified/a__alpha": {"python": 90, "other_code": 5, "nocode": 10},
        "LEVEL-2/Other/shared": {"python": 1, "other_code": 80, "nocode": 5},
        "LEVEL-2/Other/c__gamma": {"python": 3, "other_code": 3, "nocode": 0},
    },
    "population": {
        "raw_pool_repos": {"c/gamma": 4, "z/zeta": 2},
        "pool_after_filter_repos": {"z/zeta": 2},
        "mining_population_repos": {"z/zeta": 2},
    },
}


def _rows() -> dict[str, dict[str, object]]:
    rows = inv.build_rows(
        folder_queries=inv.folder_repo_queries(IDS),
        corpus_rows=ROWS,
        folder_sets={"LEVEL-2/SWE-bench_Verified/a__alpha": "test"},
        store_folders={"a/alpha": "LEVEL-2/SWE-bench_Verified/a__alpha"},
        survey=SURVEY,
        is_held_out=lambda r: r != "y/two",
        resolve=lambda r: r,
    )
    return {str(r["repository"]): r for r in rows}


def test_folder_split_by_instance_id_and_rewrite_skipped() -> None:
    fq = inv.folder_repo_queries(IDS)
    assert "Rewrite-LEVEL-2/Other/c__gamma" not in fq
    assert set(fq["LEVEL-2/Other/shared"]) == {"x/one", "y/two"}
    assert fq["LEVEL-2/Other/shared"]["x/one"]["positives"] == 3
    with pytest.raises(ValueError, match="unreadable"):
        inv.folder_repo_queries({"LEVEL-2/D/f": {"queries_ids": ["nounderscore-1"]}})


def test_counts_and_sharing() -> None:
    rows = _rows()
    assert set(rows) == {"a/alpha", "x/one", "y/two", "c/gamma"}
    a = rows["a/alpha"]
    assert (a["l2_queries"], a["l3_queries"], a["l2_positive_rows"], a["l3_positive_rows"]) == (
        2,
        1,
        7,
        30,
    )
    assert a["set_group"] == "verified" or a["set_group"] == "other"
    assert rows["x/one"]["folder_shared_with_other_repos"] == 1
    assert rows["c/gamma"]["folder_shared_with_other_repos"] == 0
    # chunks of a shared folder are split by query share (2 of 3 queries -> 400 of 600)
    assert rows["x/one"]["l2_corpus_chunks_in_folder"] == 400


def test_language_classes() -> None:
    rows = _rows()
    assert rows["a/alpha"]["language_class"] == "python"
    assert rows["x/one"]["language_class"] == "non_python"
    assert rows["c/gamma"]["language_class"] == "unknown"  # six code chunks: below the minimum
    assert inv.language_class(None) == ("unknown", None, 0)
    assert inv.language_class({"python": 50, "other_code": 50})[0] == "python"
    assert inv.language_class({"python": 15, "other_code": 85})[0] == "mixed"


def test_measured_and_estimated_units_and_costs() -> None:
    rows = _rows()
    a = rows["a/alpha"]
    assert a["units_basis"].startswith("measured") and a["distinct_unit_texts"] == 250
    assert a["parse_seconds"] == 24.0 and a["files_estimate"] == 60
    # ratio 250 texts per 1000 chunks -> 0.25; c/gamma has 500 chunks -> 125 texts
    g = rows["c/gamma"]
    assert g["units_basis"].startswith("estimated") and g["distinct_unit_texts"] == 125
    assert g["distinct_unit_texts_low"] == g["distinct_unit_texts_high"] == 125
    assert g["encode_gpu_hours_at_178"] == round(125 / 178 / 3600, 4)
    assert g["encode_gpu_hours_stored_figure"] == 0.06
    # median units per snapshot 120 over 1000 chunks -> 500 chunks -> 60 units;
    # 120 units over 60 files = 2 per file -> 30 files
    assert g["units_per_snapshot"] == 60 and g["files_estimate"] == 30


def test_leak_flags_come_from_the_training_population_not_the_raw_listing() -> None:
    rows = _rows()
    g = rows["c/gamma"]
    assert g["in_published_pool_listing"] == 1  # present in the raw listing
    assert g["in_training_population"] == 0 and g["leaks_if_evaluated"] == 0  # filtered out
    assert rows["a/alpha"]["in_published_pool_listing"] == 0
    assert rows["y/two"]["held_out_listed"] == 0


def test_csv_columns_and_summary(tmp_path: Path) -> None:
    rows = list(_rows().values())
    out = tmp_path / "inv.csv"
    inv.write_csv(rows, str(out))
    header = out.read_text(encoding="utf-8").splitlines()[0].split(",")
    assert tuple(header) == inv.COLUMNS
    s = inv.summarise(rows)
    assert s["repositories"] == 4 and s["with_l3"] == 1 and s["leaking"] == 0
