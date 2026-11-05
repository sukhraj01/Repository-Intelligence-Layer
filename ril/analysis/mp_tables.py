"""Tables of the mined-set integration pilot (E-MINED-PILOT; exploratory, not an RQ table).

Builds on ``ril.analysis.t2_tables`` (paired queries, percentage points, repository-clustered and
query-level bootstrap intervals, seeds averaged for the cell effect and shown beside it),
``ril.analysis.t5_tables.unique_rows`` (the unique-example table of D42) and
``ril.analysis.stored_stats`` (variance components and minimum detectable differences). What is
specific here:

* RAW on the mined set against RAW on the published pool of Wave 6 (the primary reading, D92 (ii));
* FILTER-BM25 against RAW and against the size-matched subsample, both on the mined set (D92 (iii));
* the minimum detectable difference at two seeds, with and without the repository term (D92 (iv)),
  for FILTER against RAW and against the subsample, from the per-query rows of the mined cells.

Implements ``docs/experiments/B.md`` "E-MINED-PILOT". Kept compatible with Python 3.10.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from typing import Any

import numpy as np

from ril.analysis import stored_rows as sr
from ril.analysis import stored_stats as ss
from ril.analysis import t2_tables as tt
from ril.analysis import t4_tables as t4
from ril.analysis import t5_tables as t5
from ril.analysis.x2_tables import write_csv

Record = dict[str, Any]
MP_TABLES_VERSION = "mp-tables/v1"
MINED_RAW = "mp_raw"
MINED_FILTER = "mp_filter_bm25"
MINED_SUB = "mp_sub"
POOL_RAW = "t5a_raw"
MINED_CELLS = (MINED_RAW, MINED_FILTER, MINED_SUB)


def effect_tables(
    results_root: str, step0_rows: str, out_dir: str, seed: int = 0
) -> tuple[list[Record], list[Record], list[Record]]:
    """Effects, seed spread and unique-example rows; each written as a table under ``out_dir``."""
    conds = {c: tt.load_condition(results_root, c) for c in (*MINED_CELLS, POOL_RAW)}
    for runs in conds.values():
        t4.attach_base(runs, step0_rows)
    effects: list[Record] = []
    spread: list[Record] = []
    for ref in (POOL_RAW, MINED_RAW, MINED_SUB):
        if not conds[ref]:
            continue
        for kind in ("dense", "rrf"):
            for level in ("L2", "L3"):
                for reading in tt.READINGS:
                    effects += tt.contrast_rows(
                        conds,
                        ref,
                        kind=kind,
                        level=level,
                        reading=reading,
                        seed=seed,
                        labels={"pilot": "mp", "reference": ref, "exploratory": True},
                    )
    for kind in ("dense", "rrf"):
        for level in ("L2", "L3"):
            for reading in tt.READINGS:
                spread += tt.seed_spread(conds, kind=kind, level=level, reading=reading)
    uniq = t5.unique_rows({c: r for c, r in conds.items() if r})
    os.makedirs(out_dir, exist_ok=True)
    write_csv(os.path.join(out_dir, "mp_effects.csv"), effects)
    write_csv(os.path.join(out_dir, "mp_seeds.csv"), spread)
    write_csv(os.path.join(out_dir, "mp_unique.csv"), uniq)
    return effects, spread, uniq


def minimum_detectable_rows(
    results_root: str, out_dir: str, seeds: Sequence[int] = (2,), draws: int = 300, seed: int = 0
) -> list[Record]:
    """Minimum detectable paired difference of FILTER against RAW and against the subsample.

    5% two-sided, 80% power, from the variance components of the per-query seed-matched
    differences of the mined cells (unit-level reading ``units_all_nomod``, dense column); with and
    without the repository term; repository-resample interval of the point value at L2.
    """
    runs = sr.discover(results_root, list(MINED_CELLS))
    panel = sr.build_panel(runs)
    rows: list[Record] = []
    for level in sr.LEVELS:
        mask = panel.level_mask(level)
        repo = ss.repo_index([r for r, k in zip(panel.repos, mask, strict=True) if k])
        view = {c: v[:, mask] for c, v in panel.values.items()}
        for ref in (MINED_RAW, MINED_SUB):
            k_pair = min(view[MINED_FILTER].shape[0], view[ref].shape[0])
            diff = view[MINED_FILTER][:k_pair] - view[ref][:k_pair]
            comp = ss.components(diff, repo)
            for k in seeds:
                for with_repo in (True, False):
                    point = ss.minimum_detectable(comp, k, with_repo)
                    rng = np.random.default_rng(seed)
                    boots = []
                    for _ in range(draws):
                        idx = ss.cluster_resample(repo, rng)
                        boots.append(
                            ss.minimum_detectable(
                                ss.components(diff[:, idx], repo[idx]), k, with_repo
                            )
                        )
                    lo, hi = ss.interval([b for b in boots if b == b])
                    rows.append(
                        {
                            "level": level,
                            "contrast": f"{MINED_FILTER} - {ref}",
                            "seeds_per_arm": k,
                            "variant": "with_repo_term" if with_repo else "query_level",
                            "mdd_points": round(100 * point, 2),
                            "lo": round(100 * lo, 2),
                            "hi": round(100 * hi, 2),
                            "queries": int(mask.sum()),
                            "repos": int(len(np.unique(repo))),
                            "seed_pairs": k_pair,
                            "exploratory": True,
                        }
                    )
    os.makedirs(out_dir, exist_ok=True)
    write_csv(os.path.join(out_dir, "mp_mdd.csv"), rows)
    return rows
