"""Metadata check of the candidate training pool: ids, overlap with the benchmarks, counts.

Implements ``docs/04_data_and_ground_truth.md`` (pool characterisation) and the pool-check part of
``docs/EXPERIMENTS.md`` (E-POOL-CHECK). The pool is an archive of one directory per pull request
(``train/<language>/<owner>__<name>-<PR>/{corpus.jsonl, queries.jsonl, qrels/test.tsv}``). This
module reads only what a zip central directory and a few HTTP range requests give: the member
table, each instance's small query and qrels members and, for a seeded sample, the corpus. It keeps
ids, counts and short metadata, never query or function text.

Standard library only and Python 3.9 compatible, because the checks run on the cluster login and
compute nodes.
"""

from __future__ import annotations

import hashlib
import json
import re
import struct
import zlib
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from ril.parsing.repo_id import normalize_repo_id

Member = Mapping[str, Any]

_DIR_RE = re.compile(r"^(?P<repo>.+)-(?P<pr>\d+)$")
_LOCAL_HEADER = struct.Struct("<IHHHHHIIIHH")
_LOCAL_SIG = 0x04034B50


def split_instance_dir(name: str) -> tuple[str, int] | None:
    """Split ``owner__name-123`` into (canonical ``owner/name``, 123); ``None`` if unreadable.

    Only the final ``-<digits>`` is the pull request number, because repository names may end in
    digits and contain hyphens. The owner is cut at the first ``__`` (GitHub owners cannot contain
    underscores).
    """
    m = _DIR_RE.match(name.strip().strip("/"))
    if m is None or "__" not in m.group("repo"):
        return None
    owner, _, rest = m.group("repo").partition("__")
    if not owner or not rest:
        return None
    return normalize_repo_id(f"{owner}/{rest}"), int(m.group("pr"))


def reference_pair(query_id: str) -> tuple[str, int] | None:
    """(repository, PR number) of a benchmark query id, or ``None`` when it carries no PR number.

    CORE-Bench and SWE-bench ids look like ``owner__name-<PR>``. The Pro split uses
    ``instance_owner__name-<hash>[-v<hash>]``; those ids do not name a PR, so they never match.
    """
    if query_id.startswith("instance_"):
        return None
    return split_instance_dir(query_id)


def pool_instances(
    members: Sequence[Member], language: str = "python"
) -> dict[str, dict[str, Member]]:
    """Group a zip member table into instances: ``{dir name: {corpus, queries, qrels}}``.

    Only complete instances (all three members present) are returned; directories are skipped.
    """
    prefix = f"train/{language}/"
    out: dict[str, dict[str, Member]] = {}
    for m in members:
        name = str(m["name"])
        if not name.startswith(prefix) or name.endswith("/"):
            continue
        parts = name[len(prefix) :].split("/")
        kind = {"corpus.jsonl": "corpus", "queries.jsonl": "queries", "test.tsv": "qrels"}.get(
            parts[-1]
        )
        if kind is None or len(parts) not in (2, 3):
            continue
        out.setdefault(parts[0], {})[kind] = m
    return {k: v for k, v in sorted(out.items()) if len(v) == 3}


def decode_member(blob: bytes, start: int, member: Member) -> bytes:
    """Decode one zip member from ``blob`` where its local header begins at ``start``.

    Why: one range request covers the queries and qrels members of an instance (they are stored
    next to each other), so the members are cut out of a single buffer. Raises ``ValueError`` on a
    bad signature, a truncated buffer or a size mismatch.
    """
    if len(blob) < start + _LOCAL_HEADER.size:
        raise ValueError("buffer too short for a local header")
    fields = _LOCAL_HEADER.unpack_from(blob, start)
    if fields[0] != _LOCAL_SIG:
        raise ValueError("bad local header signature")
    name_len, extra_len = fields[9], fields[10]
    begin = start + _LOCAL_HEADER.size + name_len + extra_len
    end = begin + int(member["compressed"])
    if len(blob) < end:
        raise ValueError("buffer too short for the member data")
    raw = blob[begin:end]
    method = int(member["method"])
    if method == 0:
        data = raw
    elif method == 8:
        data = zlib.decompress(raw, -15)
    else:
        raise ValueError(f"unsupported compression method {method}")
    if len(data) != int(member["uncompressed"]):
        raise ValueError("decoded size differs from the listing")
    return data


