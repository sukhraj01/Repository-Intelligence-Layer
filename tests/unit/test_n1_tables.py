"""The D47 reading is computed literally from the effect rows (E-PILOT-NOISE)."""

from __future__ import annotations

from typing import Any

from ril.analysis import n1_tables as n1
from ril.analysis import t2_tables as tt

Record = dict[str, Any]


def _row(cond: str, ref: str, level: str, d: float, half: float = 0.5) -> Record:
    return {
        "condition": cond,
        "part": "mean",
        "ref": f"{ref}:mean",
        "level": level,
        "reading": tt.READINGS[0],
        "kind": "dense",
        "repos": 5 if level == "L2" else 2,
        "d": d,
        "d_c_lo": d - half,
        "d_c_hi": d + half,
        "d_q_lo": d - half,
        "d_q_hi": d + half,
    }


def _both(cond: str, ref: str, d2: float, d3: float, half: float = 0.5) -> list[Record]:
    return [_row(cond, ref, "L2", d2, half), _row(cond, ref, "L3", d3, half)]


def test_reading_reports_degradation_recovery_and_shares() -> None:
    p = "n1"
    rows: list[Record] = []
    rows += _both("n1_r40_raw", n1.ANCHOR, -4.0, -6.0)
    rows += _both("n1_r40_oracle", "n1_r40_raw", 3.0, 4.5)
    rows += _both("n1_r40_filter_srs", "n1_r40_raw", 1.5, 2.25)
    rows += _both("n1_r40_filter_bm25", "n1_r40_raw", 0.1, 0.0)
    rows += _both("n1_r40_weight_srs", "n1_r40_raw", 0.8, 1.0, half=1.0)
    rows += _both("n1_r40_filter_srs", "n1_r40_sub", 0.7, 1.0)
    r = n1.reading_d47(rows, p, [40])["rates"]["40"]
    assert r["i_degrades"] and r["ii_oracle_recovers"]
    assert abs(r["ii_share_of_loss_recovered"]["L2"] - 0.75) < 1e-9
    m = r["iii_methods"]
    assert m["filter_srs"]["works"] and not m["filter_bm25"]["works"]
    assert not m["weight_srs"]["works"]  # interval reaches below 0
    assert abs(m["filter_srs"]["share_of_oracle_recovery"]["L3"] - 0.5) < 1e-9
    assert m["filter_srs"]["beats_subsample"]


def test_a_missing_level_is_not_a_pass() -> None:
    r = n1.reading_d47([], "n1", [20])["rates"]["20"]
    assert not r["i_degrades"] and not r["ii_oracle_recovers"]
    assert not any(v["works"] for v in r["iii_methods"].values())
