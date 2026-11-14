"""Run-agreement summary of the graded untrained arm and the calibration of the repeat probability.

Implements ``docs/experiments/B.md`` E-RQ3-RUN-AGREEMENT. Fast: reads the stored rows only.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ril.analysis import rq3_run_agreement as ra

ROOT = Path(__file__).resolve().parents[2]
DRIVER = ROOT / "results" / "rq3_driver"
RUN = DRIVER / "untrained_runs" / "gemini-3.8-flash" / "rrf_runs0-2"


def test_summary_on_a_small_example() -> None:
    res = {
        "a": {0: True, 1: True, 2: True},
        "b": {0: False, 1: False, 2: False},
        "c": {0: True, 1: False, 2: False},
        "d": {0: False, 1: True, 2: True},
    }
    s = ra.agreement_summary(res)
    assert (s["resolved_in_3"], s["resolved_in_some"], s["resolved_in_none"]) == (1, 2, 1)
    assert s["pairs"]["0-1"]["agree"] == 2 and s["pairs"]["1-2"]["agree"] == 4
    assert s["pooled_agreement_counts"] == [8, 12]


def test_summary_needs_three_repeats() -> None:
    with pytest.raises(ValueError):
        ra.agreement_summary({"a": {0: True, 1: True}})


def test_calibration_round_trips_and_is_monotone() -> None:
    for kappa in (1.0, 4.0):
        s = ra.calibrate_s(0.94, 0.4, kappa)
        assert s is not None
        assert abs(ra.implied_pooled_agreement(s, 0.4, kappa) - 0.94) < 1e-9
    # heterogeneity alone already explains an agreement at or below the chance agreement
    assert ra.calibrate_s(0.7, 0.4, 1.0) is None
    assert ra.implied_pooled_agreement(1.0, 0.4, 1.0) == pytest.approx(1.0)


def test_stored_rows_give_the_recorded_counts() -> None:
    s = ra.agreement_summary(ra.resolved_by_instance(ra.read_jsonl(RUN / "results.jsonl")))
    assert (s["resolved_in_3"], s["resolved_in_some"], s["resolved_in_none"]) == (118, 29, 180)
    assert [s["pairs"][k]["differ"] for k in ("0-1", "0-2", "1-2")] == [23, 28, 7]
    assert s["pooled_agreement_counts"] == [923, 981]


def test_stored_output_matches_the_rows() -> None:
    stored = json.loads((DRIVER / "rq3_run_agreement.json").read_text())
    s = ra.agreement_summary(ra.resolved_by_instance(ra.read_jsonl(RUN / "results.jsonl")))
    assert stored["pairs"] == s["pairs"]
    assert stored["pooled_agreement"] == s["pooled_agreement"]
