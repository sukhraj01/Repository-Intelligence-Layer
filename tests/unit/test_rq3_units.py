"""Tests for the unit and cache build of the executable subset (E-RQ3-UNITS, D107)."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import yaml

from ril.evaluation import rq3_units as ru
from ril.evaluation.e3_prepare import read_cache

SUBSET = {
    "executable": [
        {"instance_id": "pytest-dev__pytest-1", "repo": "pytest-dev/pytest"},
        {"instance_id": "pytest-dev__pytest-2", "repo": "pytest-dev/pytest"},
        {"instance_id": "sympy__sympy-3", "repo": "sympy/sympy"},
    ]
}


def _row(iid: str, commit: str = "c") -> dict[str, Any]:
    return {
        "instance_id": iid,
        "base_commit": commit,
        "patch": "",
        "problem_statement": f"text {iid}",
    }


def test_build_inputs_maps_folders_and_filters_repos() -> None:
    rows = [
        _row("pytest-dev__pytest-1"),
        _row("pytest-dev__pytest-2"),
        _row("sympy__sympy-3"),
        _row("x-9"),
    ]
    meta, queries = ru.build_inputs(SUBSET, rows)
    assert sorted(meta) == ["pytest-dev__pytest-1", "pytest-dev__pytest-2", "sympy__sympy-3"]
    assert (
        meta["sympy__sympy-3"]["folder"] == "sympy__sympy"
        and meta["pytest-dev__pytest-1"]["folder"] == "pytest"
    )
    assert queries["sympy__sympy-3"] == "text sympy__sympy-3"
    only, _ = ru.build_inputs(SUBSET, rows, {"sympy/sympy"})
    assert sorted(only) == ["sympy__sympy-3"]


def test_build_inputs_refuses_a_member_missing_from_the_table() -> None:
    with pytest.raises(ValueError, match="not in the table"):
        ru.build_inputs(SUBSET, [_row("pytest-dev__pytest-1")])


def test_rule_uses_the_measured_rate_and_the_limit() -> None:
    at = ru.encoding_rule(int(6.0 * 3600 * 109), 10**7)
    assert at["allowed"] and at["limit_gpu_hours"] == 6.0
    over = ru.encoding_rule(int(6.0 * 3600 * 109) + 1000, 10**7)
    assert not over["allowed"]
    assert (
        over["implied_gpu_hours_at_229"]
        < over["implied_gpu_hours_at_178"]
        < over["implied_gpu_hours"]
    )


def _git(args: list[str], cwd: Path) -> None:
    subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        env={
            **os.environ,
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@t",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@t",
        },
    )


def _repo(tmp_path: Path) -> tuple[str, str, str]:
    src = tmp_path / "src"
    src.mkdir()
    _git(["init", "-q", "-b", "main"], src)
    (src / "a.py").write_text(
        "def alpha(x):\n    return x + 1\n\n\ndef beta(y):\n    return alpha(y) * 2\n"
    )
    _git(["add", "."], src)
    _git(["commit", "-q", "-m", "one"], src)
    c1 = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=src, capture_output=True, text=True, check=True
    ).stdout.strip()
    (src / "a.py").write_text(
        "def alpha(x):\n    return x + 2\n\n\ndef gamma(z):\n    return alpha(z)\n"
    )
    _git(["commit", "-q", "-am", "two"], src)
    c2 = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=src, capture_output=True, text=True, check=True
    ).stdout.strip()
    cache = tmp_path / "repo_cache"
    cache.mkdir()
    _git(["clone", "-q", "--bare", str(src), str(cache / "pytest-dev__pytest.git")], tmp_path)
    return str(cache), c1, c2


def test_unlabelled_members_get_scores_and_texts(tmp_path: Path) -> None:
    cache, c1, c2 = _repo(tmp_path)
    cfg = {
        "experiment_id": "t",
        "seed": 0,
        "bm25": {"k1": 1.5, "b": 0.75},
        "folders": [
            {
                "role": "test",
                "dataset": ru.DATASET,
                "folder": "pytest",
                "repo": "pytest-dev/pytest",
                "levels": ["L2", "L3"],
                "units": True,
            }
        ],
    }
    cfg_path = tmp_path / "cfg.yaml"
    cfg_path.write_text(yaml.safe_dump(cfg))
    meta = {
        "pytest-dev__pytest-1": {
            "repo": "pytest-dev/pytest",
            "base_commit": c1,
            "patch": "",
            "dataset": ru.DATASET,
            "folder": "pytest",
        },
        "pytest-dev__pytest-2": {
            "repo": "pytest-dev/pytest",
            "base_commit": c2,
            "patch": "",
            "dataset": ru.DATASET,
            "folder": "pytest",
        },
    }
    queries = {
        "pytest-dev__pytest-1": "alpha returns wrong value",
        "pytest-dev__pytest-2": "gamma alpha",
    }
    dirs = {k: str(tmp_path / k) for k in ("cache", "e1", "work", "out", "prep")}
    for shard in range(2):
        fails = ru.prepare_members(
            str(cfg_path),
            str(tmp_path / "raw"),
            meta,
            queries,
            cache,
            dirs["cache"],
            dirs["e1"],
            dirs["work"],
            dirs["out"],
            shard=(shard, 2),
        )
        assert fails == []
    arrays, m = read_cache(os.path.join(dirs["cache"], "pytest-dev__pytest-2.npz"))
    assert m["l2_query_source"] == "verified_table" and m["labelled_levels"] == []
    assert arrays["scores_L2"].shape[0] == m["units"] and "gold_L2_units" not in arrays
    assert not os.listdir(dirs["e1"]) if os.path.isdir(dirs["e1"]) else True
    again = ru.prepare_members(
        str(cfg_path),
        str(tmp_path / "raw"),
        meta,
        queries,
        cache,
        dirs["cache"],
        dirs["e1"],
        dirs["work"],
        dirs["out"],
    )
    assert again == []  # resumable: nothing is rebuilt
    res = ru.prepare_unit_texts(
        str(cfg_path), meta, cache, dirs["cache"], dirs["work"], dirs["prep"]
    )
    assert res["prepared"] == 2 and res["failures"] == []
    ru.prepare_query_store(dirs["out"], dirs["prep"])
    qs = [
        json.loads(x)
        for x in open(os.path.join(dirs["prep"], "queries", f"L2__{ru.DATASET}__pytest.jsonl"))
    ]
    assert len(qs) == 2
    counts = ru.distinct_counts(dirs["prep"])
    row = counts["per_repo"]["pytest-dev__pytest"]
    assert row["instances"] == 2 and row["distinct_texts"] < row["unit_slots"]
    assert counts["saving_factor"] > 1.0 and counts["distinct_texts"] == ru.store_texts(
        dirs["prep"]
    )
    miss = ru.missing_vectors(dirs["prep"], str(tmp_path / "enc"))
    assert miss["missing"] == miss["texts_checked"] > 0
    assert np.all(np.isfinite(arrays["scores_L2"]))
