"""Oracle calibration arm on synthetic inputs (E-RQ3-ORACLE, D168).

Gold files, contexts, leak check, projection stop, analysis."""

from __future__ import annotations

import json
from typing import Any

import numpy as np
import pytest

from ril.agent.providers.driver import Projection, project_cost
from ril.agent.providers.gemini import _credits_depleted
from ril.agent.providers.oracle_leak import (
    GoldTexts,
    added_windows,
    check_items,
    check_prompt,
    check_prompt_detail,
    full_test_ids,
    header_lines,
    parse_test_list,
)
from ril.agent.providers.patch_format import build_prompt
from ril.agent.providers.spend import Price
from ril.analysis import rq3_oracle as ro
from ril.assembly.assemble import Candidate, UnitText
from ril.assembly.rq3_contexts import ContextSpec
from ril.assembly.rq3_oracle_contexts import (
    build_oracle_instance,
    gold_files_from_patch,
    oracle_candidates,
)
from ril.assembly.tokens import ApproxTokenizer

TOK = ApproxTokenizer()
META = {"instance": "o__r-1", "repo_id": "o/r", "base_commit": "abc"}

PATCH = """diff --git a/pkg/core.py b/pkg/core.py
index 1111111..2222222 100644
--- a/pkg/core.py
+++ b/pkg/core.py
@@ -10,3 +10,5 @@ def f():
     keep = 1
-    old_value = compute_old(keep)
+    new_value = compute_new_value(keep, flag=True)
+    other_value = something_else_entirely(new_value)
+    return finish_the_computation(other_value)
diff --git a/pkg/added.py b/pkg/added.py
new file mode 100644
index 0000000..3333333
--- /dev/null
+++ b/pkg/added.py
@@ -0,0 +1,2 @@
+x = 1
+y = 2
diff --git a/old/name.py b/new/name.py
similarity index 90%
rename from old/name.py
rename to new/name.py
diff --git a/pkg/gone.py b/pkg/gone.py
deleted file mode 100644
--- a/pkg/gone.py
+++ /dev/null
@@ -1,1 +0,0 @@
-z = 3
"""


def test_gold_files_from_patch() -> None:
    modified, created = gold_files_from_patch(PATCH)
    assert modified == ["old/name.py", "pkg/core.py", "pkg/gone.py"]
    assert created == ["pkg/added.py"]
    assert gold_files_from_patch("") == ([], [])


def _units() -> list[UnitText]:
    out = []
    for i, f in enumerate(["a.py", "a.py", "b.py", "c.py", "c.py", "d.py"]):
        body = "\n".join(f"    v{i}_{j} = {j}" for j in range(8))
        out.append(
            UnitText(
                f"{f}::u{i}", f, 10 * i + 1, 10 * i + 9, "function", f"u{i}", f"def u{i}():\n{body}"
            )
        )
    return out


def _arrays() -> dict[str, Any]:
    return {
        "scores_L2": np.asarray([1.0, 2.0, 3.0, 4.0, 5.0, 6.0]),
        "gold_L2_units_all": np.asarray([0, 3], dtype=np.int32),
        "gold_L2_units_all_nomod": np.asarray([0], dtype=np.int32),
    }


DENSE = {"dense_L2": np.asarray([6.0, 5.0, 4.0, 3.0, 2.0, 1.0])}


def _spec(budget: int = 8000, unit_cap: int = 1000) -> ContextSpec:
    return ContextSpec(
        budgets=(budget,), max_unit_tokens=unit_cap, candidates=3, rrf_k=100, query_level="L2"
    )


def test_gold_units_first_then_ranking_without_repeats() -> None:
    units = _units()
    ranked = [Candidate("d.py::u5", 1.0), Candidate("a.py::u0", 0.9), Candidate("b.py::u2", 0.8)]
    cands, ids = oracle_candidates(["c.py", "a.py"], units, ranked)
    assert [c.unit_id for c in cands[:4]] == ["a.py::u0", "a.py::u1", "c.py::u3", "c.py::u4"]
    assert ids == {"a.py": ["a.py::u0", "a.py::u1"], "c.py": ["c.py::u3", "c.py::u4"]}
    assert all(c.stages == ("oracle",) for c in cands[:4])
    assert [c.unit_id for c in cands[4:]] == ["d.py::u5", "a.py::u0", "b.py::u2"]


