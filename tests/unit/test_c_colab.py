"""Offline packaging and durable checkpoint tests; no browser or model execution."""

from __future__ import annotations

import ast
import gzip
import hashlib
import importlib.util
import json
import multiprocessing
import os
import shutil
import stat
import subprocess
import tomllib
import zipfile
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("c_colab_under_test", ROOT / "scripts/c_colab.py")
assert SPEC is not None and SPEC.loader is not None
kit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(kit)


def zipped(
    path: Path,
    contents: dict[str, bytes],
    *,
    manifest_files: dict[str, str] | None = None,
    extra: tuple[str, bytes, int] | None = None,
) -> tuple[Path, str]:
    checksums = {name: hashlib.sha256(blob).hexdigest() for name, blob in contents.items()}
    metadata = {
        "version": kit.VERSION,
        "commit": "a" * 40,
        "tree": "b" * 40,
        "files": checksums if manifest_files is None else manifest_files,
    }
    with zipfile.ZipFile(path, "w") as out:
        for name, blob in contents.items():
            entry = zipfile.ZipInfo(name)
            entry.external_attr = (stat.S_IFREG | 0o644) << 16
            out.writestr(entry, blob)
        out.writestr("c_colab_source.json", json.dumps(metadata).encode())
        if extra is not None:
            name, data, mode = extra
            entry = zipfile.ZipInfo(name)
            entry.external_attr = mode << 16
            out.writestr(entry, data)
    return path, kit.sha(path)


@pytest.mark.parametrize("name", ["../outside", "/absolute", "a\\b", "a/../b", "a//b", "a/./b", ""])
def test_source_names_are_canonical(name: str) -> None:
    with pytest.raises(ValueError):
        kit.safe_name(name)


def test_source_unpack_checks_all_bytes_then_reuses_exact_tree(tmp_path: Path) -> None:
    contents = {"ril/value.py": b"value = 7\n", "settings.json": b"{}\n"}
    source, checksum = zipped(tmp_path / "source.zip", contents)
    target = tmp_path / "workspace"
    metadata = kit.unpack_source(source, target, checksum)
    assert all((target / name).read_bytes() == blob for name, blob in contents.items())
    assert kit.unpack_source(source, target, checksum) == metadata
    (target / "ril/value.py").write_text("value = 8\n")
    with pytest.raises(ValueError):
        kit.unpack_source(source, target, checksum)


def test_wrong_whole_zip_hash_never_creates_destination(tmp_path: Path) -> None:
    source, _ = zipped(tmp_path / "source.zip", {"value.py": b"x=1\n"})
    target = tmp_path / "workspace"
    with pytest.raises(ValueError, match="checksum"):
        kit.unpack_source(source, target, "0" * 64)
    assert not target.exists()


@pytest.mark.parametrize("kind", ["checksum", "missing", "extra", "duplicate", "symlink", "size"])
def test_bad_source_archive_never_publishes_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    contents = {"value.py": b"x=1\n"}
    files = None
    extra = None
    if kind == "checksum":
        files = {"value.py": "0" * 64}
    elif kind == "missing":
        files = {"missing.py": hashlib.sha256(b"missing").hexdigest()}
    elif kind == "extra":
        extra = ("extra.py", b"x=2\n", stat.S_IFREG | 0o644)
    elif kind == "symlink":
        extra = ("link", b"value.py", stat.S_IFLNK | 0o777)
    elif kind == "size":
        monkeypatch.setattr(kit, "MAX_SOURCE_BYTES", 3)
    if kind == "duplicate":
        with pytest.warns(UserWarning, match="Duplicate"):
            source, checksum = zipped(
                tmp_path / "source.zip",
                contents,
                extra=("value.py", b"x=2\n", stat.S_IFREG | 0o644),
            )
    else:
        source, checksum = zipped(
            tmp_path / "source.zip", contents, manifest_files=files, extra=extra
        )
    target = tmp_path / "workspace"
    with pytest.raises(ValueError):
        kit.unpack_source(source, target, checksum)
    assert not target.exists()


def test_source_existing_manifest_tamper_is_refused(tmp_path: Path) -> None:
    source, checksum = zipped(tmp_path / "source.zip", {"value.py": b"x=1\n"})
    target = tmp_path / "workspace"
    kit.unpack_source(source, target, checksum)
    p = target / "c_colab_source.json"
    value = json.loads(p.read_text())
    value["commit"] = "f" * 40
    p.write_text(json.dumps(value))
    with pytest.raises(ValueError):
        kit.unpack_source(source, target, checksum)


