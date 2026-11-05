"""Recorded runtime proofs exercise admission without remote calls or model imports."""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from ril.data_mining.ranks import dense_audit_scores
from ril.evaluation import rewrite_cache, runtime, staging


@pytest.fixture
def admitted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    for key in list(os.environ):
        if key.startswith("SLURM") or key in {"RIL_RUNTIME", "RIL_CLUSTER", "RIL_COLAB_RECEIPT"}:
            monkeypatch.delenv(key, raising=False)
    root = tmp_path / "content"
    root.mkdir()
    boot = tmp_path / "boot_id"
    boot.write_text("boot-current\n")
    proof: dict[str, Any] = {
        "boot_id": "boot-current",
        "host_python": str(Path(sys.executable).resolve()),
        "colab_module": "/usr/local/lib/python3.12/dist-packages/google/colab/__init__.py",
        "gpus": [],
    }
    monkeypatch.setattr(runtime, "CONTENT_ROOT", root)
    monkeypatch.setattr(runtime, "BOOT_ID", boot)
    monkeypatch.setattr(runtime, "_probe_colab", lambda _: copy.deepcopy(proof))
    receipt = root / "runtime.json"
    runtime.issue_colab_receipt(receipt)
    monkeypatch.setenv("RIL_RUNTIME", "colab")
    monkeypatch.setenv("RIL_COLAB_RECEIPT", str(receipt))
    return {"root": root, "boot": boot, "proof": proof, "receipt": receipt}


def test_current_host_receipt_admits_cpu_venv_and_safe_record(
    admitted: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "secret-must-not-appear")
    monkeypatch.setenv("UNRELATED_PASSWORD", "another-secret")
    info = runtime.require_runtime()
    assert info["runtime"] == "colab" and info["gpu_allocated"] is False
    staging.require_cluster()
    result = runtime.runtime_record()
    assert result["host_alias"] == "colab" and len(result["proof_sha256"]) == 64
    assert "secret" not in json.dumps(result)
    assert "GITHUB_TOKEN" not in json.dumps(result)
    assert "SLURM_JOB_ID" not in os.environ and "RIL_CLUSTER" not in os.environ


@pytest.mark.parametrize("field", ["boot_id", "host_python", "colab_module", "gpus"])
def test_stale_or_changed_host_proof_refused(admitted: dict[str, Any], field: str) -> None:
    proof = admitted["proof"]
    proof[field] = ["T4, 15360 MiB, 550"] if field == "gpus" else "changed"
    with pytest.raises(RuntimeError, match="changed"):
        runtime.require_runtime()


def test_runtime_restart_refuses_old_receipt(admitted: dict[str, Any]) -> None:
    admitted["boot"].write_text("new-vm")
    with pytest.raises(RuntimeError, match="VM changed"):
        runtime.require_runtime()


@pytest.mark.parametrize("boot_contents", [None, "", " \n"])
def test_unavailable_boot_id_refuses_saved_receipt_and_issuance(
    admitted: dict[str, Any], monkeypatch: pytest.MonkeyPatch, boot_contents: str | None
) -> None:
    boot = admitted["boot"]
    if boot_contents is None:
        boot.unlink()
    else:
        boot.write_text(boot_contents)

    def forbidden_probe(_: str) -> dict[str, Any]:
        raise AssertionError("missing VM identity must fail before host probing")

    monkeypatch.setattr(runtime, "_probe_colab", forbidden_probe)
    # A previously valid receipt cannot supply the missing current host identity.
    with pytest.raises(RuntimeError, match="boot id unavailable"):
        runtime.require_runtime()
    fresh_receipt = admitted["root"] / "fresh.json"
    with pytest.raises(RuntimeError, match="boot id unavailable"):
        runtime.issue_colab_receipt(fresh_receipt)
    assert not fresh_receipt.exists()


def test_visible_gpu_refuses_cpu_work_even_when_cuda_is_masked(
    admitted: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    admitted["proof"]["gpus"] = ["T4, 15360 MiB, 550"]
    runtime.issue_colab_receipt(admitted["receipt"])
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "")
    with pytest.raises(RuntimeError, match="CPU runtime"):
        runtime.require_runtime()
    assert runtime.require_runtime(cpu_only=False, require_gpu=True)["gpu_allocated"]


