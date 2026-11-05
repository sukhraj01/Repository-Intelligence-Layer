"""Package a committed source tree and a browser notebook for bounded Colab development."""

from __future__ import annotations

import argparse
import fcntl
import gzip
import hashlib
import io
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import uuid
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

BASE = Path("/content/ril-colab")
VERSION = "colab-kit/v1"
MAX_SOURCE_BYTES = 128 * 2**20


def sha(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as inp:
        for block in iter(lambda: inp.read(2**20), b""):
            value.update(block)
    return value.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        temporary.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def run(args: list[str], *, cwd: Path | None = None, timeout: int | None = None) -> None:
    subprocess.run(args, cwd=cwd, check=True, timeout=timeout)


def safe_name(name: str) -> None:
    path = PurePosixPath(name)
    if (
        not path.parts
        or path.is_absolute()
        or ".." in path.parts
        or "\\" in name
        or str(path) != name
    ):
        raise ValueError("archive member must be a relative source path")


def no_symlinks(path: Path) -> None:
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("workspace paths must not contain symlinks")


def verified_blob(path: Path, checksum: str, size: int) -> None:
    if len(checksum) != 64 or any(c not in "0123456789abcdef" for c in checksum):
        raise ValueError("invalid persistent blob identity")
    no_symlinks(path)
    stat = path.stat()
    if stat.st_size != size or sha(path) != checksum:
        raise ValueError("persistent checkpoint blob is missing or corrupt")


def unpack_source(archive: Path, destination: Path, expected: str) -> dict[str, Any]:
    """Verify the entire committed-source package before making any source visible."""
    if sha(archive) != expected:
        raise ValueError("source ZIP checksum differs; upload the matching kit")
    no_symlinks(destination)
    with zipfile.ZipFile(archive) as zipped:
        entries = zipped.infolist()
        names = [item.filename for item in entries]
        if len(names) != len(set(names)) or sum(i.file_size for i in entries) > MAX_SOURCE_BYTES:
            raise ValueError("duplicate members or oversized source ZIP")
        for item in entries:
            safe_name(item.filename)
            if (item.external_attr >> 16) & 0o170000 not in (0, 0o100000):
                raise ValueError("source ZIP contains a non-regular member")
        metadata = json.loads(zipped.read("c_colab_source.json"))
        if metadata.get("version") != VERSION or set(names) != {
            "c_colab_source.json",
            *metadata["files"],
        }:
            raise ValueError("source manifest membership differs")
        for name, checksum in metadata["files"].items():
            if hashlib.sha256(zipped.read(name)).hexdigest() != checksum:
                raise ValueError("source manifest checksum differs: " + name)
        if destination.exists():
            for name, checksum in metadata["files"].items():
                no_symlinks(destination / name)
                if not (destination / name).is_file() or sha(destination / name) != checksum:
                    raise ValueError("existing source differs; use a fresh local workspace")
            if (destination / "c_colab_source.json").read_bytes() != zipped.read(
                "c_colab_source.json"
            ):
                raise ValueError("existing source identity differs")
            return metadata
        destination.parent.mkdir(parents=True, exist_ok=True)
        scratch = Path(tempfile.mkdtemp(dir=destination.parent, prefix=".source-"))
        try:
            for item in entries:
                target = scratch / item.filename
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(zipped.read(item))
                target.chmod(0o755 if (item.external_attr >> 16) & 0o111 else 0o644)
            os.replace(scratch, destination)
        finally:
            if scratch.exists():
                shutil.rmtree(scratch)
    return metadata


def profile(root: Path) -> dict[str, Any]:
    return json.loads((root / "c_colab_environment.json").read_text())


def snapshot_files(work: Path, store: Path, paths: list[Path] | None = None) -> int:
    """Copy stable completed files to immutable blobs, publishing the new index last.

    Native filesystem locks remain in /content. Git clones, temporary files and caches that
    can be rebuilt are excluded. The previous completed snapshot remains usable on failure.
    """
    no_symlinks(work)
    no_symlinks(store)
    work.parent.mkdir(parents=True, exist_ok=True)
    # Drive need not implement flock; only native local snapshot writers share this lock.
    with (work.parent / ".snapshot.lock").open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        return _snapshot_files(work, store, paths)


def _snapshot_files(work: Path, store: Path, paths: list[Path] | None = None) -> int:
    store.mkdir(parents=True, exist_ok=True)
    index_path = store / "index.json"
    old = json.loads(index_path.read_text()) if index_path.exists() else {"files": {}}
    index: dict[str, Any] = {"version": VERSION, "files": dict(old["files"])}
    selected = list(work.rglob("*")) if paths is None else paths
    for path in sorted(selected, key=lambda p: (p.suffix != ".gz", str(p))):
        relative = path.relative_to(work)
        no_symlinks(path)
        if not path.is_file() or any(part in {"git", "__pycache__"} for part in relative.parts):
            continue
        if path.name.startswith(".") or path.name.endswith((".tmp", ".part", ".lock")):
            continue
        if ".tmp." in path.name:
            continue
        try:
            stat = path.stat()
            if path.suffix == ".json":
                json.loads(path.read_text())
            if path.suffix == ".gz":
                with gzip.open(path, "rb") as inp:
                    for _ in iter(lambda: inp.read(2**20), b""):
                        pass
            checksum = sha(path)
        except (FileNotFoundError, EOFError, json.JSONDecodeError):
            continue  # An incomplete or atomically replaced source can be retried later.
        blob = store / "blobs" / checksum
        blob.parent.mkdir(parents=True, exist_ok=True)
        if blob.exists():
            verified_blob(blob, checksum, stat.st_size)
        else:
            temporary = blob.with_name(checksum + "." + uuid.uuid4().hex + ".tmp")
            try:
                shutil.copyfile(path, temporary)
                if sha(temporary) != checksum:
                    continue
                os.replace(temporary, blob)
                verified_blob(blob, checksum, stat.st_size)
            finally:
                temporary.unlink(missing_ok=True)
        after = path.stat()
        if (after.st_size, after.st_mtime_ns) != (stat.st_size, stat.st_mtime_ns):
            continue
        index["files"][str(relative)] = {
            "sha256": checksum,
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
        }
    write_json(index_path, index)
    return len(index["files"])


def restore_files(store: Path, work: Path) -> int:
    no_symlinks(store)
    no_symlinks(work)
    index_path = store / "index.json"
    if not index_path.exists():
        return 0
    index = json.loads(index_path.read_text())
    if index.get("version") != VERSION or not isinstance(index.get("files"), dict):
        raise ValueError("invalid persistent checkpoint index")
    for name, item in index["files"].items():
        safe_name(name)
        blob = store / "blobs" / item["sha256"]
        verified_blob(blob, item["sha256"], item["size"])
        target = work / name
        no_symlinks(target)
        if target.exists():
            if not target.is_file() or sha(target) != item["sha256"]:
                raise ValueError("local checkpoint differs; preserve it before a fresh restore")
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + "." + uuid.uuid4().hex + ".tmp")
        try:
            shutil.copyfile(blob, temporary)
            if sha(temporary) != item["sha256"]:
                raise ValueError("checkpoint changed during restore")
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
    return len(index["files"])


