"""Tables of the smoke pilots E-PILOT-K, E-PILOT-NEG and E-PILOT-LEAK (exploratory).

Reads the result directories the training stack writes (``results/rq2/<exp_id>/<date>_<hash8>/``:
``results.json`` with the training record and the evaluation sections, ``query_rows.csv`` with the
per-query metrics of the evaluation hook) and compares conditions. A *condition* is one ``exp_id``;
its runs differ only in the training seed.

Conventions (stated before the pilot runs, ``docs/EXPERIMENTS.md`` E-PILOT-*):

* A query is an (instance, level) pair of the evaluated role; L2 and L3 are separate rows; numbers
  are percentage points of nDCG@10 (L2) and Recall@100 (L3), as in E-DENSE-FUSION.
* Effect of a condition = mean over queries of (the condition's per-query value averaged over its
  seeds) minus (the reference condition's, likewise). Intervals are 95% percentile bootstraps over
  queries (query level) and over whole repositories (clustered, decision D17), 2,000 draws, one set
  of resamples shared by every column of a table (``ril.analysis.e3_tables.Boot``), so the
  comparisons are paired over queries. Seeds enter by averaging: the intervals carry query
  sampling, not seed-to-seed variation.
* Seed variation is reported beside it: the effect within each seed index (seed s of the
  condition minus seed s of the reference) and the reference's own seed-to-seed difference on the
  same queries (the noise floor of a retraining). With two seeds this is one difference per
  condition: it shows whether the effect is larger than one retraining's change, not a standard
  deviation that could be trusted.
* Every trained condition is also compared with the untrained base encoder (the X2 baseline
  column), which tells whether the budget moved the model at all.

Kept compatible with Python 3.10.
"""

from __future__ import annotations

import csv
import glob
import json
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from ril.analysis.x2_tables import paired_rows, write_csv

Record = dict[str, Any]
T2_TABLES_VERSION = "t2-tables/v1"
LEVEL_METRIC = {"L2": "ndcg10", "L3": "recall100"}
READINGS = ("units_all_nomod", "units_all")
"""Primary gold reading first (decision D18), the CORE-Bench-faithful one beside it."""
BASE = "coderankembed__t512"
"""The untrained base encoder's column in the evaluation (X2's CodeRankEmbed at 512 tokens)."""


@dataclass(frozen=True)
class Run:
    """One finished run: its condition, seed, variant name, per-query values and its record."""

    exp_id: str
    seed: int
    config_hash: str
    result_dir: str
    variant: str
    values: dict[tuple[str, str, str, str], float]
    """``(instance, level, column name, reading:metric) -> value`` (fractions)."""
    repo_of: dict[tuple[str, str], str]
    record: Record


def _float(x: str) -> float | None:
    return None if x in ("", None) else float(x)


