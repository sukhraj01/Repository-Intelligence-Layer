"""Tables of the stacked-expansion and L3 edge-set measurement G1: paired contrasts and query rows.

Exploratory. Reads the per-instance files of ``ril.evaluation.g1_stacked``. Every contrast is a
paired difference over queries (percentage points) with the cluster-robust t interval of D136
(``ril.analysis.cluster_t``: repository-clustered from three repositories, query-level below) and
the clustered and query-level percentile bootstrap beside it (``ril.analysis.e3_tables.Boot``,
D17). A difference is read as "beats the control" only when the t interval lies above 0; otherwise
a graph variant is reported as "does not beat control" (E-A-OWNER-ITEMS). Metrics: nDCG@10 at L2,
Recall@100 at L3; gold reading ``units_all_nomod`` (D18 primary) with ``units_all`` beside it.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from ril.analysis.cluster_t import cluster_t
from ril.analysis.e3_tables import COLUMN, Boot, EvalTable
from ril.analysis.x2_tables import BESIDE, LEVEL_METRIC, PRIMARY
from ril.evaluation.g1_stacked import PLAIN_VARIANTS, STACK_FAMILIES, STACK_N

Record = dict[str, Any]


def contrasts() -> list[tuple[str, str, str, str]]:
    """``(name, key a, key b, family)`` for every paired difference ``a - b``."""
    out: list[tuple[str, str, str, str]] = []
    for v in PLAIN_VARIANTS:
        out += [
            ("plain: graph - same-file", f"graph|{v}", f"sfscore|{v}", v),
            ("plain: graph - topm", f"graph|{v}", f"topm|{v}", v),
            ("plain: graph - random same-file", f"graph|{v}", f"sfrand|{v}", v),
            ("plain: same-file - topm", f"sfscore|{v}", f"topm|{v}", v),
            ("plain: graph - first stage", f"graph|{v}", "a_none", v),
            ("plain: same-file - first stage", f"sfscore|{v}", "a_none", v),
        ]
    out += [
        ("recency: prior - first stage", "recency", "a_none", "recency"),
        ("recency: prior - shuffled ages", "recency", "recencyshuf", "recency"),
        ("recency: prior - same-file", "recency", "sfscore|core", "recency"),
    ]
    for n in STACK_N:
        for f in STACK_FAMILIES:
            s = f"stack{n}|{f}"
            out += [
                (f"stacked N={n}: stacked - same-file", s, "ref|samefile", f),
                (f"stacked N={n}: stacked - topm swap", s, f"stacktopm{n}|{f}", f),
                (f"stacked N={n}: stacked - random swap", s, f"stackrand{n}|{f}", f),
                (f"stacked N={n}: topm swap - same-file", f"stacktopm{n}|{f}", "ref|samefile", f),
            ]
    return out


def contrast_rows(tab: EvalTable, group: str, seed: int = 0) -> tuple[list[Record], list[Record]]:
    """Contrast rows and per-repository rows for one group (role) of the table."""
    rows: list[Record] = []
    per_repo: list[Record] = []
    group_mask = np.asarray([r["role"] == group for r in tab.rows])
    for level, metric in LEVEL_METRIC.items():
        lmask = group_mask & np.asarray([r["level"] == level for r in tab.rows])
        for reading in (PRIMARY, BESIDE):
            j = COLUMN[(reading, metric)]
            base = tab.metrics[:, tab.index["a_none"], j]
            sel = np.flatnonzero(lmask & ~np.isnan(base))
            if len(sel) < 2:
                continue
            repos = [tab.rows[i]["repo"] for i in sel]
            boot = Boot(repos, seed)
            for name, ka, kb, fam in contrasts():
                d = 100 * (tab.metrics[sel, tab.index[ka], j] - tab.metrics[sel, tab.index[kb], j])
                ct = cluster_t(d, repos)
                lo, hi = ct.interval(0.05)
                _, cl_lo, cl_hi = boot.summarize(d[:, None], "cluster")
                _, q_lo, q_hi = boot.summarize(d[:, None], "micro")
                rows.append(
                    {
                        "group": group,
                        "level": level,
                        "metric": metric,
                        "gold_reading": reading,
                        "contrast": name,
                        "family": fam,
                        "a": ka,
                        "b": kb,
                        "queries": len(sel),
                        "repos": len(set(repos)),
                        "d": round(ct.d, 3),
                        "t_lo": round(lo, 3),
                        "t_hi": round(hi, 3),
                        "t_kind": ct.kind,
                        "df": ct.df,
                        "boot_cluster_lo": round(float(cl_lo[0]), 3),
                        "boot_cluster_hi": round(float(cl_hi[0]), 3),
                        "boot_query_lo": round(float(q_lo[0]), 3),
                        "boot_query_hi": round(float(q_hi[0]), 3),
                        "reading": "beats control" if lo > 0 else "does not beat control",
                    }
                )
                if reading != PRIMARY:
                    continue
                for repo in sorted(set(repos)):
                    m = np.asarray([r == repo for r in repos])
                    per_repo.append(
                        {
                            "group": group,
                            "level": level,
                            "metric": metric,
                            "contrast": name,
                            "family": fam,
                            "repo": repo,
                            "queries": int(m.sum()),
                            "d": round(float(d[m].mean()), 3),
                        }
                    )
    return rows, per_repo


def query_rows(tab: EvalTable, keys: list[str] | None = None) -> list[Record]:
    """Query-level values (percent) of every key, both readings, for the stored rows."""
    use = keys or tab.keys
    out: list[Record] = []
    for i, r in enumerate(tab.rows):
        metric = LEVEL_METRIC[r["level"]]
        for k in use:
            out.append(
                {
                    "instance": r["instance"],
                    "level": r["level"],
                    "repo": r["repo"],
                    "role": r["role"],
                    "key": k,
                    PRIMARY: round(
                        100 * float(tab.metrics[i, tab.index[k], COLUMN[(PRIMARY, metric)]]), 4
                    ),
                    BESIDE: round(
                        100 * float(tab.metrics[i, tab.index[k], COLUMN[(BESIDE, metric)]]), 4
                    ),
                }
            )
    return out


def size_rows(tab: EvalTable, group: str) -> list[Record]:
    """Mean list size, gold hits and in-file share per aux key, per level (primary reading)."""
    out: list[Record] = []
    for level in LEVEL_METRIC:
        mask = np.asarray([r["role"] == group and r["level"] == level for r in tab.rows])
        if not mask.any():
            continue
        for col, ak in enumerate(tab.aux_keys):
            sizes = tab.aux[mask, col, 0]
            out.append(
                {
                    "group": group,
                    "level": level,
                    "key": ak,
                    "queries": int(mask.sum()),
                    "mean_size": round(float(sizes.mean()), 3),
                    "mean_hits_units_all_nomod": round(float(tab.aux[mask, col, 4].mean()), 3)
                    if tab.aux.shape[2] > 4
                    else "",
                }
            )
    return out
