"""Recorded-source staging checks; never contact the network or import a model runtime."""

from __future__ import annotations

import hashlib
import io
import json
import shutil
import subprocess
import urllib.request
from pathlib import Path
from typing import Any

import pytest
import yaml

from ril.evaluation import staging as s

REVISION = "a" * 40


class Response(io.BytesIO):
    def __init__(self, body: bytes, status: int = 200, **headers: str) -> None:
        super().__init__(body)
        self.status = status
        self.headers = {"Content-Length": str(len(body)), **headers}


@pytest.fixture
def config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    monkeypatch.setenv("RIL_CLUSTER", "1")
    monkeypatch.setenv("SLURM_JOB_ID", "17")
    for key in ("SLURM_JOB_GPUS", "SLURM_GPUS_ON_NODE", "SLURM_GPUS"):
        monkeypatch.delenv(key, raising=False)
    return {
        "role": "dev",
        "rewrite": True,
        "data_root": str(tmp_path / "raw"),
        "folders": [
            {
                "repo": "conan-io/conan",
                "dataset": "SWE-bench-Live",
                "folder": "conan",
                "levels": ["L2"],
            }
        ],
    }


def recorded(
    config: dict[str, Any], *, git: bool = False
) -> tuple[dict[str, Any], dict[str, bytes]]:
    blobs = {path: (json.dumps({"_id": path}) + "\n").encode() for path in s.required_paths(config)}
    files = []
    for path, blob in blobs.items():
        sha = hashlib.sha256(blob).hexdigest()
        oid = hashlib.sha1(f"blob {len(blob)}\0".encode() + blob, usedforsecurity=False).hexdigest()
        files.append(
            {
                "path": path,
                "bytes": len(blob),
                "sha256": None if git else sha,
                "git_blob_sha1": oid if git else None,
            }
        )
    return {"version": s.VERSION, "dataset": s.DATASET, "revision": REVISION, "files": files}, blobs


