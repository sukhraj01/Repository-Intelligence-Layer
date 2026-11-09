"""Preparation of a finished mined store for training: selection, snapshot, shards, drop list.

Implements ``docs/RQ2_LAUNCH_PLAN.md`` stages 1 to 3 (E-RQ2-FULL-PREP). The pieces here are the
logic of ``scripts/ada/rq2_full_prep.sbatch``: which directories are final, a byte copy of a
prefix of the store for a trial, the split of the overlap audit into resumable shards and the
merge that gives the unsharded records, the step that takes the audit's drop list off the
training manifest (not off the store), and the checks that two runs or two readings of the same
inputs agree. Nothing here writes into the store it reads. Kept compatible with Python 3.10.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import shutil
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from ril.data_mining import cas

TIMING_KEYS: tuple[str, ...] = ("seconds",)
"""Fields of rank rows that hold wall-clock time: the only values allowed to differ between runs."""
PATH_KEYS: tuple[str, ...] = ("out", "zip", "listing_sha256")
"""Fields of stage records that name a run's own paths (or hash a file that holds one): the
listing's ``url`` is the archive's path, so its hash differs with the scratch directory. The
listing's content apart from that path is hashed separately (``listing_members_sha256``)."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def read_state_rows(path: str) -> list[dict[str, Any]]:
    with open(path, encoding="utf-8") as handle:
        return [json.loads(x) for x in handle if x.strip()]


def sha256_names(names: Iterable[str]) -> str:
    """Hash of a name list as it is written to a names file (one per line, final newline)."""
    return sha256_bytes("".join(f"{n}\n" for n in names).encode("utf-8"))


def dir_name_of_key(key: str) -> str:
    """Directory name of a state row's key ``owner/name#<PR>``: ``owner__name-<PR>``, lower case."""
    repo, _, number = key.partition("#")
    owner, _, name = repo.lower().partition("/")
    return f"{owner}__{name}-{number}"


# --------------------------------------------------------------------------- selection


@dataclass(frozen=True)
class Selection:
    """The final mined directories chosen by state order, with the hashes that repeat the choice."""

    names: list[str]
    keys: list[str]
    state_rows: int
    """Rows of the state file that were read (the whole file)."""
    last_row: int
    """Rows of the state file up to and including the last row used (1-based count)."""
    used_sha256: str
    """SHA-256 of the state lines of the rows used, in file order."""
    prefix_sha256: str
    """SHA-256 of the state file's first ``last_row`` lines."""
    skipped_open: int = 0
    """Mined rows whose directory is not complete in the store (not final), left out."""
    status: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "directories": len(self.names),
            "state_rows": self.state_rows,
            "last_row": self.last_row,
            "used_rows_sha256": self.used_sha256,
            "prefix_sha256": self.prefix_sha256,
            "skipped_open": self.skipped_open,
            "status_in_prefix": dict(sorted(self.status.items())),
            "names_sha256": sha256_names(self.names),
        }


def select_closed(state_path: str, store_root: str, limit: int | None = None) -> Selection:
    """The first ``limit`` mined rows (state order) whose directory is complete in the store.

    A row counts only when its status is ``mined`` and ``pr/<dir>/pr_meta.json`` exists: a row of
    a pull request that was quarantined, had no Python change or no positive has no directory, and
    a directory without its metadata file is not final. ``limit=None`` takes every one.
    """
    with open(state_path, "rb") as handle:
        lines = [x for x in handle.read().split(b"\n") if x.strip()]
    names: list[str] = []
    keys: list[str] = []
    used: list[bytes] = []
    status: dict[str, int] = defaultdict(int)
    skipped_open = 0
    last = 0
    for i, line in enumerate(lines, start=1):
        if limit is not None and len(names) >= limit:
            break
        row = json.loads(line)
        status[str(row["status"])] += 1
        last = i
        if row["status"] != "mined":
            continue
        name = dir_name_of_key(str(row["key"]))
        if not os.path.exists(os.path.join(store_root, "pr", name, "pr_meta.json")):
            skipped_open += 1
            continue
        names.append(name)
        keys.append(str(row["key"]))
        used.append(line + b"\n")
    prefix = b"".join(x + b"\n" for x in lines[:last])
    return Selection(
        names=names,
        keys=keys,
        state_rows=len(lines),
        last_row=last,
        used_sha256=sha256_bytes(b"".join(used)),
        prefix_sha256=sha256_bytes(prefix),
        skipped_open=skipped_open,
        status=dict(status),
    )


