"""Tables of the stored-output analysis (E-STORED-ANALYSIS; exploratory, CPU only, no run).

Reads the per-query rows kept under ``results/rq2/`` and writes the four groups of tables of
``docs/experiments/B.md``: variance components and minimum detectable differences (item 1), gain
of RAW over the untrained encoder by slice (item 2), per-query winners and best-of-arms oracles
with a seed-noise control (item 3), and the per-query loss of RAW under injected noise (item 4).
Slice (c), lexical overlap, is not computed (issue and unit texts are not on this machine).

Implements docs/experiments/B.md "E-STORED-ANALYSIS".
"""

from __future__ import annotations

import functools
import hashlib
import json
import os
import platform
import sys
from collections.abc import Callable, Mapping, Sequence
from typing import Any

import numpy as np
import numpy.typing as npt

from ril.analysis import stored_rows as sr
from ril.analysis import stored_stats as ss
from ril.analysis.x2_tables import write_csv

Record = dict[str, Any]
STORED_VERSION = "stored-analysis/v1"
W6_REF = "t5a_raw"
W6_CELLS = (
    "t5a_sub_d0",
    "t5a_filter_bm25",
    "t5a_filter_srs",
    "t5a_filter_cre",
    "t5a_weight_cre",
    "t5a_curr_cre",
)
ARM_LABEL = {
    "t5a_raw": "RAW",
    "t5a_sub_d0": "SUBSAMPLE",
    "t5a_filter_bm25": "FILTER-BM25",
    "t5a_filter_srs": "FILTER-SRS",
    "t5a_filter_cre": "FILTER-CRE",
    "t5a_weight_cre": "WEIGHT",
    "t5a_curr_cre": "CURRICULUM",
}
NOISE_SETS: Mapping[str, tuple[str, tuple[str, ...]]] = {
    "n1_r20": (
        "n1_r20_raw",
        tuple(f"n1_r20_{c}" for c in ("sub", "filter_bm25", "filter_srs", "oracle", "weight_srs")),
    ),
    "n1_r40": (
        "n1_r40_raw",
        tuple(f"n1_r40_{c}" for c in ("sub", "filter_bm25", "filter_srs", "oracle", "weight_srs")),
    ),
    "n8_r40": (
        "n8_r40_raw",
        tuple(f"n8_r40_{c}" for c in ("sub", "filter_bm25", "filter_srs", "oracle")),
    ),
}
OLD_MDD: Mapping[tuple[str, str, int], tuple[float, str]] = {
    ("w6", "L2", 3): (1.4, "E-PILOT-ARMS2"),
    ("w6", "L3", 3): (1.7, "E-PILOT-ARMS2"),
    ("n1_r20", "L2", 2): (1.56, "E-PILOT-NOISE"),
    ("n1_r20", "L3", 2): (2.77, "E-PILOT-NOISE"),
    ("n1_r40", "L2", 2): (2.15, "E-PILOT-NOISE"),
    ("n1_r40", "L3", 2): (1.86, "E-PILOT-NOISE"),
    ("n8_r40", "L2", 2): (2.00, "E-PILOT-NOISE-SIB"),
    ("n8_r40", "L3", 2): (1.93, "E-PILOT-NOISE-SIB"),
}
OLD_SEED_SD: Mapping[tuple[str, str], float] = {
    ("w6", "L2"): 0.52,
    ("w6", "L3"): 0.73,
    ("n1_r20", "L2"): 0.51,
    ("n1_r20", "L3"): 0.99,
    ("n1_r40", "L2"): 0.77,
    ("n1_r40", "L3"): 0.66,
    ("n8_r40", "L2"): 0.42,
    ("n8_r40", "L3"): 0.69,
}
THRESHOLDS = (0.0, 0.01, 0.05, 0.10)
FRACTIONS = (0.10, 0.25)
BoolArr = npt.NDArray[np.bool_]


def _r(x: float, nd: int = 3) -> float | None:
    return None if x != x else round(float(x), nd)


def _level_view(panel: sr.Panel, level: str) -> tuple[ss.IntArray, BoolArr]:
    m = panel.level_mask(level)
    return ss.repo_index([r for r, k in zip(panel.repos, m, strict=True) if k]), m


