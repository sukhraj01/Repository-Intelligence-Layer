"""Retention switch of the training run (D76): off changes nothing, on reloads to the same model.

Tiny CPU run (512 buckets, 16 dimensions). Tolerance of the half-precision reload:
``RELOAD_TOLERANCE`` (largest absolute difference of any component of a unit-length embedding),
measured on this model and stated here.
"""

from __future__ import annotations

import pytest

torch = pytest.importorskip("torch")  # Ada only: the local machine has no torch (Makefile header)
pytestmark = pytest.mark.torch

import json
from pathlib import Path
from typing import Any

import numpy as np

from ril.training import retention as rt
from ril.training.encoders import TinyEncoder
from ril.training.training import check_comparable, config_hash, train
from tests.unit._training_fixtures import synthetic_examples, train_config

RELOAD_TOLERANCE = 1e-3  # measured 1.3e-4 (max), 3.9e-5 (mean) on Ada CPU, 2026-11-05


def _run(tmp: Path, tag: str, retain_to: str | None = None, **ck: Any) -> dict[str, Any]:
    cfg = train_config(budget={"updates": 6}, checkpoint={"every": 4, "keep": 2, **ck})
    return train(
        cfg,
        synthetic_examples(repos=2, prs=4),
        results_root=str(tmp / f"r{tag}"),
        work_root=str(tmp / f"w{tag}"),
        date="2026-11-05",
        retain_dir=retain_to,
        commit="abc1234",
    )


def _state(rec: dict[str, Any]) -> dict[str, Any]:
    return torch.load(Path(rec["final_model"]) / "tiny.pt", weights_only=True)  # type: ignore[no-any-return]


def test_switch_off_is_bit_identical_and_adds_no_key(tmp_path: Path) -> None:
    absent = _run(tmp_path, "a")
    explicit_off = _run(tmp_path, "b", retain_final=False)
    sa, sb = _state(absent), _state(explicit_off)
    assert all(torch.equal(sa[k], sb[k]) for k in sa)
    assert absent["plan_sha256"] == explicit_off["plan_sha256"]
    assert "retained" not in absent and "retained" not in explicit_off
    keys = {"exp_id", "config_hash", "arm", "finished", "budget", "final_model", "final_dtype"}
    assert keys <= set(absent)
    assert absent["config_hash"] == explicit_off["config_hash"]


def test_switch_on_keeps_hash_weights_and_comparability(tmp_path: Path) -> None:
    off = _run(tmp_path, "off")
    on = _run(tmp_path, "on", str(tmp_path / "keep"), retain_final=True)
    assert on["config_hash"] == off["config_hash"]
    son, soff = _state(on), _state(off)
    assert all(torch.equal(son[k], soff[k]) for k in son)  # retention does not touch the model
    a = train_config(checkpoint={"every": 4, "keep": 2})
    b = train_config(checkpoint={"every": 4, "keep": 2, "retain_final": True})
    assert config_hash(a) == config_hash(b)
    check_comparable([a, b])


def test_reload_matches_in_memory_model_within_tolerance(tmp_path: Path) -> None:
    keep = tmp_path / "keep"
    on = _run(tmp_path, "on", str(keep), retain_final=True)
    folders = rt.list_retained(str(keep))
    assert [Path(f).name for f in folders] == [on["retained"]["folder"]]
    folder = folders[0]
    assert rt.verify_retained(folder) == []
    manifest = json.loads((Path(folder) / rt.MANIFEST_NAME).read_text(encoding="utf-8"))
    assert manifest["commit"] == "abc1234" and manifest["seed"] == 3 and manifest["updates"] == 6
    assert manifest["dtype"] == "float16" and manifest["sha256"] == on["retained"]["sha256"]
    # the half copy is smaller than the float32 final model
    stored = torch.load(Path(folder) / rt.MODEL_SUBDIR / "tiny.pt", weights_only=True)
    assert all(v.dtype == torch.float16 for v in stored.values() if v.is_floating_point())
    reloaded = TinyEncoder.load(str(Path(folder) / rt.MODEL_SUBDIR))
    memory = TinyEncoder.load(on["final_model"])
    texts = [e.query for e in synthetic_examples(repos=2, prs=4)]
    diff = np.abs(reloaded.encode_queries(texts) - memory.encode_queries(texts)).max()
    assert 0.0 < float(diff) <= RELOAD_TOLERANCE


def test_switch_on_without_directory_fails_before_training(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no retention directory"):
        _run(tmp_path, "x", None, retain_final=True)
    assert not (tmp_path / "wx").exists()


def test_rerun_replaces_the_retained_folder(tmp_path: Path) -> None:
    keep = tmp_path / "keep"
    _run(tmp_path, "one", str(keep), retain_final=True)
    _run(tmp_path, "two", str(keep), retain_final=True)
    folders = rt.list_retained(str(keep))
    assert len(folders) == 1 and rt.verify_retained(folders[0]) == []
