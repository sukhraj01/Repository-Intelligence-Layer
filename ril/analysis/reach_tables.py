"""Tables of pilot M (chunk-to-unit mapping and graph reach) from its per-instance records.

Implements the reporting side of the pilot in ``docs/EXPERIMENTS.md`` (E-GRAPH-REACH). Reads
the records written by ``ril.evaluation.chunk_unit_pilot`` (ids, paths, lines and unit ids; no
chunk text) and writes counts and intervals only.

Reach is reported as the share of new L3 positives within 1, 2 and 3 hops of the L2 positive
units, and the share with no path at all, next to three random controls, as the difference
``observed - chance`` and the ratio ``observed / chance`` with 95% bootstrap intervals. Two
bootstraps are given: over positives (treats them as independent) and over instances (the
positives of an instance are correlated: they answer one issue). With seven instances the
second is the honest one and it is wide. Everything here is a pilot: small n, exploratory.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Sequence
from typing import Any

import numpy as np

from ril.evaluation.chunk_mapping import KINDS
from ril.evaluation.graph_reach import CONTROLS, HOP_LIMITS, SUBSETS

Record = dict[str, Any]

WAVE1_REFERENCE: dict[str, int] = {
    "one_leaf_unit": 111,
    "two_plus_leaf_units": 28,
    "class_only": 5,
    "zero_units": 16,
}
"""Counts of the first label sample (160 positives of the same six folders)."""

BOOTSTRAP_DRAWS = 2000
SMALL_N = 10
PYTHON_UNIT_KINDS: tuple[str, ...] = ("function", "method", "class", "module_residual", "test_unit")
HOPS: tuple[str, ...] = tuple(f"le{h}" for h in HOP_LIMITS) + ("unreachable",)


def all_positives(instances: Sequence[Record]) -> list[Record]:
    """Every positive record with its instance and repository attached."""
    out: list[Record] = []
    for inst in instances:
        for rec in inst["positives"]:
            out.append({**rec, "instance": inst["instance"], "repo": inst["repo_id"]})
    return out


# --------------------------------------------------------------------------- mapping tables


def match_rows(instances: Sequence[Record]) -> list[Record]:
    """Match status per (repository, level) and in total: tiers and failure reasons."""
    recs = all_positives(instances)
    keys = sorted({(r["repo"], r["level"]) for r in recs})
    groups: list[tuple[str, str, list[Record]]] = [
        (repo, level, [r for r in recs if r["repo"] == repo and r["level"] == level])
        for repo, level in keys
    ]
    for level in sorted({lv for _, lv in keys}):
        groups.append(("all", level, [r for r in recs if r["level"] == level]))
    groups.append(("all", "L2+L3", recs))
    rows: list[Record] = []
    for repo, level, rs in groups:
        found = [r for r in rs if r["status"] == "found"]
        row: Record = {
            "repo": repo,
            "level": level,
            "positives": len(rs),
            "found": len(found),
            "found_unique": sum(1 for r in found if r["n_locations"] == 1),
            "found_several_locations": sum(1 for r in found if r["n_locations"] > 1),
            "several_in_one_file": sum(
                1 for r in found if r["n_locations"] > 1 and r["n_files"] == 1
            ),
            "not_found": sum(1 for r in rs if r["status"] == "not_found"),
            "empty_chunk": sum(1 for r in rs if r["status"] == "empty"),
        }
        for tier in ("exact", "trimmed", "eol_normalised", "whitespace_normalised"):
            row[f"tier_{tier}"] = sum(1 for r in found if r["tier"] == tier)
        reasons = Counter(r["reason"] for r in rs if r["status"] != "found")
        row["failure_reasons"] = ";".join(f"{k}={v}" for k, v in sorted(reasons.items()))
        row["match_rate"] = round(len(found) / len(rs), 4) if rs else None
        rows.append(row)
    return rows


def category_rows(instances: Sequence[Record]) -> list[Record]:
    """Span-to-unit categories under the frozen units and under the first sample's rule.

    ``frozen_*``: the frozen units (nested definitions folded into their parent, decision D6).
    ``rule1_*``: the first sample's rule (every nested definition is a leaf unit). ``*_full``:
    the whole chunk span; ``*_prefix``: only its first 200 characters. Comparison with the first
    sample's 111 / 28 / 5 / 16 of 160 is ``rule1_full`` (like for like) and ``frozen_full``.
    """
    recs = all_positives(instances)
    located = [r for r in recs if r["status"] == "found"]
    views = {
        name: Counter(r["views"][key] for r in located)
        for name, key in (
            ("frozen_full", "d6_full"),
            ("frozen_prefix", "d6_prefix"),
            ("rule1_full", "wave1_full"),
            ("rule1_prefix", "wave1_prefix"),
        )
    }
    mapping = [
        ("one_unit", "one_leaf_unit"),
        ("several_units", "two_plus_leaf_units"),
        ("class_only", "class_only"),
        ("module_residual", "zero_units"),
        ("none", ""),
    ]
    rows: list[Record] = []
    for d6_name, w1_name in mapping:
        rows.append(
            {
                "category": d6_name,
                "first_sample_name": w1_name,
                "first_sample_of_160": WAVE1_REFERENCE.get(w1_name) if w1_name else None,
                "rule1_full": views["rule1_full"].get(w1_name, 0) if w1_name else None,
                "rule1_prefix": views["rule1_prefix"].get(w1_name, 0) if w1_name else None,
                "frozen_full": views["frozen_full"].get(d6_name, 0),
                "frozen_prefix": views["frozen_prefix"].get(d6_name, 0),
            }
        )
    rows.append(
        {
            "category": "total_located",
            "first_sample_name": "",
            "first_sample_of_160": sum(WAVE1_REFERENCE.values()),
            "rule1_full": sum(views["rule1_full"].values()),
            "rule1_prefix": sum(views["rule1_prefix"].values()),
            "frozen_full": sum(views["frozen_full"].values()),
            "frozen_prefix": sum(views["frozen_prefix"].values()),
        }
    )
    rows.append(
        {
            "category": "also_overlaps_residual_lines",
            "frozen_full": sum(
                1 for r in located if r["overlaps_residual"] and r["category"] != "module_residual"
            ),
        }
    )
    return rows


def category_folder_rows(
    instances: Sequence[Record], reference: dict[str, dict[str, int]]
) -> list[Record]:
    """Per (level, repository) folder: the first sample's counts next to the recomputed ones.

    ``reference`` maps ``LEVEL-n/owner__name`` to the first sample's per-folder counts
    (``one_leaf_unit``, ``two_plus_leaf_units``, ``class_only``, ``zero_units``).
    """
    recs = [r for r in all_positives(instances) if r["status"] == "found"]
    rows: list[Record] = []
    keys = sorted({(r["level"], r["repo"]) for r in recs})
    for level, repo in keys:
        folder = f"LEVEL-{level[1]}/{repo.replace('/', '__')}"
        ref = reference.get(folder, {})
        rs = [r for r in recs if r["level"] == level and r["repo"] == repo]
        rule1 = Counter(r["views"]["wave1_full"] for r in rs)
        frozen = Counter(r["views"]["d6_full"] for r in rs)
        for w1, d6 in (
            ("one_leaf_unit", "one_unit"),
            ("two_plus_leaf_units", "several_units"),
            ("class_only", "class_only"),
            ("zero_units", "module_residual"),
        ):
            rows.append(
                {
                    "folder": folder,
                    "category": d6,
                    "positives": len(rs),
                    "first_sample": ref.get(w1),
                    "rule1_full": rule1.get(w1, 0),
                    "frozen_full": frozen.get(d6, 0),
                }
            )
    return rows


def kind_rows(instances: Sequence[Record]) -> list[Record]:
    """Positives by kind, per level and repository; L3 is the table the brief asks for."""
    recs = all_positives(instances)
    rows: list[Record] = []
    for level in ("L2", "L3"):
        for repo in sorted({r["repo"] for r in recs}) + ["all"]:
            rs = [r for r in recs if r["level"] == level and (repo == "all" or r["repo"] == repo)]
            if not rs:
                continue
            counts = Counter(r["kind"] for r in rs)
            row: Record = {"level": level, "repo": repo, "positives": len(rs)}
            for k in KINDS:
                row[k] = counts.get(k, 0)
            row["structural_in_test_files"] = ";".join(
                f"{k}={v}"
                for k, v in sorted(
                    Counter(r["primary_type"] for r in rs if r["kind"] == "test_unit").items()
                )
            )
            rows.append(row)
    return rows


# --------------------------------------------------------------------------- reach tables


def reach_population(instances: Sequence[Record], *, allow_several_locations: bool) -> list[Record]:
    """New L3 positives that have a graph node and a defined control, flattened.

    Excluded and counted elsewhere: positives not located, with no graph node (docs, data),
    already among the L2 units, and (unless ``allow_several_locations``) with several locations.
    """
    pop: list[Record] = []
    for inst in instances:
        reach = inst.get("reach")
        if not reach or reach.get("status") != "ok":
            continue
        by_id = {r["corpus_id"]: r for r in inst["positives"] if r["level"] == "L3"}
        for cid, entry in sorted(reach["positives"].items()):
            if entry["status"] != "ok":
                continue
            rec = by_id[cid]
            if rec["kind"] == "non_python_config":
                continue
            if rec["n_locations"] > 1 and not allow_several_locations:
                continue
            pop.append({**rec, **entry, "instance": inst["instance"], "repo": inst["repo_id"]})
    return pop


def incidence_rows(instances: Sequence[Record]) -> list[Record]:
    """Share of new L3 positives that touch at least one edge of a family, next to the share of
    all units of their snapshot that do (coverage of the family, independent of the L2 seeds)."""
    pop = reach_population(instances, allow_several_locations=True)
    base: dict[str, dict[str, float]] = {
        i["instance"]: i["reach"]["incident_base_rate"]
        for i in instances
        if i.get("reach", {}).get("status") == "ok"
    }
    rows: list[Record] = []
    groups: list[tuple[str, list[Record]]] = [("all_python", pop)]
    groups += [(k, [r for r in pop if r["kind"] == k]) for k in PYTHON_UNIT_KINDS]
    for group, rs in groups:
        if not rs:
            continue
        for fam in sorted(rs[0]["incident"]):
            share = sum(1 for r in rs if r["incident"].get(fam)) / len(rs)
            rate = sum(base[r["instance"]].get(fam, 0.0) for r in rs) / len(rs)
            rows.append(
                {
                    "group": group,
                    "family": fam,
                    "n": len(rs),
                    "positives_with_edge": _round(share),
                    "units_with_edge_in_snapshot": _round(rate),
                }
            )
    return rows


def exclusion_rows(instances: Sequence[Record]) -> list[Record]:
    """Why L3 positives are not in the reach study, per instance and in total."""
    rows: list[Record] = []
    total: Counter[str] = Counter()
    for inst in instances:
        reach = inst.get("reach")
        l3 = [r for r in inst["positives"] if r["level"] == "L3"]
        if not l3:
            continue
        c: Counter[str] = Counter()
        c["l3_positives"] = len(l3)
        for r in l3:
            if r["status"] != "found":
                c["not_located"] += 1
                continue
            entry = (reach or {}).get("positives", {}).get(r["corpus_id"], {})
            st = entry.get("status", "no_l2_units")
            if st == "ok" and r["kind"] == "non_python_config":
                c["config_file_observed_only"] += 1
            elif st == "ok" and r["n_locations"] > 1:
                c["in_study_several_locations_sensitivity_only"] += 1
            elif st == "ok":
                c["in_study"] += 1
            else:
                c[st] += 1
            if entry.get("same_text_as_l2"):
                c["text_identical_to_an_l2_positive"] += 1
        rows.append({"instance": inst["instance"], **dict(sorted(c.items()))})
        total.update(c)
    rows.append({"instance": "all", **dict(sorted(total.items()))})
    return rows


def _boot_ci(values: np.ndarray, lo: float = 2.5, hi: float = 97.5) -> tuple[float, float]:
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return float("nan"), float("nan")
    return float(np.percentile(finite, lo)), float(np.percentile(finite, hi))


def _round(x: float, nd: int = 4) -> float | None:
    return None if not np.isfinite(x) else round(float(x), nd)


def compare(
    obs: np.ndarray, ctrl: np.ndarray, cluster: np.ndarray, rng: np.random.Generator, draws: int
) -> Record:
    """Observed share, chance share, their difference and ratio, with two bootstrap intervals."""
    n = obs.size
    row: Record = {"n": int(n)}
    if n == 0:
        return row
    obs_share, ctrl_share = float(obs.mean()), float(ctrl.mean())
    row.update(obs_share=_round(obs_share), chance_share=_round(ctrl_share))
    row["difference"] = _round(obs_share - ctrl_share)
    row["ratio"] = _round(obs_share / ctrl_share) if ctrl_share > 0 else None

    idx = rng.integers(0, n, size=(draws, n))
    o_b, c_b = obs[idx].mean(axis=1), ctrl[idx].mean(axis=1)
    lo, hi = _boot_ci(o_b)
    row.update(obs_lo=_round(lo), obs_hi=_round(hi))
    lo, hi = _boot_ci(o_b - c_b)
    row.update(diff_lo=_round(lo), diff_hi=_round(hi))
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio_b = np.where(c_b > 0, o_b / c_b, np.nan)
    lo, hi = _boot_ci(ratio_b)
    row.update(
        ratio_lo=_round(lo),
        ratio_hi=_round(hi),
        ratio_defined_share=_round(float(np.isfinite(ratio_b).mean())),
    )

    labels = np.unique(cluster)
    row["n_instances"] = int(labels.size)
    if labels.size >= 2:
        pos = np.searchsorted(labels, cluster)
        o_sum = np.bincount(pos, weights=obs, minlength=labels.size)
        c_sum = np.bincount(pos, weights=ctrl, minlength=labels.size)
        size = np.bincount(pos, minlength=labels.size).astype(float)
        pick = rng.integers(0, labels.size, size=(draws, labels.size))
        w = np.zeros((draws, labels.size))
        for j in range(labels.size):
            w[:, j] = (pick == j).sum(axis=1)
        denom = w @ size
        with np.errstate(divide="ignore", invalid="ignore"):
            oc = (w @ o_sum) / denom
            cc = (w @ c_sum) / denom
        lo, hi = _boot_ci(oc - cc)
        row.update(diff_cluster_lo=_round(lo), diff_cluster_hi=_round(hi))
    return row


def reach_rows(
    instances: Sequence[Record], *, seed: int, draws: int = BOOTSTRAP_DRAWS, label: str = "primary"
) -> list[Record]:
    """Long table: group x edge subset x hop x control, with intervals.

    ``label`` is ``primary`` (positives with one location) or ``sensitivity_several_locations``
    (all located positives, first location). Groups: all new Python positives, each kind and
    each repository.
    """
    pop = reach_population(instances, allow_several_locations=label != "primary")
    rng = np.random.default_rng(seed)
    groups: list[tuple[str, list[Record]]] = [("all_python", pop)]
    for kind in PYTHON_UNIT_KINDS:
        groups.append((kind, [r for r in pop if r["kind"] == kind]))
    for repo in sorted({r["repo"] for r in pop}):
        groups.append((f"repo:{repo}", [r for r in pop if r["repo"] == repo]))
    rows: list[Record] = []
    exploratory = {s.name: s.exploratory for s in SUBSETS}
    for group, rs in groups:
        if not rs:
            continue
        cluster = np.array([r["instance"] for r in rs])
        for subset in (s.name for s in SUBSETS):
            for hop in HOPS:
                obs_all = np.array([r["reach"][subset]["obs"][hop] for r in rs])
                for control in CONTROLS:
                    keep = [r["reach"][subset]["ctrl"][control] is not None for r in rs]
                    if not any(keep):
                        continue
                    mask = np.array(keep)
                    ctrl = np.array(
                        [
                            r["reach"][subset]["ctrl"][control][hop]
                            for r, k in zip(rs, keep, strict=True)
                            if k
                        ]
                    )
                    stat = compare(obs_all[mask], ctrl, cluster[mask], rng, draws)
                    rows.append(
                        {
                            "analysis": label,
                            "group": group,
                            "subset": subset,
                            "exploratory_family": exploratory[subset],
                            "hop": hop,
                            "control": control,
                            "small_n": stat["n"] < SMALL_N,
                            **stat,
                        }
                    )
    return rows


def write_rows(path: str, rows: Sequence[Record]) -> None:
    """Write rows as CSV with the union of their keys (first-seen order), LF line ends."""
    import csv
    import os

    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def comparable(doc: Record) -> Record:
    """The records without the fields allowed to differ between identical runs (timing, host)."""
    out: Record = json.loads(json.dumps(doc))
    for inst in out["instances"]:
        inst.pop("build_seconds", None)
    out.get("hardware", {}).pop("host", None)
    return out


def run_log(
    doc: Record,
    *,
    records_sha256: str,
    rerun: Record | None,
    tables: dict[str, str],
    extras: Record,
) -> Record:
    """The log of one pilot run: configuration, hardware, counts, determinism check, table hashes.

    Counts only. ``rerun`` is the records of an independent second run of the same code; when
    given, the log states whether the two agree apart from timing and host name.
    """
    inst = doc["instances"]
    recs = all_positives(inst)
    log: Record = {
        "run": "m-chunk-unit-reach",
        "label": "exploratory pilot (small n)",
        "pilot": doc["pilot"],
        "config_hash": doc["config_hash"],
        "seed": doc["seed"],
        "control_draws": doc["draws"],
        "bootstrap_draws": BOOTSTRAP_DRAWS,
        "hardware": doc["hardware"],
        "git": doc["git"],
        "repos": doc["repos"],
        "instances": len(inst),
        "failures": doc["failures"],
        "records_sha256": records_sha256,
        "positives": Counter(r["level"] for r in recs),
        "match": match_rows(inst),
        "categories": category_rows(inst),
        "kinds": kind_rows(inst),
        "exclusions": exclusion_rows(inst),
        "determinism": None
        if rerun is None
        else {
            "second_run_identical_apart_from_timing_and_host": comparable(doc) == comparable(rerun)
        },
        "table_sha256": tables,
        **extras,
    }
    return log
