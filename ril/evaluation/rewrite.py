"""Paired original/Rewrite scoring with original qrels (D13), without model loading."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

import numpy as np
import numpy.typing as npt

from ril.evaluation.core_bench import CoreBenchFolder, CoreBenchQuery

Float = npt.NDArray[np.float64]


def text_hash(ids: Sequence[str], texts: Sequence[str]) -> str:
    """SHA-256 of ordered (id, text) pairs; cache validation includes wording and corpus order."""
    blob = json.dumps(list(zip(ids, texts, strict=True)), ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()


def folder_hashes(original: CoreBenchFolder, rewrite: CoreBenchFolder) -> dict[str, str]:
    """Content hashes expected in the score-cache metadata."""
    out = {"corpus_sha256": text_hash(original.corpus_ids, original.corpus_texts)}
    for name, folder in (("original", original), ("rewrite", rewrite)):
        out[f"{name}_sha256"] = text_hash(
            [q.query_id for q in folder.queries], [q.text for q in folder.queries]
        )
    return out


class CachedScores:
    """Pinned dense score matrices; no torch import or local encoding.

    NPZ fields: corpus_ids, query_ids, original_scores, rewrite_scores, metadata (JSON scalar).
    Metadata requires encoder, revision, and the three folder_hashes fields. Scores are raw
    similarities in the original corpus order. Artifacts are generated on the compute cluster.
    """

    def __init__(self, path: str, original: CoreBenchFolder, rewrite: CoreBenchFolder) -> None:
        with np.load(Path(path), allow_pickle=False) as cache:
            self.metadata: dict[str, Any] = json.loads(str(cache["metadata"].item()))
            for name in ("encoder", "revision"):
                if not isinstance(self.metadata.get(name), str) or not self.metadata[name].strip():
                    raise ValueError(f"dense cache requires pinned {name}")
            if (
                not isinstance(self.metadata.get("max_tokens"), int)
                or self.metadata["max_tokens"] < 8
            ):
                raise ValueError("dense cache requires max_tokens >= 8")
            if "{query}" not in self.metadata.get("query_template", ""):
                raise ValueError("dense cache requires its query_template")
            if any(self.metadata.get(k) != v for k, v in folder_hashes(original, rewrite).items()):
                raise ValueError("dense cache content hashes differ from the loaded split")
            self.query_ids = [str(q) for q in cache["query_ids"]]
            if self.query_ids != [q.query_id for q in original.queries]:
                raise ValueError("dense cache query order differs from the original")
            if [str(c) for c in cache["corpus_ids"]] != original.corpus_ids:
                raise ValueError("dense cache corpus order differs from the original")
            self.scores: dict[str, Float] = {
                name: np.asarray(cache[f"{name}_scores"], dtype=np.float64)
                for name in ("original", "rewrite")
            }
        shape = (len(self.query_ids), len(original.corpus_ids))
        if any(v.shape != shape or not np.isfinite(v).all() for v in self.scores.values()):
            raise ValueError("dense cache needs finite query-by-corpus matrices")
        self.positions = {qid: i for i, qid in enumerate(self.query_ids)}

    def score(self, query: CoreBenchQuery, condition: str) -> Float:
        """Return a view of one precomputed score row, validated at construction."""
        return cast(Float, self.scores[condition][self.positions[query.query_id]])


_ANCHOR = re.compile(r"`[^`\n]+`|https?://[^\s]+|\b\w+(?:\.\w+)+\b|\b\w*(?:Error|Exception)\b")


def anchor_counts(original: str, rewrite: str) -> dict[str, int]:
    """Exploratory exact-string anchor retention; this is a diagnostic, not a causal label."""
    before, after = set(_ANCHOR.findall(original)), set(_ANCHOR.findall(rewrite))
    return {"anchors_original": len(before), "anchors_lost": len(before - after)}