@pytest.mark.parametrize("ancestor", [False, True])
def test_source_unpack_refuses_destination_symlinks(tmp_path: Path, ancestor: bool) -> None:
    source, checksum = zipped(tmp_path / "source.zip", {"value.py": b"x=1\n"})
    outside = tmp_path / "outside"
    outside.mkdir()
    link = tmp_path / "link"
    link.symlink_to(outside, target_is_directory=True)
    destination = link / "workspace" if ancestor else link
    with pytest.raises(ValueError):
        kit.unpack_source(source, destination, checksum)
    assert not list(outside.iterdir())


def test_notebook_code_compiles_with_opt_in_real_work() -> None:
    for phase in ("cpu", "gpu"):
        nb = kit.make_notebook("0" * 64, "a" * 40, phase)
        assert nb["nbformat"] == 4
        assert nb["metadata"]["colab"]["name"] == f"ril-{phase}.ipynb"
        flags = {}
        joined = ""
        for cell in nb["cells"]:
            source = "".join(cell["source"])
            joined += source
            if cell["cell_type"] != "code":
                continue
            assert cell["outputs"] == [] and cell["execution_count"] is None
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            flags[target.id] = node.value.value
        assert "SLURM_JOB_ID" not in joined and "RIL_CLUSTER" not in joined
        assert "ghp_" not in joined and "github_pat_" not in joined
        assert "userdata.get('GITHUB_TOKEN')" in joined if phase == "cpu" else True
        expected = (
            ["PLAN_REAL_DATA", "FETCH_REAL_DATA", "RUN_BM25", "PREPARE_DENSE", "RUN_MINING"]
            if phase == "cpu"
            else ["RUN_DENSE_ENCODING"]
        )
        assert all(flags[name] is False for name in expected)
        assert "BUNDLE_SHA" in flags


def test_profile_matches_cpu_lock_and_recorded_dense_versions() -> None:
    raw = (ROOT / "poetry.lock").read_bytes()
    locked = tomllib.loads(raw.decode())
    p = yaml.safe_load((ROOT / "configs/experiments/c_colab_environment.yaml").read_text())
    expected = {
        f"{item['name']}=={item['version']}"
        for item in locked["package"]
        if set(item.get("groups", [])) & {"main", "dev"} and item["name"] != "colorama"
    }
    assert set(p["cpu"]["requirements"]) == expected
    assert p["source_lock_sha256"] == hashlib.sha256(raw).hexdigest()
    assert p["python"] == "3.11.18" and p["uv"] == "0.13.6"
    assert p["build"]["requirements"] == ["poetry-core==2.5.0"]
    gpu = set(p["gpu"]["requirements"])
    assert {
        "torch==2.4.1+cu121",
        "numpy==1.26.4",
        "transformers==4.44.2",
        "sentence-transformers==3.1.1",
        "tokenizers==0.19.1",
    } <= gpu
    assert len(gpu) == 47 and all("==" in pin and ";" not in pin for pin in gpu)
    assert not any(pin.startswith(("torch==", "nvidia-", "triton==")) for pin in expected)
    assert not p["validation"]["colab_install_tested"] and not p["validation"]["cuda_tested"]


def test_package_is_deterministic_and_contains_only_committed_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    (repo / "configs/experiments").mkdir(parents=True)
    (repo / "scripts/c_colab.py").write_text("value = 1\n")
    (repo / ".gitignore").write_text("scratch/\n")
    shutil.copyfile(
        ROOT / "configs/experiments/c_colab_environment.yaml",
        repo / "configs/experiments/c_colab_environment.yaml",
    )
    subprocess.run(["git", "init", "--quiet", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "--quiet", "-m", "fixture"], check=True)
    (repo / "scratch").mkdir()
    (repo / "scratch/not-in-source.txt").write_text("ignored\n")
    monkeypatch.setattr(kit, "__file__", str(repo / "scripts/c_colab.py"))
    first = kit.package(tmp_path / "first")
    second = kit.package(tmp_path / "second")
    assert first == second
    assert (tmp_path / "first/ril-colab-source.zip").read_bytes() == (
        tmp_path / "second/ril-colab-source.zip"
    ).read_bytes()
    with zipfile.ZipFile(tmp_path / "first/ril-colab-source.zip") as z:
        assert not any(n.startswith((".git/", "scratch/")) for n in z.namelist())
    (repo / "scripts/c_colab.py").write_text("value = 2\n")
    with pytest.raises(RuntimeError, match="commit"):
        kit.package(tmp_path / "dirty")