def test_gpu_work_refuses_cpu_runtime_before_any_model_import(admitted: dict[str, Any]) -> None:
    with pytest.raises(RuntimeError, match="NVIDIA GPU"):
        runtime.require_runtime(cpu_only=False, require_gpu=True)
    with pytest.raises(ValueError, match="NVIDIA GPU"):
        dense_audit_scores(admitted["root"] / "absent-real-pilot")


def test_dense_real_pilot_guard_stays_before_teacher_import(admitted: dict[str, Any]) -> None:
    admitted["proof"]["gpus"] = ["T4, 15360 MiB, 550"]
    runtime.issue_colab_receipt(admitted["receipt"])
    pilot = admitted["root"] / "pilot"
    pilot.mkdir()
    (pilot / "provenance.json").write_text('{"source_kind":"synthetic_recorded_responses"}')
    with pytest.raises(ValueError, match="real pilot"):
        dense_audit_scores(pilot)
    assert not (pilot / "dense").exists()


@pytest.mark.parametrize("value", [None, "not-json", "{}", '{"runtime":"other"}'])
def test_missing_or_malformed_receipt_refused(admitted: dict[str, Any], value: str | None) -> None:
    path = admitted["receipt"]
    if value is None:
        path.unlink()
    else:
        path.write_text(value)
    with pytest.raises(RuntimeError, match="receipt"):
        runtime.require_runtime()


@pytest.mark.parametrize("key,value", [("SLURM_JOB_ID", "17"), ("RIL_CLUSTER", "1")])
def test_colab_cannot_relabel_slurm(
    admitted: dict[str, Any], monkeypatch: pytest.MonkeyPatch, key: str, value: str
) -> None:
    monkeypatch.setenv(key, value)
    with pytest.raises(RuntimeError, match="spoof"):
        runtime.require_runtime()


