"""Integration: X1 extras (class-source forms, ambiguous sites, gold readings) on a small snapshot,
merged with the pilot-E3 cache and evaluated per variant; then the cross-variant tables."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from ril.analysis.x1_tables import load_variants, select_variant, variant_diffs, write_x1_tables
from ril.evaluation.e3_prepare import prepare_instance, write_cache
from ril.evaluation.unit_retrieval import analyse_units
from ril.evaluation.x1_eval import (
    Variant,
    check_alignment,
    policy_invoke_pairs,
    run_x1_eval,
    variant_arrays,
    x1_spec,
)
from ril.evaluation.x1_prepare import prepare_x1_instance
from ril.retrieval.bm25_index import BM25Params

FILES = {
    "pkg/__init__.py": "",
    "pkg/store.py": (
        "class Store:\n"
        '    """Keeps rows."""\n'
        "    LIMIT = 3\n\n"
        "    def get(self, key):\n        return key\n\n"
        "    def put(self, key, value):\n        return value\n\n"
        "class Cache:\n"
        "    def get(self, key):\n        return None\n"
    ),
    "pkg/use.py": (
        "def lookup(thing, key):\n    return thing.get(key)\n\n"
        "def literal_lookup(key):\n    d = dict()\n    return d.get(key)\n"
    ),
    "tests/test_use.py": (
        "from pkg.use import lookup\n\ndef test_lookup(store):\n    assert store.get(1) == 1\n"
    ),
}
ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.org",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.org",
}
QUERIES = {"L2": "store get key rows", "L3": "cache get key"}
LEVELS = {
    "L2": {"c1": "    def get(self, key):\n        return key\n"},
    "L3": {"c2": "class Cache:\n"},
}


@pytest.fixture
def snapshot(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    for rel, text in FILES.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8")
    for args in (["init", "-q", "-b", "main"], ["add", "-A"], ["commit", "-q", "-m", "one"]):
        subprocess.run(["git", *args], cwd=root, env=ENV, check=True, capture_output=True)
    return root


def _both(snapshot: Path) -> tuple[Any, Any, Any, Any]:
    e1 = analyse_units(str(snapshot), "acme/x1", "inst-1", QUERIES, LEVELS, "")
    e3, e3_meta = prepare_instance(str(snapshot), "acme/x1", QUERIES, e1, BM25Params(), "h3")
    x1, x1_meta = prepare_x1_instance(str(snapshot), "acme/x1", QUERIES, e1, BM25Params(), "h1")
    common = {"instance": "inst-1", "role": "dev", "dataset": "d", "folder": "f"}
    e3_meta.update(common)
    x1_meta.update(common)
    return e3, e3_meta, x1, x1_meta


def test_extras_align_with_the_e3_cache_and_differ_by_form(snapshot: Path) -> None:
    e3, e3_meta, x1, x1_meta = _both(snapshot)
    check_alignment(e3, e3_meta, x1, x1_meta)  # full scores identical, same resolved pairs
    assert not np.array_equal(x1["scores_L2_full"], x1["scores_L2_header"])
    sizes = x1_meta["index_size"]
    assert sizes["header"]["tokens"] < sizes["header_sigs"]["tokens"] < sizes["full"]["tokens"]
    assert x1_meta["ambiguous"]["sites"] >= 2  # thing.get and store.get name-match two classes
    bad = dict(x1)
    bad["scores_L2_full"] = x1["scores_L2_full"] + 1.0
    with pytest.raises(ValueError):
        check_alignment(e3, e3_meta, bad, x1_meta)


def test_policy_pairs_follow_the_evidence(snapshot: Path) -> None:
    _, _, x1, _ = _both(snapshot)
    keep = policy_invoke_pairs(x1, Variant("k", policy="keep"))
    reb = policy_invoke_pairs(x1, Variant("r", policy="rebucket"))
    drop = policy_invoke_pairs(x1, Variant("d", policy="drop"))
    assert len(drop) == 0 and 0 < len(reb) < len(keep)  # the fixture site is re-bucketed
    nofix = policy_invoke_pairs(
        x1, Variant("n", policy="rebucket", evidence=("literal", "kwargs", "annotated_external"))
    )
    assert len(nofix) == len(keep)


def test_variant_eval_and_tables(snapshot: Path, tmp_path: Path) -> None:
    e3, e3_meta, x1, x1_meta = _both(snapshot)
    write_cache(str(tmp_path / "e3" / "inst-1.npz"), e3, e3_meta)
    write_cache(str(tmp_path / "x1" / "inst-1.npz"), x1, x1_meta)
    cfg = {
        "roles": ["dev"],
        "seed": 0,
        "reference": "full",
        "variants": {"full": {}, "header": {"form": "header"}, "pol_keep": {"policy": "keep"}},
        "graph": {
            "variants": ["list"],
            "subsets": ["core"],
            "seeds": [1],
            "gammas": [0.5],
            "hops": [1],
            "draws": 1,
        },
    }
    out = str(tmp_path / "out")
    counts = run_x1_eval(cfg, str(tmp_path / "e3"), str(tmp_path / "x1"), out)
    assert counts["evaluated"] == 3
    assert run_x1_eval(cfg, str(tmp_path / "e3"), str(tmp_path / "x1"), out)["reused"] == 3
    arrays = variant_arrays(e3, e3_meta, x1, Variant("full"))
    assert np.array_equal(arrays["scores_L2"], e3["scores_L2"])
    tabs = load_variants(out, ["full", "header", "pol_keep"])
    mask = tabs["full"].mask(role="dev")
    rows = variant_diffs(tabs, "full", ["bm25"], mask, "dev_all", "L2", 0)
    ref_rows = [r for r in rows if r["variant"] == "full"]
    assert ref_rows and all("d_ref" not in r for r in ref_rows)
    keep_bm25 = [r for r in rows if r["variant"] == "pol_keep" and r["average"] == "micro"]
    assert all(r["d_ref"] == 0.0 for r in keep_bm25)  # a policy never changes BM25 alone
    summary = write_x1_tables(cfg, out, str(tmp_path / "tab"), seed=0)
    assert summary["queries"] == 2 and os.path.exists(str(tmp_path / "tab_variants.csv"))


def test_confirm_spec_refuses_more_than_stated_and_reference() -> None:
    base = {
        "roles": ["test"],
        "confirm": True,
        "graph": {"subsets": ["core"], "seeds": [5], "gammas": [0.5], "hops": [2]},
    }
    ok = {
        **base,
        "stated": "header",
        "reference": "full",
        "variants": {"full": {}, "header": {"form": "header"}},
    }
    assert len(x1_spec(ok).variants) == 2
    with pytest.raises(ValueError):
        x1_spec({**ok, "variants": {**ok["variants"], "pol_keep": {"policy": "keep"}}})
    with pytest.raises(ValueError):
        x1_spec({**base, "confirm": False, "variants": {"full": {}}})  # sweep on test
    with pytest.raises(ValueError):
        x1_spec({**ok, "variants": {"full": {"form": "nope"}}, "stated": "full"})


def test_selection_rule() -> None:
    def row(v: str, level: str, metric: str, d: float, lo: float, hi: float) -> dict[str, Any]:
        return {
            "variant": v,
            "level": level,
            "metric": metric,
            "key": "k",
            "gold_reading": "r",
            "average": "micro",
            "group": "dev_all",
            "d_ref": d,
            "d_ref_lo": lo,
            "d_ref_hi": hi,
        }

    rule = {"key": "k", "reading": "r", "reference": "full", "candidates": ["a", "b"]}
    rows = [
        row("a", "L2", "ndcg10", 1.0, -0.5, 2.5),
        row("a", "L3", "recall100", 1.0, -1.0, 3.0),
        row("b", "L2", "ndcg10", 0.5, 0.1, 0.9),
        row("b", "L3", "recall100", 0.2, -0.4, 0.8),
    ]
    got = select_variant(rows, rule)
    assert got["winner"] == "b"  # a has the larger mean but no interval above zero
    rows[2]["d_ref_hi"], rows[3]["d_ref_hi"] = 0.9, -0.1  # b now has an interval below zero
    assert select_variant(rows, rule)["winner"] == "full"