def state() -> dict[str, Any]:
    return json.loads((BASE / "state.json").read_text())


def runtime(cpu: bool = True) -> dict[str, Any]:
    from ril.evaluation.runtime import require_runtime

    return require_runtime(cpu_only=cpu, require_gpu=not cpu)


def configure_environment(source: Path, store: Path) -> dict[str, str]:
    metadata = json.loads((source / "c_colab_source.json").read_text())
    values = {
        "RIL_RUNTIME": "colab",
        "RIL_COLAB_RECEIPT": "/content/ril-runtime.json",
        "RIL_COMMIT": metadata["commit"],
        "RIL_HOST_ALIAS": "colab",
        "PYTHONPATH": str(source),
        "HF_HOME": str(store / "model-cache"),
        "UV_CACHE_DIR": str(BASE / "uv-cache"),
        "UV_PYTHON_INSTALL_DIR": str(BASE / "python"),
        "UV_PYTHON_BIN_DIR": str(BASE / "bin"),
        "UV_LINK_MODE": "copy",
        "OMP_NUM_THREADS": "2",
        "OPENBLAS_NUM_THREADS": "2",
    }
    if os.environ.get("SLURM_JOB_ID") or os.environ.get("RIL_CLUSTER"):
        raise RuntimeError("Colab cannot reuse Slurm identifiers")
    os.environ.update(values)
    return values


