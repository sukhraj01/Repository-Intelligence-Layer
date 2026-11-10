"""Unit-level BM25 variants (D119): control reproduction, keys, paired tables."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from ril.analysis import rq1_unit_bm25 as ub
from ril.analysis.e3_tables import EvalTable
from ril.evaluation import unit_bm25 as u
from ril.evaluation.e3_prepare import READINGS
from ril.parsing.repository_parser import parse_repository
from ril.retrieval.bm25_index import BM25Index, tokenize

FILES = {
    "pkg/a.py": "def read_config_file(p):\n    '''Read it.'''\n    return open(p).read()\n",
    "pkg/b.py": "def writeConfigFile(p, d):\n    '''Write it.'''\n    open(p, 'w').write(d)\n",
    "pkg/c.py": "class Parser:\n    def parse(self, text):\n        return text.split()\n",
}


def _units(tmp_path: Path) -> list[Any]:
    for rel, text in FILES.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return sorted(parse_repository(str(tmp_path), "o/r").units, key=lambda x: x.id)


def _instance(
    units: list[Any], query: str
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    n = len(units)
    idx = BM25Index(tokenize(x.source) for x in units)
    stored = idx.scores(tokenize(query))
    gold = np.asarray([i for i, x in enumerate(units) if x.name == "read_config_file"], np.int32)
    arrays: dict[str, Any] = {"scores_L2": stored}
    for r in READINGS:
        arrays[f"gold_L2_{r}"] = gold
    meta = {"instance": "i1", "units": n, "levels": ["L2"]}
    dense = {"dense_L2": np.random.default_rng(0).random(n).astype(np.float32)}
    return arrays, meta, dense


def test_control_reproduces_stored_scores_and_keys_are_complete(tmp_path: Path) -> None:
    units = _units(tmp_path)
    arrays, meta, dense = _instance(units, "read the settings file")
    info, out, checks = u.evaluate_units(
        units, {"L2": "read the settings file"}, arrays, meta, dense
    )
    assert [c["reproduces"] for c in checks] == [True]
    assert [str(k) for k in out["keys"]] == u.all_keys()
    assert out["metrics_L2"].shape == (len(u.all_keys()), 2 * len(READINGS))
    assert info["levels"]["L2"]["gold_units"] == 1


def test_a_changed_unit_text_fails_the_control_check(tmp_path: Path) -> None:
    units = _units(tmp_path)
    arrays, meta, dense = _instance(units, "read the settings file")
    arrays["scores_L2"] = arrays["scores_L2"] + 0.001
    _, _, checks = u.evaluate_units(units, {"L2": "read the settings file"}, arrays, meta, dense)
    assert not checks[0]["reproduces"] and checks[0]["max_abs_diff"] > 0


def test_unit_count_mismatch_raises(tmp_path: Path) -> None:
    units = _units(tmp_path)
    arrays, meta, dense = _instance(units, "x y")
    meta["units"] = len(units) + 1
    try:
        u.evaluate_units(units, {"L2": "x y"}, arrays, meta, dense)
    except ValueError as exc:
        assert "rebuilt" in str(exc)
    else:
        raise AssertionError("expected a ValueError")


def test_split_cell_finds_the_camel_case_name(tmp_path: Path) -> None:
    units = _units(tmp_path)
    cell = next(c for c in u.CELLS if c.name == "tok_split")
    idx = BM25Index(u.unit_documents(units, cell))
    scores = u.cell_scores(idx, "write config file", cell)
    assert units[int(np.argmax(scores))].name == "writeConfigFile"


def test_tables_pair_every_cell_with_the_control() -> None:
    rng = np.random.default_rng(1)
    keys = u.all_keys()
    q = 12
    metrics = rng.random((q, len(keys), 2 * len(READINGS)))
    rows = [
        {"instance": f"i{i}", "level": "L2", "repo": f"r{i % 3}", "role": "dev"} for i in range(q)
    ]
    tab = EvalTable(
        keys, {k: i for i, k in enumerate(keys)}, rows, metrics, [], np.zeros((q, 0, 5))
    )
    cmp = ub.compare_rows(tab, draws=50)
    cells = {r["cell"] for r in cmp}
    assert cells == {c.name for c in u.CELLS} - {"control"}
    assert {r["where"] for r in cmp} == {"alone", "fused"}
    assert ub.best_cell(tab) in cells
