"""The six E-PILOT-NOISE cells on one noised pool: sizes, hooks, same realisation per seed."""

from __future__ import annotations

import pytest

torch = pytest.importorskip("torch")  # Ada only: the local machine has no torch (Makefile header)
pytestmark = pytest.mark.torch

from typing import Any

import numpy as np

from ril.training import pool_ranks as pr
from ril.training.noise import encode_scores
from ril.training.train_jobs import TrainInputs, apply_noise
from ril.training.training import prepare_arm
from tests.unit._training_fixtures import synthetic_examples

CELLS: dict[str, dict[str, Any]] = {
    "raw": {"name": "RAW"},
    "filter": {"name": "FILTER", "filter": {"teacher": "t", "k": 3, "level": "positive"}},
    "weight": {
        "name": "WEIGHT",
        "weight": {"teacher": "t", "form": "power", "k": 3, "param": 1.0, "floor": 0.1},
    },
    "oracle": {"name": "ORACLE_CLEAN"},
    "sub": {"name": "RAW_SUBSAMPLE", "subsample": {"size": "match_clean", "draw": 0}},
}


def _inputs(tmp_path: Any) -> TrainInputs:
    exs = synthetic_examples(repos=10, prs=30)
    rng = np.random.default_rng(0)
    path = tmp_path / "scores.jsonl"
    for e in exs:
        pr.append_jsonl(
            str(path), {"dir": e.instance_id, "scores": encode_scores(rng.random(len(e.ids)))}
        )
    return TrainInputs("c", exs, None, {}, None, None, {}, {"t": str(path)})


def _cfg(arm: dict[str, Any], rate: float = 0.4, seed: int = 0) -> dict[str, Any]:
    return {"seed": seed, "noise": {"rate": rate}, "arm": arm}


def test_cells_see_one_realisation_and_only_oracle_and_subsample_use_the_ledger(
    tmp_path: Any,
) -> None:
    inp = _inputs(tmp_path)
    digests, kept = set(), {}
    for name, arm in CELLS.items():
        exs, sig, led, summary = apply_noise(_cfg(arm), inp)
        assert summary is not None and summary["rate"] == 0.4
        digests.add(summary["digest"])
        _, k, w, _ = prepare_arm(_cfg(arm), exs, sig, led)
        kept[name] = (k, w, led)
    assert len(digests) == 1
    led = kept["raw"][2]
    assert len(kept["raw"][0]) == len(inp.examples)
    assert len(kept["oracle"][0]) == led.clean_count() == len(kept["sub"][0])
    assert not any(led.is_injected(e.instance_id) for e in kept["oracle"][0])
    assert set(kept["weight"][1]) <= {1.0} | {w for w in kept["weight"][1] if 0.1 <= w <= 1.0}
    assert min(kept["weight"][1]) >= 0.1 and min(kept["weight"][1]) < 1.0
    assert len(kept["filter"][0]) < len(inp.examples)


def test_no_noise_section_is_the_plain_pool(tmp_path: Any) -> None:
    inp = _inputs(tmp_path)
    exs, sig, led, summary = apply_noise({"seed": 0, "arm": {"name": "RAW"}}, inp)
    assert exs is inp.examples and led is None and summary is None and sig == inp.signals
