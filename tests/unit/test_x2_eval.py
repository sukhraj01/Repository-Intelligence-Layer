"""Tests for the X2 evaluation (first stages, graph on top) and its tables."""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from ril.analysis.x2_tables import paired_rows, select_best, select_cut
from ril.evaluation.e3_prepare import READINGS
from ril.evaluation.x2_eval import (
    evaluate_instance,
    gold_ranks,
    minmax,
    positions,
    rrf_scores,
    spec_from_config,
)


def _instance(n: int = 30) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    rng = np.random.default_rng(0)
    arrays: dict[str, Any] = {
        "scores_L2": rng.random(n),
        "file_of_unit": np.arange(n) // 5,
        "age_days": np.zeros(n),
        "pairs_contain": np.asarray([[i, i + 1] for i in range(0, n - 1, 2)], dtype=np.int32),
        "pairs_invoke": np.asarray([[0, 7], [3, 9]], dtype=np.int32),
    }
    for r in READINGS:
        arrays[f"gold_L2_{r}"] = np.asarray([2, 11], dtype=np.int32)
    meta = {"units": n, "levels": ["L2"], "instance": "x__y-1"}
    dense = {"enc__t512": {"dense_L2": rng.random(n).astype(np.float32)}}
    return arrays, meta, dense


def test_helpers() -> None:
    s = np.asarray([0.5, 0.9, 0.5, 0.1])
    assert list(positions(s)) == [1, 0, 2, 3]
    assert gold_ranks(s, np.asarray([2, 0])) == [3, 2]
    assert np.allclose(minmax(np.asarray([2.0, 4.0])), [0.0, 1.0])
    assert np.all(minmax(np.asarray([3.0, 3.0])) == 0)
    f = rrf_scores([np.asarray([0, 1]), np.asarray([1, 0])], 60)
    assert f[0] == pytest.approx(f[1])


def test_spec_refuses_sweeps_on_test() -> None:
    cfg = {"roles": ["test"], "first": {"variants": ["a"], "rrf_ks": [1, 2]}}
    with pytest.raises(ValueError):
        spec_from_config(cfg)
    cfg["confirm"] = True
    with pytest.raises(ValueError):
        spec_from_config(cfg)
    cfg["first"] = {"variants": ["a"], "rrf_k_of": {"a": 60}}
    assert spec_from_config(cfg).first is not None


def test_first_and_graph_keys_and_identity() -> None:
    arrays, meta, dense = _instance()
    cfg = {
        "roles": ["dev"],
        "first": {"variants": ["enc__t512"], "rrf_ks": [10], "alphas": [1.0, 0.0]},
        "graph": {
            "variant": "enc__t512",
            "k": 10,
            "alpha": 0.5,
            "ways": ["list", "rrf3", "score"],
            "subsets": ["core", "contain"],
            "seeds": [3],
            "gammas": [0.5],
            "hops": [1],
            "weights": [0.0, 0.3],
            "score_controls": True,
            "draws": 2,
        },
    }
    info, out = evaluate_instance(arrays, meta, spec_from_config(cfg), dense)
    keys = [str(k) for k in out["keys"]]
    m = out["metrics_L2"]
    assert m.shape == (len(keys), 2 * len(READINGS))
    idx = {k: i for i, k in enumerate(keys)}
    # score-level fusion with alpha 1 is BM25, alpha 0 is dense
    assert np.allclose(m[idx["score|enc__t512|a1.0"]], m[idx["bm25"]])
    assert np.allclose(m[idx["score|enc__t512|a0.0"]], m[idx["dense|enc__t512"]])
    # graph weight 0 leaves the score-level first stage unchanged
    assert np.allclose(m[idx["score|core|C3|g0.5|h1|w0.0"]], m[idx["first_score"]])
    for k in ("list|core|C3|g0.5|h1", "rrf3|core|C3|g0.5|h1", "list|rand_whole|core|C3|h1"):
        assert k in idx
    assert "score|rand_files|contain|C3|g0.5|h1|w0.3" in idx
    assert info["levels"]["L2"]["gold_units"] == 2


def test_paired_rows_and_rules() -> None:
    rng = np.random.default_rng(1)
    base = rng.random((40, 1))
    vals = np.hstack([base, base + 0.1])
    repos = ["a"] * 20 + ["b"] * 20
    rows = paired_rows(vals, repos, ["x", "y"], [None, "x"], {"level": "L2"}, seed=0, draws=200)
    y = rows[1]
    assert y["d"] == pytest.approx(10.0) and y["d_q_lo"] == pytest.approx(10.0)
    assert y["c_lo"] <= y["value"] <= y["c_hi"]

    def row(name: str, level: str, value: float, d: float = 0, lo: float = 0, hi: float = 0) -> Any:
        metric = "ndcg10" if level == "L2" else "recall100"
        return {
            "name": name,
            "level": level,
            "reading": "units_all_nomod",
            "metric": metric,
            "value": value,
            "d": d,
            "d_q_lo": lo,
            "d_q_hi": hi,
        }

    rs = [row("a", "L2", 10), row("a", "L3", 30), row("b", "L2", 12), row("b", "L3", 30)]
    assert select_best(rs, ["a", "b"])["name"] == "b"
    long = [row("t1024", "L2", 0, 1, 0.2, 2), row("t1024", "L3", 0, -1, -2, 0.5)]
    assert select_cut(long, "t1024")["selected"] == 1024
    long[1]["d_q_hi"] = -0.1
    assert select_cut(long, "t1024")["selected"] == 512


def test_a_level_without_gold_arrays_is_skipped_and_the_labelled_level_is_kept() -> None:
    """Built-part members that carry an L2 query but no labels (no ``gold_L2_*``) are not
    evaluated; the same call on a labelled member is unchanged."""
    arrays, meta, dense = _instance()
    cfg = {"roles": ["test"], "first": {"variants": ["enc__t512"], "rrf_ks": [60]}}
    spec = spec_from_config({"roles": ["dev"], "first": cfg["first"]})
    labelled, _ = evaluate_instance(arrays, meta, spec, dense)
    assert list(labelled["levels"]) == ["L2"]
    bare = {k: v for k, v in arrays.items() if not k.startswith("gold_")}
    info, out = evaluate_instance(bare, meta, spec, dense)
    assert info["levels"] == {} and len(out["keys"]) == 0
    meta3 = {**meta, "levels": ["L2", "L3"]}
    two = {**arrays, "scores_L3": arrays["scores_L2"]}
    dense3 = {"enc__t512": {**dense["enc__t512"], "dense_L3": dense["enc__t512"]["dense_L2"]}}
    info3, _ = evaluate_instance(two, meta3, spec, dense3)
    assert list(info3["levels"]) == ["L2"]  # L3 has no gold arrays here: skipped, L2 kept
