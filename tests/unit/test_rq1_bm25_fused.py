"""E-A1-FUSED: the control cell reproduces the stored chunk scoring, fusion and differences hold."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import yaml

from ril.analysis import rq1_bm25_fused as fused
from ril.evaluation.core_bench import read_folder
from ril.evaluation.x2_dense import query_key, score_chunks, text_hash
from tests.unit.test_rq1_bm25_dev import CORPUS, QUERIES, _write_folder

DIM = 8


def _vectors(keys: list[str], seed: int) -> dict[str, np.ndarray[Any, Any]]:
    rng = np.random.default_rng(seed)
    out = {}
    for key in keys:
        v = rng.normal(size=DIM)
        out[key] = (v / np.linalg.norm(v)).astype(np.float32)
    return out


def _write_store(path: Path, vecs: dict[str, np.ndarray[Any, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(
        path,
        vectors=np.stack(list(vecs.values())),
        ntok=np.full(len(vecs), 10),
        hashes=np.array(list(vecs)),
    )


@pytest.fixture
def setup(tmp_path: Path) -> dict[str, Any]:
    data = tmp_path / "data"
    _write_folder(data, "L2", "Pro", "alpha")
    _write_folder(data, "L3", "Pro", "alpha")
    enc = tmp_path / "enc"
    for i, store in enumerate(("encA", "encB")):
        _write_store(
            enc / store / "chunks__o__alpha.npz",
            _vectors([text_hash(t) for _, t in CORPUS], seed=i),
        )
        for level in ("L2", "L3"):
            keys = [query_key(level, "Pro", "alpha", qid) for qid, *_ in QUERIES]
            _write_store(
                enc / store / f"queries__{level}__Pro__alpha.npz", _vectors(keys, seed=10 + i)
            )
    spec = {
        "role": "dev",
        "dataset": "Pro",
        "folder": "alpha",
        "repo": "o/alpha",
        "levels": ["L2", "L3"],
        "units": True,
    }
    cfg = {
        "seed": 0,
        "bm25": {"k1": 1.5, "b": 0.75},
        "bootstrap": {"draws": 100},
        "bm25_cells": {
            "control": ["ref", 1.5, 0.75],
            "variants": [["split", 1.5, 0.75], ["split", 2.0, 0.75]],
        },
        "dense": {"a": {"store": "encA", "rrf_k": 20}, "b": {"store": "encB", "rrf_k": 100}},
        "folders": [spec],
    }
    e1 = tmp_path / "e1.yaml"
    e1.write_text(yaml.safe_dump({**cfg, "folders": [spec]}))
    return {"data": data, "enc": enc, "cfg": cfg, "e1": e1, "tmp": tmp_path}


def test_control_cell_equals_the_stored_chunk_scoring(setup: dict[str, Any]) -> None:
    tmp: Path = setup["tmp"]
    enc = {s: str(setup["enc"] / s) for s in ("encA", "encB")}
    score_chunks(str(setup["e1"]), {"dev"}, str(setup["data"]), enc, str(tmp / "stored"))
    out = str(tmp / "out")
    assert fused.run_all(setup["cfg"], str(setup["data"]), str(setup["enc"]), out) == 2
    assert fused.run_all(setup["cfg"], str(setup["data"]), str(setup["enc"]), out) == 0
    runs = fused.load_runs(out)
    reg = fused.regression_against_stored(
        runs, setup["cfg"], str(tmp / "stored"), "ref_k1_1.5_b_0.75"
    )
    assert reg["exact"] is True and reg["checked"] == 2 * 3 * 3


def test_fusion_ranks_and_difference_table(setup: dict[str, Any]) -> None:
    rb = np.array([1, 2, 3, 4])
    rd = np.array([4, 3, 2, 1])
    # the two extremes tie at the top (1/21 + 1/24 both ways), the first list's rank breaks the tie
    assert fused.fused_ranks(rb, rd, 20).tolist() == [1, 3, 4, 2]
    cfg = setup["cfg"]
    out = str(setup["tmp"] / "out")
    fused.run_all(cfg, str(setup["data"]), str(setup["enc"]), out)
    rows = fused.query_rows(fused.load_runs(out))
    assert len(rows) == 2 * 3 * 3 * 3  # levels x queries x cells x systems
    table = fused.difference_table(rows, cfg, draws=100)
    assert {r["level"] for r in table} == {"L2", "L3", "pooled"}
    assert {r["system"] for r in table} == {"bm25", "rrf_a_k20", "rrf_b_k100"}
    pooled = [r for r in table if r["level"] == "pooled" and r["metric"] == "ndcg10"]
    assert all(r["queries"] == 6 and r["repositories"] == 1 for r in pooled)
    assert all(r["c_lo"] <= r["diff"] <= r["c_hi"] or r["c_lo"] == r["c_hi"] for r in pooled)


def test_test_folders_are_refused(setup: dict[str, Any]) -> None:
    cfg = json.loads(json.dumps(setup["cfg"]))
    cfg["folders"][0]["role"] = "test"
    with pytest.raises(ValueError, match="development folders only"):
        fused.run_all(cfg, str(setup["data"]), str(setup["enc"]), str(setup["tmp"] / "o"))


def test_read_folder_import_is_the_loader_of_the_stored_scoring(setup: dict[str, Any]) -> None:
    folder = read_folder(str(setup["data"] / "data" / "LEVEL-2" / "Pro" / "alpha"))
    assert [t for _, t in CORPUS] == list(folder.corpus_texts)


def test_cells_systems_and_single_folder_run(setup: dict[str, Any]) -> None:
    cfg = setup["cfg"]
    assert fused.cells_of(cfg)[0] == ("ref", 1.5, 0.75) and len(fused.cells_of(cfg)) == 3
    assert fused.system_names(cfg) == ["bm25", "rrf_a_k20", "rrf_b_k100"]
    out = str(setup["tmp"] / "single")
    spec = cfg["folders"][0]
    assert fused.run_folder(cfg, spec, "L2", str(setup["data"]), str(setup["enc"]), out) is True
    assert fused.run_folder(cfg, spec, "L2", str(setup["data"]), str(setup["enc"]), out) is False
