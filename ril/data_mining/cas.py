"""De-duplicated corpus store and the step that rebuilds today's directory layout (decision D93).

Implements ``docs/experiments/B.md`` E-MINE-STORE (measured in ``results/mining/dedup_measure.md``).
Directories of one repository are snapshots of the same code at different commits, so most function
rows repeat. The store keeps every distinct corpus row once per repository and, per pull request, a
manifest (the list of row slots, in the order of the corpus file). Layout under a run root::

    cas/<owner>__<name>/rows.gz         distinct rows in slot order; one gzip member per append
    cas/<owner>__<name>/digests.bin     SHA-1 of each row (20 bytes), same order
    cas/<owner>__<name>/segments.jsonl  one line per append: {"rows": n, "bytes": gzip member size}
    pr/<dir>/{corpus.manifest, queries.jsonl, qrels/test.tsv, pr_meta.json}

``segments.jsonl`` is the commit record of an append: ``rows.gz`` and ``digests.bin`` are cut back
to the sizes it states when the repository is opened, so a crash between the three writes leaves
the last committed state, never a half-written one. Rows added by a pull request that then
crashed before its directory was renamed stay in the store; a rerun finds them and reuses them.

:func:`materialise` writes ``pr/<dir>/corpus.jsonl.gz`` and the three small files of a directory
as ``MiningStore.write_instance`` wrote them before this layout existed (same bytes), so
``pack``, the rank tooling and ``ril.training.pool_reader`` read a materialised root unchanged.

Kept compatible with Python 3.10 (the cluster's compute nodes).
"""

from __future__ import annotations

import array
import gzip
import hashlib
import io
import json
import os
import shutil
import sys
import time
import zlib
from collections import defaultdict
from collections.abc import Iterable, Iterator, Sequence
from typing import Any

from ril.data_mining.files import (
    COMPRESSLEVEL,
    CORPUS_GZ,
    read_corpus,
    write_gzip_lines,
)
from ril.data_mining.files import (
    MANIFEST as MANIFEST,  # shared with files.py, which refuses to read such a directory
)

CAS_DIR = "cas"
ROWS_FILE = "rows.gz"
DIGESTS_FILE = "digests.bin"
SEGMENTS_FILE = "segments.jsonl"
DIGEST_BYTES = 20
SMALL_FILES = ("queries.jsonl", "qrels/test.tsv", "pr_meta.json")
_INT = "I"  # unsigned 32-bit slots: a repository holds far fewer than 2**32 distinct rows


class StoreError(RuntimeError):
    """The store on disk is inconsistent in a way a crash cannot explain."""


def repo_dir_name(repo: str) -> str:
    """Directory name of a repository's rows (the listing files use the same form)."""
    return repo.replace("/", "__")


def _fsync_append(path: str, data: bytes) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "ab") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def _le(values: array.array[int]) -> array.array[int]:
    if sys.byteorder == "big":  # pragma: no cover - the cluster and the engineer's machine are LE
        values.byteswap()
    return values


def encode_manifest(slots: array.array[int]) -> bytes:
    """Manifest bytes: the slots as little-endian uint32, deflated (fixed level, no header time)."""
    copy = array.array(_INT, slots)
    return zlib.compress(_le(copy).tobytes(), COMPRESSLEVEL)


def decode_manifest(data: bytes) -> array.array[int]:
    """Slots from :func:`encode_manifest` bytes."""
    values = array.array(_INT)
    values.frombytes(zlib.decompress(data))
    return _le(values)


def read_manifest(directory: str) -> array.array[int]:
    """Slots of one instance directory of a store."""
    with open(os.path.join(directory, MANIFEST), "rb") as handle:
        return decode_manifest(handle.read())