def span_for(members: Sequence[Member]) -> tuple[int, int]:
    """Byte range ``(first, last)`` of the file covering the given members (header to data end).

    The local header length is bounded by the 30-byte fixed part plus names; ``slack`` bytes are
    added to the end so a long file name or extra field cannot truncate the last member.
    """
    slack = 512
    first = min(int(m["offset"]) for m in members)
    last = max(int(m["offset"]) + 30 + int(m["compressed"]) for m in members) + slack
    return first, last


def split_rows(text: str) -> list[str]:
    """Non-empty JSON-lines rows. Splits on ``\\n`` only: ``str.splitlines`` would also cut at
    U+2028, vertical tab and similar characters that may sit unescaped inside a JSON string."""
    return [ln for ln in text.split("\n") if ln.strip()]


def parse_query(line: str) -> dict[str, Any]:
    """Keep the id, repository, base commit, metadata keys and text length of a query row."""
    row = json.loads(line)
    meta = row.get("metadata") or {}
    return {
        "id": row.get("_id"),
        "repo": meta.get("repo"),
        "base_commit": meta.get("base_commit"),
        "meta_keys": sorted(meta),
        "row_keys": sorted(row),
        "text_chars": len(row.get("text") or ""),
    }


def parse_qrels(text: str) -> list[tuple[str, int]]:
    """Parse a BEIR ``query-id<TAB>corpus-id<TAB>score`` file (header line allowed)."""
    out: list[tuple[str, int]] = []
    for line in text.split("\n"):
        cells = line.split("\t")
        if len(cells) != 3:
            continue
        try:
            out.append((cells[1], int(cells[2])))
        except ValueError:
            continue  # the header line
    return out


def parse_corpus(text: str) -> dict[str, Any]:
    """Counts of a corpus file: rows, distinct ids, ids as a list, metadata keys seen."""
    ids: list[str] = []
    meta_keys: set[str] = set()
    row_keys: set[str] = set()
    for line in text.split("\n"):
        if not line.strip():
            continue
        row = json.loads(line)
        ids.append(str(row.get("_id")))
        row_keys.update(row)
        meta_keys.update(row.get("metadata") or {})
    return {
        "functions": len(ids),
        "distinct_ids": len(set(ids)),
        "ids": ids,
        "row_keys": sorted(row_keys),
        "meta_keys": sorted(meta_keys),
    }


def sample_names(names: Iterable[str], k: int, seed: int) -> list[str]:
    """``k`` names chosen by a seeded hash order (stable across Python versions), sorted."""
    ranked = sorted(set(names), key=lambda n: hashlib.sha256(f"{seed}:{n}".encode()).hexdigest())
    return sorted(ranked[:k])


def percentile(values: Sequence[float], q: float) -> float:
    """Nearest-rank percentile with linear interpolation; ``q`` in [0, 100]."""
    if not values:
        raise ValueError("empty sequence")
    s = sorted(values)
    pos = (len(s) - 1) * q / 100.0
    lo = int(pos)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def describe(values: Sequence[float]) -> dict[str, float]:
    """Mean and quantiles of a sample (n, mean, min, p5, p25, p50, p75, p95, max)."""
    if not values:
        return {"n": 0}
    return {
        "n": float(len(values)),
        "mean": sum(values) / len(values),
        "min": float(min(values)),
        "p5": percentile(values, 5),
        "p25": percentile(values, 25),
        "p50": percentile(values, 50),
        "p75": percentile(values, 75),
        "p95": percentile(values, 95),
        "max": float(max(values)),
    }


