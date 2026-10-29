"""Tests for the graph-role measurement S1 (candidate sources and reachability)."""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from ril.analysis.s1_tables import reach_rows
from ril.evaluation.e3_prepare import READINGS
from ril.evaluation.s1_graph_role import (
    evaluate_instance,
    multi_source_reach,
    reach_keys,
    same_file_by_score,
    spec_from_config,
)
from ril.retrieval.graph_expansion import FamilyGraph


def test_same_file_by_score_orders_by_first_stage_and_tops_up() -> None:
    files = np.asarray([0, 0, 0, 1, 1, 2])
    order = np.asarray([3, 2, 0, 1, 4, 5])  # best first
    assert same_file_by_score(files, order, [3], 1) == [4]
    assert same_file_by_score(files, order, [0], 2) == [2, 1]
    # file 1 holds one other unit; the rest comes from the ranking, seeds excluded
    assert same_file_by_score(files, order, [3], 3) == [4, 2, 0]
    assert same_file_by_score(files, order, [3], 0) == []


def test_multi_source_reach_hops_and_exclusion_of_sources() -> None:
    g = FamilyGraph.from_pairs(6, {"invoke": [(0, 1), (1, 2), (2, 3)], "contain": [(0, 5)]})
    assert multi_source_reach(g, ("invoke",), [0], 2) == {1: 1, 2: 2}
    assert multi_source_reach(g, ("invoke",), [0, 3], 1) == {1: 1, 2: 1}
    assert multi_source_reach(g, ("contain",), [0], 2) == {5: 1}
    assert multi_source_reach(g, ("import",), [0], 2) == {}


def _instance(n: int = 40) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    rng = np.random.default_rng(1)
    arrays: dict[str, Any] = {
        "scores_L2": rng.random(n),
        "scores_L3": rng.random(n),
        "file_of_unit": np.arange(n) // 5,
        "age_days": np.zeros(n),
        "pairs_contain": np.asarray([[i, i + 1] for i in range(0, n - 1, 2)], dtype=np.int32),
        "pairs_invoke": np.asarray([[0, 17], [3, 29]], dtype=np.int32),
    }
    for lv in ("L2", "L3"):
        for r in READINGS:
            arrays[f"gold_{lv}_{r}"] = np.asarray([2, 31], dtype=np.int32)
    meta = {"units": n, "levels": ["L2", "L3"], "instance": "x__y-1"}
    dense = {f"dense_{lv}": rng.random(n).astype(np.float32) for lv in ("L2", "L3")}
    return arrays, meta, dense


CFG: dict[str, Any] = {
    "roles": ["dev"],
    "confirm": False,
    "graph": {
        "variant": "enc__t512",
        "k": 20,
        "alpha": 0.2,
        "seeds": [3],
        "gammas": [0.7],
        "hops": [2],
        "weights": [0.5],
        "cap": 10,
        "draws": 2,
        "reach_top": [3, 10],
    },
}


def test_evaluate_instance_layout_and_controls() -> None:
    arrays, meta, dense = _instance()
    sp, _ = spec_from_config(CFG)
    info, out = evaluate_instance(arrays, meta, sp, dense)
    keys = [str(k) for k in out["keys"]]
    assert keys[:2] == ["a_none", "a_rrf"]
    for v in "bef":
        for kind in ("graph", "sfscore", "sfrand"):
            assert f"{kind}|{v}|w0.5" in keys
    assert out["metrics_L2"].shape == (len(keys), 2 * len(READINGS))
    assert "reach_L3" in out and "reach_L2" not in out
    assert out["reach_L3"].shape == (len(READINGS) * len(reach_keys(sp.reach_top)), 4)
    # sizes: the size-matched same-file sources have the size of their graph variant
    aux = {str(k): out["aux_L2"][i] for i, k in enumerate(out["aux_keys"])}
    for v in "bef":
        assert aux[f"E|{v}|graph"][0] == aux[f"E|{v}|sfscore"][0] == aux[f"E|{v}|sfrand"][0]
    # the reachability counts are consistent: reach_not_samefile <= reach <= den
    r = out["reach_L3"]
    assert (r[:, 3] <= r[:, 2] + 1e-9).all() and (r[:, 2] <= r[:, 0] + 1e-9).all()
    # determinism
    _, out2 = evaluate_instance(arrays, meta, sp, dense)
    assert np.array_equal(out["metrics_L3"], out2["metrics_L3"], equal_nan=True)


def test_test_role_needs_confirm_and_one_weight() -> None:
    bad = {**CFG, "roles": ["dev", "test"]}
    with pytest.raises(ValueError):
        spec_from_config(bad)
    bad2 = {
        **CFG,
        "roles": ["test"],
        "confirm": True,
        "graph": {**CFG["graph"], "weights": [0.2, 0.5]},
    }
    with pytest.raises(ValueError):
        spec_from_config(bad2)


def test_reach_rows_tables(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    import ril.evaluation.s1_graph_role as mod

    monkeypatch.setattr(mod, "FIRST_STAGE_TOP", 10)
    from ril.evaluation.e3_eval import write_eval

    sp, _ = spec_from_config(CFG)
    for i, repo in enumerate(("a/a", "a/a", "b/b")):
        arrays, meta, dense = _instance(40 + i)
        arrays["gold_L3_units_all_nomod"] = np.asarray([2, 31, 39], dtype=np.int32)
        info, out = evaluate_instance(arrays, meta, sp, dense)
        info.update(role="dev", repo_id=repo, instance=f"i{i}")
        write_eval(str(tmp_path / f"i{i}.npz"), info, out)
    rows = reach_rows(str(tmp_path), "dev", 0, draws=50)
    assert rows and any(r["gold_outside_top100"] > 0 for r in rows)
    for r in rows:
        if r["family"] != "samefile":
            assert r["reach_not_same_file_count"] <= r["reach_count"] <= r["gold_outside_top100"]
