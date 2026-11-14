"""The L3 query stores of the built parts and the L3 count of the retained scores.

Regression for the sealed scoring stopping on a missing ``dense_L3``: the built parts stored
queries at L2 only, so the dense stage skipped L3 for members the folder labels at that level.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pytest

from ril.evaluation import rq3_units as ru
from ril.evaluation import score_retention as sr
from ril.evaluation.checkpoint_eval import stores_for
from ril.evaluation.e3_prepare import write_cache
from ril.evaluation.x2_dense import query_key, read_store

FOLDER = "pytest"
CONFIG = """\
folders:
- dataset: SWE-bench_Verified
  folder: pytest
  repo: pytest-dev/pytest
  role: test
  units: true
  levels: [L2, L3]
"""


def _cache(cache: Path, instance: str, levels: list[str], same: bool = True) -> None:
    s2 = np.arange(4, dtype=np.float32)
    arrays = {"scores_L2": s2}
    if "L3" in levels:
        arrays["scores_L3"] = s2.copy() if same else s2 + 1
    meta = {"instance": instance, "folder": FOLDER, "levels": levels}
    write_cache(str(cache / f"{instance}.npz"), arrays, meta)


def _l2_store(prep: Path, instances: list[str]) -> Path:
    path = prep / "queries" / f"L2__{ru.DATASET}__{FOLDER}.jsonl"
    path.parent.mkdir(parents=True)
    rows = [{"h": query_key("L2", ru.DATASET, FOLDER, i), "t": f"issue {i}"} for i in instances]
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return path


def test_l3_rows_copy_the_l2_text_for_the_members_with_an_l3_level(tmp_path: Path) -> None:
    cache, prep = tmp_path / "cache", tmp_path / "prep"
    _cache(cache, "p-1", ["L2", "L3"])
    _cache(cache, "p-2", ["L2"])
    l2 = _l2_store(prep, ["p-1", "p-2"])
    before = l2.read_bytes()
    res = ru.add_l3_query_store(str(cache), str(prep))
    assert res == {"queries_l3": {FOLDER: 1}}
    l3 = prep / "queries" / f"L3__{ru.DATASET}__{FOLDER}.jsonl"
    assert read_store([str(l3)]) == {query_key("L3", ru.DATASET, FOLDER, "p-1"): "issue p-1"}
    assert l2.read_bytes() == before  # the L2 store is not touched
    first = l3.read_bytes()
    ru.add_l3_query_store(str(cache), str(prep))
    assert l3.read_bytes() == first  # a rerun gives the same file


def test_the_dense_stage_now_finds_the_l3_store(tmp_path: Path) -> None:
    cache, prep = tmp_path / "cache", tmp_path / "prep"
    cfg = tmp_path / "e1.yaml"
    cfg.write_text(CONFIG, encoding="utf-8")
    _cache(cache, "p-1", ["L2", "L3"])
    _l2_store(prep, ["p-1"])
    names = set(stores_for(str(cfg), str(prep), ["test"], False))
    assert f"queries__L2__{ru.DATASET}__{FOLDER}" in names
    assert f"queries__L3__{ru.DATASET}__{FOLDER}" not in names  # the defect
    ru.add_l3_query_store(str(cache), str(prep))
    assert f"queries__L3__{ru.DATASET}__{FOLDER}" in set(
        stores_for(str(cfg), str(prep), ["test"], False)
    )


def test_a_member_whose_l3_text_differs_is_refused(tmp_path: Path) -> None:
    cache, prep = tmp_path / "cache", tmp_path / "prep"
    _cache(cache, "p-1", ["L2", "L3"], same=False)
    _l2_store(prep, ["p-1"])
    with pytest.raises(ValueError, match="not the L2 text"):
        ru.add_l3_query_store(str(cache), str(prep))
    assert not os.path.exists(prep / "queries" / f"L3__{ru.DATASET}__{FOLDER}.jsonl")


def test_a_member_without_an_l2_text_is_refused(tmp_path: Path) -> None:
    cache, prep = tmp_path / "cache", tmp_path / "prep"
    _cache(cache, "p-9", ["L2", "L3"])
    _l2_store(prep, ["p-1"])
    with pytest.raises(ValueError, match="no L2 query text"):
        ru.add_l3_query_store(str(cache), str(prep))


def test_the_retention_record_counts_the_members_that_carry_l3(tmp_path: Path) -> None:
    src, root = tmp_path / "src", tmp_path / "scores"
    src.mkdir()
    ids = ["o__r-1", "o__r-2"]
    np.savez_compressed(src / "o__r-1.npz", dense_L2=np.zeros(3), dense_L3=np.zeros(3))
    np.savez_compressed(src / "o__r-2.npz", dense_L2=np.zeros(3))
    sr.retain_part(
        str(src),
        ids,
        scores_root=str(root),
        run_id="r",
        part="p",
        model_sha256="m",
        config_hash="c",
        follows="E-X",
        dev_record_sha256="d",
        commit="c",
    )
    rec = sr.read_record(str(root), "r")
    assert rec is not None and rec["l3_instances"] == 1 and rec["l3_ids"] == ["o__r-1"]
    assert rec["dense_keys"] == ["dense_L2", "dense_L3"] and rec["complete"]
    assert not sr.verify(str(root), "r", ids, expected_l3=1)
    assert sr.verify(str(root), "r", ids, expected_l3=2)  # an L3 count that is short is a problem
