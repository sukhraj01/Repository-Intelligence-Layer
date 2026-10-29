"""Tables of the full contamination scan (E-CONTAM-SCAN): hits at the instance's own base commit.

Exploratory; not part of the frozen evaluation (ADR-005 addendum, decision D23). Joins the
per-shard scan output (counts and syntax-tree hashes of matched documents, no text) with the
syntax-tree hashes of the functions at each instance's own base commit, restricted to a size floor
fixed beforehand (``configs/experiments/x4_contam_scan.yaml``).

A hit means a function with the same syntax tree occurs as the ``document`` of a corpus row. It is
not evidence that the (query, document) pair was in any model's training data.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

Record = dict[str, Any]

SCAN_VERSION = "contam-scan/v1"
Z95 = 1.959963984540054


def config_hash(cfg: Mapping[str, Any], probe_version: str = "contam-probe/v1") -> str:
    """SHA-256 of the canonical JSON of the configuration plus the probe version."""
    blob = json.dumps(
        {"version": probe_version, "config": cfg},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def wilson(k: int, n: int, z: float = Z95) -> tuple[float, float]:
    """Wilson score interval for a proportion ``k / n`` (``(nan, nan)`` if ``n`` is 0)."""
    if n <= 0:
        return (math.nan, math.nan)
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, centre - half), min(1.0, centre + half))


def collect_hits(shards: Iterable[Mapping[str, Any]]) -> tuple[Counter[str], Record]:
    """Documents per matched syntax-tree hash over shard records, plus completeness checks.

    ``truncated_shards`` lists shards whose hit records fewer than their ``any_hits`` count (the
    scan caps hit records per shard); ``text_only_hits`` counts hits without a syntax-tree hash,
    which have no size and so cannot pass a floor.
    """
    docs: Counter[str] = Counter()
    rows = documents = any_hits = text_only = 0
    truncated: list[int] = []
    shard_ids: list[int] = []
    for rec in shards:
        c = rec["counts"]
        rows += c["rows"]
        documents += c["documents"]
        any_hits += c["any_hits"]
        shard_ids.append(int(rec["shard"]))
        if len(rec["hits"]) < c["any_hits"]:
            truncated.append(int(rec["shard"]))
        for h in rec["hits"]:
            a = h.get("ast_hash")
            if a is None:
                text_only += 1
            else:
                docs[a] += 1
    check: Record = {
        "shards": len(shard_ids),
        "shard_ids_min": min(shard_ids) if shard_ids else None,
        "shard_ids_max": max(shard_ids) if shard_ids else None,
        "rows": rows,
        "documents": documents,
        "any_hits": any_hits,
        "text_only_hits": text_only,
        "truncated_shards": sorted(truncated),
    }
    return docs, check


def _iv(k: int, n: int) -> list[float]:
    lo, hi = wilson(k, n)
    return [round(lo, 6), round(hi, 6)]


def repo_table(
    inst: Mapping[str, tuple[str, Mapping[str, int]]],
    docs: Mapping[str, int],
    floor: int,
) -> list[Record]:
    """Per-repository counts at ``floor`` for hashes present at the instance's own base commit.

    ``inst`` maps instance id to ``(repo, {ast hash: node count})``. Per repository: instances;
    instances with at least one matched function (Wilson interval); distinct functions (hashes)
    above the floor over its instances, how many occur in the corpus (Wilson interval, descriptive:
    functions are not independent draws); corpus documents matching them (a hash shared by several
    repositories counts for each, the total row counts it once); matched hashes per instance
    (median, maximum) and the share of an instance's functions above the floor that match (median,
    minimum, maximum). The restriction to the instance's own base commit is the per-instance
    hash set: at repository level it removes nothing from the probe, which was built from the same
    snapshots, so the repository rows equal the union-probe counts by construction.
    """
    by_repo: dict[str, list[Mapping[str, int]]] = {}
    for repo, hashes in inst.values():
        by_repo.setdefault(repo, []).append(hashes)
    rows: list[Record] = []
    all_hashes: set[str] = set()
    all_matched: set[str] = set()
    n_inst = n_hit_inst = 0
    for repo in sorted(by_repo):
        lists = by_repo[repo]
        probe = {h for hs in lists for h, n in hs.items() if n >= floor}
        matched = {h for h in probe if h in docs}
        per_inst = sorted(sum(1 for h, n in hs.items() if n >= floor and h in docs) for hs in lists)
        shares = sorted(
            sum(1 for h, n in hs.items() if n >= floor and h in docs)
            / max(1, sum(1 for n in hs.values() if n >= floor))
            for hs in lists
        )
        with_hit = sum(1 for x in per_inst if x > 0)
        all_hashes |= probe
        all_matched |= matched
        n_inst += len(lists)
        n_hit_inst += with_hit
        rows.append(
            {
                "repo": repo,
                "floor_nodes": floor,
                "instances": len(lists),
                "instances_with_hit": with_hit,
                "instances_with_hit_ci95": _iv(with_hit, len(lists)),
                "functions_above_floor": len(probe),
                "functions_matched": len(matched),
                "functions_matched_share_ci95": _iv(len(matched), len(probe)),
                "hit_documents": sum(docs[h] for h in matched),
                "matched_per_instance_median": per_inst[len(per_inst) // 2],
                "matched_per_instance_max": per_inst[-1],
                "matched_share_per_instance_median": round(shares[len(shares) // 2], 4),
                "matched_share_per_instance_min": round(shares[0], 4),
                "matched_share_per_instance_max": round(shares[-1], 4),
            }
        )
    rows.append(
        {
            "repo": "ALL (hash counted once)",
            "floor_nodes": floor,
            "instances": n_inst,
            "instances_with_hit": n_hit_inst,
            "instances_with_hit_ci95": _iv(n_hit_inst, n_inst),
            "functions_above_floor": len(all_hashes),
            "functions_matched": len(all_matched),
            "functions_matched_share_ci95": _iv(len(all_matched), len(all_hashes)),
            "hit_documents": sum(docs[h] for h in all_matched),
            "matched_per_instance_median": None,
            "matched_per_instance_max": None,
            "matched_share_per_instance_median": None,
            "matched_share_per_instance_min": None,
            "matched_share_per_instance_max": None,
        }
    )
    return rows


def size_profile(docs: Mapping[str, int], sizes: Mapping[str, int]) -> dict[str, int]:
    """Hit documents by node-count bucket of the matched function (the slice report's buckets)."""
    edges: Sequence[tuple[str, int, int]] = (
        ("under 20", 0, 20),
        ("20 to 49", 20, 50),
        ("50 to 99", 50, 100),
        ("100 or more", 100, 10**9),
    )
    out = dict.fromkeys((e[0] for e in edges), 0)
    for h, n in docs.items():
        s = sizes.get(h, 0)
        for name, lo, hi in edges:
            if lo <= s < hi:
                out[name] += n
                break
    return out