def pr_overlap(
    pool: Iterable[tuple[str, int]], references: Mapping[str, Iterable[str]]
) -> dict[str, Any]:
    """Overlap of pool (repository, PR) pairs with benchmark query ids, per reference set.

    A shared pair is the same pull request: direct leakage, whatever the repository-level filter
    says. ``name_only`` repeats the match with the owner ignored (repository name and PR number),
    a sensitivity check for renamed or transferred repositories; it over-matches by design.
    """
    pool_pairs = set(pool)
    pool_name_pairs = {(r.split("/", 1)[1], pr) for r, pr in pool_pairs}
    out: dict[str, Any] = {}
    for label, ids in references.items():
        ids = list(ids)
        pairs = {p for p in (reference_pair(i) for i in ids) if p is not None}
        exact = sorted(pairs & pool_pairs)
        name_only = sorted(p for p in pairs if (p[0].split("/", 1)[1], p[1]) in pool_name_pairs)
        out[label] = {
            "reference_ids": len(ids),
            "reference_pairs": len(pairs),
            "exact_pairs": len(exact),
            "exact_repos": len({r for r, _ in exact}),
            "name_only_pairs": len(name_only),
            "exact_list": [f"{r}#{pr}" for r, pr in exact],
        }
    return out


def positives_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Summary over instance rows with ``positives`` (qrels rows with score > 0) counts."""
    pos = [int(r["positives"]) for r in rows]
    return {
        "instances": len(rows),
        "positives_total": sum(pos),
        "positives_per_instance": describe([float(p) for p in pos]),
        "instances_with_zero_positives": sum(1 for p in pos if p == 0),
        "positives_histogram": dict(sorted(Counter(min(p, 10) for p in pos).items())),
    }


def overlap_table(summary: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Rows (reference set, ids, readable pairs, exact and owner-ignored overlaps, repositories)."""
    rows = []
    for label, o in sorted(summary["overlap"].items()):
        rows.append(
            {
                "reference": label,
                "reference_ids": o["reference_ids"],
                "reference_pairs": o["reference_pairs"],
                "exact_pairs": o["exact_pairs"],
                "exact_repos": o["exact_repos"],
                "name_only_pairs": o["name_only_pairs"],
            }
        )
    return rows


def facts_table(summary: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Flat (quantity, value) rows of the pool check, for the results table."""
    s = summary["sample"]
    pa = summary["positives_all_instances"]
    fi = s["functions_per_instance"]
    rows: list[tuple[str, Any]] = [
        ("instance_directories", summary["instances"]),
        ("distinct_repositories", summary["distinct_repos"]),
        ("distinct_repo_pr_pairs", summary["distinct_pairs"]),
        ("queries_per_directory", "1 in every directory"),
        ("query_metadata_keys", "|".join(summary["query_metadata_key_sets"])),
        ("qrel_rows_total", summary["qrel_rows_total"]),
        ("positives_per_instance_mean", round(pa["positives_per_instance"]["mean"], 2)),
        ("positives_per_instance_median", pa["positives_per_instance"]["p50"]),
        ("positives_per_instance_p95", round(pa["positives_per_instance"]["p95"], 1)),
        ("positives_per_instance_max", pa["positives_per_instance"]["max"]),
        ("directories_with_zero_positives", pa["instances_with_zero_positives"]),
        ("sample_size", s["read"]),
        ("sample_functions_mean", round(fi["mean"], 1)),
        ("sample_functions_median", fi["p50"]),
        ("sample_functions_p5", round(fi["p5"], 1)),
        ("sample_functions_p95", round(fi["p95"], 1)),
        ("sample_functions_min", fi["min"]),
        ("sample_functions_max", fi["max"]),
        ("sample_positives_mean", round(s["positives"]["positives_per_instance"]["mean"], 2)),
        ("sample_positives_median", s["positives"]["positives_per_instance"]["p50"]),
        (
            "sample_positives_found_in_corpus",
            f"{s['positives_found_in_corpus']} of {s['positives_total']}",
        ),
        ("sample_corpus_at_most_40_functions", s["instances_with_corpus_at_most_40_functions"]),
        ("base_commit_hits_with_verified", summary["base_commit_hits_with_verified"]),
        ("fetch_errors", summary["fetch_errors"]),
    ]
    return [{"quantity": k, "value": v} for k, v in rows]
