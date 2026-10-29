"""Tables of the learning curve E-PILOT-CURVE (exploratory) and the rule that reads them.

Reads the per-step result directories of ``ril.evaluation.curve_eval`` (``step_<n>/query_rows.csv``
under each seed's run directory) and writes, per level and column kind, the curve and the decision
of ``docs/EXPERIMENTS.md`` E-PILOT-CURVE. The rule was written before any curve was seen
(session file and EXPERIMENTS entry); it is implemented here as stated:

* Metric: L2 nDCG@10 and L3 Recall@100, in percentage points, mean over queries (an (instance,
  level) pair of the dev role); primary column = dense only, primary reading = ``units_all_nomod``
  (decision D18); the RRF column and the ``units_all`` reading are reported and do not decide.
* ``M(s)`` = mean over seeds of (metric at s minus step 0), paired over queries.
  ``G(s)`` = seed 0 minus seed 1 at s on the same queries. Step 0 is the untrained encoder, the
  same for both seeds.
* Intervals: 95% percentile bootstrap over whole repositories (clustered, decision D17) and over
  queries, 2,000 draws, one set of resamples for every row of a table
  (``ril.analysis.e3_tables.Boot``). With few repositories the clustered interval is coarse: the
  number of repositories is printed beside it.
* ``moved(s)``: clustered interval of ``M(s)`` excludes 0 and the smaller of the two seeds' own
  changes from step 0 (in the direction of ``M``) exceeds ``|G(s)|``.
* Increment ``I`` between consecutive steps: ``M(s_next) - M(s)``; it ``keeps moving`` if its
  clustered interval excludes 0 and ``|I| > |G(s_next)|``.
* ``knee`` (per level) = the smallest step from which no later increment keeps moving; N for the
  next pilot = the larger of the two levels' knees, capped at 2,000 (``beyond_2000`` if the last
  step before 3,000 still keeps moving into 3,000). ``no_movement`` if ``moved`` fails at the last
  step on a level that is needed (both levels).

Kept compatible with Python 3.10.
"""

from __future__ import annotations

import csv
import os
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from ril.analysis.e3_tables import Boot

T3_TABLES_VERSION = "t3-tables/v1"
Record = dict[str, Any]
Arr = np.ndarray[Any, Any]
LEVEL_METRIC = {"L2": "ndcg10", "L3": "recall100"}
PRIMARY_READING = "units_all_nomod"
CAP = 2000
DRAWS = 2000


def step_dirs(result_dir: str) -> dict[int, str]:
    """``{updates: directory}`` of the evaluated steps of one run."""
    out: dict[int, str] = {}
    for name in sorted(os.listdir(result_dir)):
        if name.startswith("step_") and os.path.exists(os.path.join(result_dir, name, "step.json")):
            out[int(name[5:])] = os.path.join(result_dir, name)
    return out


def read_step(path: str) -> dict[tuple[str, str, str], dict[str, float]]:
    """``{(instance, level, kind): {reading:metric: value}}`` from one step's ``query_rows.csv``.

    ``kind`` is ``dense``, ``rrf`` or ``bm25`` (the checkpoint's own columns).
    """
    out: dict[tuple[str, str, str], dict[str, float]] = {}
    with open(os.path.join(path, "query_rows.csv"), encoding="utf-8", newline="") as handle:
        for r in csv.DictReader(handle):
            kind = str(r["name"]).split(":")[0]
            vals = {
                k: float(v)
                for k, v in r.items()
                if ":" in k and k.split(":")[0].startswith("units") and v != ""
            }
            out[(r["instance"], r["level"], kind)] = vals
            out[(r["instance"], r["level"], "_repo")] = {"repo_" + str(r["repo"]): 0.0}
    return out