def load_run(result_dir: str, section: str = "evaluation", sub: str = "") -> Run:
    """Read one run's results and per-query rows (``sub``: the label directory of an override)."""
    with open(os.path.join(result_dir, "results.json"), encoding="utf-8") as handle:
        rec = json.load(handle)
    ev = rec[section]
    values: dict[tuple[str, str, str, str], float] = {}
    repo_of: dict[tuple[str, str], str] = {}
    path = os.path.join(result_dir, sub, "query_rows.csv")
    with open(path, encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            q = (row["instance"], row["level"])
            repo_of[q] = row["repo"]
            for k, v in row.items():
                if ":" in k:
                    f = _float(v)
                    if f is not None:
                        values[(q[0], q[1], row["name"], k)] = f
    tr = rec["training"]
    return Run(
        exp_id=str(tr["exp_id"]),
        seed=int(tr["seed"]),
        config_hash=str(tr["config_hash"]),
        result_dir=result_dir,
        variant=str(ev["variant"]),
        values=values,
        repo_of=repo_of,
        record=rec,
    )


def load_condition(
    results_root: str, exp_id: str, section: str = "evaluation", sub: str = ""
) -> list[Run]:
    """Every finished run of a condition under ``results_root/rq2/<exp_id>/``, by seed."""
    runs = []
    for d in sorted(glob.glob(os.path.join(results_root, "rq2", exp_id, "*"))):
        p = os.path.join(d, "results.json")
        if not os.path.exists(p):
            continue
        with open(p, encoding="utf-8") as handle:
            rec = json.load(handle)
        if section in rec and os.path.exists(os.path.join(d, sub, "query_rows.csv")):
            runs.append(load_run(d, section, sub))
    seeds = [r.seed for r in runs]
    if len(set(seeds)) != len(seeds):
        raise ValueError(f"{exp_id}: two runs share a seed: {seeds}")
    return sorted(runs, key=lambda r: r.seed)


def column(run: Run, kind: str) -> str:
    """The run's own column name for ``kind`` ``dense`` or ``rrf``, or a baseline's."""
    if kind == "base_dense":
        return f"dense:{BASE}"
    if kind == "base_rrf":
        return f"rrf:{BASE}"
    if kind == "bm25":
        return "bm25"
    if kind not in ("dense", "rrf"):
        raise ValueError(f"unknown column kind {kind!r}")
    return f"{kind}:{run.variant}"


def _vector(
    run: Run, queries: Sequence[tuple[str, str]], kind: str, key: str
) -> np.ndarray[Any, Any]:
    name = column(run, kind)
    return np.asarray([run.values[(q[0], q[1], name, key)] for q in queries], dtype=np.float64)


def common_queries(
    runs: Sequence[Run], kinds: Sequence[str], level: str, key: str
) -> list[tuple[str, str]]:
    """Queries of ``level`` scored under ``key`` in every run and column (sorted)."""
    sets = []
    for r in runs:
        for kind in kinds:
            name = column(r, kind)
            sets.append(
                {(i, lv) for (i, lv, n, k) in r.values if lv == level and n == name and k == key}
            )
    if not sets:
        return []
    out = set.intersection(*sets)
    return sorted(out)


def contrast_rows(
    conditions: Mapping[str, Sequence[Run]],
    reference: str,
    *,
    kind: str,
    level: str,
    reading: str,
    seed: int,
    labels: Mapping[str, Any],
) -> list[Record]:
    """Effect rows of every condition against ``reference`` (and the reference against the base).

    Columns of one paired table: the base encoder, each condition's seed mean, each condition's
    seeds; references: a condition's mean against the reference mean, seed s against the
    reference's seed s, the reference's seed s (s > first) against its first seed, the reference's
    mean against the base encoder.
    """
    key = f"{reading}:{LEVEL_METRIC[level]}"
    all_runs = [r for rs in conditions.values() for r in rs]
    ref_runs = list(conditions[reference])
    if not ref_runs:
        raise ValueError(f"no runs for the reference {reference}")
    base_kind = "base_dense" if kind == "dense" else "base_rrf"
    qs = common_queries(all_runs, [kind], level, key)
    base_name = column(ref_runs[0], base_kind)
    qs = [q for q in qs if (q[0], q[1], base_name, key) in ref_runs[0].values]
    if not qs:
        return []
    names: list[str] = ["base"]
    cols: list[np.ndarray[Any, Any]] = [_vector(ref_runs[0], qs, base_kind, key)]
    refs: list[str | None] = [None]
    ref_seeds = {r.seed: r for r in ref_runs}
    for cond, runs in conditions.items():
        if not runs:
            continue
        mats = [_vector(r, qs, kind, key) for r in runs]
        names.append(f"{cond}:mean")
        cols.append(np.mean(mats, axis=0))
        refs.append("base" if cond == reference else f"{reference}:mean")
    for cond, runs in conditions.items():
        for r in runs:
            names.append(f"{cond}:s{r.seed}")
            cols.append(_vector(r, qs, kind, key))
            if cond == reference:
                first = ref_runs[0].seed
                refs.append(None if r.seed == first else f"{reference}:s{first}")
            else:
                refs.append(f"{reference}:s{r.seed}" if r.seed in ref_seeds else None)
    repos = [ref_runs[0].repo_of[q] for q in qs]
    rows = paired_rows(
        np.stack(cols, axis=1),
        repos,
        names,
        refs,
        {**labels, "kind": kind, "level": level, "reading": reading, "metric": LEVEL_METRIC[level]},
        seed,
    )
    for row in rows:
        cond, _, part = str(row["name"]).rpartition(":")
        row["condition"] = cond or row["name"]
        row["part"] = part if cond else ""
        row["seeds"] = len(conditions.get(cond, [])) if cond else 0
    return rows


def seed_spread(
    conditions: Mapping[str, Sequence[Run]], *, kind: str, level: str, reading: str
) -> list[Record]:
    """Per condition: the mean over its common queries under each seed, the range and the SD (n=2:
    one difference; reported, not trusted)."""
    key = f"{reading}:{LEVEL_METRIC[level]}"
    all_runs = [r for rs in conditions.values() for r in rs]
    qs = common_queries(all_runs, [kind], level, key)
    out: list[Record] = []
    for cond, runs in conditions.items():
        means = [100 * float(_vector(r, qs, kind, key).mean()) for r in runs] if qs else []
        out.append(
            {
                "condition": cond,
                "kind": kind,
                "level": level,
                "reading": reading,
                "queries": len(qs),
                "seeds": [r.seed for r in runs],
                "per_seed": [round(m, 2) for m in means],
                "range": round(max(means) - min(means), 2) if means else None,
                "sd": round(float(np.std(means, ddof=1)), 2) if len(means) > 1 else None,
            }
        )
    return out


def cost_rows(conditions: Mapping[str, Sequence[Run]]) -> list[Record]:
    """Budget accounting per run (``docs/EXPERIMENTS.md`` RQ2 extras) with the filter report."""
    out: list[Record] = []
    for cond, runs in conditions.items():
        for r in runs:
            tr = r.record["training"]
            b = tr["budget"]
            f = tr.get("filter", {})
            out.append(
                {
                    "condition": cond,
                    "seed": r.seed,
                    "config_hash": r.config_hash[:12],
                    "result_dir": os.path.basename(r.result_dir),
                    "arm": tr["arm"]["name"],
                    "teacher_equals_base": tr.get("teacher_equals_base"),
                    "optimizer_updates": b.get("optimizer_updates"),
                    "batch_size": b.get("batch_size"),
                    "pool_examples": b.get("pool_examples"),
                    "unique_examples_seen": b.get("unique_examples_seen"),
                    "effective_epochs": round(float(b.get("effective_epochs", 0.0)), 3),
                    "positives_seen": b.get("positives_seen"),
                    "negative_shortfall_visits": b.get("negative_shortfall_visits"),
                    "gpu_hours_train_loop": round(float(b.get("gpu_hours_train_loop", 0.0)), 4),
                    "examples_kept_share": f.get("examples_kept_share"),
                    "positives_kept_share": f.get("positives_kept_share"),
                    "loss_first": (tr.get("loss_first") or {}).get("loss"),
                    "loss_last": (tr.get("loss_last") or {}).get("loss"),
                }
            )
    return out


def pilot_tables(
    results_root: str,
    pilot: Mapping[str, Any],
    out_dir: str,
    seed: int = 0,
) -> Record:
    """All tables of one pilot from its specification.

    ``pilot``: ``name``, ``reference`` (exp_id), ``conditions`` (list of exp_ids; the reference
    included), optional ``section`` and ``sub`` (an override evaluation, e.g. the Verified-six one),
    optional ``label`` (written into every row).
    """
    section = str(pilot.get("section", "evaluation"))
    sub = str(pilot.get("sub", ""))
    conds = {c: load_condition(results_root, c, section, sub) for c in pilot["conditions"]}
    labels = {"pilot": pilot["name"], "evaluation": section, "label": pilot.get("label", "")}
    effects: list[Record] = []
    spread: list[Record] = []
    for kind in ("dense", "rrf"):
        for level in ("L2", "L3"):
            for reading in READINGS:
                effects += contrast_rows(
                    conds,
                    str(pilot["reference"]),
                    kind=kind,
                    level=level,
                    reading=reading,
                    seed=seed,
                    labels=labels,
                )
                spread += seed_spread(conds, kind=kind, level=level, reading=reading)
    costs = cost_rows(conds)
    stem = os.path.join(out_dir, f"t2_{pilot['name']}")
    write_csv(f"{stem}_effects.csv", effects)
    write_csv(f"{stem}_seeds.csv", spread)
    write_csv(f"{stem}_runs.csv", costs)
    return {
        "version": T2_TABLES_VERSION,
        "pilot": pilot["name"],
        "runs": {c: [r.seed for r in rs] for c, rs in conds.items()},
        "effect_rows": len(effects),
        "tables": [f"{stem}_effects.csv", f"{stem}_seeds.csv", f"{stem}_runs.csv"],
    }


# --------------------------------------------------------------------------- teacher ranks


def wilson_interval(k: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    """Wilson score interval of a binomial share ``k / n`` (95% by default)."""
    if n <= 0:
        return (float("nan"), float("nan"))
    p = k / n
    den = 1 + z * z / n
    mid = (p + z * z / (2 * n)) / den
    half = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / den
    return (max(0.0, mid - half), min(1.0, mid + half))


def teacher_rows(
    rank_paths: Sequence[str],
    teachers: Sequence[str],
    ks: Sequence[int],
    draws: int,
    seed: int,
) -> tuple[list[Record], list[Record]]:
    """K-rank shares per teacher (and the agreement of each pair) and pairwise agreement rows.

    Shares on the selection (no strata): positives inside the top K, directories with no positive
    inside, with Wilson 95% intervals for the directory share (the exact interval of E-POOL-RANKS
    overflows a float at n = 2,000) (positives within one directory
    are not independent, so the positive share carries no interval here). Agreement: Spearman of
    ranks per positive (instance-clustered bootstrap) and Cohen's kappa of top-K membership, as in
    E-POOL-RANKS (``ril.analysis.x3_tables.agreement_rows``).
    """
    from ril.analysis.x3_tables import RankSet, _rank_map, agreement_rows
    from ril.training import pool_ranks as pr
    from ril.training.pool_check import split_instance_dir

    rows = [r for p in rank_paths for r in pr.read_jsonl(p)]
    dirs = sorted({str(r["dir"]) for r in rows})
    insts = []
    for d in dirs:
        sp = split_instance_dir(d)
        if sp is None:
            raise ValueError(f"unreadable instance directory {d!r}")
        insts.append(pr.PoolInstance(d, sp[0], sp[1], 0, 0, False, 0))
    sets = {t: RankSet(t, insts, rows) for t in teachers}
    shares: list[Record] = []

    def share(name: str, per_dir: list[list[int]]) -> None:
        n_dir = len(per_dir)
        n_pos = sum(len(x) for x in per_dir)
        for k in ks:
            inside = sum(1 for xs in per_dir for x in xs if x <= k)
            none = sum(1 for xs in per_dir if not any(x <= k for x in xs))
            lo, hi = wilson_interval(none, n_dir)
            shares.append(
                {
                    "teacher": name,
                    "k": k,
                    "directories": n_dir,
                    "positives": n_pos,
                    "positives_inside_share": round(inside / n_pos, 4) if n_pos else None,
                    "directories_none_inside": none,
                    "directories_none_inside_share": round(none / n_dir, 4) if n_dir else None,
                    "dir_ci": [round(lo, 4), round(hi, 4)],
                }
            )

    for t, s in sets.items():
        share(t, s.ranks)
    agree: list[Record] = []
    for i, a in enumerate(teachers):
        for b in teachers[i + 1 :]:
            agree += agreement_rows(sets[a], sets[b], ks, draws, seed)
            ra, rb = _rank_map(sets[a]), _rank_map(sets[b])
            per: dict[str, list[int]] = {}
            for key in sorted(set(ra) & set(rb)):
                per.setdefault(key[0], []).append(max(ra[key], rb[key]))
            share(f"{a}+{b}", [per[d] for d in sorted(per)])
    return shares, agree