def host_setup(source: Path, store: Path, phase: str) -> dict[str, Any]:
    """Called by the actual Colab kernel; bootstrap installs no global package overrides."""
    from ril.evaluation.runtime import issue_colab_receipt, read_boot_id, runtime_record

    configure_environment(source, store)
    issue_colab_receipt("/content/ril-runtime.json")
    runtime(cpu=phase == "cpu")
    if platform.machine() != "x86_64":
        raise RuntimeError("this pinned Colab kit currently requires Linux x86_64")
    BASE.mkdir(parents=True, exist_ok=True)
    store.mkdir(parents=True, exist_ok=True)
    old_state = (
        json.loads((BASE / "state.json").read_text()) if (BASE / "state.json").exists() else {}
    )
    boot_id = read_boot_id()
    data = {"source": str(source), "store": str(store), "phase": phase, "boot_id": boot_id}
    write_json(store / "attempts" / (uuid.uuid4().hex + ".json"), runtime_record())
    if phase == "gpu":
        restore_gpu_environment(source, store)
        write_json(BASE / "state.json", data)
        return data
    p = profile(source)
    tools = BASE / "tools"
    uv = tools / "bin/uv"
    if not uv.is_file():
        run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--quiet",
                "--no-deps",
                "--target",
                str(tools),
                "uv==" + p["uv"],
            ]
        )
    run([str(uv), "python", "install", p["python"]])
    run([str(uv), "venv", "--allow-existing", "--python", p["python"], str(BASE / "cpu")])
    requirements = BASE / "cpu-requirements.txt"
    requirements.write_text("\n".join(p["cpu"]["requirements"] + p["build"]["requirements"]) + "\n")
    run(
        [
            str(uv),
            "pip",
            "install",
            "--python",
            str(BASE / "cpu/bin/python"),
            "-r",
            str(requirements),
        ]
    )
    run(
        [
            str(uv),
            "pip",
            "install",
            "--python",
            str(BASE / "cpu/bin/python"),
            "--no-deps",
            "--no-build-isolation",
            "-e",
            str(source),
        ]
    )
    if old_state.get("boot_id") != boot_id:
        restore_files(store / "checkpoints", BASE / "work")
        restore_files(store / "mining-checkpoints", BASE / "work/mining")
    write_json(BASE / "state.json", data)
    return data


def immutable_config(path: Path, value: dict[str, Any]) -> None:
    import yaml

    if path.exists():
        if yaml.safe_load(path.read_text()) != value:
            raise ValueError("existing run configuration differs; choose a new run id")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(value, sort_keys=False))


def prepare_configs(run_id: str = "dev-v1") -> dict[str, str]:
    import yaml

    if not run_id or any(
        c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in run_id
    ):
        raise ValueError("run id must contain only letters, digits, underscore or hyphen")
    info = state()
    source = Path(info["source"])
    work = BASE / "work"
    paths = {}
    for kind in ("bm25", "dense"):
        cfg = yaml.safe_load(
            (source / f"configs/experiments/c_rewrite_{kind}_dev.yaml").read_text()
        )
        cfg["data_root"] = str(work / "raw")
        cfg["output"] = str(work / "runs" / run_id / kind)
        cfg["log_path"] = str(work / "runs" / run_id / f"{kind}-log.json")
        if kind == "dense":
            cfg["retriever"]["cache_root"] = str(work / "index" / run_id)
        path = work / "configs" / f"{run_id}-{kind}.yaml"
        immutable_config(path, cfg)
        paths[kind] = str(path)
    return paths


def checkpoint(paths: list[Path] | None = None) -> int:
    info = state()
    return snapshot_files(BASE / "work", Path(info["store"]) / "checkpoints", paths)


def smoke() -> dict[str, Any]:
    import yaml

    runtime()
    info = state()
    source = Path(info["source"])
    out = BASE / "work" / "smoke" / uuid.uuid4().hex
    cfg = yaml.safe_load((source / "configs/experiments/c_eval_smoke.yaml").read_text())
    cfg.update(output=str(out / "eval"), log_path=str(out / "eval-log.json"))
    cfg["data_root"] = str(source / cfg["data_root"])
    path = out / "eval.yaml"
    immutable_config(path, cfg)
    run([sys.executable, "-m", "ril.evaluation.run", "--config", str(path)], cwd=source)
    paired = yaml.safe_load((source / "configs/agent/c_paired_fixture.yaml").read_text())
    paired["output"] = str(out / "paired")
    pp = out / "paired.yaml"
    immutable_config(pp, paired)
    run(
        [sys.executable, str(source / "scripts/c_paired_runner.py"), "--config", str(pp)],
        cwd=source,
    )
    run(
        [sys.executable, str(source / "scripts/c_paired_runner.py"), "--config", str(pp)],
        cwd=source,
    )
    result = {
        "status": "CPU_SETUP_READY",
        "source_commit": os.environ["RIL_COMMIT"],
        "smoke_output": str(out),
        "real_instances": 0,
        "actual_usd": 0,
    }
    write_json(out / "ready.json", result)
    checkpoint()
    return result


def stage(mode: str, run_id: str) -> dict[str, Any]:
    import yaml

    from ril.evaluation.staging import acquire, build_plan, create_manifest

    runtime()
    paths = prepare_configs(run_id)
    cfg = yaml.safe_load(Path(paths["bm25"]).read_text())
    work = BASE / "work"
    manifest = work / "dataset-manifest.json"
    if not manifest.exists():
        revision = subprocess.check_output(
            [
                "git",
                "ls-remote",
                "https://huggingface.co/datasets/zhangfw123/CORE-Bench",
                "refs/heads/main",
            ],
            text=True,
        ).split()[0]
        write_json(manifest, create_manifest(cfg, revision))
    plan = build_plan(
        cfg, json.loads(manifest.read_text()), max_total_bytes=2 * 2**30, max_file_bytes=512 * 2**20
    )
    write_json(work / "dataset-plan.json", plan)
    checkpoint()
    if mode == "fetch":
        acquire(
            cfg,
            plan,
            on_completed=lambda path, _state: checkpoint(
                [path, Path(cfg["data_root"]) / "provenance.json"]
            ),
        )
        checkpoint()
    return plan


