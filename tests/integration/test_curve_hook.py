"""The step hook of the training loop (learning-curve evaluation): called at the listed update
counts, once each, also across a resumption; it does not change the trained weights.

Synthetic data and the tiny model: a plumbing check, no number here is a result.
"""

from __future__ import annotations

import pytest

torch = pytest.importorskip("torch")  # Ada only: the local machine has no torch (Makefile header)
pytestmark = pytest.mark.torch

from pathlib import Path

from ril.evaluation.curve_eval import save_half, step_dir
from ril.training.encoders import TinyEncoder, TrainEncoder
from ril.training.training import train
from tests.unit._training_fixtures import synthetic_examples, train_config


class Recorder:
    def __init__(self, steps: list[int]) -> None:
        self.steps = frozenset(steps)
        self.calls: list[int] = []
        self.first_weights: dict[int, float] = {}

    def __call__(self, n: int, enc: TrainEncoder) -> None:
        self.calls.append(n)
        self.first_weights[n] = float(next(iter(enc.module.parameters())).detach().sum())


def test_hook_called_at_listed_steps_and_resumes(tmp_path: Path) -> None:
    exs = synthetic_examples()
    cfg = train_config(exp_id="t3_hook", budget={"updates": 12}, checkpoint={"every": 4, "keep": 1})
    common = dict(results_root=str(tmp_path / "r"), date="2026-10-29")
    ref_hook = Recorder([0, 4, 8, 12])
    ref = train(cfg, exs, work_root=str(tmp_path / "w_ref"), hook=ref_hook, **common)  # type: ignore[arg-type]
    assert ref["finished"] and ref_hook.calls == [0, 4, 8, 12]
    assert ref_hook.first_weights[0] != ref_hook.first_weights[12]
    # interrupted after 6 updates, resumed at the checkpoint of update 4: the call at 4 repeats
    # (the hook is idempotent), 0 and the later steps are not repeated or skipped
    part = Recorder([0, 4, 8, 12])
    train(cfg, exs, work_root=str(tmp_path / "w"), stop_after=6, hook=part, **common)  # type: ignore[arg-type]
    assert part.calls == [0, 4]
    rest = Recorder([0, 4, 8, 12])
    done = train(cfg, exs, work_root=str(tmp_path / "w"), hook=rest, **common)  # type: ignore[arg-type]
    assert done["finished"] and rest.calls == [4, 8, 12]
    assert rest.first_weights[12] == ref_hook.first_weights[12]  # the hook changed nothing


def test_save_half_leaves_the_encoder_and_step_dir_names(tmp_path: Path) -> None:
    enc = TinyEncoder(64, 8, 32, seed=1)
    before = float(next(iter(enc.module.parameters())).sum())
    save_half(enc, str(tmp_path / "snap"))
    assert float(next(iter(enc.module.parameters())).sum()) == before
    assert (tmp_path / "snap" / "encoder.json").exists()
    assert step_dir("res", 100).endswith("step_00100")