# --------------------------------------------------------------------------- snapshot


def _copy_once(src: str, dst: str, manifest: list[dict[str, Any]], root: str) -> None:
    """Copy a file atomically; an existing destination must hold the same bytes (never replaced)."""
    digest = sha256_file(src)
    if os.path.exists(dst):
        if sha256_file(dst) != digest:
            raise cas.StoreError(f"{dst} exists and differs from {src}; nothing overwritten")
    else:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        tmp = dst + ".tmp"
        shutil.copyfile(src, tmp)
        os.replace(tmp, dst)
    manifest.append(
        {"path": os.path.relpath(dst, root), "bytes": os.path.getsize(dst), "sha256": digest}
    )


def snapshot_store(
    store_root: str, state_path: str, dest_root: str, selection: Selection
) -> dict[str, Any]:
    """Byte copy of the selected directories and their repositories' rows into a store.

    The copy is itself a de-duplicated store: ``pr/<dir>`` for each name, ``cas/<repo>`` of every
    repository they belong to (whole, so every slot they reference resolves) and ``state.jsonl``
    holding the state lines up to the last row used. Reads ``store_root`` only. Returns the manifest
    (path, bytes, SHA-256 per file) and writes it next to the copy.
    """
    manifest: list[dict[str, Any]] = []
    repos: dict[str, str] = {}
    for name in selection.names:
        src = os.path.join(store_root, "pr", name)
        for fname in sorted(os.listdir(src)):
            path = os.path.join(src, fname)
            if os.path.isdir(path):
                for sub in sorted(os.listdir(path)):
                    _copy_once(
                        os.path.join(path, sub),
                        os.path.join(dest_root, "pr", name, fname, sub),
                        manifest,
                        dest_root,
                    )
            else:
                _copy_once(path, os.path.join(dest_root, "pr", name, fname), manifest, dest_root)
        with open(os.path.join(src, "pr_meta.json"), encoding="utf-8") as handle:
            repo = str(json.load(handle)["repo"])
        repos[cas.repo_dir_name(repo)] = repo
    for rdir in sorted(repos):
        src = os.path.join(store_root, "cas", rdir)
        for fname in sorted(os.listdir(src)):
            _copy_once(
                os.path.join(src, fname),
                os.path.join(dest_root, "cas", rdir, fname),
                manifest,
                dest_root,
            )
    with open(state_path, "rb") as handle:
        lines = [x for x in handle.read().split(b"\n") if x.strip()][: selection.last_row]
    tmp_state = os.path.join(dest_root, "state.jsonl.tmp")
    with open(tmp_state, "wb") as handle:
        handle.write(b"".join(x + b"\n" for x in lines))
    final_state = os.path.join(dest_root, "state.jsonl")
    if os.path.exists(final_state) and sha256_file(final_state) != sha256_file(tmp_state):
        raise cas.StoreError(f"{final_state} exists and differs; nothing overwritten")
    os.replace(tmp_state, final_state)
    manifest.append(
        {
            "path": "state.jsonl",
            "bytes": os.path.getsize(final_state),
            "sha256": sha256_file(final_state),
        }
    )
    manifest.sort(key=lambda r: str(r["path"]))
    doc = {
        "selection": selection.to_dict(),
        "repositories": len(repos),
        "files": len(manifest),
        "bytes": sum(int(r["bytes"]) for r in manifest),
        "manifest": manifest,
    }
    with open(os.path.join(dest_root, "snapshot.json"), "w", encoding="utf-8") as handle:
        json.dump(doc, handle, indent=1, sort_keys=True)
        handle.write("\n")
    return doc


def verify_snapshot(dest_root: str) -> dict[str, Any]:
    """Re-hash every file of a snapshot against its manifest (``missing`` and ``changed`` lists)."""
    with open(os.path.join(dest_root, "snapshot.json"), encoding="utf-8") as handle:
        doc = json.load(handle)
    missing: list[str] = []
    changed: list[str] = []
    for row in doc["manifest"]:
        path = os.path.join(dest_root, row["path"])
        if not os.path.exists(path):
            missing.append(row["path"])
        elif sha256_file(path) != row["sha256"]:
            changed.append(row["path"])
    return {"files": len(doc["manifest"]), "missing": missing, "changed": changed}


