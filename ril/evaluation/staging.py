"""Bounded original/Rewrite dev staging with pinned upstream identities."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import shutil
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from ril.evaluation.runtime import require_runtime

Record = dict[str, Any]
Open = Callable[[urllib.request.Request], Any]
DATASET = "zhangfw123/CORE-Bench"
VERSION = "rewrite-staging/v1"
# Exact dataset directory identities, not caller-provided repository labels alone.
DEV_FOLDERS = {
    ("internetarchive/openlibrary", "SWE-bench_Pro", "instance_internetarchive__openlibrary"): (
        "L2",
        "L3",
    ),
    ("qutebrowser/qutebrowser", "SWE-bench_Pro", "instance_qutebrowser__qutebrowser"): ("L2", "L3"),
    ("ansible/ansible", "SWE-bench_Pro", "instance_ansible__ansible"): ("L2", "L3"),
    ("conan-io/conan", "SWE-bench-Live", "conan"): ("L2",),
    ("deepset-ai/haystack", "SWE-bench-Live", "deepset"): ("L2",),
    ("streamlink/streamlink", "SWE-bench-Live", "streamlink__streamlink"): ("L2",),
}


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=".staging-")
    try:
        with os.fdopen(fd, "w") as out:
            out.write(canonical(value) + "\n")
            out.flush()
            os.fsync(out.fileno())
        os.replace(name, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def require_cluster(*, cpu_only: bool = True) -> None:
    """Compatibility entry for admitted Slurm or explicitly selected Colab execution."""
    require_runtime(cpu_only=cpu_only)


def required_paths(config: Mapping[str, Any]) -> list[str]:
    if config.get("role") != "dev" or config.get("rewrite") is not True:
        raise ValueError("staging is restricted to paired Rewrite dev configurations")
    folders = config.get("folders")
    if not isinstance(folders, list) or not folders:
        raise ValueError("explicit dev folders required")
    paths: set[str] = set()
    for folder in folders:
        if not isinstance(folder, dict) or set(folder) != {"repo", "dataset", "folder", "levels"}:
            raise ValueError("invalid dev folder entry")
        identity = tuple(folder.get(key) for key in ("repo", "dataset", "folder"))
        if any(not isinstance(x, str) for x in identity):
            raise ValueError("invalid dev folder identity")
        levels = folder["levels"]
        if identity not in DEV_FOLDERS or not isinstance(levels, list) or not levels:
            raise ValueError("folder identity is outside the registered dev allowlist")
        for level in levels:
            if level not in DEV_FOLDERS[identity]:
                raise ValueError("level unavailable for registered dev folder")
            prefix = f"LEVEL-{level[1]}/{folder['dataset']}/{folder['folder']}"
            for name in ("corpus.jsonl", "queries.jsonl", "qrels.jsonl"):
                path = f"data/{prefix}/{name}"
                if path in paths:
                    raise ValueError("duplicate dev folder and level")
                paths.add(path)
            paths.add(f"data/Rewrite-{prefix}/queries.jsonl")
    return sorted(paths)


def open_url(request: urllib.request.Request) -> Any:
    return urllib.request.urlopen(request, timeout=60)


def create_manifest(config: Mapping[str, Any], revision: str, *, opener: Open = open_url) -> Record:
    """Read only selected tree directories; revision must be a caller-pinned commit SHA."""
    require_cluster()
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("dataset revision must be a full lowercase commit SHA")
    wanted = required_paths(config)
    entries: dict[str, Record] = {}
    for directory in sorted({str(Path(p).parent) for p in wanted}):
        url = (
            f"https://huggingface.co/api/datasets/{DATASET}/tree/{revision}/{directory}"
            "?recursive=false&limit=1000"
        )
        with opener(urllib.request.Request(url)) as response:
            if response.status != 200 or response.headers.get("Link"):
                raise ValueError("unexpected or paginated selected-directory tree response")
            # Selected directories contain only a handful of metadata entries.
            raw = response.read(2**20 + 1)
            if len(raw) > 2**20:
                raise ValueError("tree metadata exceeds bounded response size")
            page = json.loads(raw)
        if not isinstance(page, list):
            raise ValueError("tree metadata must be a list")
        for entry in page:
            if not isinstance(entry, dict) or entry.get("path") not in wanted:
                continue
            path = entry["path"]
            if path in entries or entry.get("type") != "file":
                raise ValueError("duplicate or invalid selected tree entry")
            lfs = entry.get("lfs") or {}
            entries[path] = {
                "path": path,
                "bytes": entry.get("size"),
                "sha256": lfs.get("oid"),
                "git_blob_sha1": None if lfs else entry.get("oid"),
            }
    result = {
        "version": VERSION,
        "dataset": DATASET,
        "revision": revision,
        "files": list(entries.values()),
    }
    build_plan(config, result, max_total_bytes=2**63, max_file_bytes=2**63)
    return result


def build_plan(
    config: Mapping[str, Any],
    manifest: Mapping[str, Any],
    *,
    max_total_bytes: int,
    max_file_bytes: int,
) -> Record:
    wanted = required_paths(config)
    if manifest.get("version") != VERSION or manifest.get("dataset") != DATASET:
        raise ValueError("unexpected staging manifest identity")
    if not re.fullmatch(r"[0-9a-f]{40}", str(manifest.get("revision", ""))):
        raise ValueError("manifest requires a pinned dataset commit SHA")
    if any(type(n) is not int or n <= 0 for n in (max_total_bytes, max_file_bytes)):
        raise ValueError("positive integer disk bounds required")
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise ValueError("manifest files required")
    found = []
    for item in files:
        if not isinstance(item, dict) or set(item) != {"path", "bytes", "sha256", "git_blob_sha1"}:
            raise ValueError("invalid file manifest entry")
        path, size = item["path"], item["bytes"]
        if path not in wanted or path in found:
            raise ValueError("unexpected or duplicate manifest path")
        found.append(path)
        if type(size) is not int or size <= 0 or size > max_file_bytes:
            raise ValueError("file size exceeds bound or is invalid")
        sha, blob = item["sha256"], item["git_blob_sha1"]
        if not (
            isinstance(sha, str)
            and re.fullmatch(r"[0-9a-f]{64}", sha)
            and blob is None
            or isinstance(blob, str)
            and re.fullmatch(r"[0-9a-f]{40}", blob)
            and sha is None
        ):
            raise ValueError("one valid upstream SHA-256 or Git blob checksum required")
    if sorted(found) != wanted:
        raise ValueError("manifest is missing required original or Rewrite files")
    total = sum(item["bytes"] for item in files)
    if total > max_total_bytes:
        raise ValueError("total download size exceeds explicit bound")
    return {
        "version": VERSION,
        "dataset": DATASET,
        "revision": manifest["revision"],
        "files": sorted(files, key=lambda x: x["path"]),
        "total_bytes": total,
        "required_free_bytes_upper_bound": total + max(item["bytes"] for item in files),
        "memory_note": "streaming transfer; measure index/model/score peak memory separately",
        "manifest_sha256": digest(canonical(manifest).encode()),
    }


def checksums(path: Path) -> Record:
    sha, blob = hashlib.sha256(), hashlib.sha1(usedforsecurity=False)
    blob.update(f"blob {path.stat().st_size}\0".encode())
    rows = 0
    last = b""
    with path.open("rb") as inp:
        for block in iter(lambda: inp.read(2**20), b""):
            sha.update(block)
            blob.update(block)
            rows += block.count(b"\n")
            last = block[-1:]
    rows += int(bool(last) and last != b"\n")
    return {"sha256": sha.hexdigest(), "git_blob_sha1": blob.hexdigest(), "rows": rows}


def verify(path: Path, item: Mapping[str, Any]) -> Record:
    actual = checksums(path)
    if path.stat().st_size != item["bytes"] or any(
        item[key] is not None and actual[key] != item[key] for key in ("sha256", "git_blob_sha1")
    ):
        raise ValueError(f"staged file checksum/size mismatch: {item['path']}")
    return actual


def safe_target(root: Path, relative: str) -> Path:
    target = root / relative
    current = target
    while current != root:
        if current.is_symlink():
            raise ValueError("symlinks are not allowed in staging destinations")
        current = current.parent
    if any(p.is_symlink() for p in (root, *root.parents)):
        raise ValueError("symlink staging root or ancestor is not allowed")
    return target


def download(target: Path, item: Mapping[str, Any], revision: str, *, opener: Open) -> Record:
    if target.exists():
        return verify(target, item)
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".part")
    if partial.is_symlink():
        raise ValueError("symlink partial file is not allowed")
    url = f"https://huggingface.co/datasets/{DATASET}/resolve/{revision}/{item['path']}"
    for attempt in range(3):
        have = partial.stat().st_size if partial.exists() else 0
        size = item["bytes"]
        if have > size:
            raise ValueError("partial file exceeds pinned size")
        if have == size:
            break
        req = urllib.request.Request(
            url, headers={"Range": f"bytes={have}-", "Accept-Encoding": "identity"}
        )
        try:
            with opener(req) as response:
                expected = f"bytes {have}-{size - 1}/{size}"
                if response.status == 206:
                    if response.headers.get("Content-Range") != expected:
                        raise ValueError("range response does not match pinned file and offset")
                elif response.status != 200 or have:
                    raise ValueError("server ignored resume range or returned unexpected status")
                if response.headers.get("Content-Encoding", "identity") != "identity":
                    raise ValueError("encoded range response is unsupported")
                if response.headers.get("Content-Length") != str(size - have):
                    raise ValueError("response length differs from pinned remaining bytes")
                with partial.open("ab") as out:
                    try:
                        while block := response.read(2**20):
                            if out.tell() + len(block) > size:
                                raise ValueError("response exceeds pinned size")
                            out.write(block)
                    finally:
                        out.flush()
                        os.fsync(out.fileno())
            if partial.stat().st_size == size:
                break
        except (OSError, urllib.error.URLError):
            if attempt == 2:
                raise
            time.sleep(2**attempt)
    actual = verify(partial, item)
    os.replace(partial, target)
    directory = os.open(target.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
    return actual


def acquire(
    config: Mapping[str, Any],
    plan: Record,
    *,
    opener: Open = open_url,
    on_completed: Callable[[Path, Record], None] | None = None,
) -> Record:
    """Acquire sources; optional checkpoint callback follows each verified durable publication.

    The callback receives the final file path and current read-only provenance mapping, including
    already completed files on resume. A callback error aborts without undoing durable local data.
    """
    require_cluster()
    # Revalidate even when called directly with a purported plan.
    manifest = {k: plan[k] for k in ("version", "dataset", "revision", "files")}
    checked = build_plan(
        config, manifest, max_total_bytes=plan["total_bytes"], max_file_bytes=plan["total_bytes"]
    )
    root = Path(config["data_root"]).absolute()
    safe_target(root, "provenance.json")
    root.mkdir(parents=True, exist_ok=True)
    lock = safe_target(root, ".c_staging.lock")
    with lock.open("a+") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        state_path = safe_target(root, "provenance.json")
        identity = {k: checked[k] for k in ("version", "dataset", "revision", "files")}
        if state_path.exists():
            state = json.loads(state_path.read_text())
            if not isinstance(state, dict) or not isinstance(state.get("completed"), dict):
                raise ValueError("invalid staging provenance")
            if state.get("identity") != identity:
                raise ValueError("staging source identity changed; use a new data root")
        else:
            # Refuse to adopt a partial file whose pinned identity was never recorded.
            if any(root.rglob("*.part")):
                raise ValueError("partial data without provenance cannot be resumed")
            state = {
                "identity": identity,
                "created_utc": datetime.now(UTC).isoformat(),
                "completed": {},
            }
            atomic_json(state_path, state)
        remaining = []
        for item in checked["files"]:
            target = safe_target(root, item["path"])
            if target.exists():
                verify(target, item)
                continue
            partial = safe_target(root, item["path"] + ".part")
            have = partial.stat().st_size if partial.exists() else 0
            if have > item["bytes"]:
                raise ValueError("partial file exceeds pinned size")
            remaining.append(item["bytes"] - have)
        needed = sum(remaining) + max(remaining, default=0)
        if shutil.disk_usage(root).free < needed:
            raise ValueError("insufficient free disk for remaining transfer and scratch bound")
        for item in checked["files"]:
            path = safe_target(root, item["path"])
            actual = download(path, item, checked["revision"], opener=opener)
            record = {**item, **actual}
            if state["completed"].get(item["path"]) != record:
                state["completed"][item["path"]] = record
                atomic_json(state_path, state)
            if on_completed is not None:
                on_completed(path, state)
        return state


def verify_staged(config: Mapping[str, Any], plan: Record) -> Record:
    """Verify every pinned source and completed provenance record without changing files."""
    root = Path(config["data_root"]).absolute()
    state_path = safe_target(root, "provenance.json")
    state = json.loads(state_path.read_text())
    if not isinstance(state, dict) or not isinstance(state.get("completed"), dict):
        raise ValueError("invalid staging provenance")
    identity = {k: plan[k] for k in ("version", "dataset", "revision", "files")}
    if state.get("identity") != identity:
        raise ValueError("staged source identity differs from the plan")
    if set(state.get("completed", {})) != {item["path"] for item in plan["files"]}:
        raise ValueError("staged acquisition is incomplete")
    for item in plan["files"]:
        actual = verify(safe_target(root, item["path"]), item)
        if state["completed"][item["path"]] != {**item, **actual}:
            raise ValueError("completed provenance does not match verified file")
    return state


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("manifest", "plan", "fetch", "verify"))
    parser.add_argument("--config", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--revision")
    parser.add_argument("--max-total-bytes", type=int, default=2**30)
    parser.add_argument("--max-file-bytes", type=int, default=512 * 2**20)
    parser.add_argument("--plan-output")
    args = parser.parse_args()
    config = yaml.safe_load(Path(args.config).read_text())
    if not isinstance(config, dict):
        raise ValueError("configuration must be a mapping")
    path = Path(args.manifest)
    if args.mode == "manifest":
        if path.exists():
            raise ValueError("manifest already exists; use it or select a new path")
        manifest = create_manifest(config, args.revision or "")
        atomic_json(path, manifest)
    manifest = json.loads(path.read_text())
    if args.revision is not None and manifest.get("revision") != args.revision:
        raise ValueError("manifest revision differs from the requested revision")
    plan = build_plan(
        config, manifest, max_total_bytes=args.max_total_bytes, max_file_bytes=args.max_file_bytes
    )
    if args.plan_output:
        out = Path(args.plan_output)
        if out.exists() and json.loads(out.read_text()) != plan:
            raise ValueError("recorded plan differs; choose a new path")
        if not out.exists():
            atomic_json(out, plan)
    if args.mode == "fetch":
        acquire(config, plan)
    elif args.mode == "verify":
        verify_staged(config, plan)
    print(canonical(plan))  # noqa: T201  # CLI emits machine-readable staging plan JSON.


if __name__ == "__main__":
    main()
