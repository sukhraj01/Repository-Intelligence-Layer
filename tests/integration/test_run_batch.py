"""The run-batch path of ``scripts/train.py`` on the tiny model: several configurations trained from
one loaded cache, each evaluated (per-query rows written), the model dropped, finished runs skipped
on a rerun, and an override evaluation stored under its own label. Ada only (torch)."""

from __future__ import annotations

import pytest

torch = pytest.importorskip("torch")  # Ada only: the local machine has no torch (Makefile header)
pytestmark = pytest.mark.torch

import json  # noqa: E402
import os  # noqa: E402
from pathlib import Path  # noqa: E402

import yaml  # noqa: E402

from ril.training.pool_reader import write_cache  # noqa: E402
from scripts.train import main  # noqa: E402
from tests.unit._training_fixtures import (  # noqa: E402
    synthetic_examples,
    train_config,
    write_feature_table,
    x2_inputs,
)


def test_run_batch_trains_evaluates_and_skips(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exs = synthetic_examples(repos=3, prs=5)
    cache = str(tmp_path / "pool.jsonl.gz")
    write_cache(cache, exs)
    table = str(tmp_path / "features.csv")
    write_feature_table(table, exs, ("bm25",))
    ev = {"roles": ["dev"], "rrf_k": 60, "batch_size": 8, "chunks": False, "seed": 0}
    paths = []
    for name, arm in (
        ("t2_raw", {"name": "RAW"}),
        ("t2_f", {"name": "FILTER", "filter": {"teacher": "bm25", "k": 5, "level": "positive"}}),
    ):
        cfg = train_config(
            exp_id=name,
            arm=arm,
            evaluation=ev,
            budget={"updates": 6},
            checkpoint={"every": 6, "keep": 1},
        )
        p = tmp_path / f"{name}.yaml"
        p.write_text(yaml.safe_dump(cfg))
        paths.append(str(p))
    over = tmp_path / "over.yaml"
    over.write_text(yaml.safe_dump({"label": "again", "rrf_k": 30}))
    x2 = x2_inputs(str(tmp_path / "x2"))
    args = [
        "run-batch",
        *paths,
        "--cache",
        cache,
        "--feature-table",
        table,
        "--results-root",
        str(tmp_path / "res"),
        "--work-root",
        str(tmp_path / "ck"),
        "--date",
        "2026-10-25",
        "--e1-config",
        x2["e1"],
        "--prep",
        x2["prep"],
        "--e3-cache",
        x2["cache"],
        "--data-root",
        x2["data_root"],
        "--work",
        str(tmp_path / "ew"),
        "--extra-eval",
        str(over),
    ]
    assert main(args) == 0
    out = capsys.readouterr().out
    rec = json.loads(out[out.index("{\n") :])
    assert rec["done"] == paths and rec["skipped"] == []
    for name in ("t2_raw", "t2_f"):
        (rdir,) = (tmp_path / "res" / "rq2" / name).iterdir()
        res = json.loads((rdir / "results.json").read_text())
        assert {"training", "evaluation", "evaluation_again"} <= set(res)
        assert (rdir / "query_rows.csv").exists() and (rdir / "again" / "query_rows.csv").exists()
        assert res["evaluation_again"]["rrf_k"] == 30
    ck = tmp_path / "ck" / "t2_raw"
    assert not ck.exists() or not any(os.scandir(ck))  # the model and checkpoints were dropped
    assert main(args) == 0
    out = capsys.readouterr().out
    assert json.loads(out[out.index("{\n") :])["skipped"] == paths