def test_context_holds_every_gold_file_and_fills_the_rest() -> None:
    rec = build_oracle_instance(
        META, _arrays(), DENSE, _units(), _spec(), TOK, ["c.py"], ["new.py"], "g"
    )
    ctx = rec["contexts"]["oracle|8000"]
    files = {e["file"] for e in ctx["manifest"]["entries"]}
    assert "c.py" in files and len(files) > 1
    st = rec["oracle"]["8000"]
    assert st["n_gold_file_units"] == 2 and st["n_gold_units_in"] == 2
    assert st["all_gold_file_units_intact"] and not st["gold_files_affected"]
    assert st["files_created"] == ["new.py"]
    assert rec["gold_files_sha256"] == "g"
    assert rec["coverage"][0]["arm"] == "oracle"


def test_gold_file_larger_than_the_budget_uses_the_same_cut_and_is_counted() -> None:
    rec = build_oracle_instance(
        META,
        _arrays(),
        DENSE,
        _units(),
        _spec(budget=70, unit_cap=1000),
        TOK,
        ["a.py", "c.py"],
        [],
        "g",
    )
    st = rec["oracle"]["70"]
    assert st["gold_files_affected"] and not st["all_gold_file_units_intact"]
    assert st["n_gold_units_left_out"] >= 1
    assert rec["contexts"]["oracle|70"]["manifest"]["total_tokens"] <= 70


def test_unit_cap_truncation_counts_as_affected() -> None:
    rec = build_oracle_instance(
        META, _arrays(), DENSE, _units(), _spec(unit_cap=32), TOK, ["a.py"], [], "g"
    )
    st = rec["oracle"]["8000"]
    assert st["n_gold_units_cut"] >= 1 and st["gold_files_affected"]


def test_file_without_units_is_counted() -> None:
    rec = build_oracle_instance(
        META, _arrays(), DENSE, _units(), _spec(), TOK, ["README.rst", "c.py"], [], "g"
    )
    st = rec["oracle"]["8000"]
    assert st["n_files_without_units"] == 1 and st["files_without_units"] == ["README.rst"]


def test_build_is_deterministic() -> None:
    a = build_oracle_instance(META, _arrays(), DENSE, _units(), _spec(), TOK, ["c.py"], [], "g")
    b = build_oracle_instance(META, _arrays(), DENSE, _units(), _spec(), TOK, ["c.py"], [], "g")
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


# ------------------------------------------------------------------ leakage check

TEST_PATCH = """diff --git a/tests/test_core.py b/tests/test_core.py
--- a/tests/test_core.py
+++ b/tests/test_core.py
@@ -1,2 +1,6 @@
+def test_new_behaviour_of_the_core_function():
+    result = core.f(argument_one, argument_two)
+    assert result == expected_value_from_the_report
"""
GOLD = GoldTexts(
    PATCH,
    TEST_PATCH,
    ("tests/test_core.py::test_new_behaviour_of_the_core_function", "test_bare_name_here"),
)


def _prompt(context: str, issue: str = "the issue") -> str:
    return build_prompt(issue, context)


def test_clean_context_has_no_finding() -> None:
    ctx = "### pkg/core.py:1-9 function f (rank 1)\ndef f():\n    old_value = compute_old(1)"
    assert check_prompt(_prompt(ctx), GOLD) == []


def test_added_lines_of_the_gold_patch_are_found() -> None:
    ctx = (
        "### x.py:1-4 function g (rank 1)\n"
        "    new_value = compute_new_value(keep, flag=True)\n"
        "\n"
        "    other_value = something_else_entirely(new_value)\n"
        "    return finish_the_computation(other_value)\n"
    )
    kinds = {f["kind"] for f in check_prompt(_prompt(ctx), GOLD)}
    assert kinds == {"added_run"}


def test_patch_header_and_test_id_are_found() -> None:
    ctx = (
        "diff --git a/pkg/core.py b/pkg/core.py\n"
        "see tests/test_core.py::test_new_behaviour_of_the_core_function"
    )
    kinds = {f["kind"] for f in check_prompt(_prompt(ctx), GOLD)}
    assert kinds == {"patch_header", "test_id"}


