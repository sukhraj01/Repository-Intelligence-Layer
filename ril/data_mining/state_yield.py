"""Yield of a mining store from its state log alone, against gate G2 (no directory is opened).

Implements ``docs/RQ2_LAUNCH_PLAN.md`` stage 1 and ``docs/RQ2_PROTOCOL.md`` O10 (G2: at least
10,000 positives at full scale). ``report`` needs the ``summary.json`` a finished session writes;
this reads ``state.jsonl`` (one row per attempted pull request), so it works while a run is going,
after a session that stopped on a fault, and on a store converted from a run root. Positives here
are the unrestricted count of the miner (``counters.positives``); the ``non_test`` primary reading
(D96) and the ``pool_aligned`` sensitivity reading need the materialised directories and are counted
by ``rank-prepare``. Kept compatible with Python 3.10.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable, Mapping
from typing import Any

G2_POSITIVES = 10_000
G2_PILOT_DIRECTORIES = 100


def read_state(path: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def reason_class(reason: str) -> str:
    """``snapshot_timeout`` and ``corpus_error:<Class>`` keep their name; others lose the detail."""
    head, _, tail = reason.partition(":")
    if head in ("corpus_error", "changed_file_unparseable"):
        return f"{head}:{tail}" if tail else head
    return head or "unspecified"


def yield_report(
    rows: Iterable[Mapping[str, Any]], *, target_attempted: int | None = None
) -> dict[str, Any]:
    """Counts, quarantine by reason class, positives and a linear projection to the target."""
    rows = list(rows)
    n = len(rows)
    status = Counter(r["status"] for r in rows)
    mined = [r for r in rows if r["status"] == "mined"]
    positives = [int((r.get("counters") or {}).get("positives", 0)) for r in mined]
    reasons = Counter(
        reason_class(str(r.get("reason", ""))) for r in rows if r["status"] == "quarantined"
    )
    repos = Counter(str(r["key"]).split("#")[0] for r in rows)
    out: dict[str, Any] = {
        "attempted": n,
        "status": dict(sorted(status.items())),
        "mined_share": round(len(mined) / n, 4) if n else None,
        "quarantined_share": round(status["quarantined"] / n, 4) if n else None,
        "quarantine_by_reason": dict(sorted(reasons.items(), key=lambda kv: (-kv[1], kv[0]))),
        "timeout_quarantined": int(reasons.get("snapshot_timeout", 0)),
        "mined_with_positive": sum(1 for p in positives if p > 0),
        "positives_unrestricted": sum(positives),
        "positives_per_mined": round(sum(positives) / len(mined), 2) if mined else None,
        "repositories_seen": len(repos),
        "largest_repositories": repos.most_common(5),
    }
    if target_attempted and n:
        f = target_attempted / n
        proj = round(sum(positives) * f)
        out["projection"] = {
            "target_attempted": target_attempted,
            "basis": "linear in the rows so far (seeded hash order: a prefix is a sample)",
            "mined": round(len(mined) * f),
            "positives_unrestricted": proj,
            "g2_positives": G2_POSITIVES,
            "g2_met_unrestricted": proj >= G2_POSITIVES,
        }
    out["g2_pilot_directories_met"] = out["mined_with_positive"] >= G2_PILOT_DIRECTORIES
    return out
