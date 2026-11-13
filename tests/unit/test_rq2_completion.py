"""Completion check of the final RQ2 runs (docs/RQ2_LAUNCH_PLAN.md section 11)."""

from __future__ import annotations

import json
from pathlib import Path

from ril.bench import rq2_completion as rc

H = "a" * 64


def _run(retain: bool = True) -> dict[str, object]:
    return {
        "run_id": "mined_raw_u100_s100",
        "cell": "mined_raw",
        "seed": 100,
        "account": "C",
        "config_hash": H,
        "optimizer_updates": 100,
        "retain_final": retain,
    }


def _write(root: Path, ret: Path, *, updates: int = 100, mhash: str = H) -> None:
    d = root / "rq2f_mined_raw" / f"2026-11-12_{H[:8]}"
    d.mkdir(parents=True)
    training = {
        "config_hash": H,
        "seed": 100,
        "finished": True,
        "teacher_equals_base": False,
        "budget": {"optimizer_updates": updates, "gpu_hours_train_loop": 0.07},
        "retained": {"folder": "f"},
    }
    (d / "results.json").write_text(json.dumps({"training": training}), encoding="utf-8")
    (ret / "f").mkdir(parents=True)
    (ret / "f" / "manifest.json").write_text(json.dumps({"config_hash": mhash}), encoding="utf-8")


def test_complete_run(tmp_path: Path) -> None:
    _write(tmp_path / "r", tmp_path / "m")
    c = rc.check_run(
        _run(), results_root=tmp_path / "r", retained_root=tmp_path / "m", leakage_passed=True
    )
    assert c.complete and c.retained == "present" and c.optimizer_updates == 100


def test_short_run_wrong_manifest_missing_and_leakage_are_reported(tmp_path: Path) -> None:
    _write(tmp_path / "r", tmp_path / "m", updates=60, mhash="b" * 64)
    c = rc.check_run(
        _run(), results_root=tmp_path / "r", retained_root=tmp_path / "m", leakage_passed=False
    )
    assert not c.complete and len(c.problems) == 3
    gone = rc.check_run(
        _run(), results_root=tmp_path / "none", retained_root=None, leakage_passed=True
    )
    assert not gone.complete and gone.result_dir is None


def test_unretained_run_and_exclusion(tmp_path: Path) -> None:
    _write(tmp_path / "r", tmp_path / "m")
    c = rc.check_run(
        _run(False), results_root=tmp_path / "r", retained_root=None, leakage_passed=True
    )
    assert c.complete and c.retained == "not retained by design"
    out = rc.check_all(
        [_run()],
        results_roots={"C": tmp_path / "r"},
        retained_roots={"C": tmp_path / "m"},
        leakage={"C": {"passed": 41, "failed": 0}},
        excluded_run_ids=frozenset({"mined_raw_u100_s100"}),
    )
    assert out == []
