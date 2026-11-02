"""Pack a mined run into a zip the pool reader streams, with its member listing (design D66).

Implements ``docs/experiments/B.md`` E-MINE-PILOT. ``ril.training.pool_reader`` reads a pool by
range requests over a zip and a member listing with offsets. The run root holds the same layout as
loose directories; this module writes the zip (stored or deflated members, fixed timestamps,
sorted names, so the same run gives the same bytes), the listing in the form
``scripts/ada/zip_remote_listing.py`` produces, and a local ``Fetch`` for the reader. The reader
itself is not changed.

Kept compatible with Python 3.10 (the cluster's compute nodes).
"""

from __future__ import annotations

import json
import os
import struct
import zipfile
from typing import Any

from ril.data_mining.agreement import is_test_id
from ril.data_mining.files import read_corpus

POOL_PREFIX = "train/python/"
INSTANCE_FILES = ("corpus.jsonl", "queries.jsonl", "qrels/test.tsv")
FIXED_TIME = (2020, 1, 1, 0, 0, 0)
_LOCAL = struct.Struct("<IHHHHHIIIHH")


def list_dirs(root: str) -> list[str]:
    """Complete instance directories under ``root/pr`` (sorted)."""
    base = os.path.join(root, "pr")
    if not os.path.isdir(base):
        return []
    return sorted(
        d
        for d in os.listdir(base)
        if not d.endswith(".tmp") and os.path.exists(os.path.join(base, d, "pr_meta.json"))
    )


def instance_bytes(base: str, drop_tests: bool) -> tuple[bytes, bytes] | None:
    """``(corpus, qrels)`` bytes of one instance directory, or ``None`` if nothing is left.

    With ``drop_tests`` the corpus loses the functions of test files (D9 path rule) and the qrels
    lose their positives; a directory with no positive left is dropped. This is the pool-like
    reading: the published pool's corpora hold no test-file functions and none of its positives is
    in a test file (``results/mining/m1_agreement.md``).
    """
    corpus = read_corpus(base)
    with open(os.path.join(base, "qrels", "test.tsv"), "rb") as handle:
        qrels = handle.read()
    if not drop_tests:
        return corpus, qrels
    keep_rows = [
        line
        for line in corpus.decode("utf-8").splitlines(keepends=True)
        if line.strip() and not is_test_id(str(json.loads(line)["_id"]))
    ]
    lines = qrels.decode("utf-8").splitlines(keepends=True)
    kept_qrels = [lines[0]] + [
        line for line in lines[1:] if line.strip() and not is_test_id(line.split("\t")[1])
    ]
    if len(kept_qrels) < 2:
        return None
    return "".join(keep_rows).encode("utf-8"), "".join(kept_qrels).encode("utf-8")


def pack_zip(root: str, zip_path: str, *, deflate: bool = True, drop_tests: bool = False) -> int:
    """Write ``zip_path`` with ``train/python/<dir>/{corpus.jsonl, queries.jsonl, qrels/test.tsv}``.

    Returns the number of instances packed. ``pr_meta.json`` stays out (the pool has no such
    member). ``drop_tests`` writes the pool-like reading (see :func:`instance_bytes`).
    """
    names = list_dirs(root)
    packed = len(names)
    tmp = zip_path + ".tmp"
    method = zipfile.ZIP_DEFLATED if deflate else zipfile.ZIP_STORED
    with zipfile.ZipFile(tmp, "w", compression=method) as zf:
        for name in names:
            base = os.path.join(root, "pr", name)
            kept = instance_bytes(base, drop_tests)
            if kept is None:
                packed -= 1
                continue
            for member in INSTANCE_FILES:
                if member == "corpus.jsonl":
                    data = kept[0]
                elif member == "qrels/test.tsv":
                    data = kept[1]
                else:
                    with open(os.path.join(base, *member.split("/")), "rb") as handle:
                        data = handle.read()
                info = zipfile.ZipInfo(f"{POOL_PREFIX}{name}/{member}", date_time=FIXED_TIME)
                info.compress_type = method
                info.external_attr = 0o644 << 16
                zf.writestr(info, data)
    os.replace(tmp, zip_path)
    return packed


def listing_of(zip_path: str, url: str) -> dict[str, Any]:
    """Member table with local-header offsets: ``{"url", "members": [{name, offset, ...}]}``."""
    members: list[dict[str, Any]] = []
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            members.append(
                {
                    "name": info.filename,
                    "offset": info.header_offset,
                    "compressed": info.compress_size,
                    "uncompressed": info.file_size,
                    "method": info.compress_type,
                }
            )
    return {"url": url, "members": members}


def write_listing(zip_path: str, listing_path: str) -> None:
    """Write the listing JSON next to the zip (the reader's ``load_listing`` input)."""
    doc = listing_of(zip_path, os.path.abspath(zip_path))
    with open(listing_path, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(doc, sort_keys=True, separators=(",", ":")) + "\n")


def local_fetch(url: str, first: int, last: int) -> bytes:
    """``Fetch`` over a local file: bytes ``first`` to ``last`` inclusive (HTTP Range semantics)."""
    with open(url, "rb") as handle:
        handle.seek(first)
        return handle.read(last - first + 1)