def evaluate(kind: str, run_id: str) -> None:
    runtime()
    info = state()
    source = Path(info["source"])
    configs = prepare_configs(run_id)
    path = Path(configs[kind])
    import yaml

    cfg = yaml.safe_load(path.read_text())
    verify_sources(cfg)
    if Path(cfg["output"]).exists() or Path(cfg["log_path"]).exists():
        raise ValueError("run outputs already exist; use a fresh run id")
    try:
        run([sys.executable, "-m", "ril.evaluation.run", "--config", str(path)], cwd=source)
    finally:
        checkpoint()


def verify_sources(config: dict[str, Any]) -> None:
    from ril.evaluation.staging import build_plan, verify_staged

    manifest = json.loads((BASE / "work/dataset-manifest.json").read_text())
    plan = build_plan(config, manifest, max_total_bytes=2 * 2**30, max_file_bytes=512 * 2**20)
    verify_staged(config, plan)


def prepare_gpu() -> dict[str, Any]:
    """Install and snapshot the pinned GPU environment while no GPU is allocated."""
    runtime()
    info = state()
    source = Path(info["source"])
    store = Path(info["store"])
    p = profile(source)
    uv = BASE / "tools/bin/uv"
    target = BASE / "gpu"
    run([str(uv), "venv", "--allow-existing", "--python", p["python"], str(target)])
    requirements = BASE / "gpu-requirements.txt"
    requirements.write_text("\n".join(p["gpu"]["requirements"] + p["build"]["requirements"]) + "\n")
    run(
        [
            str(uv),
            "pip",
            "install",
            "--python",
            str(target / "bin/python"),
            "-r",
            str(requirements),
            "--extra-index-url",
            p["gpu"]["index_url"],
            "--index-strategy",
            p["gpu"]["index_strategy"],
        ]
    )
    run(
        [
            str(uv),
            "pip",
            "install",
            "--python",
            str(target / "bin/python"),
            "--no-deps",
            "--no-build-isolation",
            "-e",
            str(source),
        ]
    )
    # Only Hub transfer code is imported here, never torch, transformers or the model.
    code = (
        "from ril.retrieval.dense_encoder import ENCODERS; from huggi"
        "ngface_hub import snapshot_download; s=ENCODERS['coderankemb"
        "ed']; print(snapshot_download(s.model_id,revision=s.revision"
        "))"
    )
    run([str(target / "bin/python"), "-c", code], cwd=source)
    archive = store / "gpu-environment.tar.gz"
    temp = archive.with_suffix(".tmp")
    try:
        with tarfile.open(temp, "w:gz", compresslevel=1) as tar:
            for name in ("python", "gpu"):

                def safe_link(item: tarfile.TarInfo) -> tarfile.TarInfo:
                    if item.issym():
                        origin = BASE / item.name
                        dest = (origin.parent / item.linkname).resolve()
                        if not dest.is_relative_to(BASE.resolve()):
                            raise ValueError("environment link escapes the Colab workspace")
                        item.linkname = os.path.relpath(dest, origin.parent)
                    if item.islnk():
                        safe_name(item.linkname)
                    return item

                tar.add(BASE / name, arcname=name, filter=safe_link)
        checksum = sha(temp)
        os.replace(temp, archive)
    finally:
        temp.unlink(missing_ok=True)
    result = {
        "sha256": checksum,
        "profile_sha256": sha(source / "c_colab_environment.json"),
        "architecture": platform.machine(),
        "source_commit": os.environ["RIL_COMMIT"],
    }
    write_json(store / "gpu-environment.json", result)
    checkpoint()
    return result


def restore_gpu_environment(source: Path, store: Path) -> None:
    metadata = json.loads((store / "gpu-environment.json").read_text())
    archive = store / "gpu-environment.tar.gz"
    if (
        metadata["profile_sha256"] != sha(source / "c_colab_environment.json")
        or metadata["architecture"] != platform.machine()
        or metadata["source_commit"] != os.environ["RIL_COMMIT"]
        or sha(archive) != metadata["sha256"]
    ):
        raise ValueError("GPU environment snapshot identity/checksum differs; prepare again on CPU")
    with tarfile.open(archive, "r:gz") as tar:
        for item in tar.getmembers():
            safe_name(item.name)
        tar.extractall(BASE, filter="data")
    restore_files(store / "checkpoints", BASE / "work")