def _pairs(a: ss.FloatArray, b: ss.FloatArray) -> ss.FloatArray:
    """Seed-matched differences ``a - b`` (rows: seed index in common order)."""
    k = min(a.shape[0], b.shape[0])
    return a[:k] - b[:k]


def decomposition(results_root: str, out_dir: str, draws: int, seed: int) -> dict[str, Any]:
    """Item 1: components for RAW levels and cell differences; minimum detectable differences."""
    comp_rows: list[Record] = []
    mdd_rows: list[Record] = []
    sets: dict[str, tuple[str, Sequence[str]]] = {"w6": (W6_REF, W6_CELLS), **NOISE_SETS}
    for name, (ref, cells) in sets.items():
        runs = sr.discover(results_root, [ref, *cells])
        panel = sr.build_panel(runs)
        for level in sr.LEVELS:
            repo, m = _level_view(panel, level)
            n_seeds = {c: panel.values[c].shape[0] for c in panel.values}
            lv = {c: v[:, m] for c, v in panel.values.items()}
            diffs = {c: _pairs(lv[c], lv[ref]) for c in cells if c in lv and ref in lv}
            comp_rows.append(
                {
                    "set": name,
                    "level": level,
                    "subject": f"{ref} (levels)",
                    **_flat(ss.components(lv[ref], repo)),
                }
            )
            per_cell = {c: ss.components(d, repo) for c, d in diffs.items()}
            for c, rec in per_cell.items():
                comp_rows.append(
                    {"set": name, "level": level, "subject": f"{c} - {ref}", **_flat(rec)}
                )
            pooled = ss.mean_components(list(per_cell.values()))
            seed_vars = [ss.components(lv[c], repo)["seed_var_direct"] for c in lv]
            sd_all, _ = ss.old_style_seed_mdd(seed_vars, 2)

            def pooled_stat(
                idx: ss.IntArray,
                codes: ss.IntArray,
                k: int,
                with_repo: bool,
                diffs: Mapping[str, ss.FloatArray] = diffs,
            ) -> float:
                comps = [ss.components(d[:, idx], codes) for d in diffs.values()]
                return ss.minimum_detectable(ss.mean_components(comps), k, with_repo)

            for k in (2, 3):
                for with_repo in (True, False):
                    point = ss.minimum_detectable(pooled, k, with_repo)
                    lo, hi = _boot_pooled(
                        repo,
                        functools.partial(pooled_stat, k=k, with_repo=with_repo),
                        draws,
                        seed,
                        level == "L2",
                    )
                    old = OLD_MDD.get((name, level, k))
                    row: Record = {
                        "set": name,
                        "level": level,
                        "seeds_per_arm": k,
                        "variant": "with_repo_term" if with_repo else "query_level",
                        "mdd_points": _r(100 * point, 2),
                        "lo": _r(100 * lo, 2),
                        "hi": _r(100 * hi, 2),
                        "repos": int(len(np.unique(repo))),
                        "queries": int(m.sum()),
                        "interval": "repository-cluster"
                        if level == "L2"
                        else "queries within repository",
                        "stored_value": old[0] if old else None,
                        "stored_in": old[1] if old else None,
                    }
                    if old:
                        row["ratio"] = _r(100 * point / old[0], 2)
                        outside = (lo == lo) and not (100 * lo <= old[0] <= 100 * hi)
                        row["disagrees"] = bool(
                            outside if lo == lo else not 0.8 <= 100 * point / old[0] <= 1.25
                        )
                    mdd_rows.append(row)
            sd_old = OLD_SEED_SD.get((name, level))
            mdd_rows.append(
                {
                    "set": name,
                    "level": level,
                    "seeds_per_arm": 2,
                    "variant": "pooled_seed_sd_all_cells",
                    "mdd_points": _r(100 * sd_all, 3),
                    "stored_value": sd_old,
                    "stored_in": "seed SD quoted in the entry",
                    "queries": int(m.sum()),
                    "repos": int(len(np.unique(repo))),
                    "seeds_of_cells": json.dumps(n_seeds, sort_keys=True),
                }
            )
    write_csv(os.path.join(out_dir, "s1_components.csv"), comp_rows)
    write_csv(os.path.join(out_dir, "s1_mdd.csv"), mdd_rows)
    return {"components": len(comp_rows), "mdd": len(mdd_rows)}