def test_issue_text_is_not_checked() -> None:
    issue = "diff --git a/pkg/core.py b/pkg/core.py quoted by the reporter"
    assert check_prompt(_prompt("clean", issue), GOLD) == []


def test_bare_test_names_do_not_fail_but_are_counted() -> None:
    from ril.agent.providers.oracle_leak import short_test_name_count

    ctx = "def test_bare_name_here(): pass"
    assert check_prompt(_prompt(ctx), GOLD) == []
    assert short_test_name_count(_prompt(ctx), GOLD) == 1


def test_helpers() -> None:
    assert "diff --git a/pkg/core.py b/pkg/core.py" in header_lines(PATCH)
    assert added_windows("+a\n+b\n") == []
    ids, bare = full_test_ids(["test_one_name", "a/b.py::t_one", "test_x (mod.C)", "ab"])
    assert bare == ["test_one_name"] and ids == ["a/b.py::t_one", "test_x (mod.C)"]
    assert parse_test_list('["a", "b"]') == ["a", "b"] and parse_test_list("") == []


def test_check_items_fails_on_a_finding_and_on_unknown_gold() -> None:
    items = [
        {"instance_id": "i1", "arm": "oracle", "prompt_sha256": "h1", "prompt": _prompt("clean")},
        {
            "instance_id": "i2",
            "arm": "oracle",
            "prompt_sha256": "h2",
            "prompt": _prompt("diff --git a/pkg/core.py b/pkg/core.py"),
        },
    ]
    rep = check_items(items, {"i1": GOLD, "i2": GOLD})
    assert not rep["clean"] and rep["prompts_with_findings"] == 1
    assert rep["rows"][1]["findings"][0]["digest"]
    assert "pkg/core.py" not in json.dumps(rep)
    with pytest.raises(ValueError):
        check_items(items, {"i1": GOLD})


def test_differential_mode_separates_preexisting_text_from_foreign_text() -> None:
    body = (
        "    new_value = compute_new_value(keep, flag=True)\n"
        "    other_value = something_else_entirely(new_value)\n"
        "    return finish_the_computation(other_value)\n"
    )
    ctx = "### x.py:1-3 function g (rank 1)\n" + body
    on_disk = {"x.py": body}
    # the same lines stood in the file before the patch: a coincidence, not a leak
    found, pre = check_prompt_detail(_prompt(ctx), GOLD, on_disk.get)
    assert found == [] and pre >= 1
    # the lines are not in the base-commit file: foreign text in the context
    found, _ = check_prompt_detail(_prompt(ctx), GOLD, {"x.py": "def g():\n    pass\n"}.get)
    kinds = {f["kind"] for f in found}
    assert kinds == {"added_run", "not_prepatch"}
    # a block whose file cannot be read at the base commit is not accepted as pre-patch text
    found, _ = check_prompt_detail(_prompt(ctx), GOLD, {}.get)
    assert {f["kind"] for f in found} >= {"not_prepatch"}


def test_differential_mode_keeps_truncation_marker_and_test_ids() -> None:
    tid = "tests/test_core.py::test_new_behaviour_of_the_core_function"
    ctx = (
        "### t.py:1-3 function h (rank 1)\ndef h():\n    # "
        + tid
        + "\n# ... truncated, 4 more lines"
    )
    base = {"t.py": "def h():\n    # " + tid + "\n"}
    found, pre = check_prompt_detail(_prompt(ctx), GOLD, base.get)
    assert found == [] and pre == 1
    found, _ = check_prompt_detail(_prompt(ctx), GOLD, {"t.py": "def h():\n"}.get)
    assert {f["kind"] for f in found} >= {"test_id", "not_prepatch"}


# ------------------------------------------------------------------ spend

PRICE = Price("m", 1.0, 2.0, True, "t", 0.1)


def _call(iid: str, inp: int = 1_000_000, out: int = 0) -> dict[str, Any]:
    return {"instance_id": iid, "input_tokens": inp, "output_tokens": out, "cached_tokens": 0}


def test_projection_waits_for_enough_instances() -> None:
    rows = [_call("a"), _call("b")]
    proj = Projection(3, 10, 5.0, PRICE, lambda: rows)
    assert project_cost(proj) is None


