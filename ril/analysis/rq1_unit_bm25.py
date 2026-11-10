"""Tables of the unit-level BM25 variants (D119, E-FREEZE-AND-LATENCY).

Reads the evaluation files of ``ril.evaluation.unit_bm25`` (development set only). Percentages;
differences are percentage points. Intervals as in ``ril.analysis.rq1_ladder``: the cluster-robust t
interval over repositories decides (L3 has two repositories, so it is query-level and marked), the
repository bootstrap beside it. Every cell is paired with the control on the query, alone
(``bm25|c`` minus ``bm25|control``) and inside the fusion (``rrf|c`` minus ``rrf|control``).

Kept compatible with Python 3.10.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

import numpy as np

from ril.analysis import rq1_ladder as lad
from ril.analysis.e3_tables import DRAWS, Boot, EvalTable
from ril.evaluation.unit_bm25 import CELLS, CONTROL, all_keys

Record = dict[str, Any]


def check_keys(tab: EvalTable) -> None:
    if tab.keys != all_keys():
        raise ValueError("key layout differs from unit_bm25.all_keys()")


def compare_rows(tab: EvalTable, seed: int = 0, draws: int = DRAWS) -> list[Record]:
    """Every non-control cell against the control, alone and fused, per level, reading, metric."""
    rows: list[Record] = []
    for level in ("L2", "L3"):
        for reading in lad.READINGS_SHOWN:
            idx, repos = lad.level_panel(tab, level, reading)
            if idx.size < 2:
                continue
            boot = Boot(repos, seed, draws)
            for cell in CELLS:
                if cell.name == CONTROL.name:
                    continue
                for kind in ("bm25", "rrf"):
                    for metric in lad.METRICS:
                        d = lad._vector(tab, idx, f"{kind}|{cell.name}", reading, metric) - (
                            lad._vector(tab, idx, f"{kind}|{CONTROL.name}", reading, metric)
                        )
                        f = lad.interval_fields(d, repos, boot)
                        rows.append(
                            {
                                "level": level,
                                "reading": reading,
                                "metric": metric,
                                "primary": metric == lad.LEVEL_PRIMARY[level]
                                and reading == lad.PRIMARY_READING,
                                "cell": cell.name,
                                "where": "alone" if kind == "bm25" else "fused",
                                **f,
                                "verdict": lad.verdict(f["t_lo"], f["t_hi"]),
                            }
                        )
    return rows


def best_cell(tab: EvalTable) -> str:
    """Rule of the configuration: best mean L2 nDCG@10 of BM25 alone among the non-control cells."""
    idx, _ = lad.level_panel(tab, "L2", lad.PRIMARY_READING)
    best, best_v = "", -1.0
    for cell in CELLS:
        if cell.name == CONTROL.name:
            continue
        v = float(lad._vector(tab, idx, f"bm25|{cell.name}", lad.PRIMARY_READING, "ndcg10").mean())
        if v > best_v:
            best, best_v = cell.name, v
    return best


def value_rows(tab: EvalTable, seed: int = 0, draws: int = DRAWS) -> list[Record]:
    return lad.summary_rows(tab, "unit_bm25", seed, draws)


def regression_rows(
    tab: EvalTable, ladder_summary: list[Record], tol: float = 0.005
) -> list[Record]:
    """Control cells against the stored ladder values of the same instances.

    ``bm25|control`` is the ladder's ``ref|bm25``, ``rrf|control`` its ``p|first`` (rung 2),
    ``dense`` its ``r1|dense``; same queries and scores, so they must agree.
    """
    pairs = (("bm25|control", "ref|bm25"), ("rrf|control", "p|first"), ("dense", "r1|dense"))
    out: list[Record] = []
    for level in ("L2", "L3"):
        idx, _ = lad.level_panel(tab, level, lad.PRIMARY_READING)
        metric = lad.LEVEL_PRIMARY[level]
        for key, ladder_key in pairs:
            want = [
                r
                for r in ladder_summary
                if r["level"] == level
                and r["reading"] == lad.PRIMARY_READING
                and r["metric"] == metric
                and r["key"] == ladder_key
            ]
            if not want:
                continue
            ref = float(want[0]["mean"])
            got = float(lad._vector(tab, idx, key, lad.PRIMARY_READING, metric).mean())
            out.append(
                {
                    "level": level,
                    "metric": metric,
                    "key": key,
                    "ladder_key": ladder_key,
                    "ladder_queries": int(want[0]["n"]),
                    "queries": int(idx.size),
                    "ladder": round(ref, 4),
                    "recomputed": round(got, 4),
                    "abs_diff": round(abs(got - ref), 4),
                    "reproduces": abs(got - ref) <= tol and int(want[0]["n"]) == int(idx.size),
                }
            )
    return out


def sha256_text(rows_text: str) -> str:
    return hashlib.sha256(rows_text.encode("utf-8")).hexdigest()


def sizes(tab: EvalTable) -> Record:
    """Instances, queries and repositories behind the tables."""
    return {
        "instances": len({r["instance"] for r in tab.rows}),
        "queries": {lv: int(tab.mask(level=lv).sum()) for lv in ("L2", "L3")},
        "repos": {
            lv: len({r["repo"] for r, m in zip(tab.rows, tab.mask(level=lv), strict=True) if m})
            for lv in ("L2", "L3")
        },
        "keys": len(tab.keys),
    }


def dump(path: str, doc: Record) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(
            doc,
            fh,
            indent=1,
            sort_keys=True,
            default=lambda o: float(o) if isinstance(o, np.floating) else str(o),
        )
        fh.write("\n")
