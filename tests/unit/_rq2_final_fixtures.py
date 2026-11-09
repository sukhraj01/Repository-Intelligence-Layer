"""Synthetic per-query rows with a known effect for the tests of ``ril.analysis.rq2_final``.

Values are fractions around 0.5; the true paired difference of the effect cells against the
reference is ``effect`` points on average, with an optional repository-level spread ``tau`` of the
effect (the clustered case) and per-seed and per-seed-by-query noise. Nothing here is a result.
"""

from __future__ import annotations

from typing import Any

import numpy as np

CELLS = ("mined_raw", "mined_sub", "mined_filter_bm25")


def synthetic_rows(
    *,
    effects: dict[str, float],
    seed: int,
    repos: int = 12,
    per_repo: int = 25,
    seeds: int = 3,
    tau: float = 0.0,
    sd_repo: float = 0.05,
    sd_query: float = 0.10,
    sd_seed_query: float = 0.02,
    eval_set: str = "dev",
    levels: tuple[str, ...] = ("L2", "L3"),
    cells: tuple[str, ...] = CELLS,
) -> list[dict[str, Any]]:
    """Rows for ``cells``; ``effects[cell]`` (points) is added to the cell's mean, 0 if absent."""
    rng = np.random.default_rng(seed)
    rows: list[dict[str, Any]] = []
    for level in levels:
        repo_shift = rng.normal(0, sd_repo, repos)
        repo_effect = rng.normal(0, tau / 100.0, repos)
        for r in range(repos):
            for qn in range(per_repo):
                base = 0.5 + repo_shift[r] + rng.normal(0, sd_query)
                for cell in cells:
                    mean = base
                    if cell in effects:
                        mean += effects[cell] / 100.0 + repo_effect[r]
                    for s in range(seeds):
                        v = float(np.clip(mean + rng.normal(0, sd_seed_query), 0.0, 1.0))
                        rows.append(
                            {
                                "run_id": f"{cell}_s{s}",
                                "cell": cell,
                                "seed": 100 + s,
                                "eval_set": eval_set,
                                "level": level,
                                "repo": f"org/repo{r:02d}",
                                "query_id": f"{level}-r{r:02d}-q{qn:03d}",
                                "n_positives": 1 + qn % 3,
                                "ndcg10": v,
                                "recall100": float(np.clip(v + 0.1, 0.0, 1.0)),
                            }
                        )
    return rows


def run_table(rows: list[dict[str, Any]], distinct: int = 3200) -> list[dict[str, Any]]:
    """One diagnostics row per (cell, seed) of ``rows``."""
    seen = sorted({(r["cell"], r["seed"], r["run_id"]) for r in rows})
    return [
        {
            "run_id": rid,
            "cell": c,
            "seed": s,
            "config_hash": f"hash-{rid}",
            "optimizer_updates": 100,
            "examples_seen": 3200,
            "distinct_directories_seen": distinct,
            "pool_examples": 5000,
        }
        for c, s, rid in seen
    ]