def test_snapshot_roundtrip_ignores_incomplete_and_regenerable_files(tmp_path: Path) -> None:
    work = tmp_path / "work"
    work.mkdir()
    (work / "ready.json").write_text('{"complete":true}\n')
    with gzip.open(work / "pool.jsonl.gz", "wb") as out:
        out.write(b'{"id":1}\n')
    for name in ["writing.json.part", "write.tmp", "cache.lock", ".staging-xyz"]:
        (work / name).write_text("partial")
    (work / "invalid.json").write_text("{")
    (work / "git").mkdir()
    (work / "git/rebuild").write_text("cache")
    store = tmp_path / "store"
    assert kit.snapshot_files(work, store) == 2
    target = tmp_path / "target"
    assert kit.restore_files(store, target) == 2
    assert (target / "ready.json").read_bytes() == (work / "ready.json").read_bytes()
    assert (target / "pool.jsonl.gz").read_bytes() == (work / "pool.jsonl.gz").read_bytes()
    assert sorted(p.name for p in target.iterdir()) == ["pool.jsonl.gz", "ready.json"]


def test_snapshot_does_not_trust_only_unchanged_mtime_and_size(tmp_path: Path) -> None:
    work = tmp_path / "work"
    work.mkdir()
    p = work / "ready.json"
    p.write_text('{"value":1}\n')
    store = tmp_path / "store"
    kit.snapshot_files(work, store)
    before = p.stat()
    p.write_text('{"value":2}\n')
    os.utime(p, ns=(before.st_atime_ns, before.st_mtime_ns))
    kit.snapshot_files(work, store)
    target = tmp_path / "restore"
    kit.restore_files(store, target)
    assert (target / p.name).read_text() == p.read_text()


def test_corrupt_stored_blob_refused_by_repeat_snapshot_and_restore(tmp_path: Path) -> None:
    work = tmp_path / "work"
    work.mkdir()
    (work / "ready.json").write_text("{}\n")
    store = tmp_path / "store"
    kit.snapshot_files(work, store)
    index = json.loads((store / "index.json").read_text())
    blob = store / "blobs" / index["files"]["ready.json"]["sha256"]
    blob.write_bytes(b"bad")
    with pytest.raises(ValueError, match="corrupt"):
        kit.snapshot_files(work, store)
    with pytest.raises(ValueError, match="corrupt"):
        kit.restore_files(store, tmp_path / "target")


@pytest.mark.parametrize("ancestor", [False, True])
def test_restore_refuses_destination_symlinks(tmp_path: Path, ancestor: bool) -> None:
    work = tmp_path / "work"
    (work / "nested").mkdir(parents=True)
    (work / "nested/ready.json").write_text("{}\n")
    store = tmp_path / "store"
    kit.snapshot_files(work, store)
    target = tmp_path / "target"
    target.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    if ancestor:
        (target / "nested").symlink_to(outside, target_is_directory=True)
    else:
        (target / "nested").mkdir()
        (outside / "ready.json").write_text("{}\n")
        (target / "nested/ready.json").symlink_to(outside / "ready.json")
    with pytest.raises(ValueError):
        kit.restore_files(store, target)


def test_interrupted_restore_does_not_publish_partial_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    work = tmp_path / "work"
    work.mkdir()
    payload = b'{"value":1234567}\n'
    (work / "ready.json").write_bytes(payload)
    store = tmp_path / "store"
    kit.snapshot_files(work, store)
    target = tmp_path / "target"
    original = kit.shutil.copyfile

    def interrupted(source: Path, destination: Path) -> None:
        Path(destination).write_bytes(Path(source).read_bytes()[:3])
        raise OSError("recorded interruption")

    monkeypatch.setattr(kit.shutil, "copyfile", interrupted)
    with pytest.raises(OSError):
        kit.restore_files(store, target)
    assert not (target / "ready.json").exists()
    monkeypatch.setattr(kit.shutil, "copyfile", original)
    kit.restore_files(store, target)
    assert (target / "ready.json").read_bytes() == payload


