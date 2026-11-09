"""Tests for the stacked-expansion measurement G1 (lists, controls, regression to S1, tables)."""

from __future__ import annotations

from typing import Any

import numpy as np

from ril.analysis.g1_tables import contrast_rows
from ril.evaluation.g1_stacked import STACK_N, evaluate_instance, stacked_list
from ril.evaluation.s1_graph_role import evaluate_instance as s1_evaluate
from ril.evaluation.s1_graph_role import spec_from_config
from tests.unit.test_s1_graph_role import CFG, _instance


def _with_tc() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    arrays, meta, dense = _instance(60)
    arrays["pairs_tests"] = np.asarray([[1, 40], [7, 51]], dtype=np.int32)
    arrays["pairs_configures"] = np.asarray([[2, 33]], dtype=np.int32)
    return arrays, meta, dense


def test_stacked_list_fills_to_budget_without_duplicates() -> None:
    assert stacked_list([1, 2], [9], [2, 3, 4], 5) == [1, 2, 9, 3, 4]
    assert stacked_list([1, 2], [], [3], 5) == [1, 2, 3]
    assert stacked_list([1, 2, 3], [7, 8], [], 4) == [1, 2, 3, 7]


def test_keys_and_core_rows_equal_s1() -> None:
    arrays, meta, dense = _with_tc()
    sp, _ = spec_from_config(CFG)
    _, out = evaluate_instance(arrays, meta, sp, dense)
    _, s1 = s1_evaluate(arrays, meta, sp, dense)
    keys = [str(k) for k in out["keys"]]
    s1keys = [str(k) for k in s1["keys"]]
    for kind in ("graph", "sfscore", "sfrand", "topm"):
        assert f"{kind}|core" in keys and f"{kind}|coretc" in keys and f"{kind}|tc" in keys
        a = out["metrics_L3"][keys.index(f"{kind}|core")]
        b = s1["metrics_L3"][s1keys.index(f"{kind}|b|w0.5")]
        assert np.allclose(a, b, equal_nan=True)
    for n in STACK_N:
        for f in ("nc", "nctc", "tc"):
            for kind in ("stack", "stacktopm", "stackrand"):
                assert f"{kind}{n}|{f}" in keys
    assert "ref|samefile" in keys and "recency" in keys and "recencyshuf" in keys


def test_reference_equals_sfscore_core_and_determinism() -> None:
    arrays, meta, dense = _with_tc()
    sp, _ = spec_from_config(CFG)
    _, out = evaluate_instance(arrays, meta, sp, dense)
    keys = [str(k) for k in out["keys"]]
    assert np.array_equal(
        out["metrics_L2"][keys.index("ref|samefile")],
        out["metrics_L2"][keys.index("sfscore|core")],
        equal_nan=True,
    )
    _, out2 = evaluate_instance(arrays, meta, sp, dense)
    assert np.array_equal(out["metrics_L3"], out2["metrics_L3"], equal_nan=True)


def test_contrast_rows_layout(tmp_path: Any) -> None:
    from ril.analysis.e3_tables import load_eval_dir
    from ril.evaluation.e3_eval import write_eval

    sp, _ = spec_from_config(CFG)
    for i, repo in enumerate(("a/a", "a/a", "b/b", "c/c")):
        arrays, meta, dense = _with_tc()
        meta = {**meta, "instance": f"x__y-{i}"}
        info, out = evaluate_instance(arrays, meta, sp, dense)
        info.update(
            instance=meta["instance"], role="dev", dataset="d", folder="f", repo_id=repo, units=60
        )
        write_eval(str(tmp_path / f"{i}.npz"), info, out)
    tab = load_eval_dir(str(tmp_path))
    rows, per_repo = contrast_rows(tab, "dev")
    assert rows and per_repo
    r = next(x for x in rows if x["contrast"] == "plain: graph - same-file" and x["level"] == "L3")
    assert r["repos"] == 3 and r["t_kind"] == "repository-clustered" and r["df"] == 2
    assert r["reading"] in ("beats control", "does not beat control")
