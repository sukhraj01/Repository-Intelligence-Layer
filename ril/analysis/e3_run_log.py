"""Counts-only run log for pilots E3 to E6 (configuration hashes, seeds, hardware, sizes).

Everything here is read from the cache and evaluation files; no text of any kind.
"""

from __future__ import annotations

import glob
import hashlib
import os
import platform
from collections import Counter
from typing import Any

from ril.evaluation.e3_eval import read_eval
from ril.evaluation.e3_prepare import read_cache

Record = dict[str, Any]


def file_sha256(path: str) -> str:
    """SHA-256 of a file's bytes."""
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def cache_summary(cache_dir: str) -> Record:
    """Sizes, timings, hardware and the agreement check of the per-instance caches."""
    by_role: Counter[str] = Counter()
    by_folder: Counter[str] = Counter()
    units = checked = mismatched = missing_gold = no_history = 0
    seconds = 0.0
    hosts: Counter[str] = Counter()
    hashes: set[str] = set()
    edge_totals: Counter[str] = Counter()
    for path in sorted(glob.glob(os.path.join(cache_dir, "*.npz"))):
        _, meta = read_cache(path)
        by_role[meta["role"]] += 1
        by_folder[meta["folder"]] += 1
        units += int(meta["units"])
        checked += int(meta["e1_rank_checked"])
        mismatched += int(meta["e1_rank_mismatch"])
        missing_gold += int(meta["gold_ids_not_in_units"])
        no_history += int(meta["units_without_history"])
        seconds += float(meta["seconds_total"])
        hosts[str(meta["hardware"].get("host"))] += 1
        hashes.add(str(meta["config_hash"]))
        for fam, n in meta["edge_pairs"].items():
            edge_totals[fam] += int(n)
    return {
        "instances_by_role": dict(by_role),
        "instances_by_folder": dict(sorted(by_folder.items())),
        "units_summed_over_snapshots": units,
        "bm25_ranks_compared_with_pilot_e1": checked,
        "bm25_rank_mismatches": mismatched,
        "gold_ids_not_in_units": missing_gold,
        "units_without_history": no_history,
        "prepare_seconds_summed": round(seconds, 1),
        "prepare_hosts": dict(hosts),
        "prepare_config_hashes": sorted(hashes),
        "edge_pairs_summed_over_snapshots": dict(sorted(edge_totals.items())),
    }


def eval_summary(eval_dir: str, config_path: str) -> Record:
    """Hash, size and query counts of one evaluation directory."""
    hashes: set[str] = set()
    queries: Counter[str] = Counter()
    keys = 0
    for path in sorted(glob.glob(os.path.join(eval_dir, "*.npz"))):
        info, arrays = read_eval(path)
        hashes.add(str(info["eval_hash"]))
        keys = max(keys, len(arrays["keys"]))
        for level in info["levels"]:
            queries[f"{info['role']}:{level}"] += 1
    return {
        "config_file": config_path,
        "config_file_sha256": file_sha256(config_path),
        "evaluation_hashes": sorted(hashes),
        "queries": dict(sorted(queries.items())),
        "keys_per_query": keys,
        "evaluated_on": platform.platform(),
        "python": platform.python_version(),
    }
