"""Manifest, verification, inventory and archiving plan of retained models (no torch).

``ril.training.retention``; the training-side tests are in ``test_retention_training.py``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from ril.training import retention as rt

CFG = {
    "exp_id": "cell_a",
    "seed": 3,
    "evaluation": {"roles": ["dev"]},
    "checkpoint": {"retain_final": True},
}


def _folder(root: Path, name: str, payload: bytes = b"weights") -> Path:
    folder = root / name
    model = folder / rt.MODEL_SUBDIR
    model.mkdir(parents=True)
    (model / "a.bin").write_bytes(payload)
    (model / "sub").mkdir()
    (model / "sub" / "b.json").write_text("{}", encoding="utf-8")
    manifest = rt.build_manifest(
        CFG,
        config_hash="ab" * 32,
        arm={"name": "RAW"},
        updates_done=100,
        model_dir=str(model),
        dtype="float16",
        commit="deadbeef",
    )
    rt.write_manifest(str(folder), manifest)
    return folder


def test_manifest_fields_and_clean_verification(tmp_path: Path) -> None:
    folder = _folder(tmp_path, "x")
    m = json.loads((folder / rt.MANIFEST_NAME).read_text(encoding="utf-8"))
    assert m["config_hash"] == "ab" * 32 and m["commit"] == "deadbeef" and m["seed"] == 3
    assert m["arm"] == {"name": "RAW"} and m["cell"] == "cell_a" and m["updates"] == 100
    assert m["evaluation_set_ids"] == ["dev"] and m["dtype"] == "float16"
    assert m["bytes"] == len(b"weights") + 2
    assert len(m["sha256"]) == 64
    assert rt.verify_retained(str(folder)) == []


def test_verification_catches_change_removal_and_extra_file(tmp_path: Path) -> None:
    folder = _folder(tmp_path, "x")
    model = folder / rt.MODEL_SUBDIR
    (model / "a.bin").write_bytes(b"weightz")  # same size, other content
    assert any("differs" in p for p in rt.verify_retained(str(folder)))
    (model / "a.bin").write_bytes(b"weights")
    assert rt.verify_retained(str(folder)) == []
    (model / "extra").write_text("x", encoding="utf-8")
    assert any("not in the manifest" in p for p in rt.verify_retained(str(folder)))
    (model / "extra").unlink()
    (model / "sub" / "b.json").unlink()
    assert any("missing" in p for p in rt.verify_retained(str(folder)))


def test_missing_manifest_and_model(tmp_path: Path) -> None:
    (tmp_path / "bare").mkdir()
    assert rt.verify_retained(str(tmp_path / "bare")) == ["manifest.json is missing"]
    folder = _folder(tmp_path, "y")
    for p in sorted((folder / rt.MODEL_SUBDIR).rglob("*"), reverse=True):
        p.unlink() if p.is_file() else p.rmdir()
    (folder / rt.MODEL_SUBDIR).rmdir()
    assert rt.verify_retained(str(folder)) == ["model folder is missing"]


def test_tree_digest_depends_on_names_and_content(tmp_path: Path) -> None:
    a = rt.tree_files(str(_folder(tmp_path, "a", b"one") / rt.MODEL_SUBDIR))
    b = rt.tree_files(str(_folder(tmp_path, "b", b"two") / rt.MODEL_SUBDIR))
    assert rt.tree_digest(a) != rt.tree_digest(b)
    assert rt.tree_digest(a) == rt.tree_digest(list(a))


def test_inventory_and_plan_skip_failed_folders(tmp_path: Path) -> None:
    good = _folder(tmp_path, "good")
    bad = _folder(tmp_path, "bad")
    (bad / rt.MODEL_SUBDIR / "a.bin").write_bytes(b"corrupt")
    (tmp_path / "not_a_model").mkdir()
    rows = rt.inventory(str(tmp_path))
    assert [r["folder"] for r in rows] == ["bad", "good"]
    assert [r["status"] == "ok" for r in rows] == [False, True]
    plan = "\n".join(rt.archive_plan(rows, source=str(tmp_path), dest_alias=None, dest_dir="d"))
    assert "folders to copy: 1" in plan and "SKIP  bad" in plan and "not set" in plan
    assert good.name in plan


def test_retain_dir_checks(tmp_path: Path) -> None:
    assert rt.retain_dir_from_env({}) is None
    assert rt.retain_dir_from_env({"RETAIN_DIR": "  "}) is None
    assert rt.retain_dir_from_env({"RETAIN_DIR": "/x/y"}) == "/x/y"
    with pytest.raises(ValueError, match="absolute"):
        rt.check_retain_dir("relative/dir")
    repo = tmp_path / "work"
    (repo / ".git").mkdir(parents=True)
    with pytest.raises(ValueError, match="git work tree"):
        rt.check_retain_dir(str(repo / "models"))
    assert rt.check_retain_dir(str(tmp_path / "outside")) == os.path.realpath(
        str(tmp_path / "outside")
    )


def test_requested_flag_default_off() -> None:
    assert rt.retain_requested({"checkpoint": {"every": 1}}) is False
    assert rt.retain_requested({"checkpoint": {"retain_final": True}}) is True