def _flat(rec: Record) -> Record:
    out = {
        k: (_r(100.0**2 * v, 4) if k.startswith(("s2", "seed_var")) else v) for k, v in rec.items()
    }
    out["flags"] = ";".join(rec["flags"])
    return out


def _boot_pooled(
    repo: ss.IntArray,
    stat: Callable[[ss.IntArray, ss.IntArray], float],
    draws: int,
    seed: int,
    clustered: bool = True,
) -> tuple[float, float]:
    """Interval of the pooled minimum detectable difference; repositories resampled.

    Each drawn copy of a repository gets its own group code, so a repository drawn twice counts as
    two groups, as in any cluster bootstrap.
    """
    rng = np.random.default_rng(seed)
    codes = np.unique(repo)
    vals: list[float] = []
    for _ in range(draws):
        if not clustered:  # queries resampled inside each repository (L3, two repositories)
            idx = np.concatenate(
                [rng.choice(np.flatnonzero(repo == c), size=int((repo == c).sum())) for c in codes]
            )
            vals.append(stat(idx, repo[idx]))
            continue
        picks = rng.choice(codes, size=len(codes), replace=True)
        idx = np.concatenate([np.flatnonzero(repo == c) for c in picks])
        new = np.concatenate(
            [np.full(int((repo == c).sum()), i, dtype=np.int64) for i, c in enumerate(picks)]
        )
        vals.append(stat(idx, new))
    return ss.interval(vals)


def slice_labels(
    keys: Sequence[sr.Key], repos: Sequence[str], info: Mapping[sr.Key, Mapping[str, Any]]
) -> dict[str, dict[str, BoolArr]]:
    """Masks per slice family (``repository``, ``n_positives``, ``kind``, ``kind_mix``)."""
    n = len(keys)
    fam: dict[str, dict[str, BoolArr]] = {
        "repository": {},
        "n_positives": {},
        "kind": {},
        "kind_mix": {},
    }
    for r in sorted(set(repos)):
        fam["repository"][r] = np.array([x == r for x in repos], dtype=bool)
    npos = np.array([info[k]["n_pos"] for k in keys], dtype=np.float64)
    for label, m in ss.quartile_bins(npos):
        fam["n_positives"][label] = m
    for kd in sr.KINDS:
        m = np.array([kd in info[k]["kinds"] for k in keys], dtype=bool)
        if m.any():
            fam["kind"][kd] = m
    single = np.array([len(info[k]["kinds"]) == 1 for k in keys], dtype=bool)
    fam["kind_mix"]["single_kind"] = single
    fam["kind_mix"]["mixed_kinds"] = ~single & np.array(
        [len(info[k]["kinds"]) > 1 for k in keys], dtype=bool
    )
    assert n == len(repos)
    return fam


def slice_tables(
    name: str,
    gain_by_level: Mapping[str, ss.FloatArray],
    panel_keys: Sequence[sr.Key],
    panel_repos: Sequence[str],
    info: Mapping[sr.Key, Mapping[str, Any]],
    draws: int,
    seed: int,
) -> list[Record]:
    """Slice-table rows for a per-query gain or loss aligned with ``panel_keys``."""
    rows: list[Record] = []
    for level in sr.LEVELS:
        sel = [i for i, k in enumerate(panel_keys) if k[0] == level]
        keys = [panel_keys[i] for i in sel]
        repos = [panel_repos[i] for i in sel]
        gain = gain_by_level[level]
        repo = ss.repo_index(repos)
        fams = slice_labels(keys, repos, info)
        for fam, masks in fams.items():
            for rec in ss.slice_gain(
                gain,
                repo,
                masks,
                draws,
                seed,
                stratum=(fam == "repository"),
                clustered=(level == "L2"),
            ):
                if rec["slice"] == "all" and fam != "repository":
                    continue
                rows.append(
                    {
                        "analysis": name,
                        "level": level,
                        "family": fam,
                        "interval": "repository-cluster" if level == "L2" else "query-level",
                        **{
                            k: (
                                _r(100 * v, 2)
                                if k in ("mean_gain", "lo", "hi")
                                else _r(v, 3)
                                if isinstance(v, float)
                                else v
                            )
                            for k, v in rec.items()
                        },
                    }
                )
    return rows


