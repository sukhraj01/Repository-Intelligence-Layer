"""Tables of the encoder numbers E7 (exploratory): paired encoder difference and class form.

Rows carry the mean over queries (D17) with query-level and repository-clustered bootstrap
intervals (2,000 draws) for the value and for the paired difference against a stated reference;
see ``ril.analysis.x2_tables.paired_rows``. Values are percentages; differences points.
"""

from __future__ import annotations

from ril.analysis.e3_tables import load_eval_dir
from ril.analysis.x2_tables import Record, unit_rows, write_csv
from ril.evaluation.e7_encoders import ENCODERS_FIXED, form_table, per_repo_diff

CRE, QW = "coderankembed", "qwen3-embedding-0.6b"
LEVEL_METRIC = (("L2", "ndcg10"), ("L3", "recall100"))


def write_pair(eval_dir: str, group: str, prefix: str, seed: int) -> int:
    """RRF(BM25, Qwen3) minus RRF(BM25, CodeRankEmbed), plus the per-repository differences."""
    tab = load_eval_dir(eval_dir)
    rcre = f"rrf|{ENCODERS_FIXED[CRE][0]}|k{ENCODERS_FIXED[CRE][1]}"
    rqw = f"rrf|{ENCODERS_FIXED[QW][0]}|k{ENCODERS_FIXED[QW][1]}"
    dcre, dqw = f"dense|{ENCODERS_FIXED[CRE][0]}", f"dense|{ENCODERS_FIXED[QW][0]}"
    rows = unit_rows(
        tab,
        group,
        [
            ("rrf_cre", rcre, None),
            ("rrf_qwen3", rqw, "rrf_cre"),
            ("dense_cre", dcre, None),
            ("dense_qwen3", dqw, "dense_cre"),
            ("bm25", "bm25", None),
        ],
        seed,
    )
    rows = [r for r in rows if (r["level"], r["metric"]) in LEVEL_METRIC]
    repo: list[Record] = []
    for level, metric in LEVEL_METRIC:
        for reading in ("units_all_nomod", "units_all"):
            repo += per_repo_diff(tab, group, rqw, rcre, level, reading, metric)
    write_csv(f"{prefix}_pair.csv", rows)
    write_csv(f"{prefix}_pair_repos.csv", repo)
    return len(rows) + len(repo)


def write_form(
    e3_cache: str, x1_cache: str, dense_root: str, role: str, prefix: str, seed: int
) -> int:
    """Class form ``header`` against ``full`` for BM25, dense alone and RRF, per encoder."""
    tab = form_table(e3_cache, x1_cache, dense_root, role)
    rows: list[Record] = []
    for enc in ENCODERS_FIXED:
        for kind in ("dense", "rrf"):
            cols = [
                ("full", f"{kind}|{enc}|full", None),
                ("header", f"{kind}|{enc}|header", "full"),
            ]
            for r in unit_rows(tab, role, cols, seed):
                if (r["level"], r["metric"]) in LEVEL_METRIC:
                    rows.append({**r, "encoder": enc, "kind": kind})
    for r in unit_rows(
        tab, role, [("full", "bm25|full", None), ("header", "bm25|header", "full")], seed
    ):
        if (r["level"], r["metric"]) in LEVEL_METRIC:
            rows.append({**r, "encoder": "", "kind": "bm25"})
    write_csv(f"{prefix}_form_{role}.csv", rows)
    return len(rows)
