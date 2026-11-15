"""No-retrieval floor arm on synthetic inputs (E-RQ3-FLOOR, D169).

Empty-context rows and prompts, no path filter for this arm only, leak check on an empty context,
analysis contrasts."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from ril.agent.providers.floor_arm import FLOOR_ARM, floor_rows
from ril.agent.providers.oracle_leak import GoldTexts, check_items
from ril.agent.providers.patch_format import build_prompt, parse_edits
from ril.agent.providers.pilot_run import load_items
from ril.agent.providers.rq3_prompts import EXCERPT_MARK, prepare_screened
from ril.analysis import rq3_floor as rf

REPLY = "FILE: pkg/core.py\n<<<<<<< SEARCH\nold\n=======\nnew\n>>>>>>> REPLACE\n"


def _rows():
    return floor_rows(
        {"a-1": "Issue A", "a-2": "Issue B"},
        {"a-1": "o/r", "a-2": "o/r"},
        ["a-2", "a-1", "a-3"],
        8000,
    )


def test_floor_rows_are_empty_context_and_report_missing_issue() -> None:
    rows, skipped = _rows()
    assert [r["instance_id"] for r in rows] == ["a-1", "a-2"]
    assert all(r["context"] == "" and r["files"] == [] and r["arm"] == FLOOR_ARM for r in rows)
    assert skipped == [{"instance_id": "a-3", "reason": "no_issue_text"}]


def test_floor_prompt_has_template_and_empty_excerpt_section(tmp_path: Path) -> None:
    rows, _ = _rows()
    n, rejected = prepare_screened(rows, tmp_path)
    assert n == 2 and not rejected
    items = load_items(tmp_path)
    for it in items:
        assert it["paths"] is None
        assert it["prompt"].startswith(build_prompt("Issue A", "")[:200])
        assert it["prompt"].rstrip().endswith(EXCERPT_MARK)
    assert [i for i in items if i["instance_id"] == "a-1"][0]["prompt"] == build_prompt(
        "Issue A", ""
    )


def test_without_path_filter_a_reply_is_usable_and_with_an_empty_filter_it_is_not() -> None:
    edits, err = parse_edits(REPLY, None)
    assert err is None and len(edits) == 1
    assert parse_edits(REPLY, [])[1] == "path_not_in_context"  # why the floor arm has no filter


def test_leak_check_passes_an_empty_context_and_needs_gold_texts(tmp_path: Path) -> None:
    rows, _ = _rows()
    prepare_screened(rows, tmp_path)
    items = load_items(tmp_path)
    gold = {
        i: GoldTexts(
            "diff --git a/x b/x\n+++ b/x\n+aaaa bbbb cccc dddd eeee ffff gggg hhhh\n",
            "",
            ("tests/t.py::test_x",),
        )
        for i in ("a-1", "a-2")
    }
    report = check_items(items, gold, lambda iid: lambda path: None)
    assert report["clean"] and report["prompts_checked"] == 2 and report["mode"] == "differential"


def _rows_for(arm: str, values: list[int], run: int) -> list[dict]:
    return [
        {
            "instance_id": f"i{n}",
            "arm": arm,
            "run": run,
            "resolved": bool(v),
            "resolved_tolerant": bool(v),
        }
        for n, v in enumerate(values)
    ]


def test_floor_contrasts_are_other_minus_floor_with_matched_k() -> None:
    n = 40
    rng = np.random.default_rng(0)
    other = [int(x) for x in rng.integers(0, 2, n)]
    rows = _rows_for("floor", [0] * n, 0) + sum((_rows_for("rrf", other, k) for k in (0, 1, 2)), [])
    inst = [f"i{i}" for i in range(n)]
    out = rf.floor_contrasts(rows, inst, {"floor": (0,), "rrf": (0, 1, 2)}, seed=0, resamples=200)
    kinds = {(r["reading"], r["k_form"]) for r in out}
    assert ("exact", "own k (3 vs 1)") in kinds and ("exact", "matched k (1 vs 1)") in kinds
    d = [r for r in out if r["reading"] == "exact"][0]
    assert d["first"] == "rrf" and d["second"] == FLOOR_ARM
    assert abs(d["difference"] - sum(other) / n) < 1e-9


def test_mdd_for_filters_by_rate_and_runs() -> None:
    mdd = [
        {"rate": "0.4", "runs": "1", "x": 1},
        {"rate": "0.4", "runs": "4", "x": 2},
        {"rate": "0.1", "runs": "1", "x": 3},
    ]
    assert [r["x"] for r in rf.mdd_for(mdd, 0.4, (1, 2, 3))] == [1]
    json.dumps(rf.mdd_for(mdd, 0.4, (1,)))