UNTRAINED_DIR = "t3_curve_raw/2026-10-29_3909db9c/step_00000"


def _panel(
    results_root: str, cells: Sequence[str], extra: Mapping[str, sr.Run] | None = None
) -> sr.Panel:
    runs = sr.discover(results_root, cells)
    all_runs: dict[str, list[sr.Run]] = dict(runs)
    for name, run in (extra or {}).items():
        all_runs[name] = [run]
    return sr.build_panel(all_runs)


def _by_level(panel: sr.Panel, vec: ss.FloatArray) -> dict[str, ss.FloatArray]:
    return {lv: vec[panel.level_mask(lv)] for lv in sr.LEVELS}


def gain_tables(results_root: str, units_dir: str, out_dir: str, draws: int, seed: int) -> Record:
    """Item 2: per-query gain of RAW (100 updates, Wave 6, seed mean) over the untrained encoder."""
    untrained = sr.Run("untrained", 0, os.path.join(results_root, UNTRAINED_DIR))
    panel = _panel(results_root, [W6_REF], {"untrained": untrained})
    info = sr.gold_info(units_dir, panel.keys)
    gain = panel.values[W6_REF].mean(axis=0) - panel.values["untrained"][0]
    rows = slice_tables(
        "raw_minus_untrained", _by_level(panel, gain), panel.keys, panel.repos, info, draws, seed
    )
    write_csv(os.path.join(out_dir, "s2_gain_by_slice.csv"), rows)
    return {"queries": len(panel.keys), "rows": len(rows)}


def complementarity_tables(results_root: str, out_dir: str, draws: int, seed: int) -> Record:
    """Item 3: winners, margin shares, oracles and the seed-noise controls at Wave 6."""
    cells = [W6_REF, *W6_CELLS]
    panel = _panel(results_root, cells)
    rows: list[Record] = []
    ctrl: list[Record] = []
    for level in sr.LEVELS:
        m = panel.level_mask(level)
        repo = ss.repo_index([r for r, k in zip(panel.repos, m, strict=True) if k])
        lv = {c: panel.values[c][:, m] for c in cells}
        arms = {ARM_LABEL[c]: lv[c].mean(axis=0) for c in cells}
        rec = ss.complementarity(arms, "RAW", THRESHOLDS)
        base = {
            "level": level,
            "queries": rec["queries"],
            "oracle_label": "upper bound, not a method",
        }
        for arm, w in rec["wins"].items():
            rows.append({**base, "row": "wins", "arm": arm, "value": w})
        rows.append({**base, "row": "ties", "arm": "", "value": rec["ties"]})
        for t, v in rec["share_best_other_beats_ref"].items():
            margin = np.vstack([x for n, x in arms.items() if n != "RAW"]).max(axis=0) - arms["RAW"]
            lo, hi = ss.bootstrap(repo, ss.share_stat(margin, float(t)), draws, seed, level == "L2")
            rows.append(
                {
                    **base,
                    "row": f"share_best_other_beats_RAW_by_>{t}",
                    "arm": "best non-RAW arm",
                    "value": _r(v, 3),
                    "lo": _r(lo, 3),
                    "hi": _r(hi, 3),
                }
            )
        # oracle over seed-averaged arms, over single runs, and the same-arm controls
        raw_runs = lv[W6_REF]
        sub_runs = lv["t5a_sub_d0"]
        every = np.vstack([lv[c] for c in cells])
        oracles = {
            "RAW (mean of seeds)": arms["RAW"],
            "O2: best of the two RAW seeds": raw_runs.max(axis=0),
            "O4: best of RAW and subsample, 2 seeds each": np.vstack([raw_runs, sub_runs]).max(
                axis=0
            ),
            "O7: best of 7 arms (seed-averaged)": np.vstack(list(arms.values())).max(axis=0),
            "O14: best of 14 runs (7 arms x 2 seeds)": every.max(axis=0),
        }
        for label, v in oracles.items():
            lo, hi = ss.bootstrap(repo, ss.mean_stat(v), draws, seed, level == "L2")
            ctrl.append(
                {
                    **base,
                    "oracle": label,
                    "mean_points": _r(100 * float(v.mean()), 2),
                    "lo": _r(100 * lo, 2),
                    "hi": _r(100 * hi, 2),
                    "minus_RAW_mean_points": _r(100 * float(v.mean() - arms["RAW"].mean()), 2),
                }
            )
        d = raw_runs[1] - raw_runs[0]
        for t in THRESHOLDS:
            for lab, dd in (("RAW seed1 beats seed0", d), ("RAW seed0 beats seed1", -d)):
                lo, hi = ss.bootstrap(repo, ss.share_stat(dd, t), draws, seed, level == "L2")
                ctrl.append(
                    {
                        **base,
                        "oracle": f"control: share where {lab} by >{t:g}",
                        "mean_points": _r(float((dd > t).mean()), 3),
                        "lo": _r(lo, 3),
                        "hi": _r(hi, 3),
                    }
                )
            best2 = raw_runs.max(axis=0) - arms["RAW"]
            ctrl.append(
                {
                    **base,
                    "oracle": f"control: share where best of 2 RAW seeds beats RAW mean by >{t:g}",
                    "mean_points": _r(float((best2 > t).mean()), 3),
                }
            )
    write_csv(os.path.join(out_dir, "s3_complementarity.csv"), rows)
    write_csv(os.path.join(out_dir, "s3_oracles_and_controls.csv"), ctrl)
    return {"queries": len(panel.keys), "rows": len(rows) + len(ctrl)}