def test_concurrent_snapshots_preserve_both_completed_indexes(tmp_path: Path) -> None:
    works = [tmp_path / "first", tmp_path / "second"]
    for index, work in enumerate(works):
        work.mkdir()
        for n in range(80):
            (work / f"{index}-{n}.json").write_text(json.dumps({"value": n}) + "\n")
    context = multiprocessing.get_context("fork")
    ready = context.Event()
    store = tmp_path / "store"

    def snapshot(work: Path) -> None:
        ready.wait(5)
        kit.snapshot_files(work, store)

    children = [context.Process(target=snapshot, args=(work,)) for work in works]
    try:
        for child in children:
            child.start()
        ready.set()
        for child in children:
            child.join(10)
        assert all(child.exitcode == 0 for child in children)
    finally:
        for child in children:
            if child.is_alive():
                child.terminate()
                child.join()
    target = tmp_path / "restored"
    assert kit.restore_files(store, target) == 160
    assert len(list(target.glob("*.json"))) == 160


def test_existing_source_member_symlink_is_refused(tmp_path: Path) -> None:
    source, checksum = zipped(tmp_path / "source.zip", {"ril/value.py": b"x=1\n"})
    target = tmp_path / "workspace"
    kit.unpack_source(source, target, checksum)
    outside = tmp_path / "external.py"
    outside.write_bytes(b"x=1\n")
    member = target / "ril/value.py"
    member.unlink()
    member.symlink_to(outside)
    with pytest.raises(ValueError):
        kit.unpack_source(source, target, checksum)


def test_checkpoint_index_rejects_noncanonical_paths(tmp_path: Path) -> None:
    work = tmp_path / "work"
    work.mkdir()
    (work / "ready.json").write_text("{}\n")
    store = tmp_path / "store"
    kit.snapshot_files(work, store)
    index = json.loads((store / "index.json").read_text())
    index["files"]["../outside.json"] = index["files"].pop("ready.json")
    (store / "index.json").write_text(json.dumps(index))
    with pytest.raises(ValueError):
        kit.restore_files(store, tmp_path / "target")
    assert not (tmp_path / "outside.json").exists()


def test_checkpoint_missing_blob_is_refused(tmp_path: Path) -> None:
    work = tmp_path / "work"
    work.mkdir()
    (work / "ready.json").write_text("{}\n")
    store = tmp_path / "store"
    kit.snapshot_files(work, store)
    index = json.loads((store / "index.json").read_text())
    (store / "blobs" / index["files"]["ready.json"]["sha256"]).unlink()
    with pytest.raises((ValueError, FileNotFoundError)):
        kit.restore_files(store, tmp_path / "target")


@pytest.mark.parametrize("phase", ["cpu", "gpu"])
def test_setup_retries_restore_after_interruption(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, phase: str
) -> None:
    from ril.evaluation import runtime

    base, source, store = tmp_path / "content", tmp_path / "source", tmp_path / "drive"
    source.mkdir()
    (source / "c_colab_environment.json").write_text(
        json.dumps(
            {
                "python": "3.11.18",
                "uv": "0.13.6",
                "cpu": {"requirements": []},
                "build": {"requirements": []},
            }
        )
    )
    monkeypatch.setattr(kit, "BASE", base)
    monkeypatch.setattr(kit, "configure_environment", lambda *_: {})
    monkeypatch.setattr(kit, "runtime", lambda **_: {})
    monkeypatch.setattr(kit.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(kit, "run", lambda *_, **__: None)
    monkeypatch.setattr(runtime, "issue_colab_receipt", lambda *_: {})
    monkeypatch.setattr(runtime, "runtime_record", lambda: {"runtime": "mock_colab"})
    calls = []

    def restore(*_: object) -> int:
        calls.append("restore")
        if len(calls) == 1:
            raise OSError("recorded interrupted restore")
        return 0

    if phase == "gpu":
        monkeypatch.setattr(kit, "restore_gpu_environment", restore)
    else:
        monkeypatch.setattr(kit, "restore_files", restore)
    with pytest.raises(OSError, match="interrupted"):
        kit.host_setup(source, store, phase)
    assert not (base / "state.json").exists()
    kit.host_setup(source, store, phase)
    assert len(calls) >= 2
    assert json.loads((base / "state.json").read_text())["phase"] == phase
