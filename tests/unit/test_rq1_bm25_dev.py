"""A1-DEV runner: the reference cell is the E1 run, cells resume, and the selection rule holds."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ril.analysis import rq1_bm25_dev as a1
from ril.evaluation.core_bench import evaluate_folder, read_folder
from ril.retrieval.bm25_index import BM25Params

CORPUS = [
    ("c0", "def parse_header(raw): return raw.split(':')"),
    ("c1", "class HttpClient:\n    def send_request(self, url): pass"),
    ("c2", "def read_config(path): return open(path).read()"),
    ("c3", "README: how to send a request with the http client"),
    ("c4", "def parseHeaderValue(value): return value.strip()"),
]
QUERIES = [
    ("q0", "header parsing fails on empty value", ["c0", "c4", "c2"], ["c4"]),
    ("q1", "send request through HttpClient", None, ["c1"]),
    ("q2", "config file is read twice", ["c2", "c3"], ["c2"]),
]


def _write_folder(root: Path, level: str, dataset: str, folder: str) -> None:
    d = root / "data" / a1.LEVEL_DIR[level] / dataset / folder
    d.mkdir(parents=True)
    with open(d / "corpus.jsonl", "w") as fh:
        for cid, text in CORPUS:
            fh.write(json.dumps({"_id": cid, "title": "", "text": text}) + "\n")
    with open(d / "queries.jsonl", "w") as fh:
        for qid, text, cand, _ in QUERIES:
            row: dict[str, Any] = {"_id": qid, "text": text}
            if cand is not None:
                row["filtered_corpus_id"] = cand
            fh.write(json.dumps(row) + "\n")
    with open(d / "qrels.jsonl", "w") as fh:
        for qid, _, _, pos in QUERIES:
            for cid in pos:
                fh.write(json.dumps({"query_id": qid, "corpus_id": cid, "score": 1}) + "\n")


def _cfg(folders: list[tuple[str, str, list[str]]], role: str = "dev") -> dict[str, Any]:
    return {
        "seed": 0,
        "prefilter_k": 10000,
        "metrics": {"ndcg_at": 10},
        "bm25": {"k1": 1.5, "b": 0.75},
        "bootstrap": {"draws": 200},
        "stage1": {"tokenizers": ["ref", "split", "split_noorig"], "k1": 1.5, "b": 0.75},
        "stage2": {"k1": [1.2, 1.5], "b": [0.75]},
        "folders": [
            {"role": role, "dataset": ds, "folder": f, "repo": f"o/{f}", "levels": lv}
            for ds, f, lv in folders
        ],
    }


@pytest.fixture
def data(tmp_path: Path) -> Path:
    _write_folder(tmp_path, "L2", "Pro", "alpha")
    _write_folder(tmp_path, "L3", "Pro", "alpha")
    _write_folder(tmp_path, "L2", "Live", "beta")
    return tmp_path


FOLDERS = [("Pro", "alpha", ["L2", "L3"]), ("Live", "beta", ["L2"])]


def test_reference_cell_reproduces_the_e1_records(data: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    a1.run_cells(_cfg(FOLDERS), str(data), str(out), [("ref", 1.5, 0.75)])
    run = a1.load_cell(str(out), ("ref", 1.5, 0.75))[0]
    folder = read_folder(str(data / "data" / "LEVEL-2" / "Pro" / "alpha"))
    assert run["records"] == json.loads(json.dumps(evaluate_folder(folder, BM25Params())))


def test_cells_resume_and_test_folders_are_refused(data: Path, tmp_path: Path) -> None:
    cfg, out = _cfg(FOLDERS), str(tmp_path / "out")
    cells = a1.stage_cells(cfg, "stage1")
    assert a1.run_cells(cfg, str(data), out, cells) == 9
    assert a1.run_cells(cfg, str(data), out, cells) == 0
    with pytest.raises(ValueError, match="development folders only"):
        a1.run_cells(_cfg(FOLDERS, role="test"), str(data), out, cells)


def test_summary_selection_and_regression(data: Path, tmp_path: Path) -> None:
    cfg, out = _cfg(FOLDERS), str(tmp_path / "out")
    s1 = a1.stage_cells(cfg, "stage1")
    a1.run_cells(cfg, str(data), out, s1)
    rows = a1.summarise_cells(out, s1, ("ref", 1.5, 0.75), draws=200)
    assert [r["cell"] for r in rows] == [a1.cell_name(c) for c in s1]
    assert rows[0]["diff_vs_baseline"] == 0.0 and rows[0]["queries"] == 9
    assert rows[0]["repositories"] == 2
    pick = a1.choose(rows, "ref_k1_1.5_b_0.75")
    assert pick["adopted"] in {pick["best"], "ref_k1_1.5_b_0.75"}
    reg = a1.regression_check(out, ["alpha", "beta"], rows[0]["ndcg10"], 9)
    assert reg["exact"] is True
    assert a1.regression_check(out, ["alpha"], rows[0]["ndcg10"], 9)["exact"] is False


def test_choose_needs_a_clustered_interval_above_zero() -> None:
    rows = [
        {"cell": "base", "ndcg10": 20.0, "clustered_lo": 0.0},
        {"cell": "x", "ndcg10": 21.0, "clustered_lo": -0.1},
    ]
    assert a1.choose(rows, "base")["adopted"] == "base"
    rows[1]["clustered_lo"] = 0.2
    assert a1.choose(rows, "base")["adopted"] == "x"


def test_stage2_grid_is_on_one_tokenizer() -> None:
    cells = a1.stage_cells(_cfg(FOLDERS), "stage2", "split")
    assert cells == [("split", 1.2, 0.75), ("split", 1.5, 0.75)]
    with pytest.raises(ValueError):
        a1.stage_cells(_cfg(FOLDERS), "stage2")


def test_query_level_rows_and_run_file_hashes(data: Path, tmp_path: Path) -> None:
    cfg, out = _cfg(FOLDERS), str(tmp_path / "out")
    s1 = a1.stage_cells(cfg, "stage1")
    a1.run_cells(cfg, str(data), out, s1)
    rows = a1.query_level_rows(out, s1)
    assert len(rows) == 9 * 3
    assert {r["cell"] for r in rows} == {a1.cell_name(c) for c in s1}
    first = [r for r in rows if r["cell"] == "ref_k1_1.5_b_0.75"]
    pooled = a1.summarise_cells(out, s1[:1], s1[0], draws=200)[0]["ndcg10"]
    assert round(sum(r["ndcg10"] for r in first) / len(first), 4) == pooled
    assert all(0.0 <= r["recall100"] <= 100.0 and r["positives"] >= 1 for r in rows)
    files = a1.run_file_hashes(out)
    assert len(files) == 9 and all(len(str(f["sha256"])) == 64 for f in files)
    assert files == a1.run_file_hashes(out)