class RepoRows:
    """The distinct rows of one repository."""

    def __init__(self, root: str, repo: str) -> None:
        self.dir = os.path.join(root, CAS_DIR, repo_dir_name(repo))
        self.repo = repo
        self.rows_path = os.path.join(self.dir, ROWS_FILE)
        self.digests_path = os.path.join(self.dir, DIGESTS_FILE)
        self.segments_path = os.path.join(self.dir, SEGMENTS_FILE)

    def committed(self) -> tuple[int, int]:
        """``(rows, rows.gz bytes)`` of the committed appends; cut the files back to them."""
        rows = size = 0
        if os.path.exists(self.segments_path):
            with open(self.segments_path, encoding="utf-8") as handle:
                for line in handle:
                    try:
                        seg = json.loads(line)
                    except ValueError:
                        break  # a torn last line: that append was not committed
                    rows += int(seg["rows"])
                    size += int(seg["bytes"])
        for path, want in ((self.rows_path, size), (self.digests_path, rows * DIGEST_BYTES)):
            have = os.path.getsize(path) if os.path.exists(path) else 0
            if have < want:
                raise StoreError(f"{path}: {have} bytes, the commit record needs {want}")
            if have > want:
                with open(path, "r+b") as handle:
                    handle.truncate(want)
        return rows, size

    def digests(self) -> list[bytes]:
        """The committed row digests in slot order."""
        rows, _ = self.committed()
        if rows == 0:
            return []
        with open(self.digests_path, "rb") as handle:
            blob = handle.read()
        return [blob[i : i + DIGEST_BYTES] for i in range(0, rows * DIGEST_BYTES, DIGEST_BYTES)]

    def add(self, lines: Iterable[bytes]) -> array.array[int]:
        """Slots of ``lines`` (each one corpus row with its newline); new rows are appended.

        The three files are written rows, digests, commit record, each synced, in that order.
        """
        known = {d: i for i, d in enumerate(self.digests())}
        slots = array.array(_INT)
        buf = io.BytesIO()
        fresh: list[bytes] = []
        with gzip.GzipFile(
            filename="", fileobj=buf, mode="wb", compresslevel=COMPRESSLEVEL, mtime=0
        ) as member:
            for line in lines:
                digest = hashlib.sha1(line).digest()
                slot = known.get(digest)
                if slot is None:
                    slot = len(known)
                    known[digest] = slot
                    fresh.append(digest)
                    member.write(line)
                slots.append(slot)
        if fresh:
            payload = buf.getvalue()
            _fsync_append(self.rows_path, payload)
            _fsync_append(self.digests_path, b"".join(fresh))
            record = json.dumps({"bytes": len(payload), "rows": len(fresh)}, sort_keys=True)
            _fsync_append(self.segments_path, (record + "\n").encode("utf-8"))
        return slots

    def load(self) -> RowBlock:
        """All committed rows, decompressed, as one buffer with row offsets."""
        rows, size = self.committed()
        if rows == 0:
            return RowBlock(b"", array.array("Q", [0]))
        with open(self.rows_path, "rb") as handle:
            data = gzip.decompress(handle.read(size))
        offsets = array.array("Q", [0])
        pos = 0
        while True:
            nxt = data.find(b"\n", pos)
            if nxt < 0:
                break
            pos = nxt + 1
            offsets.append(pos)
        if len(offsets) - 1 != rows or pos != len(data):
            raise StoreError(f"{self.rows_path}: {len(offsets) - 1} rows found, {rows} committed")
        return RowBlock(data, offsets)


class RowBlock:
    """Decompressed rows of one repository: one buffer, one offset per row."""

    def __init__(self, data: bytes, offsets: array.array[int]) -> None:
        self.data = data
        self.offsets = offsets

    def __len__(self) -> int:
        return len(self.offsets) - 1

    def line(self, slot: int) -> bytes:
        return self.data[self.offsets[slot] : self.offsets[slot + 1]]


def split_lines(corpus: bytes) -> Iterator[bytes]:
    """Rows of a corpus file: every non-blank line with its newline (JSON never holds a raw one)."""
    for line in corpus.splitlines(keepends=True):
        if line.strip():
            yield line


def write_corpus(root: str, repo: str, lines: Iterable[bytes]) -> bytes:
    """Add a corpus to the store of ``repo`` and return its manifest bytes."""
    return encode_manifest(RepoRows(root, repo).add(lines))


def _repo_of(directory: str) -> str:
    with open(os.path.join(directory, "pr_meta.json"), encoding="utf-8") as handle:
        return str(json.load(handle)["repo"])