def build_vectors(
    runs: Mapping[int, Mapping[int, dict[tuple[str, str, str], dict[str, float]]]],
    *,
    level: str,
    kind: str,
    reading: str,
) -> tuple[list[tuple[str, str]], list[str], dict[tuple[int, int], Arr]]:
    """Per (seed, step) metric vector over the queries present in every run and step.

    Returns the queries, their repositories and ``{(seed, step): values as fractions}``. A query
    missing under any step or seed (or without gold under the reading) is dropped for all.
    """
    key = f"{reading}:{LEVEL_METRIC[level]}"
    sets = []
    for steps in runs.values():
        for q in steps.values():
            sets.append(
                {(i, lv) for (i, lv, k), v in q.items() if k == kind and lv == level and key in v}
            )
    qs = sorted(set.intersection(*sets)) if sets else []
    seed0 = next(iter(runs))
    step0 = next(iter(runs[seed0]))
    repos = [next(iter(runs[seed0][step0][(i, lv, "_repo")])).removeprefix("repo_") for i, lv in qs]
    vec = {
        (s, n): np.asarray([q[(i, lv, kind)][key] for i, lv in qs], dtype=np.float64)
        for s, steps in runs.items()
        for n, q in steps.items()
    }
    return qs, repos, vec


def curve_rows(
    runs: Mapping[int, Mapping[int, dict[tuple[str, str, str], dict[str, float]]]],
    *,
    level: str,
    kind: str,
    reading: str,
    seed: int = 0,
    draws: int = DRAWS,
) -> list[Record]:
    """The curve table of one level, kind and reading, in percentage points.

    One row per step > 0 and one per consecutive pair (``part`` = ``step`` or ``increment``).
    """
    qs, repos, vec = build_vectors(runs, level=level, kind=kind, reading=reading)
    if not qs:
        return []
    seeds = sorted(runs)
    steps = sorted(next(iter(runs.values())))
    base = vec[(seeds[0], 0)] * 100
    cols: list[Arr] = []
    meta: list[Record] = []

    def add(d: Arr, **info: Any) -> None:
        cols.append(d)
        meta.append(info)

    def mean_at(n: int) -> Arr:
        return np.mean([vec[(s, n)] for s in seeds], axis=0) * 100

    for n in steps:
        if n == 0:
            continue
        add(mean_at(n) - base, part="M", step=n, seed="mean")
        for s in seeds:
            add(vec[(s, n)] * 100 - base, part="delta", step=n, seed=s)
        if len(seeds) == 2:
            add((vec[(seeds[0], n)] - vec[(seeds[1], n)]) * 100, part="G", step=n, seed="s0-s1")
        add(mean_at(n), part="level", step=n, seed="mean")
    pos = [n for n in steps if n > 0]
    for a, b in zip([0, *pos[:-1]], pos, strict=True):
        add(mean_at(b) - (base if a == 0 else mean_at(a)), part="I", step=b, seed=f"{a}->{b}")
    d = np.stack(cols, axis=1)
    boot = Boot(repos, seed, draws)
    mean, qlo, qhi = boot.summarize(d, "micro")
    _, clo, chi = boot.summarize(d, "cluster")
    out: list[Record] = []
    for j, m in enumerate(meta):
        out.append(
            {
                **m,
                "level": level,
                "kind": kind,
                "reading": reading,
                "metric": LEVEL_METRIC[level],
                "queries": len(qs),
                "repos": len(set(repos)),
                "value": round(float(mean[j]), 3),
                "q_lo": round(float(qlo[j]), 3),
                "q_hi": round(float(qhi[j]), 3),
                "c_lo": round(float(clo[j]), 3),
                "c_hi": round(float(chi[j]), 3),
            }
        )
    return out


def _get(rows: Sequence[Record], part: str, step: int, seed: Any = None) -> Record:
    for r in rows:
        if r["part"] == part and r["step"] == step and (seed is None or r["seed"] == seed):
            return r
    raise KeyError((part, step, seed))


def _excludes_zero(r: Record) -> bool:
    return bool(r["c_lo"] > 0 or r["c_hi"] < 0)