# --------------------------------------------------------------------------- audit shards


def shard_of(repo: str, shards: int) -> int:
    """Shard of a repository: by hash, so the split does not depend on the store's size or order."""
    return int(hashlib.sha256(repo.encode("utf-8")).hexdigest()[:8], 16) % shards


def shard_names(store_root: str, names: Sequence[str], shards: int) -> list[list[str]]:
    """The names split into ``shards`` lists by repository (a repository is never split)."""
    if shards < 1:
        raise ValueError("shards must be at least 1")
    out: list[list[str]] = [[] for _ in range(shards)]
    for name in names:
        out[shard_of(cas._repo_of(os.path.join(store_root, "pr", name)), shards)].append(name)
    return out


def merge_audit_records(shard_dirs: Sequence[str]) -> list[dict[str, Any]]:
    """Records of several shard directories in the order an unsharded audit writes them.

    ``audit_store`` walks repositories in sorted order and each repository's directories in sorted
    order, so sorting the union by ``(repo, directory)`` gives the same list. A directory in two
    shards is an error.
    """
    records: list[dict[str, Any]] = []
    for d in shard_dirs:
        with open(os.path.join(d, "records.jsonl"), encoding="utf-8") as handle:
            records.extend(json.loads(x) for x in handle if x.strip())
    seen: set[str] = set()
    for r in records:
        if r["directory"] in seen:
            raise ValueError(f"directory {r['directory']} appears in two shards")
        seen.add(str(r["directory"]))
    records.sort(key=lambda r: (str(r["repo"]), str(r["directory"])))
    return records


# --------------------------------------------------------------------------- drop list


def read_names(path: str) -> list[str]:
    with open(path, encoding="utf-8") as handle:
        return [x.strip() for x in handle if x.strip()]


def apply_drop_list(names: Sequence[str], drop: Sequence[str]) -> tuple[list[str], list[str]]:
    """``(kept, dropped)``: the manifest's names without the drop list, in the manifest's order.

    A name in the drop list that the manifest does not hold is an error: the list was built for
    another store or another selection. Only the manifest changes; the store is never touched.
    """
    have = set(names)
    unknown = sorted(set(drop) - have)
    if unknown:
        raise ValueError(
            f"{len(unknown)} names of the drop list are not in the manifest: {unknown[:3]}"
        )
    drop_set = set(drop)
    return [n for n in names if n not in drop_set], [n for n in names if n in drop_set]


# --------------------------------------------------------------------------- byte identity


def verify_materialised(store_root: str, view_root: str, names: Sequence[str]) -> dict[str, Any]:
    """Check materialised directories against the store: small files equal, rows equal by slot.

    For each name the small files of ``pr/<dir>`` must equal the store's byte for byte and the
    decompressed corpus must be the concatenation of the stored rows at the manifest's slots.
    """
    by_repo: dict[str, list[str]] = defaultdict(list)
    for name in names:
        by_repo[cas._repo_of(os.path.join(store_root, "pr", name))].append(name)
    mismatches: list[str] = []
    checked = 0
    for repo in sorted(by_repo):
        block = cas.RepoRows(store_root, repo).load()
        for name in sorted(by_repo[repo]):
            src = os.path.join(store_root, "pr", name)
            out = os.path.join(view_root, "pr", name)
            small = cas._read_small(src)
            ok = True
            for fname, data in small.items():
                with open(os.path.join(out, *fname.split("/")), "rb") as handle:
                    ok = ok and handle.read() == data
            with gzip.open(os.path.join(out, "corpus.jsonl.gz"), "rb") as handle:
                got = handle.read()
            want = b"".join(block.line(s) for s in cas.read_manifest(src))
            if not ok or got != want:
                mismatches.append(name)
            checked += 1
    return {"checked": checked, "mismatches": mismatches, "identical": not mismatches}


