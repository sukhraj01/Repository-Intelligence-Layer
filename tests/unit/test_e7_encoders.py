"""Unit tests of the E7 encoder-number helpers (numpy only)."""

import numpy as np

from ril.analysis.e3_tables import COLUMN, EvalTable
from ril.evaluation.e7_encoders import form_keys, per_repo_diff


def _table() -> EvalTable:
    keys = ["a", "b"]
    rows = [
        {"level": "L2", "repo": "r1", "role": "dev"},
        {"level": "L2", "repo": "r1", "role": "dev"},
        {"level": "L2", "repo": "r2", "role": "dev"},
        {"level": "L3", "repo": "r2", "role": "dev"},
    ]
    m = np.zeros((4, 2, 8))
    col = COLUMN[("units_all_nomod", "ndcg10")]
    m[:, 0, col] = [0.5, 0.3, 0.2, 0.9]
    m[:, 1, col] = [0.1, 0.1, 0.3, 0.1]
    return EvalTable(keys, {"a": 0, "b": 1}, rows, m, [], np.zeros((4, 0, 5)))


def test_per_repo_diff_means_per_repository_and_level() -> None:
    out = per_repo_diff(_table(), "dev", "a", "b", "L2", "units_all_nomod", "ndcg10")
    assert [(r["repo"], r["queries"], r["d"]) for r in out] == [("r1", 2, 30.0), ("r2", 1, -10.0)]


def test_per_repo_diff_is_antisymmetric() -> None:
    ab = per_repo_diff(_table(), "dev", "a", "b", "L2", "units_all_nomod", "ndcg10")
    ba = per_repo_diff(_table(), "dev", "b", "a", "L2", "units_all_nomod", "ndcg10")
    assert [r["d"] for r in ab] == [-r["d"] for r in ba]


def test_form_keys_name_every_column() -> None:
    assert form_keys("enc", "header") == ["bm25|header", "dense|enc|header", "rrf|enc|header"]