def encode(run_id: str) -> None:
    runtime(cpu=False)
    with (BASE / "encoding-budget.lock").open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        _encode(run_id)


def _encode(run_id: str) -> None:
    runtime(cpu=False)
    info = state()
    source = Path(info["source"])
    store = Path(info["store"])
    configs = prepare_configs(run_id)
    import yaml

    cfg = yaml.safe_load(Path(configs["dense"]).read_text())
    verify_sources(cfg)
    cache = Path(cfg["retriever"]["cache_root"])
    if cache.exists() and any(cache.rglob("*.npz")):
        raise ValueError("preserve the existing dense cache and select a fresh run id")
    budget_path = store / "encoding-budget.json"
    budget = (
        json.loads(budget_path.read_text())
        if budget_path.exists()
        else {"reserved_hours": 0, "attempts": []}
    )
    if budget["reserved_hours"] + 0.5 > 8:
        raise RuntimeError("eight-hour encoding reservation budget exhausted")
    budget["reserved_hours"] += 0.5
    attempt = {
        "id": uuid.uuid4().hex,
        "reserved_hours": 0.5,
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    budget["attempts"].append(attempt)
    write_json(budget_path, budget)
    started = time.monotonic()
    try:
        # One initial batch and a bounded score matrix; full-process sizing is still required.
        run(
            [
                sys.executable,
                str(source / "scripts/c_prepare_rewrite_scores.py"),
                "--config",
                configs["dense"],
                "--batch-size",
                "1",
                "--max-score-bytes",
                str(128 * 2**20),
            ],
            cwd=source,
            timeout=1800,
        )
    finally:
        attempt["elapsed_seconds"] = time.monotonic() - started
        write_json(budget_path, budget)
        checkpoint()


def mining() -> None:
    """Interactive public-data pilot; periodic snapshots omit regenerable bare Git caches."""
    import threading

    runtime()
    if not os.environ.get("GITHUB_TOKEN"):
        raise RuntimeError("configure GITHUB_TOKEN in Colab Secrets first")
    info = state()
    source = Path(info["source"])
    stop = threading.Event()
    failures: list[str] = []

    def mining_checkpoint() -> None:
        snapshot_files(BASE / "work/mining", Path(info["store"]) / "mining-checkpoints")

    def mirror() -> None:
        while not stop.wait(60):
            try:
                mining_checkpoint()
            except Exception as exc:
                failures.append(type(exc).__name__)
                return

    worker = threading.Thread(target=mirror, daemon=True)
    worker.start()
    try:
        run(
            [
                sys.executable,
                str(source / "scripts/c_mine_prs.py"),
                "mine",
                "--live",
                "--config",
                str(source / "configs/experiments/c_raw_pr_pilot.yaml"),
                "--out",
                str(BASE / "work/mining"),
            ],
            cwd=source,
        )
        run(
            [
                sys.executable,
                str(source / "scripts/c_mine_prs.py"),
                "ranks",
                "--out",
                str(BASE / "work/mining"),
            ],
            cwd=source,
        )
    finally:
        stop.set()
        worker.join(timeout=120)
        mining_checkpoint()
    if failures:
        raise RuntimeError("periodic checkpoint failed: " + failures[0])


def report() -> dict[str, Any]:
    from importlib.metadata import version

    from ril.evaluation.runtime import runtime_record

    info = state()
    source = Path(info["source"])
    store = Path(info["store"])
    p = profile(source)
    expected = (
        p["cpu" if info["phase"] == "cpu" else "gpu"]["requirements"] + p["build"]["requirements"]
    )
    installed = {}
    for pin in expected:
        name, required = pin.split("==", 1)
        actual = version(name)
        if actual != required:
            raise RuntimeError("installed package differs from pinned profile: " + name)
        installed[name] = actual
    if platform.python_version() != p["python"]:
        raise RuntimeError("project interpreter differs from pinned Python version")
    cuda = None
    if info["phase"] == "gpu":
        runtime(cpu=False)
        import importlib

        torch = importlib.import_module("torch")
        if not torch.cuda.is_available():
            raise RuntimeError("the restored environment cannot use the assigned CUDA device")
        value = torch.ones((2, 2), device="cuda")
        value @ value
        torch.cuda.synchronize()
        cuda = {
            "torch": torch.__version__,
            "cuda": torch.version.cuda,
            "gpu": torch.cuda.get_device_name(),
            "matmul_passed": True,
        }
    result = {
        "status": "COLAB_READY",
        "phase": info["phase"],
        "source_commit": os.environ["RIL_COMMIT"],
        "runtime": runtime_record(),
        "persistent_store": str(store),
        "environment_profile_sha256": sha(source / "c_colab_environment.json"),
        "model_api_usd": 0,
        "compute_usd": None,
        "live_agent_adapter": "not configured; fixture-only",
        "cross_platform_parity": "not measured",
        "cuda_check": cuda,
        "installed_packages": installed,
    }
    path = store / "reports" / (uuid.uuid4().hex + ".json")
    write_json(path, result)
    return result


def cell(kind: str, text: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "cell_type": kind,
        "metadata": {},
        "source": text.splitlines(keepends=True),
    }
    if kind == "code":
        result.update(execution_count=None, outputs=[])
    return result


def make_notebook(bundle_sha: str, commit: str, phase: str) -> dict[str, Any]:
    intro = f"""# RIL Colab {phase.upper()} setup

Use a **{phase.upper()} runtime**. Run cells top to bottom.
Source commit `{commit}` is checked before execution.
Start with the CPU notebook. Google Drive stores checkpoints.
Temporary environments run under /content.
Real data/model sections are disabled until their resource plans have been inspected.
No paid model service or live repair agent is configured. Free runtimes can end without warning.
"""
    bootstrap = f"""from pathlib import Path
import hashlib, importlib.util, json, os, shutil, sys, zipfile
from google.colab import drive, files

drive.mount('/content/drive')
BUNDLE_SHA = {bundle_sha!r}
STORE = Path('/content/drive/MyDrive/ril-colab/{commit[:12]}')
STORE.mkdir(parents=True, exist_ok=True)
BUNDLE = STORE / 'ril-colab-source.zip'
if not BUNDLE.exists():
    uploaded = files.upload()  # Select ril-colab-source.zip from this kit.
    if len(uploaded) != 1:
        raise ValueError('Upload exactly the source ZIP from this kit')
    raw = next(iter(uploaded.values()))
    if hashlib.sha256(raw).hexdigest() != BUNDLE_SHA:
        raise ValueError('Wrong source ZIP; use the matching kit')
    BUNDLE.write_bytes(raw)
if hashlib.sha256(BUNDLE.read_bytes()).hexdigest() != BUNDLE_SHA:
    raise ValueError('Stored source ZIP is corrupt; restore the original kit file')
# The kit ZIP is checksum-pinned; bootstrap code is verified before it is executed.
with zipfile.ZipFile(BUNDLE) as z:
    bootstrap_source = z.read('scripts/c_colab.py')
    metadata = json.loads(z.read('c_colab_source.json'))
    if hashlib.sha256(bootstrap_source).hexdigest() != metadata['files']['scripts/c_colab.py']:
        raise ValueError('Bootstrap checksum differs')
bootstrap_file = Path('/content/ril-colab-bootstrap.py')
bootstrap_file.write_bytes(bootstrap_source)
spec = importlib.util.spec_from_file_location('ril_colab_bootstrap', bootstrap_file)
kit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kit)
SOURCE = Path('/content/ril-colab/source')
kit.unpack_source(BUNDLE, SOURCE, BUNDLE_SHA)
sys.path.insert(0, str(SOURCE))
kit.host_setup(SOURCE, STORE, {phase!r})
os.chdir(SOURCE)
PY = str(Path('/content/ril-colab/{"cpu" if phase == "cpu" else "gpu"}/bin/python'))
def run_stage(name, *args):
    kit.run([PY, str(SOURCE / 'scripts/c_colab.py'), name, *args], cwd=SOURCE)
print('Pinned source and {phase} environment ready')
"""
    cells = [
        cell("markdown", intro),
        cell(
            "markdown",
            (
                "## 1. Mount Drive, upload the source ZIP once, and prepare t"
                "he environment\nAllow the Google Drive consent dialog. Do not"
                " enter tokens in a code cell.\n"
            ),
        ),
        cell("code", bootstrap),
    ]
    if phase == "cpu":
        cells += [
            cell(
                "markdown",
                (
                    "## 2. Run model-free checks\nExpected final status: CPU_SETUP"
                    "_READY, then COLAB_READY. These are synthetic checks.\n"
                ),
            ),
            cell("code", "run_stage('smoke')\nrun_stage('report')\n"),
            cell(
                "markdown",
                (
                    "## 3. Optional: inspect the real development-data plan\nThe d"
                    "efault remains setup-only. Enable planning to pin the source"
                    " revision and list the 36 required files. The hard transfer "
                    "bounds are 2 GiB total and 512 MiB per file. A bound failure"
                    " requires a reviewed sizing change, not automatic expansion."
                    "\n"
                ),
            ),
            cell(
                "code",
                (
                    "PLAN_REAL_DATA = False\nRUN_ID = 'dev-v1'\nif PLAN_REAL_DATA:\n"
                    "    run_stage('plan', '--run-id', RUN_ID)\n"
                ),
            ),
            cell(
                "markdown",
                (
                    "## 4. Optional: stage sources and run CPU retrieval\nEnable f"
                    "etch only after reading the plan. Enable evaluation only aft"
                    "er a small memory-sizing probe on the runtime; this setup do"
                    "es not claim a measured full-process bound. Choose a new RUN"
                    "_ID for a new recorded experiment.\n"
                ),
            ),
            cell(
                "code",
                (
                    "FETCH_REAL_DATA = False\nRUN_BM25 = False\nif FETCH_REAL_DATA:"
                    "\n    run_stage('fetch', '--run-id', RUN_ID)\nif RUN_BM25:\n   "
                    " run_stage('bm25', '--run-id', RUN_ID)\n"
                ),
            ),
            cell(
                "markdown",
                (
                    "## 5. Optional: prepare dense dependencies and weights on CP"
                    "U\nThis downloads several GiB. It installs a separate Ada-com"
                    "patible GPU environment and saves its verified snapshot and "
                    "pinned model cache to Drive. No model is loaded here. Finish"
                    " this before switching runtime to GPU and opening the GPU no"
                    "tebook.\n"
                ),
            ),
            cell(
                "code", "PREPARE_DENSE = False\nif PREPARE_DENSE:\n    run_stage('prepare-gpu')\n"
            ),
            cell(
                "markdown",
                (
                    "## 6. Optional: real public PR pilot\nAdd a read-only GITHUB_"
                    "TOKEN in Colab Secrets and grant notebook access. The script"
                    " retains the 200-repository/2,000-PR caps. Completed snapsho"
                    "ts are copied every 60 seconds; abrupt VM loss can require r"
                    "eplay since the last completed snapshot. Bare Git caches are"
                    " rebuilt. No full-scale expansion is enabled.\n"
                ),
            ),
            cell(
                "code",
                (
                    "RUN_MINING = False\nif RUN_MINING:\n    from google.colab impo"
                    "rt userdata\n    os.environ['GITHUB_TOKEN'] = userdata.get('G"
                    "ITHUB_TOKEN')\n    try:\n        run_stage('mining')\n    final"
                    "ly:\n        os.environ.pop('GITHUB_TOKEN', None)\n"
                ),
            ),
            cell(
                "markdown",
                (
                    "## 7. Save the readiness report\nShare the final report or a "
                    "non-secret error. Keep source ZIP/notebook together. Use the"
                    " GPU notebook only after CPU model/environment preparation; "
                    "final cross-platform metric parity is still unmeasured.\n"
                ),
            ),
            cell("code", "run_stage('report')\n"),
        ]
    else:
        cells += [
            cell(
                "markdown",
                (
                    "## 2. Inspect the assigned GPU\nThe first cell restores the C"
                    "PU-prepared environment; it does not download packages or we"
                    "ights. A pinned profile/architecture/checksum mismatch stops"
                    ".\n"
                ),
            ),
            cell("code", "kit.run(['nvidia-smi'])\nrun_stage('report')\n"),
            cell(
                "markdown",
                (
                    "## 3. Optional: build paired dense scores\nEnable only after "
                    "data and full-process memory sizing are ready. Each call res"
                    "erves 0.5 of the 8 encoding hours and has a 30-minute subpro"
                    "cess timeout. Interrupted reservations are not refunded. Thi"
                    "s is an encoding budget, not billing or a limit on idle note"
                    "book GPU time.\n"
                ),
            ),
            cell(
                "code",
                (
                    "RUN_DENSE_ENCODING = False\nRUN_ID = 'dev-v1'\nif RUN_DENSE_EN"
                    "CODING:\n    run_stage('encode', '--run-id', RUN_ID)\n"
                ),
            ),
            cell(
                "markdown",
                (
                    "## 4. Save and release the runtime\nReturn to the CPU noteboo"
                    "k for cached-score evaluation. Finish this cell when done to"
                    " release the GPU; Drive snapshots remain.\n"
                ),
            ),
            cell(
                "code",
                (
                    "run_stage('report')\n# Run the following line when finished w"
                    "ith this GPU runtime:\n# from google.colab import runtime; ru"
                    "ntime.unassign()\n"
                ),
            ),
        ]
    if phase == "cpu":
        cells[-2:-2] = [
            cell(
                "markdown",
                "## After GPU encoding: CPU cached-score evaluation\n"
                "Return to a CPU runtime, rerun setup, and keep the same RUN_ID. "
                "Enable this only after its verified dense caches exist.\n",
            ),
            cell(
                "code",
                "RUN_DENSE_EVAL = False\nif RUN_DENSE_EVAL:\n"
                "    run_stage('dense-eval', '--run-id', RUN_ID)\n",
            ),
        ]
    cells.insert(
        1,
        cell(
            "markdown",
            "Use one active Colab VM per Drive work area. "
            "Stop the earlier runtime before switching CPU/GPU notebooks. "
            "Local locks do not coordinate independent VMs.\n",
        ),
    )
    for index, item in enumerate(cells):
        value = f"{phase}:{index}:" + "".join(item["source"])
        item["id"] = hashlib.sha256(value.encode()).hexdigest()[:12]
    return {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "kernelspec": {"name": "python3", "display_name": "Python 3"},
            "colab": {"name": f"ril-{phase}.ipynb", "provenance": []},
        },
        "cells": cells,
    }


