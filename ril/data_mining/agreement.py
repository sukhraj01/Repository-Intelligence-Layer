"""Agreement of the mined positives with the published pool's positives (stage M1).

Implements ``docs/experiments/B.md`` E-MINE-PILOT question 1. For a pull request that is in both
sets (same repository and number) the mined positive set (function and method units that own a
changed old-side line) is compared with the pool's positive set (qrels score above 0), in two
readings: all positives, and positives outside test files. Differences are classified, never
hidden: a pool positive that the miner has in its side table (class or module unit), in its corpus
but not positive, or not in its corpus; a mined extra that lies in a test file or not.

Pure functions over ids and the mined ``pr_meta.json``; the pool side is fetched by the job layer.
Kept compatible with Python 3.10 (the cluster's compute nodes).
"""

from __future__ import annotations

import re
import statistics
from collections.abc import Mapping, Sequence
from typing import Any

from ril.parsing.path_rules import is_test_path

_PATH_RE = re.compile(r"^(?P<path>.*\.py)/")


def path_of(pool_id: str) -> str:
    """Repository-relative file path of a pool function id (``<path>.py/<qualified name>``)."""
    m = _PATH_RE.match(pool_id)
    return m.group("path") if m else pool_id


def is_test_id(pool_id: str) -> bool:
    """True if the id's file is a test file under the D9 path rule."""
    return is_test_path(path_of(pool_id))


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    """Jaccard index; two empty sets agree fully (1.0)."""
    return 1.0 if not a and not b else len(a & b) / len(a | b)


def _reading(ids: frozenset[str], reading: str) -> frozenset[str]:
    """The ids of one reading: ``all``, or ``non_test`` (outside test files)."""
    return ids if reading == "all" else frozenset(i for i in ids if not is_test_id(i))


def compare_pr(
    meta: Mapping[str, Any],
    mined_corpus_ids: frozenset[str],
    pool_positives: frozenset[str],
    pool_corpus_ids: frozenset[str],
) -> dict[str, Any]:
    """One row: sets, agreement in both readings and the classification of every difference."""
    positives = list(meta["positives"])
    mined = frozenset(str(p["pool_id"]) for p in positives if p["in_corpus"])
    side = frozenset(str(p["pool_id"]) for p in positives if not p["in_corpus"])
    out: dict[str, Any] = {
        "repo": meta["repo"],
        "pr": meta["pr"],
        "mined": len(mined),
        "pool": len(pool_positives),
    }
    for reading in ("all", "non_test"):
        a = _reading(mined, reading)
        b = _reading(pool_positives, reading)
        out[reading] = {
            "mined": len(a),
            "pool": len(b),
            "exact": a == b,
            "jaccard": round(jaccard(a, b), 6),
            "extra": sorted(a - b),
            "missing": sorted(b - a),
        }
    missing_all = pool_positives - mined
    out["missing_why"] = {
        i: (
            "in_mined_side_table"
            if i in side
            else "in_mined_corpus_not_positive"
            if i in mined_corpus_ids
            else "not_in_mined_corpus"
        )
        for i in sorted(missing_all)
    }
    out["extra_why"] = {
        i: ("test_file" if is_test_id(i) else "non_test_file")
        for i in sorted(mined - pool_positives)
    }
    out["matched"] = sorted(mined & pool_positives)
    out["extra_in_pool_corpus"] = sorted(i for i in mined - pool_positives if i in pool_corpus_ids)
    union = mined_corpus_ids | pool_corpus_ids
    out["corpus_jaccard"] = round(
        len(mined_corpus_ids & pool_corpus_ids) / len(union) if union else 1.0, 6
    )
    return out


def summarize(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """The agreement table: exact-match share, mean Jaccard, extras and missing, both readings."""
    out: dict[str, Any] = {"prs_compared": len(rows)}
    for reading in ("all", "non_test"):
        cells = [r[reading] for r in rows]
        n = len(cells)
        out[reading] = {
            "exact_share": sum(1 for c in cells if c["exact"]) / n if n else 0.0,
            "jaccard_mean": round(statistics.fmean(c["jaccard"] for c in cells), 4) if n else 0.0,
            "jaccard_median": statistics.median(c["jaccard"] for c in cells) if n else 0.0,
            "extra_total": sum(len(c["extra"]) for c in cells),
            "missing_total": sum(len(c["missing"]) for c in cells),
            "prs_with_extra": sum(1 for c in cells if c["extra"]),
            "prs_with_missing": sum(1 for c in cells if c["missing"]),
        }
    why: dict[str, int] = {}
    for r in rows:
        for v in r["missing_why"].values():
            why[v] = why.get(v, 0) + 1
    out["missing_why"] = dict(sorted(why.items()))
    ex: dict[str, int] = {}
    for r in rows:
        for v in r["extra_why"].values():
            ex[v] = ex.get(v, 0) + 1
    out["extra_why"] = dict(sorted(ex.items()))
    out["pool_positives_in_test_files"] = sum(
        1 for r in rows for i in [*r["matched"], *r["all"]["missing"]] if is_test_id(i)
    )
    out["pool_positives_total"] = sum(r["pool"] for r in rows)
    return out


def mined_test_share(metas: Sequence[Mapping[str, Any]]) -> dict[str, float | int]:
    """Share of mined positives (corpus functions) in test files over mined directories (D69)."""
    total = 0
    in_test = 0
    for m in metas:
        for p in m["positives"]:
            if p["in_corpus"]:
                total += 1
                in_test += 1 if p["is_test"] else 0
    return {
        "mined_positives": total,
        "in_test_files": in_test,
        "share": in_test / total if total else 0.0,
    }
