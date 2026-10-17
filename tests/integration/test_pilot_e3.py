"""Integration: cache of one snapshot (parse, graph, history, BM25) and the E3 to E5 evaluation."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from ril.evaluation.e3_eval import (
    EvalSpec,
    GraphGrid,
    RecencyGrid,
    WeightGrid,
    evaluate_instance,
    graph_key,
    run_eval,
    spec_from_config,
    subset_table,
)
from ril.evaluation.e3_prepare import prepare_instance, read_cache, write_cache
from ril.evaluation.unit_retrieval import analyse_units
from ril.retrieval.bm25_index import BM25Params

FILES = {
    "pkg/__init__.py": "",
    "pkg/parse.py": (
        "def tokenise(text):\n    return text.split()\n\n\n"
        "def parse_header(text):\n    return tokenise(text)[0]\n"
    ),
    "pkg/render.py": (
        "from pkg.parse import parse_header\n\n\n"
        "class Page:\n"
        "    def title(self, text):\n        return parse_header(text)\n\n"
        "    def footer(self):\n        return 'footer'\n"
    ),
    "pkg/misc.py": "def unrelated_one():\n    return 1\n\n\ndef unrelated_two():\n    return 2\n",
    "tests/test_parse.py": (
        "from pkg.parse import tokenise\n\n\n"
        "def test_tokenise():\n    assert tokenise('a b') == ['a', 'b']\n"
    ),
}
ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.org",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.org",
}


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, env=ENV, capture_output=True, text=True, check=True
    ).stdout.strip()


@pytest.fixture
def snapshot(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    for rel, text in FILES.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "one")
    (root / "pkg/misc.py").write_text(FILES["pkg/misc.py"] + "\n# touched\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "two")
    return root


def _cache(snapshot: Path) -> tuple[dict[str, np.ndarray[Any, Any]], dict[str, Any]]:
    queries = {"L2": "parse header tokenise text", "L3": "render the page title footer"}
    levels = {
        "L2": {"c1": "def parse_header(text):\n    return tokenise(text)[0]\n"},
        "L3": {"c2": "    def title(self, text):\n        return parse_header(text)\n"},
    }
    e1 = analyse_units(str(snapshot), "acme/mini", "inst-1", queries, levels, "")
    return prepare_instance(str(snapshot), "acme/mini", queries, e1, BM25Params(), "hash0")


def test_prepare_builds_scores_edges_gold_and_agrees_with_pilot_e1(snapshot: Path) -> None:
    arrays, meta = _cache(snapshot)
    n = meta["units"]
    assert meta["e1_rank_checked"] > 0 and meta["e1_rank_mismatch"] == 0
    assert meta["gold_ids_not_in_units"] == 0
    assert arrays["scores_L2"].shape == (n,) and arrays["age_days"].shape == (n,)
    assert np.isfinite(arrays["age_days"]).all()  # every file has a history
    assert {"contain", "import", "invoke"} <= set(meta["edge_pairs"])
    assert len(arrays["gold_L2_units"]) == 1 and len(arrays["gold_L3_units"]) == 1
    assert int(arrays["pairs_contain"].max()) < meta["nodes"]


def test_evaluate_baseline_equals_unit_ranks_and_expansion_helps_a_neighbour(
    snapshot: Path, tmp_path: Path
) -> None:
    arrays, meta = _cache(snapshot)
    meta.update(instance="inst-1", role="dev")
    spec = EvalSpec(
        roles=("dev",),
        graph=GraphGrid(
            subsets=("invoke", "contain", "all"),
            seeds=(1,),
            gammas=(0.5,),
            hops=(1, 2),
            cap=5,
            draws=2,
        ),
        recency=RecencyGrid(lam=(0.1,), tau_days=(30.0,)),
    )
    info, out = evaluate_instance(arrays, meta, spec)
    keys = list(out["keys"])
    m = out["metrics_L2"]
    base = m[keys.index("bm25")]
    assert 0.0 <= base.min() and base.max() <= 1.0
    # top-1 seed for "parse header tokenise text" is parse_header; its invoke neighbour tokenise
    # is promoted by the edited list, never demoted below the baseline for this gold
    row = m[keys.index(graph_key("list", "invoke", 1, 0.5, 1))]
    assert row[1] >= base[1]
    # control keys exist for both controls and both variants, with the same layout at L3
    assert "rrf|rand_files|all|C1|h2" in keys and "list|rand_whole|invoke|C1|h1" in keys
    assert out["metrics_L3"].shape == out["metrics_L2"].shape
    assert len(out["aux_keys"]) == 3 * 1 * 2  # subsets x C x hops (one gamma)
    assert info["levels"]["L2"]["gold_units"] == 1


def test_evaluation_is_deterministic_and_roundtrips_through_files(
    snapshot: Path, tmp_path: Path
) -> None:
    arrays, meta = _cache(snapshot)
    meta.update(instance="inst-1", role="dev", dataset="d", folder="f", config_hash="hash0")
    cache_dir = tmp_path / "cache"
    write_cache(str(cache_dir / "inst-1.npz"), arrays, meta)
    back, meta_back = read_cache(str(cache_dir / "inst-1.npz"))
    assert meta_back["units"] == meta["units"]
    assert all(np.array_equal(back[k], arrays[k]) for k in arrays)
    cfg = {
        "roles": ["dev"],
        "graph": {"seeds": [1, 3], "gammas": [0.3], "hops": [2], "subsets": ["core"], "draws": 2},
        "recency": {"lam": [0.1], "tau_days": [90]},
    }
    counts = run_eval(cfg, str(cache_dir), str(tmp_path / "o1"))
    assert counts["evaluated"] == 1
    run_eval(cfg, str(cache_dir), str(tmp_path / "o2"))
    a = np.load(tmp_path / "o1" / "inst-1.npz")
    b = np.load(tmp_path / "o2" / "inst-1.npz")
    assert np.array_equal(a["metrics_L2"], b["metrics_L2"])
    assert run_eval(cfg, str(cache_dir), str(tmp_path / "o1"))["reused"] == 1


def test_weighted_run_matches_uniform_run_for_equal_weights(snapshot: Path) -> None:
    arrays, meta = _cache(snapshot)
    meta.update(instance="inst-1", role="dev")
    fams = subset_table()["core"]
    spec = EvalSpec(
        roles=("dev",),
        graph=GraphGrid(subsets=("core",), seeds=(3,), gammas=(0.5,), hops=(2,), draws=1),
        weights=WeightGrid(
            sets={"flat": {f: 0.5 for f in fams}}, subsets=("core",), seeds=(3,), hops=(2,)
        ),
    )
    _, out = evaluate_instance(arrays, meta, spec)
    keys = list(out["keys"])
    m = out["metrics_L2"]
    for variant in ("list", "rrf"):
        u = m[keys.index(graph_key(variant, "core", 3, 0.5, 2))]
        w = m[keys.index(f"{variant}|core|C3|w:flat|h2")]
        assert np.allclose(u, w)


def test_test_roles_need_a_single_setting_specification() -> None:
    cfg = {"roles": ["test"], "graph": {"seeds": [3], "gammas": [0.5], "hops": [2]}}
    with pytest.raises(ValueError, match="confirm"):
        spec_from_config(cfg)
    cfg["confirm"] = True
    spec_from_config(cfg)  # one setting: accepted
    cfg["graph"]["seeds"] = [1, 3]  # type: ignore[index]
    with pytest.raises(ValueError, match="one C"):
        spec_from_config(cfg)
    bad = {
        "roles": ["dev", "test"],
        "confirm": True,
        "recency": {"lam": [0.1, 0.2], "tau_days": [30]},
    }
    with pytest.raises(ValueError, match="recency"):
        spec_from_config(bad)


def test_query_without_matching_terms_leaves_every_variant_at_the_baseline(snapshot: Path) -> None:
    arrays, meta = _cache(snapshot)
    meta.update(instance="inst-1", role="dev")
    arrays["scores_L2"] = np.zeros_like(arrays["scores_L2"])
    spec = EvalSpec(
        roles=("dev",),
        graph=GraphGrid(subsets=("all",), seeds=(3,), gammas=(0.5,), hops=(2,), draws=1),
    )
    _, out = evaluate_instance(arrays, meta, spec)
    m = out["metrics_L2"]
    assert np.allclose(m, m[0])  # all keys equal the bm25 row
