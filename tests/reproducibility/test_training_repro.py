"""Same configuration and seed give the same training run, bit for bit; another seed does not."""

from __future__ import annotations

import pytest

torch = pytest.importorskip("torch")  # Ada only: the local machine has no torch (Makefile header)
pytestmark = pytest.mark.torch

from pathlib import Path

from ril.training.training import train
from tests.unit._training_fixtures import synthetic_examples, train_config


def _run(tmp: Path, tag: str, seed: int) -> tuple[str, dict[str, torch.Tensor]]:
    cfg = train_config(seed=seed, budget={"updates": 6})
    rec = train(
        cfg,
        synthetic_examples(repos=2, prs=4),
        results_root=str(tmp / f"r{tag}"),
        work_root=str(tmp / f"w{tag}"),
        date="2026-10-25",
    )
    state = torch.load(Path(rec["final_model"]) / "tiny.pt", weights_only=True)
    return str(rec["plan_sha256"]), state


def test_same_seed_same_run_other_seed_differs(tmp_path: Path) -> None:
    p1, s1 = _run(tmp_path, "a", 5)
    p2, s2 = _run(tmp_path, "b", 5)
    p3, s3 = _run(tmp_path, "c", 6)
    assert p1 == p2 and all(torch.equal(s1[k], s2[k]) for k in s1)
    assert p1 != p3 and not all(torch.equal(s1[k], s3[k]) for k in s1)
