"""Corpus files of a run root: stored compressed, read back as the pool's ``corpus.jsonl``.

Implements ``docs/experiments/B.md`` E-MINE-PILOT. A mined directory holds the whole function
corpus of one snapshot (megabytes of text, tens of megabytes for a large repository), and the home
file system of the cluster writes slowly and is under quota. The run root therefore stores the
corpus as ``corpus.jsonl.gz`` (fixed header, no timestamp, so the bytes repeat); :func:`pack_zip`
writes it into the archive as the pool's plain ``corpus.jsonl`` member, so the reader's contract
is unchanged. Readers accept a run root that still has the plain file.

Kept compatible with Python 3.10 (the cluster's compute nodes).
"""

from __future__ import annotations

import gzip
import io
import os
from collections.abc import Iterable

CORPUS_PLAIN = "corpus.jsonl"
CORPUS_GZ = "corpus.jsonl.gz"
COMPRESSLEVEL = 6


def gzip_bytes(data: bytes) -> bytes:
    """Deterministic gzip of ``data`` (no file name, modification time 0)."""
    buf = io.BytesIO()
    with gzip.GzipFile(
        filename="", fileobj=buf, mode="wb", compresslevel=COMPRESSLEVEL, mtime=0
    ) as handle:
        handle.write(data)
    return buf.getvalue()


def read_corpus(directory: str) -> bytes:
    """The uncompressed corpus of one instance directory (compressed or plain file)."""
    gz = os.path.join(directory, CORPUS_GZ)
    if os.path.exists(gz):
        with open(gz, "rb") as handle:
            return gzip.decompress(handle.read())
    with open(os.path.join(directory, CORPUS_PLAIN), "rb") as handle:
        return handle.read()


def corpus_size(directory: str) -> int:
    """Uncompressed size in bytes, from the gzip trailer when the corpus is compressed."""
    gz = os.path.join(directory, CORPUS_GZ)
    if os.path.exists(gz):
        with open(gz, "rb") as handle:
            handle.seek(-4, os.SEEK_END)
            return int.from_bytes(handle.read(4), "little")  # size modulo 2**32: below 4 GB here
    return os.path.getsize(os.path.join(directory, CORPUS_PLAIN))


def write_gzip_lines(path: str, lines: Iterable[bytes]) -> None:
    """Write ``lines`` to ``path`` as one gzip stream without building the whole text in memory.

    Same bytes as :func:`gzip_bytes` of their concatenation (fixed header, level and no
    timestamp); the file is written to a temporary name, synced and renamed.
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "wb") as raw:
        with gzip.GzipFile(
            filename="", fileobj=raw, mode="wb", compresslevel=COMPRESSLEVEL, mtime=0
        ) as handle:
            for line in lines:
                handle.write(line)
        raw.flush()
        os.fsync(raw.fileno())
    os.replace(tmp, path)
