"""Measured disk saving of a content-addressed corpus store (proposal; nothing is stored this way).

Implements ``docs/experiments/B.md`` E-MINE-PILOT (scale-up preparation). Directories of one
repository are snapshots of the same code at different commits, so most function rows repeat. This
module measures, on an existing run root, how many bytes a store would need that keeps every
distinct row once per repository (as one compressed stream) plus, per directory, the list of row indices
(a compressed manifest), against the bytes the run root uses now. It reads the run root and writes
nothing; the output format, ``ril/training/pool_reader.py`` and the rank tooling are not touched.

Kept compatible with Python 3.10 (the cluster's compute nodes).
"""

from __future__ import annotations

import array
import hashlib
import json
import os
import zlib
from collections import defaultdict
from typing import Any

from ril.data_mining.files import CORPUS_GZ, read_corpus
from ril.data_mining.pack import list_dirs

LEVEL = 6


def _repo_of(root: str, name: str) -> str:
    with open(os.path.join(root, "pr", name, "pr_meta.json"), encoding="utf-8") as handle:
        return str(json.load(handle)["repo"])


def measure(root: str) -> dict[str, Any]:
    """Bytes now against bytes of a per-repository distinct-row store plus manifests."""
    by_repo: dict[str, list[str]] = defaultdict(list)
    for name in list_dirs(root):
        by_repo[_repo_of(root, name)].append(name)
    now_bytes = rows_total = rows_distinct = plain_total = plain_distinct = 0
    blob_bytes = manifest_bytes = 0
    per_repo: list[dict[str, Any]] = []
    for repo in sorted(by_repo):
        index: dict[bytes, int] = {}
        stream = zlib.compressobj(LEVEL)
        repo_now = repo_blob = repo_manifest = repo_rows = 0
        for name in sorted(by_repo[repo]):
            base = os.path.join(root, "pr", name)
            path = os.path.join(base, CORPUS_GZ)
            repo_now += os.path.getsize(path) if os.path.exists(path) else 0
            ids = array.array("I")
            for line in read_corpus(base).splitlines(keepends=True):
                if not line.strip():
                    continue
                digest = hashlib.sha1(line).digest()
                repo_rows += 1
                plain_total += len(line)
                slot = index.get(digest)
                if slot is None:
                    slot = len(index)
                    index[digest] = slot
                    plain_distinct += len(line)
                    repo_blob += len(stream.compress(line))
                ids.append(slot)
            repo_manifest += len(zlib.compress(ids.tobytes(), LEVEL))
        repo_blob += len(stream.flush())
        now_bytes += repo_now
        blob_bytes += repo_blob
        manifest_bytes += repo_manifest
        rows_total += repo_rows
        rows_distinct += len(index)
        per_repo.append(
            {
                "repo": repo,
                "directories": len(by_repo[repo]),
                "bytes_now": repo_now,
                "bytes_store": repo_blob + repo_manifest,
            }
        )
    store = blob_bytes + manifest_bytes
    return {
        "directories": sum(len(v) for v in by_repo.values()),
        "repositories": len(by_repo),
        "rows": {"total": rows_total, "distinct_per_repository": rows_distinct},
        "plain_bytes": {"total": plain_total, "distinct": plain_distinct},
        "bytes_now_compressed_corpora": now_bytes,
        "bytes_store": {"blobs": blob_bytes, "manifests": manifest_bytes, "total": store},
        "saving_share": round(1 - store / now_bytes, 4) if now_bytes else 0.0,
        "per_repository": per_repo,
    }