def decide(rows: Sequence[Record], steps: Sequence[int]) -> Record:
    """Apply the rule of the module docstring to one level's primary rows."""
    pos = [n for n in steps if n > 0]
    seeds = sorted({r["seed"] for r in rows if r["part"] == "delta"})
    info: Record = {"moved": {}, "keeps_moving": {}}
    for n in pos:
        m = _get(rows, "M", n)
        g = abs(_get(rows, "G", n)["value"]) if any(r["part"] == "G" for r in rows) else 0.0
        sign = 1.0 if m["value"] >= 0 else -1.0
        smaller = min(sign * _get(rows, "delta", n, s)["value"] for s in seeds)
        info["moved"][n] = bool(_excludes_zero(m) and smaller > g)
    for a, b in zip(pos[:-1], pos[1:], strict=True):
        inc = next(r for r in rows if r["part"] == "I" and r["step"] == b)
        g = abs(_get(rows, "G", b)["value"]) if any(r["part"] == "G" for r in rows) else 0.0
        info["keeps_moving"][f"{a}->{b}"] = bool(_excludes_zero(inc) and abs(inc["value"]) > g)
    pairs = [f"{a}->{b}" for a, b in zip(pos[:-1], pos[1:], strict=True)]
    knee = pos[-1]
    for i in range(len(pairs) - 1, -1, -1):
        if info["keeps_moving"][pairs[i]]:
            break
        knee = pos[i]
    info["knee"] = knee
    info["moved_at_last"] = info["moved"][pos[-1]]
    return info


def decide_all(primary: Mapping[str, Sequence[Record]], steps: Sequence[int]) -> Record:
    """Both levels together: ``no_movement``, per-level knees, N (capped) and ``beyond_2000``."""
    per = {lv: decide(rows, steps) for lv, rows in primary.items() if rows}
    no_move = not all(p["moved_at_last"] for p in per.values()) if per else True
    knee = max(p["knee"] for p in per.values()) if per else None
    grid = [n for n in steps if n > 0]
    pairs = [f"{a}->{b}" for a, b in zip(grid[:-1], grid[1:], strict=True)]
    beyond = bool(per) and any(p["keeps_moving"].get(pairs[-1], False) for p in per.values())
    n_t4: int | None = None
    if not no_move and knee is not None:
        at_or_past = [n for n in grid if n >= knee]
        n_t4 = min(at_or_past[0] if at_or_past else CAP, CAP)
        if beyond:
            n_t4 = CAP
    return {
        "levels": per,
        "no_movement": no_move,
        "knee": knee,
        "beyond_2000": beyond,
        "n_for_next_pilot": n_t4,
    }


def load_runs(
    run_dirs: Mapping[int, str],
) -> dict[int, dict[int, dict[tuple[str, str, str], dict[str, float]]]]:
    """``{seed: {step: per-query metrics}}`` from the run directories of the seeds."""
    return {
        seed: {n: read_step(p) for n, p in step_dirs(d).items()} for seed, d in run_dirs.items()
    }


def all_tables(
    runs: Mapping[int, Mapping[int, dict[tuple[str, str, str], dict[str, float]]]],
    *,
    seed: int = 0,
    draws: int = DRAWS,
) -> tuple[list[Record], Record]:
    """Every curve row (both levels, dense and RRF, both readings) and the decision."""
    rows: list[Record] = []
    steps = sorted(next(iter(runs.values())))
    primary: dict[str, list[Record]] = {}
    for level in ("L2", "L3"):
        for kind in ("dense", "rrf"):
            for reading in (PRIMARY_READING, "units_all"):
                part = curve_rows(
                    runs, level=level, kind=kind, reading=reading, seed=seed, draws=draws
                )
                rows += part
                if kind == "dense" and reading == PRIMARY_READING:
                    primary[level] = part
    return rows, decide_all(primary, steps)