def plan(config: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    return s.build_plan(config, manifest, max_total_bytes=100000, max_file_bytes=10000)


def opener_for(blobs: dict[str, bytes], calls: list[tuple[str, int]]) -> s.Open:
    def opener(req: urllib.request.Request) -> Response:
        path = req.full_url.split(f"/resolve/{REVISION}/", 1)[1]
        start = int(str(req.get_header("Range")).split("=")[1].split("-")[0])
        calls.append((path, start))
        data = blobs[path]
        return Response(
            data[start:], 206, **{"Content-Range": f"bytes {start}-{len(data) - 1}/{len(data)}"}
        )

    return opener


def test_exact_full_configs_have36_minimal_files() -> None:
    paths = []
    for kind in ("bm25", "dense"):
        cfg = yaml.safe_load(Path(f"configs/experiments/c_rewrite_{kind}_dev.yaml").read_text())
        paths.append(s.required_paths(cfg))
    assert paths[0] == paths[1]
    assert len(paths[0]) == 36
    assert not any("Verified" in p for p in paths[0])
    assert all(not ("Rewrite-" in p and not p.endswith("queries.jsonl")) for p in paths[0])


@pytest.mark.parametrize(
    "mutation", ["role", "rewrite", "relabeled", "traversal", "level", "duplicate"]
)
def test_selection_refuses_scope_drift(config: dict[str, Any], mutation: str) -> None:
    if mutation == "role":
        config["role"] = "test"
    elif mutation == "rewrite":
        config["rewrite"] = False
    elif mutation == "relabeled":
        config["folders"][0]["dataset"] = "SWE-bench_Verified"
    elif mutation == "traversal":
        config["folders"][0]["folder"] = "../conan"
    elif mutation == "level":
        config["folders"][0]["levels"] = ["L3"]
    else:
        config["folders"] *= 2
    with pytest.raises(ValueError):
        s.required_paths(config)


@pytest.mark.parametrize(
    "mutation",
    [
        "revision",
        "dataset",
        "missing",
        "extra",
        "duplicate",
        "hash",
        "negative",
        "boolean",
        "too_large",
    ],
)
def test_plan_refuses_bad_manifest(config: dict[str, Any], mutation: str) -> None:
    manifest, _ = recorded(config)
    if mutation == "revision":
        manifest["revision"] = "main"
    elif mutation == "dataset":
        manifest["dataset"] = "other/data"
    elif mutation == "missing":
        manifest["files"].pop()
    elif mutation == "extra":
        manifest["files"][0]["path"] = "../outside"
    elif mutation == "duplicate":
        manifest["files"].append(manifest["files"][0])
    elif mutation == "hash":
        manifest["files"][0]["sha256"] = None
    elif mutation == "negative":
        manifest["files"][0]["bytes"] = -1
    elif mutation == "boolean":
        manifest["files"][0]["bytes"] = True
    else:
        manifest["files"][0]["bytes"] = 100001
    with pytest.raises(ValueError):
        plan(config, manifest)


def test_plan_byte_bounds_and_no_network(config: dict[str, Any]) -> None:
    manifest, blobs = recorded(config)
    out = plan(config, manifest)
    total = sum(map(len, blobs.values()))
    assert out["total_bytes"] == total
    assert out["required_free_bytes_upper_bound"] == total + max(map(len, blobs.values()))
    with pytest.raises(ValueError, match="total"):
        s.build_plan(config, manifest, max_total_bytes=total - 1, max_file_bytes=10000)


@pytest.mark.parametrize(
    "key,value",
    [
        ("RIL_CLUSTER", "0"),
        ("SLURM_JOB_ID", ""),
        ("SLURM_JOB_ID", "0"),
        ("SLURM_JOB_GPUS", "0"),
        ("SLURM_GPUS_ON_NODE", "1"),
    ],
)
def test_network_gate_precedes_dispatch(
    config: dict[str, Any], monkeypatch: pytest.MonkeyPatch, key: str, value: str
) -> None:
    monkeypatch.setenv(key, value)

    def forbidden(req: urllib.request.Request) -> Any:
        raise AssertionError("network call escaped gate")

    with pytest.raises(RuntimeError):
        s.create_manifest(config, REVISION, opener=forbidden)
    manifest, _ = recorded(config)
    with pytest.raises(RuntimeError):
        s.acquire(config, plan(config, manifest), opener=forbidden)


@pytest.mark.parametrize("git", [False, True])
def test_fetch_verify_idempotence_low_disk(
    config: dict[str, Any], monkeypatch: pytest.MonkeyPatch, git: bool
) -> None:
    manifest, blobs = recorded(config, git=git)
    calls: list[tuple[str, int]] = []
    p = plan(config, manifest)
    first = s.acquire(config, p, opener=opener_for(blobs, calls))
    assert len(calls) == 4
    before = Path(config["data_root"], "provenance.json").read_bytes()
    monkeypatch.setattr(s.shutil, "disk_usage", lambda _: shutil._ntuple_diskusage(10000, 10000, 0))
    second = s.acquire(config, p, opener=opener_for(blobs, calls))
    assert first == second and len(calls) == 4
    assert Path(config["data_root"], "provenance.json").read_bytes() == before
    assert s.verify_staged(config, p) == first
    assert all(x["rows"] == 1 for x in first["completed"].values())


def test_partial_resume_uses_remaining_space(
    config: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest, blobs = recorded(config)
    p = plan(config, manifest)
    root = Path(config["data_root"])
    root.mkdir()
    identity = {k: p[k] for k in ("version", "dataset", "revision", "files")}
    s.atomic_json(root / "provenance.json", {"identity": identity, "completed": {}})
    remaining = []
    for path, data in blobs.items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        partial = target.with_name(target.name + ".part")
        partial.write_bytes(data[:-1])
        remaining.append(1)
    monkeypatch.setattr(s.shutil, "disk_usage", lambda _: shutil._ntuple_diskusage(10000, 9995, 5))
    calls: list[tuple[str, int]] = []
    s.acquire(config, p, opener=opener_for(blobs, calls))
    assert len(calls) == 4
    assert all(start == len(blobs[path]) - 1 for path, start in calls)


@pytest.mark.parametrize(
    "kind", ["ignored", "range", "length", "encoding", "overflow", "truncated", "checksum"]
)
def test_bad_response_never_becomes_completed(config: dict[str, Any], kind: str) -> None:
    manifest, blobs = recorded(config)
    item = manifest["files"][0]
    target = Path(config["data_root"]) / item["path"]
    raw = blobs[item["path"]]
    target.parent.mkdir(parents=True)
    partial = target.with_name(target.name + ".part")
    if kind == "ignored":
        partial.write_bytes(raw[:1])

    def wrong(req: urllib.request.Request) -> Response:
        if kind == "ignored":
            return Response(raw)
        if kind == "range":
            return Response(raw, 206, **{"Content-Range": "bytes 1-2/3"})
        if kind == "length":
            return Response(raw, 200, **{"Content-Length": "1"})
        if kind == "encoding":
            return Response(raw, 200, **{"Content-Encoding": "gzip"})
        if kind == "overflow":
            return Response(raw + b"x", 200, **{"Content-Length": str(len(raw))})
        if kind == "truncated":
            return Response(raw[:-1], 200, **{"Content-Length": str(len(raw))})
        return Response(b"x" * len(raw))

    with pytest.raises(ValueError):
        s.download(target, item, REVISION, opener=wrong)
    assert not target.exists()


def test_interrupted_stream_resumes_exact_offset(
    config: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest, blobs = recorded(config)
    item = manifest["files"][0]
    target = Path(config["data_root"]) / item["path"]
    raw = blobs[item["path"]]
    dispatched = []

    class Interrupted(Response):
        def read(self, size: int = -1) -> bytes:
            if self.tell():
                raise OSError("recorded connection reset")
            return super().read(3)

    def opener(req: urllib.request.Request) -> Response:
        start = int(str(req.get_header("Range")).split("=")[1].split("-")[0])
        dispatched.append(start)
        if len(dispatched) == 1:
            return Interrupted(raw)
        return Response(
            raw[start:], 206, **{"Content-Range": f"bytes {start}-{len(raw) - 1}/{len(raw)}"}
        )

    monkeypatch.setattr(s.time, "sleep", lambda _: None)
    s.download(target, item, REVISION, opener=opener)
    assert dispatched == [0, 3] and target.read_bytes() == raw


def test_corrupt_completed_and_identity_drift_refused(config: dict[str, Any]) -> None:
    manifest, blobs = recorded(config)
    p = plan(config, manifest)
    calls: list[tuple[str, int]] = []
    s.acquire(config, p, opener=opener_for(blobs, calls))
    path = Path(config["data_root"]) / manifest["files"][0]["path"]
    path.write_bytes(b"x" * path.stat().st_size)
    with pytest.raises(ValueError, match="checksum"):
        s.acquire(config, p, opener=opener_for(blobs, calls))
    assert len(calls) == 4
    manifest["revision"] = "b" * 40
    with pytest.raises(ValueError, match="identity"):
        s.acquire(config, plan(config, manifest), opener=opener_for(blobs, calls))


def test_orphan_partials_symlink_ancestors_and_missing_provenance(
    config: dict[str, Any], tmp_path: Path
) -> None:
    manifest, _ = recorded(config)
    p = plan(config, manifest)
    root = Path(config["data_root"])
    root.mkdir()
    (root / "orphan.part").write_bytes(b"x")
    with pytest.raises(ValueError, match="without provenance"):
        s.acquire(config, p)
    outside = tmp_path / "outside"
    outside.mkdir()
    link = tmp_path / "link"
    link.symlink_to(outside, target_is_directory=True)
    config["data_root"] = str(link / "nested")
    with pytest.raises(ValueError, match="symlink"):
        s.acquire(config, p)
    assert not (outside / "nested").exists()


def test_manifest_pins_exact_selected_metadata(config: dict[str, Any]) -> None:
    manifest, _ = recorded(config)
    wanted = {e["path"]: e for e in manifest["files"]}
    calls = []

    def tree(req: urllib.request.Request) -> Response:
        calls.append(req.full_url)
        assert f"/tree/{REVISION}/" in req.full_url
        directory = req.full_url.split(f"/tree/{REVISION}/", 1)[1].split("?", 1)[0]
        rows = [
            {"path": e["path"], "type": "file", "size": e["bytes"], "lfs": {"oid": e["sha256"]}}
            for e in wanted.values()
            if str(Path(e["path"]).parent) == directory
        ]
        return Response(json.dumps(rows).encode())

    actual = s.create_manifest(config, REVISION, opener=tree)
    assert sorted(actual["files"], key=lambda x: x["path"]) == sorted(
        manifest["files"], key=lambda x: x["path"]
    )
    assert len(calls) == 2


def test_rows_without_final_lf(tmp_path: Path) -> None:
    p = tmp_path / "rows.jsonl"
    p.write_bytes(b"{}\n{}")
    assert s.checksums(p)["rows"] == 2


def test_sbatch_syntax_and_local_refusal() -> None:
    for path in sorted(Path("scripts/ada").glob("c_rewrite_*.sbatch")):
        subprocess.run(["bash", "-n", str(path)], check=True)
        run = subprocess.run(
            ["bash", str(path)], capture_output=True, text=True, env={"PATH": "/usr/bin:/bin"}
        )
        assert run.returncode != 0 and "SLURM_JOB_ID" in run.stderr
        text = path.read_text()
        assert "#SBATCH --partition" not in text and "#SBATCH --account" not in text
        assert "#SBATCH --qos" not in text


@pytest.mark.parametrize("mode", ["plan", "fetch", "verify"])
def test_cli_explicit_revision_drift_refused_before_dispatch(
    config: dict[str, Any], monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mode: str
) -> None:
    manifest, _ = recorded(config)
    cfg_path, manifest_path = tmp_path / "config.yaml", tmp_path / "manifest.json"
    cfg_path.write_text(yaml.safe_dump(config))
    manifest_path.write_text(json.dumps(manifest))

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("changed revision reached a staging operation")

    monkeypatch.setattr(s, "acquire", forbidden)
    monkeypatch.setattr(s, "verify_staged", forbidden)
    monkeypatch.setattr(
        "sys.argv",
        [
            "c_stage_rewrite.py",
            mode,
            "--config",
            str(cfg_path),
            "--manifest",
            str(manifest_path),
            "--revision",
            "b" * 40,
        ],
    )
    with pytest.raises(ValueError, match="manifest revision differs"):
        s.main()
    assert not Path(config["data_root"]).exists()


def test_completion_callback_follows_verified_durable_publication(config: dict[str, Any]) -> None:
    manifest, blobs = recorded(config)
    p = plan(config, manifest)
    calls: list[tuple[str, int]] = []
    completed = []

    def checkpoint(path: Path, state: dict[str, Any]) -> None:
        relative = str(path.relative_to(Path(config["data_root"])))
        assert path.read_bytes() == blobs[relative]
        assert not path.with_name(path.name + ".part").exists()
        assert json.loads(Path(config["data_root"], "provenance.json").read_text()) == state
        assert relative in state["completed"]
        completed.append(relative)

    s.acquire(config, p, opener=opener_for(blobs, calls), on_completed=checkpoint)
    s.acquire(config, p, opener=opener_for(blobs, calls), on_completed=checkpoint)
    assert completed == sorted(blobs) * 2
    assert len(calls) == 4


def test_callback_failure_keeps_verified_source_for_resume(config: dict[str, Any]) -> None:
    manifest, blobs = recorded(config)
    p = plan(config, manifest)
    calls: list[tuple[str, int]] = []

    def unavailable_store(path: Path, state: dict[str, Any]) -> None:
        raise OSError("recorded persistent store unavailable")

    with pytest.raises(OSError, match="persistent store"):
        s.acquire(config, p, opener=opener_for(blobs, calls), on_completed=unavailable_store)
    state = json.loads(Path(config["data_root"], "provenance.json").read_text())
    assert len(state["completed"]) == len(calls) == 1
    s.acquire(config, p, opener=opener_for(blobs, calls))
    assert len(calls) == 4


def test_corrupt_source_never_reaches_checkpoint_callback(config: dict[str, Any]) -> None:
    manifest, _ = recorded(config)
    completed = []

    def corrupt(req: urllib.request.Request) -> Response:
        item = manifest["files"][0]
        return Response(b"x" * item["bytes"])

    with pytest.raises(ValueError, match="checksum"):
        s.acquire(
            config,
            plan(config, manifest),
            opener=corrupt,
            on_completed=lambda *a: completed.append(a),
        )
    assert not completed