def _write_dir(final: str, files: dict[str, bytes], corpus_lines: Iterable[bytes] | None) -> None:
    tmp = final + ".tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    if corpus_lines is not None:
        write_gzip_lines(os.path.join(tmp, CORPUS_GZ), corpus_lines)
    for name, data in files.items():
        path = os.path.join(tmp, *name.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    if os.path.isdir(final):
        shutil.rmtree(final)
    os.replace(tmp, final)


def _read_small(directory: str) -> dict[str, bytes]:
    out: dict[str, bytes] = {}
    for name in SMALL_FILES:
        with open(os.path.join(directory, *name.split("/")), "rb") as handle:
            out[name] = handle.read()
    return out


def instance_names(root: str) -> list[str]:
    """Complete instance directories under ``root/pr`` (metadata file present), sorted."""
    base = os.path.join(root, "pr")
    if not os.path.isdir(base):
        return []
    return sorted(
        d
        for d in os.listdir(base)
        if not d.endswith(".tmp") and os.path.exists(os.path.join(base, d, "pr_meta.json"))
    )


def convert(src_root: str, dst_root: str) -> dict[str, Any]:
    """Build a store at ``dst_root`` from a run root that holds ``corpus.jsonl.gz`` directories.

    Reads ``src_root`` only. Directories are taken in sorted order, so the same run root gives the
    same store bytes. A directory that is already complete in ``dst_root`` is skipped (resumable).
    """
    done = skipped = 0
    t0 = time.perf_counter()
    for name in instance_names(src_root):
        final = os.path.join(dst_root, "pr", name)
        if os.path.exists(os.path.join(final, "pr_meta.json")):
            skipped += 1
            continue
        base = os.path.join(src_root, "pr", name)
        manifest = write_corpus(dst_root, _repo_of(base), split_lines(read_corpus(base)))
        _write_dir(final, {MANIFEST: manifest, **_read_small(base)}, None)
        done += 1
    return {"converted": done, "skipped": skipped, "seconds": round(time.perf_counter() - t0, 1)}


def materialise(
    store_root: str, out_root: str, names: Sequence[str] | None = None
) -> dict[str, Any]:
    """Rebuild ``out_root/pr/<dir>`` (today's layout) for ``names`` (default: every directory).

    One repository's rows are decompressed once and every requested directory of that repository
    is written from them. The result is byte-identical to the directories the miner wrote before
    the store existed (:func:`compare_roots` checks it). Existing complete output is skipped.
    """
    wanted = list(names) if names is not None else instance_names(store_root)
    by_repo: dict[str, list[str]] = defaultdict(list)
    for name in wanted:
        by_repo[_repo_of(os.path.join(store_root, "pr", name))].append(name)
    written = skipped = 0
    t0 = time.perf_counter()
    peak_rows = 0
    for repo in sorted(by_repo):
        todo = [
            n
            for n in sorted(by_repo[repo])
            if not os.path.exists(os.path.join(out_root, "pr", n, "pr_meta.json"))
        ]
        skipped += len(by_repo[repo]) - len(todo)
        if not todo:
            continue
        block = RepoRows(store_root, repo).load()
        peak_rows = max(peak_rows, len(block))
        for name in todo:
            src = os.path.join(store_root, "pr", name)
            slots = read_manifest(src)
            if slots and max(slots) >= len(block):
                raise StoreError(f"{name}: slot {max(slots)} beyond the {len(block)} stored rows")
            _write_dir(
                os.path.join(out_root, "pr", name),
                _read_small(src),
                (block.line(s) for s in slots),
            )
            written += 1
        del block
    return {
        "materialised": written,
        "skipped": skipped,
        "repositories": len(by_repo),
        "largest_repository_rows": peak_rows,
        "seconds": round(time.perf_counter() - t0, 1),
    }


def directory_digest(directory: str) -> str:
    """SHA-256 over the relative paths and bytes of every file under one directory."""
    h = hashlib.sha256()
    for dirpath, dirnames, filenames in os.walk(directory):
        dirnames.sort()
        for fname in sorted(filenames):
            path = os.path.join(dirpath, fname)
            h.update(os.path.relpath(path, directory).replace(os.sep, "/").encode("utf-8") + b"\0")
            with open(path, "rb") as handle:
                for block in iter(lambda: handle.read(1 << 20), b""):
                    h.update(block)
            h.update(b"\0")
    return h.hexdigest()


def compare_roots(a_root: str, b_root: str) -> dict[str, Any]:
    """Checksum comparison of two run roots, directory by directory (names and every file)."""
    a_names, b_names = instance_names(a_root), instance_names(b_root)
    common = sorted(set(a_names) & set(b_names))
    different = [
        n
        for n in common
        if directory_digest(os.path.join(a_root, "pr", n))
        != directory_digest(os.path.join(b_root, "pr", n))
    ]
    return {
        "directories_a": len(a_names),
        "directories_b": len(b_names),
        "compared": len(common),
        "identical": len(common) - len(different),
        "different": different[:20],
        "only_in_a": sorted(set(a_names) - set(b_names))[:20],
        "only_in_b": sorted(set(b_names) - set(a_names))[:20],
        "all_identical": not different and a_names == b_names,
    }


def store_bytes(root: str) -> dict[str, int]:
    """Bytes of the store: rows, digests, commit records, and the per-directory files."""
    out = {"rows": 0, "digests": 0, "segments": 0, "directories": 0}
    cas = os.path.join(root, CAS_DIR)
    if os.path.isdir(cas):
        for repo in os.listdir(cas):
            for key, fname in (
                ("rows", ROWS_FILE),
                ("digests", DIGESTS_FILE),
                ("segments", SEGMENTS_FILE),
            ):
                path = os.path.join(cas, repo, fname)
                out[key] += os.path.getsize(path) if os.path.exists(path) else 0
    base = os.path.join(root, "pr")
    if os.path.isdir(base):
        for dirpath, _dirs, files in os.walk(base):
            out["directories"] += sum(os.path.getsize(os.path.join(dirpath, f)) for f in files)
    out["total"] = sum(out.values())
    return out
