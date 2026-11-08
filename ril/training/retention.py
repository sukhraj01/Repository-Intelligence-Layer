"""Retention of final models: a half-precision copy plus a manifest, outside the repository.

Implements ``docs/RQ2_PROTOCOL.md`` section 11 (O9, D76): the final models that feed RQ3 and the
report are kept, in half precision, with enough metadata to check them later. Checkpoints with
optimizer state stay in node-local space and are removed at job exit (``docs/COMPUTE.md``); this
module only handles the finished model.

The switch is the configuration key ``checkpoint.retain_final`` (default off) and the target is the
job environment variable ``RETAIN_DIR``. The key is a storage option, not an experiment parameter:
it is left out of the configuration hash and of the held-identical view, so a run with it on has
the same hash, the same result directory and the same trained weights as one with it off.

Nothing here imports torch: the writing of the model itself is done by the caller
(``ril.training.training``), this module computes the manifest and checks it.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping
from typing import Any

RETAIN_ENV = "RETAIN_DIR"
MANIFEST_NAME = "manifest.json"
MODEL_SUBDIR = "model"
MANIFEST_VERSION = "retention/v1"
Record = dict[str, Any]


def retain_requested(cfg: Mapping[str, Any]) -> bool:
    """Whether the configuration asks for the final model to be retained."""
    return bool(cfg["checkpoint"].get("retain_final", False))


def retain_dir_from_env(env: Mapping[str, str] | None = None) -> str | None:
    """The retention directory of the job environment, or ``None`` if unset or empty."""
    value = (os.environ if env is None else env).get(RETAIN_ENV, "").strip()
    return value or None


def check_retain_dir(path: str) -> str:
    """Return the absolute retention directory; refuse a relative path or one inside a git tree.

    Why: retained models are large binary files that must never reach a tracked folder, and a
    relative path would depend on the working directory of the job.
    """
    if not os.path.isabs(path):
        raise ValueError(f"{RETAIN_ENV} must be an absolute path, got {path!r}")
    probe = os.path.realpath(path)
    while True:
        if os.path.exists(os.path.join(probe, ".git")):
            raise ValueError(f"{RETAIN_ENV} lies inside a git work tree ({probe})")
        parent = os.path.dirname(probe)
        if parent == probe:
            break
        probe = parent
    return os.path.realpath(path)


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def tree_files(model_dir: str) -> list[Record]:
    """Every file under ``model_dir``: relative path, size, SHA-256; sorted by path."""
    rows: list[Record] = []
    for base, _dirs, names in os.walk(model_dir):
        for name in names:
            full = os.path.join(base, name)
            rows.append(
                {
                    "path": os.path.relpath(full, model_dir).replace(os.sep, "/"),
                    "bytes": os.path.getsize(full),
                    "sha256": _sha256_file(full),
                }
            )
    return sorted(rows, key=lambda r: str(r["path"]))


def tree_digest(files: list[Record]) -> str:
    """SHA-256 over the sorted ``path``, ``sha256`` lines: one hash for the whole model folder."""
    h = hashlib.sha256()
    for r in files:
        h.update(f"{r['path']}\0{r['sha256']}\n".encode())
    return h.hexdigest()


def evaluation_set_ids(cfg: Mapping[str, Any]) -> list[str]:
    """Evaluation sets the run is meant to be scored on: ``evaluation.set_ids`` or the roles."""
    ev = cfg.get("evaluation") or {}
    ids = ev.get("set_ids") or ev.get("roles") or []
    return [str(x) for x in ids]


def build_manifest(
    cfg: Mapping[str, Any],
    *,
    config_hash: str,
    arm: Mapping[str, Any],
    updates_done: int,
    model_dir: str,
    dtype: str,
    commit: str | None,
) -> Record:
    """Manifest of a retained model: what produced it and what it consists of."""
    files = tree_files(model_dir)
    return {
        "version": MANIFEST_VERSION,
        "config_hash": config_hash,
        "commit": commit or "unknown",
        "seed": int(cfg["seed"]),
        "arm": dict(arm),
        "cell": str(cfg["exp_id"]),
        "updates": int(updates_done),
        "evaluation_set_ids": evaluation_set_ids(cfg),
        "dtype": dtype,
        "sha256": tree_digest(files),
        "bytes": sum(int(r["bytes"]) for r in files),
        "files": files,
    }


def write_manifest(retained_dir: str, manifest: Mapping[str, Any]) -> str:
    """Write ``manifest.json`` next to the model folder (atomically); returns its path."""
    path = os.path.join(retained_dir, MANIFEST_NAME)
    with open(f"{path}.tmp", "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=1, sort_keys=True, default=str)
        handle.write("\n")
    os.replace(f"{path}.tmp", path)
    return path


def verify_retained(retained_dir: str) -> list[str]:
    """Problems found in one retained folder (empty list = the manifest matches the files)."""
    path = os.path.join(retained_dir, MANIFEST_NAME)
    if not os.path.isfile(path):
        return ["manifest.json is missing"]
    with open(path, encoding="utf-8") as handle:
        manifest = json.load(handle)
    model_dir = os.path.join(retained_dir, MODEL_SUBDIR)
    if not os.path.isdir(model_dir):
        return ["model folder is missing"]
    problems: list[str] = []
    files = tree_files(model_dir)
    listed = {str(r["path"]): r for r in manifest.get("files", [])}
    actual = {str(r["path"]): r for r in files}
    for p in sorted(set(listed) - set(actual)):
        problems.append(f"listed file missing: {p}")
    for p in sorted(set(actual) - set(listed)):
        problems.append(f"file not in the manifest: {p}")
    for p in sorted(set(listed) & set(actual)):
        if listed[p]["sha256"] != actual[p]["sha256"] or listed[p]["bytes"] != actual[p]["bytes"]:
            problems.append(f"file differs from the manifest: {p}")
    if not problems and tree_digest(files) != manifest.get("sha256"):
        problems.append("folder digest differs from the manifest")
    if not problems and sum(int(r["bytes"]) for r in files) != manifest.get("bytes"):
        problems.append("byte size differs from the manifest")
    return problems


def list_retained(root: str) -> list[str]:
    """Folders under ``root`` that hold a manifest, sorted."""
    out = [
        os.path.join(root, name)
        for name in sorted(os.listdir(root))
        if os.path.isfile(os.path.join(root, name, MANIFEST_NAME))
    ]
    return out


def inventory(root: str) -> list[Record]:
    """One row per retained folder: name, cell, seed, size, manifest status.

    ``status`` is ``ok`` when every file matches the manifest, else the first problem found.
    """
    rows: list[Record] = []
    for folder in list_retained(root):
        with open(os.path.join(folder, MANIFEST_NAME), encoding="utf-8") as handle:
            m = json.load(handle)
        problems = verify_retained(folder)
        rows.append(
            {
                "folder": os.path.basename(folder),
                "cell": m.get("cell"),
                "seed": m.get("seed"),
                "arm": (m.get("arm") or {}).get("name"),
                "updates": m.get("updates"),
                "dtype": m.get("dtype"),
                "bytes": m.get("bytes"),
                "sha256": m.get("sha256"),
                "status": "ok" if not problems else problems[0],
            }
        )
    return rows


def archive_plan(
    rows: list[Record], *, source: str, dest_alias: str | None, dest_dir: str
) -> list[str]:
    """Plain-text plan for archiving verified folders; nothing is executed.

    Folders whose manifest check failed are listed as skipped. The copy itself is a numbered
    local script that takes the destination alias as its argument (checksums compared, no deletion).
    """
    ok = [r for r in rows if r["status"] == "ok"]
    bad = [r for r in rows if r["status"] != "ok"]
    total = sum(int(r["bytes"] or 0) for r in ok)
    lines = [
        f"source: {source}",
        f"destination: {dest_alias or '<alias for the archive account: not set>'}:{dest_dir}",
        f"folders to copy: {len(ok)}   total: {total / 1e6:.1f} MB ({total} bytes)",
    ]
    lines += [f"  copy  {r['folder']}  {int(r['bytes'] or 0) / 1e6:.1f} MB" for r in ok]
    lines += [f"  SKIP  {r['folder']}  ({r['status']})" for r in bad]
    lines.append("each copy is compared by checksum on the destination; nothing is deleted")
    return lines