def noise_tables(results_root: str, units_dir: str, out_dir: str, draws: int, seed: int) -> Record:
    """Item 4: per-query loss of RAW under injected noise: slices, concentration, no change."""
    noised = {"n1_r20": "n1_r20_raw", "n1_r40": "n1_r40_raw", "n8_r40": "n8_r40_raw"}
    panel = _panel(results_root, [W6_REF, *noised.values()])
    info = sr.gold_info(units_dir, panel.keys)
    slice_rows: list[Record] = []
    conc_rows: list[Record] = []
    nochange_rows: list[Record] = []
    for tag, cell in noised.items():
        loss = panel.values[W6_REF].mean(axis=0) - panel.values[cell].mean(axis=0)
        slice_rows += slice_tables(
            f"loss_{tag}", _by_level(panel, loss), panel.keys, panel.repos, info, draws, seed
        )
        for level in sr.LEVELS:
            m = panel.level_mask(level)
            repo = ss.repo_index([r for r, k in zip(panel.repos, m, strict=True) if k])
            base_m = panel.values[W6_REF][:, m].mean(axis=0)
            noise_m = panel.values[cell][:, m].mean(axis=0)
            lm = loss[m]
            ref_runs = panel.values[W6_REF][:, m]
            for label, vec in (
                (f"loss_{tag}", lm),
                ("reference: RAW r=0 seed0 - seed1", ref_runs[0] - ref_runs[1]),
                ("reference: RAW r=0 seed1 - seed0", ref_runs[1] - ref_runs[0]),
            ):
                rec = ss.concentration(vec, FRACTIONS)
                row: Record = {"set": tag, "level": level, "vector": label, "queries": len(vec)}
                for k, v in rec.items():
                    row[k] = _r(100 * v, 2) if k in ("total_loss", "positive_mass") else _r(v, 3)
                for f in FRACTIONS:
                    key = f"share_total_{f:g}"
                    lo, hi = ss.bootstrap(
                        repo, ss.concentration_stat(vec, f, key), draws, seed, level == "L2"
                    )
                    row[key + "_lo"], row[key + "_hi"] = _r(lo, 3), _r(hi, 3)
                conc_rows.append(row)
            same = np.abs(lm) <= ss.TIE
            frozen = same & (
                ((base_m <= ss.TIE) & (noise_m <= ss.TIE))
                | ((base_m >= 1 - ss.TIE) & (noise_m >= 1 - ss.TIE))
            )
            lo, hi = ss.bootstrap(
                repo, ss.mean_stat(same.astype(np.float64)), draws, seed, level == "L2"
            )
            nochange_rows.append(
                {
                    "set": tag,
                    "level": level,
                    "queries": int(m.sum()),
                    "no_change_share": _r(float(same.mean()), 3),
                    "lo": _r(lo, 3),
                    "hi": _r(hi, 3),
                    "no_change_and_metric_cannot_move_share": _r(float(frozen.mean()), 3),
                    "worse_share": _r(float((lm > ss.TIE).mean()), 3),
                    "better_share": _r(float((lm < -ss.TIE).mean()), 3),
                }
            )
    for level in sr.LEVELS:  # reference: no noise, the two seeds of RAW against each other
        m = panel.level_mask(level)
        repo = ss.repo_index([r for r, k in zip(panel.repos, m, strict=True) if k])
        d = panel.values[W6_REF][0, m] - panel.values[W6_REF][1, m]
        same = np.abs(d) <= ss.TIE
        lo, hi = ss.bootstrap(
            repo, ss.mean_stat(same.astype(np.float64)), draws, seed, level == "L2"
        )
        nochange_rows.append(
            {
                "set": "reference: RAW r=0 seed0 vs seed1",
                "level": level,
                "queries": int(m.sum()),
                "no_change_share": _r(float(same.mean()), 3),
                "lo": _r(lo, 3),
                "hi": _r(hi, 3),
                "worse_share": _r(float((d > ss.TIE).mean()), 3),
                "better_share": _r(float((d < -ss.TIE).mean()), 3),
            }
        )
    write_csv(os.path.join(out_dir, "s4_loss_by_slice.csv"), slice_rows)
    write_csv(os.path.join(out_dir, "s4_loss_concentration.csv"), conc_rows)
    write_csv(os.path.join(out_dir, "s4_no_change.csv"), nochange_rows)
    return {
        "queries": len(panel.keys),
        "rows": len(slice_rows) + len(conc_rows) + len(nochange_rows),
    }