def package(output: Path) -> dict[str, Any]:
    import yaml

    root = Path(__file__).resolve().parents[1]
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True).strip():
        raise RuntimeError("commit source changes before packaging")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    if output.exists() and any(output.iterdir()):
        raise ValueError("use an empty kit output directory")
    output.mkdir(parents=True, exist_ok=True)
    with tarfile.open(
        fileobj=io.BytesIO(
            subprocess.check_output(["git", "archive", "--format=tar", commit], cwd=root)
        )
    ) as archive:
        members = archive.getmembers()
        if sum(item.size for item in members) > MAX_SOURCE_BYTES:
            raise ValueError("source tree exceeds package bound")
        contents = {}
        modes = {}
        for item in members:
            if item.isdir():
                continue
            if not item.isfile():
                raise ValueError("only regular committed source files can be packaged")
            safe_name(item.name)
            stream = archive.extractfile(item)
            assert stream is not None
            contents[item.name] = stream.read()
            modes[item.name] = item.mode
    env = yaml.safe_load(contents["configs/experiments/c_colab_environment.yaml"])
    contents["c_colab_environment.json"] = (json.dumps(env, sort_keys=True) + "\n").encode()
    metadata = {
        "version": VERSION,
        "commit": commit,
        "tree": subprocess.check_output(
            ["git", "rev-parse", "HEAD^{tree}"], cwd=root, text=True
        ).strip(),
        "files": {
            name: hashlib.sha256(data).hexdigest() for name, data in sorted(contents.items())
        },
    }
    contents["c_colab_source.json"] = (json.dumps(metadata, sort_keys=True) + "\n").encode()
    bundle = output / "ril-colab-source.zip"
    with zipfile.ZipFile(bundle, "w", compression=zipfile.ZIP_DEFLATED) as zipped:
        for name, data in sorted(contents.items()):
            item = zipfile.ZipInfo(name)
            item.external_attr = (0o100000 | modes.get(name, 0o644)) << 16
            item.compress_type = zipfile.ZIP_DEFLATED
            zipped.writestr(item, data)
    checksum = sha(bundle)
    for phase in ("cpu", "gpu"):
        write_json(output / f"ril-{phase}.ipynb", make_notebook(checksum, commit, phase))
    result = {
        "version": VERSION,
        "source_commit": commit,
        "zip_sha256": checksum,
        "zip_bytes": bundle.stat().st_size,
        "tracked_source_files": len(metadata["files"]) - 1,
        "source_bytes": sum(map(len, contents.values())),
        "colab_execution_tested": False,
    }
    write_json(output / "kit.json", result)
    (output / "START_HERE.txt").write_text(
        "Open https://colab.research.google.com/ and upload ril-cpu.i"
        "pynb. Keep runtime CPU. Run cells from top to bottom; allow "
        "Drive access and upload ril-colab-source.zip when asked. Def"
        "ault cells install the pinned CPU environment and run synthe"
        "tic readiness checks only. Expected final status COLAB_READY"
        ". Optional sections remain disabled until resource preparati"
        "on. For dense work, prepare its environment/weights in the C"
        "PU notebook first, then upload ril-gpu.ipynb in an NVIDIA GP"
        "U runtime. No paid service or live agent is configured.\n"
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "stage",
        choices=[
            "package",
            "smoke",
            "plan",
            "fetch",
            "bm25",
            "dense-eval",
            "prepare-gpu",
            "encode",
            "mining",
            "report",
        ],
    )
    parser.add_argument("--out", type=Path, default=Path("data/processed/c_colab_kit"))
    parser.add_argument("--run-id", default="dev-v1")
    args = parser.parse_args()
    if args.stage == "package":
        result = package(args.out)
    elif args.stage == "smoke":
        result = smoke()
    elif args.stage in ("plan", "fetch"):
        result = stage(args.stage, args.run_id)
    elif args.stage in ("bm25", "dense-eval"):
        evaluate("bm25" if args.stage == "bm25" else "dense", args.run_id)
        result = {"status": "complete"}
    elif args.stage == "prepare-gpu":
        result = prepare_gpu()
    elif args.stage == "encode":
        encode(args.run_id)
        result = {"status": "complete"}
    elif args.stage == "mining":
        mining()
        result = {"status": "complete"}
    else:
        result = report()
    print(json.dumps(result, sort_keys=True))  # noqa: T201


if __name__ == "__main__":
    main()
