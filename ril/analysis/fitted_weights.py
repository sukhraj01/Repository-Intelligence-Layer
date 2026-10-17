"""Edge-family weights fitted from data (pilot E4, exploratory).

Two ways to turn data into one weight per edge family, both scaled so that the best family gets
the hand-set decay ``gamma0`` (the weights are then directly comparable with the hand-set decay of
pilot E3, which gives every family ``gamma0``):

* ``fit_from_reach``: from the graph-reach table of pilot M (``results/tables/m_reach.csv``): how
  often a new L3 positive lies within ``hop`` hops of the L2 units over the family alone
  (``statistic='reach'``), or how much more often than random units of the same files
  (``statistic='excess'``, negative values count as 0). Fitted on the three pilot-M repositories.
* ``fit_from_precision``: from the expansions of pilot E3: the share of the units that a family
  alone adds that are gold units, summed over the queries of the fitting repositories.

A family whose statistic is 0 gets weight 0, i.e. it is not traversed.
"""

from __future__ import annotations

import csv
from collections.abc import Mapping
from typing import Any

import numpy as np

from ril.analysis.e3_tables import EvalTable

REACH_SUBSET = {
    "contain": "contain",
    "import": "import",
    "invoke": "invoke_both",
    "inherit": "inherit",
    "tests": "tests",
    "configures": "configures",
    "co_change": "co_change_n3",
}
"""Family of the expansion engine -> edge subset name in the reach table."""


def scale_to_gamma(stat: Mapping[str, float], gamma0: float) -> dict[str, float]:
    """Divide by the best family and multiply by ``gamma0`` (all zero stays all zero)."""
    top = max(stat.values(), default=0.0)
    if top <= 0:
        return {f: 0.0 for f in stat}
    return {f: round(gamma0 * max(v, 0.0) / top, 4) for f, v in stat.items()}


def fit_from_reach(
    csv_path: str, *, hop: str = "le2", statistic: str = "reach", gamma0: float = 0.5
) -> dict[str, float]:
    """Weights from the primary, all-Python rows of the reach table."""
    if statistic not in ("reach", "excess"):
        raise ValueError("statistic must be 'reach' or 'excess'")
    with open(csv_path, encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    stat: dict[str, float] = {}
    for fam, sub in REACH_SUBSET.items():
        match = [
            r
            for r in rows
            if r["analysis"] == "primary"
            and r["group"] == "all_python"
            and r["subset"] == sub
            and r["hop"] == hop
            and r["control"] == "same_files"
        ]
        if len(match) != 1:
            raise ValueError(f"expected one reach row for {fam} ({sub}), found {len(match)}")
        col = "obs_share" if statistic == "reach" else "difference"
        stat[fam] = max(float(match[0][col]), 0.0)
    return scale_to_gamma(stat, gamma0)


def fit_from_precision(
    tab: EvalTable,
    rows_mask: np.ndarray[Any, Any],
    *,
    families: tuple[str, ...],
    seeds: int,
    gamma: float,
    hops: int,
    gamma0: float = 0.5,
) -> dict[str, float]:
    """Weights from the share of added units that are gold (reading ``units``), pooled over rows."""
    stat: dict[str, float] = {}
    for fam in families:
        key = f"E|{fam}|C{seeds}|g{gamma}|h{hops}"
        j = tab.aux_keys.index(key)
        size = float(tab.aux[rows_mask, j, 0].sum())
        hits = float(tab.aux[rows_mask, j, 1].sum())
        stat[fam] = hits / size if size > 0 else 0.0
    return scale_to_gamma(stat, gamma0)
