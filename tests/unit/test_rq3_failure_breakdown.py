"""Failure breakdown on a small fixture (E-RQ3-FAILURE-BREAKDOWN): classes, status, counts."""

from __future__ import annotations

import math

import numpy as np

from ril.analysis import rq3_failure_breakdown as fb


def _row(iid: str, arm: str, run: int, outcome: str) -> dict[str, object]:
    return {
        "instance_id": iid,
        "arm": arm,
        "run": run,
        "outcome": outcome,
        "resolved": outcome == "resolved",
        "input_tokens": 1000,
        "cached_tokens": 400,
        "output_tokens": 50,
        "thought_tokens": 5,
        "calls": 2,
        "cost_usd": 0.01,
    }


def test_outcome_classes() -> None:
    assert fb.outcome_class("resolved") == "resolved"
    assert fb.outcome_class("unusable") == "no_usable_edit"
    assert fb.outcome_class("apply_failed:no_match") == "edits_failed_to_apply"
    assert fb.outcome_class("apply_failed:multiple_matches") == "edits_failed_to_apply"
    assert fb.outcome_class("executed_unresolved") == "tests_failed"
    assert fb.outcome_class("exec_error:x") == "exec_error"


def test_status_and_presence() -> None:
    assert fb.status_of(0, 0) == "na"
    assert fb.status_of(2, 2) == "all"
    assert fb.status_of(2, 1) == "some"
    assert fb.status_of(2, 0) == "none"
    entries = [{"file": "a.py", "unit_id": "a.py::f"}, {"file": "b.py", "unit_id": "b.py::g"}]
    p = fb.presence(entries, ["a.py", "c.py"], ["a.py::f", "a.py::h"])
    assert p == {"n_gold_files": 2, "files_in": 1, "n_gold_units": 2, "units_in": 1}


PRES_BASE = {
    "i1": dict(
        n_gold_files=1, files_in=0, n_gold_files_py=1, files_in_py=0, n_gold_units=1, units_in=0
    ),
    "i2": dict(
        n_gold_files=2, files_in=2, n_gold_files_py=2, files_in_py=2, n_gold_units=2, units_in=1
    ),
    "i3": dict(
        n_gold_files=1, files_in=1, n_gold_files_py=1, files_in_py=1, n_gold_units=1, units_in=1
    ),
    "i4": dict(
        n_gold_files=0, files_in=0, n_gold_files_py=0, files_in_py=0, n_gold_units=0, units_in=0
    ),
}
PRES_ARM = {
    "i1": dict(
        n_gold_files=1, files_in=1, n_gold_files_py=1, files_in_py=1, n_gold_units=1, units_in=1
    ),  # gain
    "i2": dict(
        n_gold_files=2, files_in=1, n_gold_files_py=2, files_in_py=1, n_gold_units=2, units_in=1
    ),  # all -> some
    "i3": dict(
        n_gold_files=1, files_in=1, n_gold_files_py=1, files_in_py=1, n_gold_units=1, units_in=1
    ),  # kept
    "i4": dict(
        n_gold_files=0, files_in=0, n_gold_files_py=0, files_in_py=0, n_gold_units=0, units_in=0
    ),
}
OUTS = {
    "i1": ["resolved", "unusable"],
    "i2": ["executed_unresolved", "resolved"],
    "i3": ["resolved", "resolved"],
    "i4": ["apply_failed:no_match", "unusable"],
}


def _rows(arm: str) -> list[dict[str, object]]:
    return [_row(i, arm, k, o) for i, outs in OUTS.items() for k, o in enumerate(outs)]


def test_attempts_and_failure_split() -> None:
    att = fb.attempts(_rows("a"), "a", OUTS, PRES_BASE)
    assert len(att) == 8
    split = {r["outcome_class"]: r for r in fb.failure_split(att, "file_status")}
    assert split["no_usable_edit"]["n"] == 2 and split["no_usable_edit"]["none"] == 1
    assert split["tests_failed"]["all"] == 1
    total = split["all_unresolved"]
    assert total["n"] == 4 and total["na"] == 2
    assert math.isclose(total["share_all_gold"], 1 / 4)


def test_conditional_rates_cover_every_attempt() -> None:
    att = fb.attempts(_rows("a"), "a", OUTS, PRES_BASE)
    tab = {r["status"]: r for r in fb.conditional_rates(att, "file_status", seed=0, resamples=200)}
    assert tab["all"]["attempts"] == 4 and tab["all"]["resolved"] == 3
    assert tab["none"]["attempts"] == 2 and tab["none"]["resolved"] == 1
    assert sum(r["attempts"] for r in tab.values()) == 8


def test_paired_counts_gross_and_net() -> None:
    base = fb.attempts(_rows("a"), "a", OUTS, PRES_BASE)
    arm = fb.attempts(_rows("b"), "b", OUTS, PRES_ARM)
    allc = fb.paired_counts(base, arm, "file_status", "all")
    # i1 gains all (0 -> 1 of 1), i2 loses all (2 of 2 -> 1 of 2), i3 kept present, i4 has no gold
    assert (
        allc["gains"],
        allc["losses"],
        allc["kept_present"],
        allc["kept_absent"],
        allc["no_gold"],
    ) == (1, 1, 1, 0, 1)
    assert allc["net"] == 0 and allc["gross_moved"] == 2
    anyc = fb.paired_counts(base, arm, "file_status", "any")
    # any gold file: i1 gains, i2 keeps (some present both), i3 keeps
    assert (anyc["gains"], anyc["losses"], anyc["kept_present"]) == (1, 0, 2)
    assert anyc["net"] == 1 and anyc["present_base"] == 2 and anyc["present_arm"] == 3


def test_efficiency_means_and_totals() -> None:
    e = fb.efficiency(_rows("a"), "a", OUTS)
    assert e["attempts"] == 8
    assert e["prompt_tokens_per_attempt"] == 1000 and e["uncached_prompt_tokens_per_attempt"] == 600
    assert e["calls_per_attempt"] == 2 and math.isclose(e["cost_usd_total"], 0.08)


def test_gap_closed_and_consistency_are_deterministic() -> None:
    u = np.array([1.0, 0.0, 1.0, 0.0] * 5)
    f = np.array([0.0, 0.0, 1.0, 0.0] * 5)
    o = np.array([1.0, 1.0, 1.0, 0.0] * 5)
    g1 = fb.gap_closed(u, f, o, seed=3, resamples=500)
    g2 = fb.gap_closed(u, f, o, seed=3, resamples=500)
    assert g1 == g2
    assert math.isclose(g1["ratio"], (2 / 4 - 1 / 4) / (3 / 4 - 1 / 4))
    base = fb.attempts(_rows("a"), "a", OUTS, PRES_BASE)
    arm = fb.attempts(_rows("b"), "b", OUTS, PRES_ARM)
    sb = {i: 0.5 for i in OUTS}
    sa = {i: 0.5 for i in OUTS}
    c = fb.consistency_check(base, arm, sb, sa, "file_status", seed=0, resamples=200)
    assert c["net_all_gold"] == 0 and c["predicted_effect_literal_points"] == 0.0
