"""Dense-teacher cost measurement on a seeded sample of the mined example cache (D125).

Why: FILTER with a dense teacher on the mined set is a conditional cell; it runs only if one
teacher pass over the prepared directories is projected at no more than ``RULE_MAX_GPU_HOURS``.
The pass scores every snapshot function once per repository (``RepoVectorCache``), so its cost
follows the number of *distinct* texts per repository, not the number of directories. The sample
is timed on the real encoder; the whole cache is counted on the CPU (distinct texts per
repository, queries); the projection is the measured seconds per distinct text and per query
times those counts.
Implements ``docs/RQ2_LAUNCH_PLAN.md`` section 11 (D125) and ``docs/RQ2_PROTOCOL.md`` section 11.
"""

from __future__ import annotations

import hashlib
import random
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from ril.training.pool_reader import PoolExample

RULE_MAX_GPU_HOURS = 6.0
"""Largest projected full-store pass that keeps the conditional cell (D125)."""


def _text_keys(ex: PoolExample) -> list[str]:
    return [
        hashlib.sha1(t.encode("utf-8")).hexdigest()
        for t in (*ex.positive_texts, *ex.candidate_texts)
    ]


@dataclass(frozen=True)
class StoreCounts:
    """What a teacher pass over a set of examples has to encode."""

    directories: int
    repositories: int
    queries: int
    function_rows: int
    distinct_texts: int


def count_store(examples: Sequence[PoolExample]) -> StoreCounts:
    """Distinct function texts per repository summed over repositories (the pass's encode count)."""
    seen: dict[str, set[str]] = {}
    rows = 0
    for ex in examples:
        keys = _text_keys(ex)
        rows += len(keys)
        seen.setdefault(ex.repo, set()).update(keys)
    return StoreCounts(
        directories=len(examples),
        repositories=len(seen),
        queries=len(examples),
        function_rows=rows,
        distinct_texts=sum(len(v) for v in seen.values()),
    )


def sample_examples(examples: Sequence[PoolExample], n: int, seed: int) -> list[PoolExample]:
    """``n`` directories drawn without replacement (seeded), ordered by repository then id."""
    if n > len(examples):
        raise ValueError(f"sample of {n} from {len(examples)} directories")
    ordered = sorted(examples, key=lambda e: e.instance_id)
    picked = random.Random(seed).sample(ordered, n)
    return sorted(picked, key=lambda e: (e.repo, e.instance_id))


def project(
    sample_seconds: float, sample: StoreCounts, full: StoreCounts, *, query_seconds: float = 0.0
) -> dict[str, float]:
    """Full-store GPU hours from the sample's timing.

    ``dedup``: seconds per distinct text of the sample (encode time only) times the full distinct
    count, plus seconds per query times the number of directories. ``per_directory``: sample seconds
    per directory times the directories; an upper bound, since a random sample shares fewer texts
    between directories of a repository than the whole store does.
    """
    if sample.distinct_texts <= 0 or sample.directories <= 0:
        raise ValueError("empty sample")
    enc_s = sample_seconds - query_seconds
    per_text = enc_s / sample.distinct_texts
    per_query = query_seconds / sample.queries
    dedup = per_text * full.distinct_texts + per_query * full.queries
    per_dir = sample_seconds / sample.directories * full.directories
    return {
        "seconds_per_distinct_text": per_text,
        "seconds_per_query": per_query,
        "dedup_gpu_hours": dedup / 3600.0,
        "per_directory_gpu_hours": per_dir / 3600.0,
    }


def rule(projected_gpu_hours: float) -> bool:
    """The D125 rule: the conditional cell runs only at or under the limit."""
    return projected_gpu_hours <= RULE_MAX_GPU_HOURS


def measure(
    examples: Sequence[PoolExample],
    sample: Sequence[PoolExample],
    encoder: Any,
    *,
    batch_size: int,
    warmup_texts: int = 64,
    sync: Callable[[], None] = lambda: None,
) -> dict[str, Any]:
    """Time the sample with ``RepoVectorCache`` exactly as the teacher pass does.

    The first ``warmup_texts`` texts are encoded and discarded before timing; ``sync`` is called
    before and after each timed section (``torch.cuda.synchronize`` on a GPU).
    """
    from ril.training.pool_ranks import RepoVectorCache

    first = sample[0]
    encoder.encode_documents(
        list((*first.positive_texts, *first.candidate_texts))[:warmup_texts], batch_size
    )
    cache = RepoVectorCache()
    q_total = 0.0
    wall = 0.0
    per_dir: list[dict[str, float | str | int]] = []
    for ex in sample:
        texts = list((*ex.positive_texts, *ex.candidate_texts))
        sync()
        t0 = time.perf_counter()
        q = encoder.encode_query(ex.query)
        sync()
        tq = time.perf_counter() - t0
        t1 = time.perf_counter()
        _, encoded = cache.scores(ex.repo, texts, q, encoder, batch_size)
        sync()
        te = time.perf_counter() - t1
        q_total += tq
        wall += tq + te
        per_dir.append(
            {
                "dir": ex.instance_id,
                "functions": len(texts),
                "encoded": encoded,
                "seconds": round(tq + te, 4),
            }
        )
    s = count_store(sample)
    f = count_store(examples)
    out = project(wall, s, f, query_seconds=q_total)
    return {
        "sample": s.__dict__,
        "full": f.__dict__,
        "sample_seconds": round(wall, 3),
        "cache_hits": cache.hits,
        "cache_misses": cache.misses,
        "projection": out,
        "rule_max_gpu_hours": RULE_MAX_GPU_HOURS,
        "cell_on": rule(out["dedup_gpu_hours"]),
        "per_directory": per_dir,
    }
