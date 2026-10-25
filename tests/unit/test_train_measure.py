"""Tests for the training-throughput measurement (stage train_step)."""

from __future__ import annotations

import csv
from pathlib import Path

from ril.bench.train_measure import measure_job, shape_config, workload_id
from ril.training.pool_reader import write_cache
from tests.unit._training_fixtures import synthetic_examples, train_config


def test_measure_rows_per_shape(tmp_path: Path) -> None:
    import yaml

    cfg = train_config()
    cfg_path = tmp_path / "c.yaml"
    cfg_path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    cache = str(tmp_path / "pool.jsonl.gz")
    write_cache(cache, synthetic_examples(repos=2, prs=4))
    out = measure_job(
        str(cfg_path),
        cache,
        [(4, 2, 1, 32), (2, 1, 1, 16)],
        str(tmp_path / "m.json"),
        str(tmp_path / "lat"),
        device="cpu",
        warmup=1,
        timed=2,
    )
    assert [s["status"] for s in out["shapes"]] == ["ok", "ok"]
    assert out["shapes"][0]["workload_id"] == "train-tiny-b4-n2-p1-t32-v1"
    with open(tmp_path / "lat" / "throughput_log.csv", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert [r["stage"] for r in rows] == ["train_step", "train_step"]
    assert int(rows[0]["units"]) == 8 and float(rows[0]["units_per_s"]) > 0
    assert workload_id(shape_config(cfg, 1, 0, 1, 8)) == "train-tiny-b1-n0-p1-t8-v1"