def input_hash(results_root: str, units_dir: str, draws: int, seed: int) -> str:
    """sha256 over the settings and the contents of every per-query file the tables read."""
    cells = [W6_REF, *W6_CELLS, *(c for ref, cs in NOISE_SETS.values() for c in (ref, *cs))]
    h = hashlib.sha256(json.dumps([STORED_VERSION, draws, seed, sr.READING]).encode())
    paths = [
        os.path.join(r.directory, "query_rows.csv")
        for runs in sr.discover(results_root, sorted(set(cells))).values()
        for r in runs
    ]
    paths.append(os.path.join(results_root, UNTRAINED_DIR, "query_rows.csv"))
    for path in sorted(paths):
        h.update(path.encode())
        with open(path, "rb") as fh:
            h.update(hashlib.sha256(fh.read()).digest())
    h.update(str(len(os.listdir(units_dir))).encode())
    return h.hexdigest()


def run_all(
    results_root: str,
    units_dir: str,
    out_dir: str,
    draws: int = 2000,
    seed: int = 0,
) -> Record:
    """Produce every table; returns the log record (inputs, counts)."""
    os.makedirs(out_dir, exist_ok=True)
    log: Record = {
        "version": STORED_VERSION,
        "draws": draws,
        "seed": seed,
        "skipped": [
            "item 2(c) lexical overlap: issue and unit texts of the dev repositories not available",
            "Wave 5 (t4a_*): per-query rows not under results/rq2",
        ],
        "reading": sr.READING,
        "metrics": dict(sr.METRIC_BY_LEVEL),
    }
    log["hardware"] = {
        "device": "cpu",
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "gpu": None,
    }
    log["config_hash"] = input_hash(results_root, units_dir, draws, seed)
    log["decomposition"] = decomposition(results_root, out_dir, draws, seed)
    log["gain"] = gain_tables(results_root, units_dir, out_dir, draws, seed)
    log["complementarity"] = complementarity_tables(results_root, out_dir, draws, seed)
    log["noise"] = noise_tables(results_root, units_dir, out_dir, draws, seed)
    return log


def dump(log: Record, path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(log, fh, indent=1, sort_keys=True, default=str)
        fh.write("\n")