def _normalised(path: str, timing_keys: Sequence[str]) -> bytes:
    """File bytes with timing fields of JSON-lines rows removed and gzip read through."""
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rb") as handle:
        data: bytes = handle.read()
    if not (path.endswith(".jsonl") or path.endswith(".jsonl.gz")):
        return data
    out = []
    for line in data.splitlines(keepends=True):
        if not line.strip():
            continue
        row = json.loads(line)
        for k in timing_keys:
            row.pop(k, None)
            if isinstance(row.get("extra"), dict):
                row["extra"].pop(k, None)
        out.append(json.dumps(row, sort_keys=True).encode("utf-8") + b"\n")
    return b"".join(out)


def compare_outputs(
    a_dir: str,
    b_dir: str,
    *,
    suffixes: Sequence[str] = (".jsonl", ".json", ".csv", ".txt", ".tsv", ".gz", ".zip"),
    skip: Sequence[str] = ("stages.jsonl", "run_env.json", "env_"),
    timing_keys: Sequence[str] = TIMING_KEYS,
) -> dict[str, Any]:
    """Compare the outputs of two runs of the same stages file by file.

    Equal means byte-equal, except that rank rows are compared without their timing fields and
    gzip files by their decompressed bytes (a gzip header holds a time). Files whose names start
    with an entry of ``skip`` (the stage table and the environment records, which hold job ids and
    timings) differ by design and are not compared; a
    ``.json`` that holds a ``seconds`` key at top level is compared without it.
    """

    def files(root: str) -> dict[str, str]:
        found: dict[str, str] = {}
        for dirpath, _, fnames in os.walk(root):
            for f in fnames:
                if f.startswith(tuple(skip)) or not f.endswith(tuple(suffixes)):
                    continue
                p = os.path.join(dirpath, f)
                found[os.path.relpath(p, root)] = p
        return found

    fa, fb = files(a_dir), files(b_dir)
    only_a = sorted(set(fa) - set(fb))
    only_b = sorted(set(fb) - set(fa))
    differing: list[str] = []
    equal = 0
    for rel in sorted(set(fa) & set(fb)):
        if rel.endswith(".zip"):
            same = sha256_file(fa[rel]) == sha256_file(fb[rel])
        elif rel.endswith(".json") and not rel.endswith(".jsonl"):
            same = _json_equal(fa[rel], fb[rel], timing_keys)
        else:
            same = _normalised(fa[rel], timing_keys) == _normalised(fb[rel], timing_keys)
        if same:
            equal += 1
        else:
            differing.append(rel)
    return {
        "compared": equal + len(differing),
        "equal": equal,
        "differing": differing,
        "only_in_first": only_a,
        "only_in_second": only_b,
        "identical": not differing and not only_a and not only_b,
    }


def _json_equal(a: str, b: str, timing_keys: Sequence[str]) -> bool:
    def load(p: str) -> Any:
        with open(p, encoding="utf-8") as handle:
            doc = json.load(handle)
        return _strip_timing(doc, timing_keys)

    return bool(load(a) == load(b))


def _strip_timing(doc: Any, keys: Sequence[str]) -> Any:
    """Remove timing and host fields at any depth (they are the measurement, not the output)."""
    if isinstance(doc, dict):
        return {
            k: _strip_timing(v, keys)
            for k, v in doc.items()
            if k not in keys and k not in ("host", "hardware", *PATH_KEYS)
        }
    if isinstance(doc, list):
        return [_strip_timing(v, keys) for v in doc]
    return doc


def listing_members_sha256(listing_path: str) -> str:
    """Hash of a zip listing without its ``url`` (the archive's path): the members and offsets."""
    with open(listing_path, encoding="utf-8") as handle:
        doc = json.load(handle)
    doc.pop("url", None)
    return sha256_bytes(json.dumps(doc, sort_keys=True).encode("utf-8"))


def cache_summary(path: str) -> dict[str, Any]:
    """Counts of an example cache read one line at a time (memory does not grow with the cache)."""
    repos: set[str] = set()
    ids: list[str] = []
    positives = candidates = 0
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            repos.add(str(row["repo"]))
            ids.append(str(row["instance_id"]))
            positives += len(row["positive_ids"])
            candidates += len(row["candidate_ids"])
    return {
        "examples": len(ids),
        "positives": positives,
        "candidates": candidates,
        "repos": sorted(repos),
        "ids": ids,
    }