def test_projection_stops_over_the_cap_and_passes_under_it() -> None:
    rows = [_call(i) for i in "abc"]
    over = project_cost(Projection(3, 10, 5.0, PRICE, lambda: rows))
    assert over is not None and over["projected_usd"] == pytest.approx(10.0)
    assert over["exceeds_cap"]
    under = project_cost(Projection(3, 10, 12.0, PRICE, lambda: rows))
    assert under is not None and not under["exceeds_cap"]


def test_projection_uses_only_the_first_instances() -> None:
    rows = [_call("a"), _call("b"), _call("c", inp=50_000_000)]
    res = project_cost(Projection(2, 4, 100.0, PRICE, lambda: rows))
    assert res is not None and res["cost_first_n_usd"] == pytest.approx(2.0)


def test_depleted_credit_message_is_a_stop_but_the_quota_text_is_not() -> None:
    assert _credits_depleted(
        "Your prepayment credits are depleted. Please add credit to your account"
    )
    assert not _credits_depleted(
        "You exceeded your current quota, check your plan and billing details"
    )


# ------------------------------------------------------------------ analysis


def _rows(
    arm: str, runs: tuple[int, ...], resolved: dict[str, tuple[bool, ...]]
) -> list[dict[str, Any]]:
    out = []
    for iid, flags in resolved.items():
        for k in runs:
            f = flags[k % len(flags)]
            out.append(
                {
                    "instance_id": iid,
                    "arm": arm,
                    "run": k,
                    "resolved": f,
                    "resolved_tolerant": f,
                    "outcome": "resolved" if f else "executed_unresolved",
                }
            )
    return out


def test_contrasts_use_own_and_matched_k() -> None:
    ids = [f"i{n}" for n in range(8)]
    oracle = _rows("oracle", (0, 1), {i: (True,) for i in ids})
    other = _rows("rrf", (0, 1, 2), {i: (n < 4,) for n, i in enumerate(ids)})
    runs = {"oracle": (0, 1), "rrf": (0, 1, 2)}
    t = ro.contrasts(oracle + other, ids, runs, seed=0, resamples=500)
    exact = [r for r in t if r["reading"] == "exact"]
    assert [r["k_form"] for r in exact] == ["own k (2 vs 3)", "matched k (2 vs 2)"]
    assert exact[0]["difference"] == pytest.approx(0.5)
    assert exact[0]["p_permutation"] is not None
    assert all(r["role"] == "exploratory_estimate" for r in t)


def test_gold_miss_and_retrieval_vs_reasoning() -> None:
    ids = ["i0", "i1", "i2", "i3"]
    gold = {"i0": ["a.py"], "i1": ["b.py"], "i2": ["c.py"], "i3": []}
    files = {
        "rrf": {"i0": ["z.py"], "i1": ["b.py"], "i2": ["z.py"], "i3": ["z.py"]},
        "raw": {"i0": ["z.py"], "i1": ["b.py"], "i2": ["z.py"], "i3": ["z.py"]},
    }
    miss = ro.gold_miss(files, gold, ids)
    assert miss["i0"]["rrf_files_in"] == 0 and miss["i1"]["rrf_files_in"] == 1
    rows = _rows("oracle", (0, 1), {i: (True,) for i in ids})
    rows += _rows("rrf", (0, 1), {i: (False,) for i in ids})
    rows += _rows("raw", (0, 1), {i: (False,) for i in ids})
    out = ro.retrieval_vs_reasoning(
        rows,
        ids,
        {"oracle": (0, 1), "rrf": (0, 1), "raw": (0, 1)},
        miss,
        {"both": ["rrf", "raw"]},
        resamples=200,
    )
    assert out[0]["instances"] == 2  # i0 and i2; i3 has no gold file, i1 was not missed
    assert out[0]["oracle_resolved"] == 1.0 and out[0]["oracle_minus_rrf"] == 1.0


def test_mdd_rows_selects_rate_and_runs() -> None:
    mdd = [
        {"rate": "0.4", "runs": "2", "mdd_points": "7.1"},
        {"rate": "0.4", "runs": "1", "mdd_points": "8.2"},
        {"rate": "0.3", "runs": "2", "mdd_points": "7.0"},
    ]
    assert [r["mdd_points"] for r in ro.mdd_rows(mdd)] == ["7.1"]