def test_receipt_cannot_be_loaded_outside_colab_root(
    admitted: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    outside = tmp_path / "receipt.json"
    outside.write_bytes(admitted["receipt"].read_bytes())
    monkeypatch.setenv("RIL_COLAB_RECEIPT", str(outside))
    with pytest.raises(RuntimeError, match="receipt"):
        runtime.require_runtime()
    with pytest.raises(ValueError, match="beneath /content"):
        runtime.issue_colab_receipt(outside)


def test_receipt_issuance_refuses_local_host(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(runtime, "CONTENT_ROOT", tmp_path / "absent")
    with pytest.raises(RuntimeError, match="Colab host"):
        runtime.issue_colab_receipt(tmp_path / "receipt.json")


@pytest.mark.parametrize(
    "env",
    [
        {},
        {"RIL_RUNTIME": "local"},
        {"RIL_CLUSTER": "1", "SLURM_JOB_ID": "fake"},
        {"RIL_CLUSTER": "1", "SLURM_JOB_ID": "0"},
        {"RIL_CLUSTER": "0", "SLURM_JOB_ID": "17"},
        {"RIL_RUNTIME": "colab"},
    ],
)
def test_flags_alone_do_not_admit_runtime(env: dict[str, str]) -> None:
    with pytest.raises(RuntimeError):
        runtime.require_runtime(environ=env)


def test_existing_slurm_cpu_and_gpu_behavior() -> None:
    env = {"RIL_CLUSTER": "1", "SLURM_JOB_ID": "17"}
    assert runtime.require_runtime(environ=env)["runtime"] == "slurm"
    with pytest.raises(RuntimeError, match="GPU allocation"):
        runtime.require_runtime(environ=env, cpu_only=False, require_gpu=True)
    env["SLURM_JOB_GPUS"] = "0"
    with pytest.raises(RuntimeError, match="CPU-only"):
        runtime.require_runtime(environ=env)
    assert runtime.require_runtime(environ=env, cpu_only=False, require_gpu=True)["gpu_allocated"]
    with pytest.raises(ValueError, match="mutually exclusive"):
        runtime.require_runtime(environ=env, require_gpu=True)


def test_encoding_gate_precedes_model_import(
    admitted: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "argv", ["rewrite_cache", "--config", "absent.yaml"])
    with pytest.raises(RuntimeError, match="NVIDIA GPU"):
        rewrite_cache.main()
    assert "torch" not in sys.modules


def test_colab_fetch_gate_precedes_transport(
    admitted: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    admitted["proof"]["gpus"] = ["T4, 15360 MiB, 550"]
    runtime.issue_colab_receipt(admitted["receipt"])

    def forbidden(*args: Any) -> Any:
        raise AssertionError("transport must not start on an attached GPU")

    with pytest.raises(RuntimeError, match="CPU runtime"):
        staging.create_manifest({}, "a" * 40, opener=forbidden)


def test_cli_live_gate_precedes_token_or_transport(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = {
        "PATH": os.environ["PATH"],
        "RIL_RUNTIME": "colab",
        "GITHUB_TOKEN": "unprinted-test-value",
    }
    result = subprocess.run(
        [
            sys.executable,
            "scripts/c_mine_prs.py",
            "mine",
            "--live",
            "--config",
            "absent.yaml",
            "--out",
            str(tmp_path / "raw"),
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode != 0 and "receipt" in result.stderr
    assert "unprinted-test-value" not in result.stderr
    assert not (tmp_path / "raw").exists()


def test_probe_validates_schema_and_hides_host_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        runtime.subprocess, "run", lambda *a, **kw: SimpleNamespace(stdout='{"bad":"proof"}')
    )
    with pytest.raises(RuntimeError, match="invalid Colab"):
        runtime._probe_colab(sys.executable)
    monkeypatch.setattr(
        runtime.subprocess, "run", lambda *a, **kw: SimpleNamespace(stdout="x" * 20000)
    )
    with pytest.raises(RuntimeError, match="host verification failed"):
        runtime._probe_colab(sys.executable)


def test_archive_provenance_requires_pinned_original_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from ril.data_mining.c_miner import source_checkout

    monkeypatch.delenv("RIL_COMMIT", raising=False)
    with pytest.raises(ValueError, match="full RIL_COMMIT"):
        source_checkout(tmp_path)
    monkeypatch.setenv("RIL_COMMIT", "latest")
    with pytest.raises(ValueError, match="full RIL_COMMIT"):
        source_checkout(tmp_path)
    monkeypatch.setenv("RIL_COMMIT", "a" * 40)
    proof = source_checkout(tmp_path)
    assert proof == {
        "git_hash": "a" * 40,
        "git_dirty": True,
        "source_control": "archive_without_git",
        "git_status": "unavailable",
    }


def test_recorded_mining_from_source_archive_without_git(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import shutil

    from ril.data_mining.recording import synthetic_recording

    root = Path.cwd()
    archive = tmp_path / "archive"
    archive.mkdir()
    shutil.copytree(root / "ril", archive / "ril", ignore=shutil.ignore_patterns("__pycache__"))
    (archive / "scripts").mkdir()
    shutil.copyfile(root / "scripts/c_mine_prs.py", archive / "scripts/c_mine_prs.py")
    recording = tmp_path / "recording.json"
    recording.write_text(json.dumps(synthetic_recording(3)))
    output = tmp_path / "mined"
    env = {**os.environ, "RIL_COMMIT": "a" * 40}
    subprocess.run(
        [
            sys.executable,
            "scripts/c_mine_prs.py",
            "mine",
            "--recording",
            str(recording),
            "--out",
            str(output),
        ],
        cwd=archive,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    provenance = json.loads((output / "provenance.json").read_text())
    assert provenance["git_hash"] == "a" * 40
    assert provenance["git_dirty"] is True and provenance["git_status"] == "unavailable"
    assert provenance["source_control"] == "archive_without_git"
    assert provenance["source_kind"] == "synthetic_recorded_responses"
    assert "ril/evaluation/runtime.py" in provenance["implementation_sources"]