# --------------------------------------------------------------------------- projection


def project_stage(measured_seconds: float, trial_units: float, full_units: float) -> float:
    """Linear projection of one stage's time: ``seconds * full / trial`` (no interval)."""
    if trial_units <= 0:
        raise ValueError("the trial has no units")
    return measured_seconds * full_units / trial_units


def quarter_means(values: Sequence[float], quarters: int = 4) -> list[float]:
    """Mean of ``values`` in each consecutive quarter of the sequence (growth over mining time)."""
    n = len(values)
    out: list[float] = []
    for q in range(quarters):
        chunk = values[q * n // quarters : (q + 1) * n // quarters]
        out.append(sum(chunk) / len(chunk) if chunk else 0.0)
    return out


def mapping_sum(rows: Iterable[Mapping[str, Any]], key: str) -> float:
    return float(sum(float(r.get(key, 0) or 0) for r in rows))


def tree_size(path: str) -> int:
    """Total bytes of the files under ``path``."""
    return sum(os.path.getsize(os.path.join(d, f)) for d, _, files in os.walk(path) for f in files)


def cas_megabytes(store_root: str, names: Sequence[str]) -> float:
    """Megabytes of distinct-row storage (``cas/<repo>``) behind the named directories."""
    repos: set[str] = set()
    for name in names:
        repos.add(cas.repo_dir_name(cas._repo_of(os.path.join(store_root, "pr", name))))
    total = 0
    for r in repos:
        base = os.path.join(store_root, "cas", r)
        total += sum(os.path.getsize(os.path.join(base, f)) for f in os.listdir(base))
    return total / 1e6


def fit_two_factor(
    trial: tuple[float, float, float], probe: tuple[float, float, float]
) -> tuple[float, float] | None:
    """``(a, b)`` with ``seconds = a * distinct_row_MB + b * million_slots`` through two runs.

    Each run is ``(seconds, distinct_row_MB, million_slots)``. Two points fix two coefficients and
    leave no degrees of freedom: the result is a reading, not an estimate with an interval. It
    returns ``None`` when the runs are collinear or a coefficient comes out negative.
    """
    (t1, c1, s1), (t2, c2, s2) = trial, probe
    det = c1 * s2 - c2 * s1
    if abs(det) < 1e-9:
        return None
    a = (t1 * s2 - t2 * s1) / det
    b = (c1 * t2 - c2 * t1) / det
    return (a, b) if a >= 0 and b >= 0 else None


def quarter_table(
    rows: Sequence[Mapping[str, Any]], cas_bytes: Mapping[str, int], quarters: int = 4
) -> list[dict[str, Any]]:
    """The store's growth by quarter of the state log: rows, mined, size of the snapshots, new rows.

    ``cas_bytes`` maps a repository's directory name (``owner__name``) to the bytes of its distinct
    rows; a repository is charged to the quarter in which its first mined pull request appears, so
    the column shows how fast the distinct-row store grows against the number of directories.
    """
    n = len(rows)
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for q in range(quarters):
        chunk = rows[q * n // quarters : (q + 1) * n // quarters]
        mined = [r for r in chunk if r.get("status") == "mined"]
        units = [float((r.get("counters") or {}).get("corpus_units", 0)) for r in mined]
        pos = [float((r.get("counters") or {}).get("positives", 0)) for r in mined]
        new: list[str] = []
        for r in mined:
            repo = cas.repo_dir_name(str(r["key"]).partition("#")[0].lower())
            if repo not in seen:
                seen.add(repo)
                new.append(repo)
        added = sum(int(cas_bytes.get(x, 0)) for x in new)
        out.append(
            {
                "quarter": q + 1,
                "rows": len(chunk),
                "mined": len(mined),
                "quarantined": sum(1 for r in chunk if r.get("status") == "quarantined"),
                "mean_corpus_units": round(sum(units) / len(units), 1) if units else 0.0,
                "positives_per_mined": round(sum(pos) / len(pos), 2) if pos else 0.0,
                "new_repositories": len(new),
                "new_distinct_row_bytes": added,
                "new_distinct_row_bytes_per_mined": round(added / len(mined)) if mined else 0,
            }
        )
    return out


def corpus_units_of_mined(state_rows: Iterable[Mapping[str, Any]]) -> list[float]:
    """``corpus_units`` (functions in the snapshot) of each mined row, in state order."""
    return [
        float((r.get("counters") or {}).get("corpus_units", 0))
        for r in state_rows
        if r.get("status") == "mined"
    ]


def project_chain(
    stage_rows: Sequence[Mapping[str, Any]],
    *,
    trial_directories: int,
    full_directories: int,
    trial_units: Sequence[float],
    full_units: Sequence[float],
    reading_share: Mapping[str, float] | None = None,
    probe_rows: Sequence[Mapping[str, Any]] | None = None,
    trial_x: tuple[float, float] | None = None,
    probe_x: tuple[float, float] | None = None,
    full_x: tuple[float, float] | None = None,
    exclude_steps: Sequence[str] = (),
) -> dict[str, Any]:
    """Project each stage's measured time to the full set, two linear readings, no interval.

    ``per_directory`` scales the trial's seconds by the number of directories. ``per_corpus_unit``
    scales by the sum of ``corpus_units`` (functions in the base-commit snapshot), which is what
    materialise, BM25 and the cache read; the quarter means show how the store grew while it was
    mined, so the range between the two readings is the spread the growth can cause. Peak memory
    is not scaled: it is decided by the largest repository or the largest cache and is reported as
    measured.
    """
    q_trial = quarter_means(trial_units)
    q_full = quarter_means(full_units)
    ratio_dirs = full_directories / trial_directories
    ratio_units = sum(full_units) / sum(trial_units)

    def seconds_of(row: Mapping[str, Any]) -> float:
        """Seconds of a stage's steps, leaving out steps of other readings (``exclude_steps``)."""
        steps = row.get("steps") or []
        if not exclude_steps or not steps:
            return float(row["step_seconds"])
        return sum(
            float(s["seconds"]) for s in steps if not str(s["step"]).endswith(tuple(exclude_steps))
        )

    probe_by = {str(r["stage"]): r for r in probe_rows or ()}
    rows: list[dict[str, Any]] = []
    for r in stage_rows:
        sec = seconds_of(r)
        two: dict[str, Any] | None = None
        pr_ = probe_by.get(str(r["stage"]))
        if pr_ is not None and trial_x and probe_x and full_x and sec > 0:
            fit = fit_two_factor((sec, trial_x[0], trial_x[1]), (seconds_of(pr_), *probe_x))
            two = {
                "probe_seconds": seconds_of(pr_),
                "coefficients": None
                if fit is None
                else {"seconds_per_distinct_row_mb": fit[0], "seconds_per_million_slots": fit[1]},
                "full_seconds": None
                if fit is None
                else round(fit[0] * full_x[0] + fit[1] * full_x[1], 1),
            }
        rows.append(
            {
                "stage": r["stage"],
                "trial_seconds": sec,
                "per_directory_seconds": sec / trial_directories,
                "full_seconds_per_directory": round(sec * ratio_dirs, 1),
                "full_seconds_per_corpus_unit": round(sec * ratio_units, 1),
                "trial_maxrss_mb": round(int(r["maxrss_kb"]) / 1024, 1),
                "trial_bytes_written": int(r["bytes_written"]),
                "full_bytes_per_directory": int(int(r["bytes_written"]) * ratio_dirs),
                "full_bytes_per_corpus_unit": int(int(r["bytes_written"]) * ratio_units),
                "two_factor": two,
            }
        )
    return {
        "basis": "linear in the trial's measured seconds and bytes; no interval",
        "trial_directories": trial_directories,
        "full_directories": full_directories,
        "ratio_directories": round(ratio_dirs, 3),
        "ratio_corpus_units": round(ratio_units, 3),
        "corpus_units_per_directory_trial": round(sum(trial_units) / len(trial_units), 1),
        "corpus_units_per_directory_full": round(sum(full_units) / len(full_units), 1),
        "quarter_means_trial": [round(x, 1) for x in q_trial],
        "quarter_means_full": [round(x, 1) for x in q_full],
        "reading_share": dict(reading_share or {}),
        "stages": rows,
    }
