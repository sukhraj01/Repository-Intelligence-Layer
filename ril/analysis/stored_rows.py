"""Readers for the per-query rows kept under ``results/rq2/`` (E-STORED-ANALYSIS; exploratory).

A run directory holds ``config.yaml`` and ``query_rows.csv``; the dense column of the primary gold
reading is one value per (level, instance): nDCG@10 at L2 and Recall@100 at L3, as in the arms
tables. This module only reads and aligns; every statistic is in ``ril.analysis.stored_stats``.
The gold-set size and the kinds of a query's positives come from the per-instance unit files of
the BM25 development run (``data/processed/e1/out/units``), under the same reading
(``units_all`` without module ids), so a query's size is the denominator of its recall.

Implements docs/experiments/B.md "E-STORED-ANALYSIS".
"""

from __future__ import annotations

import csv
import json
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
import numpy.typing as npt

READING = "units_all_nomod"
METRIC_BY_LEVEL: Mapping[str, str] = {"L2": "ndcg10", "L3": "recall100"}
LEVELS: tuple[str, ...] = ("L2", "L3")
KINDS: tuple[str, ...] = ("function", "method", "class", "test_unit")
Key = tuple[str, str]
"""(level, instance)."""
FloatArray = npt.NDArray[np.float64]


@dataclass(frozen=True)
class Run:
    """One stored run: its cell id (``exp_id``), seed and directory."""

    cell: str
    seed: int
    directory: str


def _config_value(path: str, key: str) -> str:
    """Value of a top-level ``key: value`` line of a small YAML file (no parser needed)."""
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.startswith(key + ":"):
                return line.split(":", 1)[1].strip().strip("'\"")
    raise KeyError(f"{key} not in {path}")


def discover(results_root: str, cells: Sequence[str]) -> dict[str, list[Run]]:
    """Runs of each cell that have both ``config.yaml`` and ``query_rows.csv``, sorted by seed."""
    out: dict[str, list[Run]] = {}
    for cell in cells:
        base = os.path.join(results_root, cell)
        runs: list[Run] = []
        if os.path.isdir(base):
            for name in sorted(os.listdir(base)):
                d = os.path.join(base, name)
                cfg, rows = os.path.join(d, "config.yaml"), os.path.join(d, "query_rows.csv")
                if os.path.exists(cfg) and os.path.exists(rows):
                    runs.append(Run(cell, int(_config_value(cfg, "seed")), d))
        out[cell] = sorted(runs, key=lambda r: r.seed)
    return out


def read_dense(rows_path: str) -> dict[Key, tuple[str, float]]:
    """(level, instance) -> (repo, value) of the dense column; the level's primary metric only.

    Queries whose metric is empty (no gold unit under the reading) are left out."""
    out: dict[Key, tuple[str, float]] = {}
    with open(rows_path, encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            if r["role"] != "dev" or not r["name"].startswith("dense:"):
                continue
            level = r["level"]
            if level not in METRIC_BY_LEVEL:
                continue
            cell = r[f"{READING}:{METRIC_BY_LEVEL[level]}"]
            if cell == "":  # no gold unit under this reading: the metric is undefined, not 0
                continue
            out[(level, r["instance"])] = (r["repo"], float(cell))
    return out


def gold_info(units_dir: str, keys: Sequence[Key]) -> dict[Key, dict[str, Any]]:
    """Per query: gold-set size under ``units_all_nomod`` and the kinds of its positives."""
    out: dict[Key, dict[str, Any]] = {}
    cache: dict[str, dict[str, Any]] = {}
    for level, inst in keys:
        if inst not in cache:
            with open(os.path.join(units_dir, f"{inst}.json"), encoding="utf-8") as fh:
                cache[inst] = json.load(fh)
        gold: set[str] = set()
        kinds: set[str] = set()
        for p in cache[inst]["positives"]:
            if p["level"] != level:
                continue
            ids = {u for u in p["units_all"] if not u.endswith("::<module>")}
            if ids:
                gold |= ids
                kinds.add(p["kind"])
        out[(level, inst)] = {"n_pos": len(gold), "kinds": kinds}
    return out


@dataclass
class Panel:
    """Aligned per-query values: ``values[cell]`` is an array of shape (seeds, queries)."""

    keys: list[Key]
    repos: list[str]
    values: dict[str, FloatArray]
    seeds: dict[str, list[int]]

    def level_mask(self, level: str) -> npt.NDArray[np.bool_]:
        return np.array([k[0] == level for k in self.keys], dtype=bool)


def build_panel(
    runs: Mapping[str, Sequence[Run]],
    reference_keys: Sequence[Key] | None = None,
) -> Panel:
    """Align every run on the queries all of them have (or on ``reference_keys`` if given)."""
    loaded: dict[str, list[dict[Key, tuple[str, float]]]] = {}
    for cell, rs in runs.items():
        loaded[cell] = [read_dense(os.path.join(r.directory, "query_rows.csv")) for r in rs]
    common: set[Key] | None = None if reference_keys is None else set(reference_keys)
    for rows in loaded.values():
        for d in rows:
            common = set(d) if common is None else common & set(d)
    keys = sorted(common or set())
    repos: list[str] = []
    for rows in loaded.values():
        if rows:
            repos = [rows[0][k][0] for k in keys]
            break
    values = {
        cell: np.array([[d[k][1] for k in keys] for d in rows], dtype=np.float64)
        for cell, rows in loaded.items()
        if rows
    }
    seeds = {cell: [r.seed for r in runs[cell]] for cell in values}
    return Panel(keys, repos, values, seeds)
