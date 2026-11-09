"""Final analysis of the RQ2 experiment: arms, paired contrasts, Holm, delta, verdicts, fallback.

Implements ``docs/RQ2_PROTOCOL.md`` sections 4, 6 and 11: D17 (mean over queries,
repository-clustered bootstrap), D69 (two confirmatory contrasts), D71 (L3 metric Recall@100 with
nDCG@10 beside it), D72 (Holm within each family, uncorrected intervals beside), D73 (delta = 1.5
points), D80 (the fallback RQ3 contrast), D82 (fresh noise draws are the caller's data, not a
choice here) and D100 (sealed order: the final evaluation sets are read only after a named dev
analysis).

Nothing in this module chooses an analysis. Every rule is a constant or a function below, written
before any final row exists, and each is tied to its protocol source in its docstring. Where the
protocol is silent the module takes the narrowest reading and says so in ``ASSUMPTIONS``; the
questions that follow from those are listed in the entry ``E-RQ2-ANALYSIS``.

Input rows (one per run, cell, seed, evaluation set, level, repository, query): ``run_id, cell,
seed, eval_set, level, repo, query_id, n_positives, ndcg10, recall100``. Values are fractions;
every reported difference is in percentage points. No torch, no model call.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt

from ril.evaluation.stats import Boot

ANALYSIS_VERSION = "rq2-final-analysis/v1"
ALPHA = 0.05
"""Two-sided level of every interval and of the Holm family (docs/RQ2_PROTOCOL.md section 4)."""
DELTA = 1.5
"""Smallest difference worth reporting, in points at both levels (D73)."""
DRAWS = 2000
BOOT_SEED = 0
"""Bootstrap draws and seed of section 4 ("2,000 draws, seed 0")."""
MIN_CLUSTERS = 3
"""Repository-clustered interval from three repositories up, query-level below (section 4)."""

LEVELS: tuple[str, ...] = ("L2", "L3")
METRICS: tuple[str, ...] = ("ndcg10", "recall100")
PRIMARY_METRIC: Mapping[str, str] = {"L2": "ndcg10", "L3": "recall100"}
"""L2 nDCG@10, L3 Recall@100 with nDCG@10 beside it (D71)."""
DEV_SETS: tuple[str, ...] = ("dev",)
SEALED_SETS: tuple[str, ...] = ("eight", "exec377")
"""The eight evaluation repositories (D100) and the executable 377 (D106): final, read once."""

ROW_COLUMNS: tuple[str, ...] = (
    "run_id",
    "cell",
    "seed",
    "eval_set",
    "level",
    "repo",
    "query_id",
    "n_positives",
    "ndcg10",
    "recall100",
)
RUN_COLUMNS: tuple[str, ...] = (
    "run_id",
    "cell",
    "seed",
    "config_hash",
    "optimizer_updates",
    "examples_seen",
    "distinct_directories_seen",
    "pool_examples",
)
"""Per-run diagnostics. One example is one pool directory visit (docs/RQ2_PROTOCOL.md section 3,
matching rule), so the distinct examples a run saw are the distinct directories."""

ASSUMPTIONS: tuple[str, ...] = (
    "Holm family = the contrasts of one family on one evaluation set, both levels (m counts the "
    "contrasts that exist on that set); sets are never pooled",
    "families follow section 4 with D69 applied: confirmatory (FILTER-BM25 against RAW and "
    "against the subsample), then SweRankEmbed-Small, then WEIGHT and CURRICULUM, then the "
    "injected calibration cells; all but the first are exploratory",
    "the interval a verdict is read from is the Holm-adjusted interval of the contrast's own "
    "family; the uncorrected interval is reported beside it",
    "the L3 leave-largest-repository-out check (rule 3) compares the sign of the point estimate",
    "arms separate (D80, rule 7) iff FILTER-BM25 against RAW is positive on every final set that "
    "has both levels, and at least one does; exploratory contrasts never decide the fallback",
    "the indistinguishable flag (rule 4) is |difference| below the pooled seed SD of the two cells",
)


class SealedOrderError(ValueError):
    """A final evaluation set was read without naming the dev analysis that precedes it (D100)."""


_ENTRY_ID = re.compile(r"^E-[A-Z0-9]+(?:-[A-Z0-9]+)*$")


def require_dev_analysis(entry_id: str | None, docs_root: Path | None = None) -> str:
    """The id of the dev-analysis entry that precedes a look at the final sets, validated (D100).

    The id must have the form of an experiment entry id and, when ``docs_root`` is given, must be a
    registry row of ``docs/EXPERIMENTS.md`` or ``docs/experiments/*.md``.
    """
    if not entry_id or not _ENTRY_ID.match(entry_id):
        raise SealedOrderError(
            "the final evaluation sets are sealed: give the id of the dev-analysis entry that "
            "precedes them (D100)"
        )
    if docs_root is not None:
        files = [
            docs_root / "docs" / "EXPERIMENTS.md",
            *sorted((docs_root / "docs").glob("experiments/*.md")),
        ]
        needle = f"| {entry_id} |"
        if not any(f.exists() and needle in f.read_text(encoding="utf-8") for f in files):
            raise SealedOrderError(
                f"dev-analysis entry {entry_id} is not in the experiment registry"
            )
    return entry_id


def check_sealed(
    eval_sets: Iterable[str], dev_analysis_id: str | None, docs_root: Path | None
) -> str | None:
    """Refuse a sealed set without the dev-analysis id; return the id when one is needed."""
    if any(s in SEALED_SETS for s in eval_sets):
        return require_dev_analysis(dev_analysis_id, docs_root)
    return dev_analysis_id


# ------------------------------------------------------------------------------------ input

Record = dict[str, Any]
Arr = npt.NDArray[np.float64]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_rows(
    path: Path, *, dev_analysis_id: str | None = None, docs_root: Path | None = None
) -> list[Record]:
    """Per-query rows of a CSV. Refuses a sealed evaluation set without ``dev_analysis_id``."""
    with open(path, encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        missing = set(ROW_COLUMNS) - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"{path}: missing columns {sorted(missing)}")
        raw = list(reader)
    check_sealed({r["eval_set"] for r in raw}, dev_analysis_id, docs_root)
    out: list[Record] = []
    for r in raw:
        out.append(
            {
                **{k: r[k] for k in ("run_id", "cell", "eval_set", "level", "repo", "query_id")},
                "seed": int(r["seed"]),
                "n_positives": None if r["n_positives"] == "" else int(r["n_positives"]),
                "ndcg10": float(r["ndcg10"]),
                "recall100": float(r["recall100"]),
            }
        )
    return out


def read_runs(path: Path) -> list[Record]:
    with open(path, encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        missing = set(RUN_COLUMNS) - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"{path}: missing columns {sorted(missing)}")
        return [dict(r) for r in reader]


@dataclass
class CellData:
    """One cell on one (set, level): per-seed per-query values aligned on the level's queries."""

    seeds: list[int]
    values: dict[str, Arr]
    """metric -> (seeds, queries) in fractions."""
    n_positives: list[int | None]

    def pooled(self, metric: str) -> Arr:
        """Mean over the cell's seeds per query (the cell's value; as the pilot tables do)."""
        return np.asarray(self.values[metric].mean(axis=0), dtype=np.float64)


@dataclass
class LevelPanel:
    eval_set: str
    level: str
    query_ids: list[str]
    repos: list[str]
    cells: dict[str, CellData]
    queries_dropped: int = 0

    @property
    def n_repos(self) -> int:
        return len(set(self.repos))

    @property
    def interval_kind(self) -> str:
        return "repository-clustered" if self.n_repos >= MIN_CLUSTERS else "query-level"


def build_panels(
    rows: Sequence[Mapping[str, Any]], *, intersect: bool = False
) -> dict[tuple[str, str], LevelPanel]:
    """Align rows into one panel per (evaluation set, level), queries sorted by id.

    Refuses duplicates, non-finite or out-of-range values, a query with two repositories, a cell
    whose seeds do not cover the same queries, and (unless ``intersect``) cells on different
    queries: a missing row must never be dropped silently. The order of the input rows is
    irrelevant (queries and seeds are sorted).
    """
    seen: set[tuple[str, int, str, str, str]] = set()
    grouped: dict[tuple[str, str], dict[str, dict[int, dict[str, Record]]]] = {}
    repo_of: dict[tuple[str, str, str], str] = {}
    for r in rows:
        if r["level"] not in LEVELS:
            raise ValueError(f"unknown level {r['level']!r}")
        key = (
            str(r["cell"]),
            int(r["seed"]),
            str(r["eval_set"]),
            str(r["level"]),
            str(r["query_id"]),
        )
        if key in seen:
            raise ValueError(f"duplicate row {key}")
        seen.add(key)
        for m in METRICS:
            v = float(r[m])
            if not math.isfinite(v) or not 0.0 <= v <= 1.0 + 1e-9:
                raise ValueError(f"{key}: {m} = {v!r} is not a fraction")
        rk = (str(r["eval_set"]), str(r["level"]), str(r["query_id"]))
        if repo_of.setdefault(rk, str(r["repo"])) != str(r["repo"]):
            raise ValueError(f"query {rk} appears in two repositories")
        g = grouped.setdefault((str(r["eval_set"]), str(r["level"])), {})
        g.setdefault(str(r["cell"]), {}).setdefault(int(r["seed"]), {})[str(r["query_id"])] = {
            "ndcg10": float(r["ndcg10"]),
            "recall100": float(r["recall100"]),
            "n": r.get("n_positives"),
        }
    panels: dict[tuple[str, str], LevelPanel] = {}
    for (eset, level), cells in sorted(grouped.items()):
        sets: list[set[str]] = []
        for cell, by_seed in cells.items():
            per_seed = [set(q) for q in by_seed.values()]
            if any(s != per_seed[0] for s in per_seed):
                raise ValueError(f"{eset}/{level}/{cell}: seeds cover different queries")
            sets.append(per_seed[0])
        common = set.intersection(*sets)
        union = set.union(*sets)
        if common != union and not intersect:
            raise ValueError(
                f"{eset}/{level}: cells cover different queries ({len(union) - len(common)} differ)"
            )
        ids = sorted(common)
        panel = LevelPanel(
            eset, level, ids, [repo_of[(eset, level, q)] for q in ids], {}, len(union) - len(common)
        )
        for cell, by_seed in sorted(cells.items()):
            seeds = sorted(by_seed)
            vals = {
                m: np.asarray([[by_seed[s][q][m] for q in ids] for s in seeds]) for m in METRICS
            }
            first = by_seed[seeds[0]]
            panel.cells[cell] = CellData(seeds, vals, [first[q]["n"] for q in ids])
        panels[(eset, level)] = panel
    return panels


# ------------------------------------------------------------------------------- statistics


def _quantiles(boots: Arr, alpha: float) -> tuple[float, float]:
    lo, hi = np.quantile(boots, [alpha / 2, 1 - alpha / 2])
    return float(lo), float(hi)


def bootstrap_p(boots: Arr) -> float:
    """Two-sided bootstrap p-value, ``(b + 1) / (B + 1)`` form (never exactly 0). Only orders the
    contrasts for Holm; the decisions are read off the intervals."""
    below = int((boots <= 0).sum())
    above = int((boots >= 0).sum())
    return min(1.0, 2.0 * (min(below, above) + 1) / (len(boots) + 1))


def holm_adjust(p: Sequence[float]) -> list[float]:
    """Holm step-down adjusted p-values (``p.adjust(method = "holm")``), in the input order."""
    m = len(p)
    order = sorted(range(m), key=lambda i: (p[i], i))
    out = [0.0] * m
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, (m - rank) * p[i])
        out[i] = min(1.0, running)
    return out


@dataclass(frozen=True)
class ContrastSpec:
    """arm minus reference, in a family; ``status`` is the protocol's label (D69)."""

    name: str
    arm: str
    reference: str
    family: str
    status: str


def _spec(arm: str, ref: str, family: str, status: str) -> ContrastSpec:
    return ContrastSpec(f"{arm} - {ref}", arm, ref, family, status)


def _vs_raw_and_sub(arm: str, family: str, status: str, raw: str, sub: str) -> list[ContrastSpec]:
    return [_spec(arm, raw, family, status), _spec(arm, sub, family, status)]


FINAL_CONTRASTS: tuple[ContrastSpec, ...] = (
    *_vs_raw_and_sub("mined_filter_bm25", "confirmatory", "confirmatory", "mined_raw", "mined_sub"),
    *_vs_raw_and_sub(
        "mined_filter_srs", "exploratory_teacher", "exploratory", "mined_raw", "mined_sub"
    ),
    *_vs_raw_and_sub(
        "mined_weight", "exploratory_secondary", "exploratory", "mined_raw", "mined_sub"
    ),
    *_vs_raw_and_sub(
        "mined_curriculum", "exploratory_secondary", "exploratory", "mined_raw", "mined_sub"
    ),
    _spec("inj_oracle", "inj_raw", "injected", "exploratory"),
    _spec("inj_filter_bm25", "inj_raw", "injected", "exploratory"),
    _spec("inj_filter_srs", "inj_raw", "injected", "exploratory"),
    _spec("inj_weight", "inj_raw", "injected", "exploratory"),
    _spec("inj_filter_bm25", "inj_sub", "injected", "exploratory"),
    _spec("inj_filter_srs", "inj_sub", "injected", "exploratory"),
)
"""Cell ids are those of ``ril/training/rq2_plan.py`` (a test cross-checks them)."""

CONFIRMATORY = "confirmatory"
RQ3_ARM = "mined_filter_bm25"
RQ3_REFERENCE = "mined_raw"
RQ3_FALLBACK = (
    "RAW against the untrained encoder "
    "(labelled: does training help, not does supervision quality help; D80)"
)


@dataclass
class Estimate:
    """One contrast on one (set, level, metric); ``boots`` stays out of the output."""

    spec: ContrastSpec
    eval_set: str
    level: str
    metric: str
    primary: bool
    interval_kind: str
    queries: int
    repos: int
    d: float
    ci: tuple[float, float]
    ci_query: tuple[float, float]
    ci_cluster: tuple[float, float] | None
    p: float
    per_seed: list[dict[str, float]]
    seed_sd: float | None
    sd_a: float | None
    sd_b: float | None
    boots: Arr
    holm: dict[str, Any] | None = None


def _seed_sd(per_seed_means: Arr) -> float | None:
    return float(np.std(per_seed_means, ddof=1)) if per_seed_means.size > 1 else None


def estimate(panel: LevelPanel, spec: ContrastSpec, metric: str, boot: Boot) -> Estimate | None:
    """The paired contrast of ``spec`` on one panel, or None when either cell is absent.

    Per query the cell value is the mean over its seeds; the difference is paired on the query and
    the interval resamples whole repositories (D17) when there are three or more, queries below
    that. Per-seed differences use the seeds both cells share. The bootstrap carries query and
    repository sampling, not retraining variance, so the seed spread is reported beside it.
    """
    if spec.arm not in panel.cells or spec.reference not in panel.cells:
        return None
    a, b = panel.cells[spec.arm], panel.cells[spec.reference]
    diff = 100.0 * (a.pooled(metric) - b.pooled(metric))
    clustered = panel.n_repos >= MIN_CLUSTERS
    w_main = boot.cluster if clustered else boot.micro
    boots = np.asarray(w_main @ diff, dtype=np.float64)
    ci_query = _quantiles(np.asarray(boot.micro @ diff), ALPHA)
    ci_cluster = _quantiles(np.asarray(boot.cluster @ diff), ALPHA) if clustered else None
    shared = sorted(set(a.seeds) & set(b.seeds))
    per_seed = [
        {
            "seed": float(s),
            "d": float(
                100.0
                * (a.values[metric][a.seeds.index(s)] - b.values[metric][b.seeds.index(s)]).mean()
            ),
        }
        for s in shared
    ]
    sa = _seed_sd(100.0 * a.values[metric].mean(axis=1))
    sb = _seed_sd(100.0 * b.values[metric].mean(axis=1))
    pooled = _seed_sd(np.asarray([x["d"] for x in per_seed])) if len(per_seed) > 1 else None
    return Estimate(
        spec,
        panel.eval_set,
        panel.level,
        metric,
        metric == PRIMARY_METRIC[panel.level],
        panel.interval_kind,
        len(panel.query_ids),
        panel.n_repos,
        float(diff.mean()),
        _quantiles(boots, ALPHA),
        ci_query,
        ci_cluster,
        bootstrap_p(boots),
        per_seed,
        pooled,
        sa,
        sb,
        boots,
    )


def holm_group(ests: Sequence[Estimate]) -> None:
    """Holm step-down over one family on one set (D72), decided on the intervals, in place.

    Contrasts are ordered by bootstrap p-value (ties by name). At step k of m the contrast is
    rejected when its interval at level ``1 - ALPHA / (m - k + 1)`` excludes zero; the first miss
    stops the procedure and every later contrast keeps that step's level. The reported interval
    is the one at the contrast's own step level, so "excludes zero" and "rejected" are the same
    statement. The adjusted p-value (``holm_adjust`` of the bootstrap p-values) is reported beside.
    """
    m = len(ests)
    if m == 0:
        return
    order = sorted(range(m), key=lambda i: (ests[i].p, ests[i].spec.name))
    adjusted = holm_adjust([ests[i].p for i in range(m)])
    stopped_at: int | None = None
    for rank, i in enumerate(order, start=1):
        e = ests[i]
        step = rank if stopped_at is None else stopped_at
        alpha_k = ALPHA / (m - step + 1)
        lo, hi = _quantiles(e.boots, alpha_k)
        rejected = stopped_at is None and (lo > 0 or hi < 0)
        if stopped_at is None and not rejected:
            stopped_at = rank
        e.holm = {
            "m": m,
            "rank": rank,
            "alpha_step": alpha_k,
            "ci": (lo, hi),
            "rejected": bool(rejected),
            "p_adjusted": adjusted[i],
        }


def classify(d: float, lo: float, hi: float, delta: float = DELTA) -> str:
    """The protocol's three words for one interval (section 6 with D73).

    ``reported-effect``: the interval excludes zero on the positive side and the point estimate is
    at least delta. ``inconclusive``: the lower end is at or below zero and the upper end reaches
    delta, so the design can exclude neither zero nor delta. ``estimate-with-bounds``: everything
    else, including a gain below delta and a loss (``harmful`` is flagged beside).
    """
    if lo > 0 and d >= delta:
        return "reported-effect"
    if lo <= 0 and hi >= delta:
        return "inconclusive"
    return "estimate-with-bounds"


def _leave_out(
    panel: LevelPanel, spec: ContrastSpec, metric: str, seed: int, draws: int
) -> Record | None:
    """The contrast without the repository with most queries (rule 3 names django on Verified)."""
    if spec.arm not in panel.cells or spec.reference not in panel.cells or panel.n_repos < 2:
        return None
    counts: dict[str, int] = {}
    for r in panel.repos:
        counts[r] = counts.get(r, 0) + 1
    biggest = sorted(counts, key=lambda r: (-counts[r], r))[0]
    keep = np.asarray([r != biggest for r in panel.repos])
    repos = [r for r in panel.repos if r != biggest]
    diff = (
        100.0
        * (panel.cells[spec.arm].pooled(metric) - panel.cells[spec.reference].pooled(metric))[keep]
    )
    boot = Boot(repos, seed, draws)
    clustered = len(set(repos)) >= MIN_CLUSTERS
    boots = np.asarray((boot.cluster if clustered else boot.micro) @ diff)
    lo, hi = _quantiles(boots, ALPHA)
    return {
        "left_out": biggest,
        "queries": int(keep.sum()),
        "repos": len(set(repos)),
        "d": float(diff.mean()),
        "ci": (lo, hi),
        "interval": "repository-clustered" if clustered else "query-level",
    }


def _sign(x: float) -> int:
    return (x > 0) - (x < 0)


def _is_final(eval_set: str) -> bool:
    return eval_set in SEALED_SETS


def arm_claims(
    ests: Sequence[Estimate], leave: Mapping[tuple[str, str, str], Record | None], delta: float
) -> list[Record]:
    """Section 6's verdict per (arm, reference, final set) from the primary-metric estimates.

    ``positive``: reported-effect at both levels on the final set, the same sign on dev at both
    levels, and (rule 3) the L3 estimate keeps its sign without the largest repository.
    ``level-specific``: reported-effect at exactly one level (every set with only one level lands
    here at best). ``inconclusive``: no effect and an interval reaching delta at either level, or
    an effect that dev or the leave-out check does not confirm. ``estimate-with-bounds``: the rest.
    """
    primary = [e for e in ests if e.primary and e.holm is not None]
    out: list[Record] = []
    keys = sorted({(e.spec.name, e.eval_set) for e in primary if _is_final(e.eval_set)})
    for name, eset in keys:
        by_level = {e.level: e for e in primary if e.spec.name == name and e.eval_set == eset}
        verdicts = {
            lv: classify(e.d, e.holm["ci"][0], e.holm["ci"][1], delta)
            for lv, e in by_level.items()
            if e.holm
        }
        dev = {e.level: e for e in primary if e.spec.name == name and e.eval_set in DEV_SETS}
        both = set(by_level) == set(LEVELS)
        effects = [lv for lv, v in verdicts.items() if v == "reported-effect"]
        reasons: list[str] = []
        dev_same_sign = both and all(lv in dev and dev[lv].d > 0 for lv in LEVELS)
        lo3 = leave.get((name, eset, "L3"))
        leave_ok = (
            lo3 is None or _sign(lo3["d"]) == _sign(by_level["L3"].d) if "L3" in by_level else True
        )
        if both and len(effects) == 2 and dev_same_sign and leave_ok:
            claim = "positive"
        elif len(effects) >= 1 and not (both and len(effects) == 2):
            claim = "level-specific"
        elif both and len(effects) == 2:
            claim = "inconclusive"
            if not dev_same_sign:
                reasons.append("dev does not show the same sign at both levels")
            if not leave_ok:
                reasons.append("L3 changes sign without the largest repository (rule 3)")
        elif any(v == "inconclusive" for v in verdicts.values()):
            claim = "inconclusive"
        else:
            claim = "estimate-with-bounds"
        out.append(
            {
                "contrast": name,
                "eval_set": eset,
                "family": by_level[next(iter(by_level))].spec.family,
                "levels": verdicts,
                "claim": claim,
                "reasons": reasons,
                "dev_same_sign_both_levels": bool(dev_same_sign),
                "harmful": {lv: bool(e.holm["ci"][1] < 0) for lv, e in by_level.items() if e.holm},
            }
        )
    return out


def fallback(claims: Sequence[Mapping[str, Any]]) -> Record:
    """D80 and rule 7, stated from the claims and not from judgement.

    The arms separate iff FILTER-BM25 against RAW is ``positive`` on every final set that has both
    levels and at least one such set exists. The RQ3 primary contrast is then FILTER against RAW,
    else the declared fallback.
    """
    name = f"{RQ3_ARM} - {RQ3_REFERENCE}"
    both = [c for c in claims if c["contrast"] == name and set(c["levels"]) == set(LEVELS)]
    separates = bool(both) and all(c["claim"] == "positive" for c in both)
    return {
        "rule": "arms separate iff the confirmatory FILTER-BM25 - RAW contrast is positive "
        "(both levels, dev sign, leave-out) on every final set with both levels",
        "sets_considered": [c["eval_set"] for c in both],
        "separates": separates,
        "rq3_primary_contrast": f"{RQ3_ARM} against {RQ3_REFERENCE}" if separates else RQ3_FALLBACK,
        "fallback_declared": not separates,
    }


# ------------------------------------------------------------------------- dose-response


def dose_response(
    panels: Mapping[tuple[str, str], LevelPanel],
    rates: Mapping[float, Mapping[str, str]],
    *,
    seed: int = BOOT_SEED,
    draws: int = DRAWS,
    eval_sets: Sequence[str] | None = None,
) -> list[Record]:
    """Rule 2: paired gain over RAW and share of the ORACLE-CLEAN recovery at each noise rate.

    ``rates`` maps a rate to ``{"raw": cell, "oracle": cell, "<method>": cell, ...}``. "Rises with
    r" is claimed only if the gain at the highest rate exceeds the gain at the next lower one by
    more than the difference's own interval, i.e. the paired interval of the difference of gains
    has a lower end above zero. With one rate nothing can be said about a rise.
    """
    out: list[Record] = []
    ordered = sorted(rates)
    for (eset, level), panel in sorted(panels.items()):
        if eval_sets is not None and eset not in eval_sets:
            continue
        metric = PRIMARY_METRIC[level]
        boot = Boot(panel.repos, seed, draws)
        w = boot.cluster if panel.n_repos >= MIN_CLUSTERS else boot.micro
        gains: dict[tuple[float, str], Arr] = {}
        for r in ordered:
            cells = rates[r]
            if cells["raw"] not in panel.cells:
                continue
            raw = panel.cells[cells["raw"]].pooled(metric)
            for method, cell in cells.items():
                if method == "raw" or cell not in panel.cells:
                    continue
                gains[(r, method)] = 100.0 * (panel.cells[cell].pooled(metric) - raw)
        for (r, method), g in sorted(gains.items()):
            lo, hi = _quantiles(np.asarray(w @ g), ALPHA)
            oracle = gains.get((r, "oracle"))
            share = None
            if method != "oracle" and oracle is not None and oracle.mean() > 0:
                share = float(g.mean() / oracle.mean())
            out.append(
                {
                    "eval_set": eset,
                    "level": level,
                    "metric": metric,
                    "rate": r,
                    "method": method,
                    "cell": rates[r][method],
                    "gain": float(g.mean()),
                    "ci": (lo, hi),
                    "interval": panel.interval_kind,
                    "share_of_oracle": share,
                }
            )
        for method in sorted({m for (_, m) in gains}):
            have = [r for r in ordered if (r, method) in gains]
            row: Record = {
                "eval_set": eset,
                "level": level,
                "metric": metric,
                "method": method,
                "kind": "rise",
            }
            if len(have) < 2:
                row.update(rises_with_r=None, note="not evaluable: fewer than two noise rates")
            else:
                hi_r, lo_r = have[-1], have[-2]
                dd = gains[(hi_r, method)] - gains[(lo_r, method)]
                lo, hi = _quantiles(np.asarray(w @ dd), ALPHA)
                row.update(
                    rate_high=hi_r,
                    rate_low=lo_r,
                    gain_difference=float(dd.mean()),
                    ci=(lo, hi),
                    rises_with_r=bool(lo > 0),
                )
            out.append(row)
    return out


def _paired_ci(
    panel: LevelPanel, metric: str, w: Arr, a: str, b: str
) -> tuple[float, tuple[float, float]]:
    d = 100.0 * (panel.cells[a].pooled(metric) - panel.cells[b].pooled(metric))
    return float(d.mean()), _quantiles(np.asarray(w @ d), ALPHA)


def calibration_sanity(
    panels: Mapping[tuple[str, str], LevelPanel],
    *,
    raw: str,
    oracle: str,
    clean: str | None,
    seed: int = BOOT_SEED,
    draws: int = DRAWS,
) -> list[Record]:
    """Rule 1: RAW must degrade against the clean cell and ORACLE-CLEAN must recover it.

    Both are read on the dev set only (the calibration cells are not evaluated on the final sets).
    Without a clean cell in the design the first condition cannot be evaluated, and the
    calibration is then not declared informative.
    """
    out: list[Record] = []
    for (eset, level), panel in sorted(panels.items()):
        if eset not in DEV_SETS or raw not in panel.cells or oracle not in panel.cells:
            continue
        metric = PRIMARY_METRIC[level]
        boot = Boot(panel.repos, seed, draws)
        w = boot.cluster if panel.n_repos >= MIN_CLUSTERS else boot.micro

        rec_d, rec_ci = _paired_ci(panel, metric, w, oracle, raw)
        row: Record = {
            "eval_set": eset,
            "level": level,
            "interval": panel.interval_kind,
            "oracle_minus_raw": rec_d,
            "oracle_ci": rec_ci,
            "oracle_recovers": bool(rec_ci[0] > 0),
        }
        if clean is not None and clean in panel.cells:
            deg_d, deg_ci = _paired_ci(panel, metric, w, raw, clean)
            row.update(raw_minus_clean=deg_d, raw_ci=deg_ci, raw_degrades=bool(deg_ci[1] < 0))
            row["informative"] = bool(row["oracle_recovers"] and row["raw_degrades"])
        else:
            row.update(
                raw_degrades=None,
                informative=None,
                note="not evaluable: no clean cell in the design",
            )
        out.append(row)
    return out


# ----------------------------------------------------------------------------- orchestration


def cell_summaries(
    panels: Mapping[tuple[str, str], LevelPanel], seed: int, draws: int
) -> list[Record]:
    """Per cell, set, level, metric: mean over queries, both intervals (D17), seed spread."""
    out: list[Record] = []
    for (eset, level), panel in sorted(panels.items()):
        boot = Boot(panel.repos, seed, draws)
        for cell, data in sorted(panel.cells.items()):
            for metric in METRICS:
                v = 100.0 * data.pooled(metric)
                per_seed = 100.0 * data.values[metric].mean(axis=1)
                clustered = panel.n_repos >= MIN_CLUSTERS
                out.append(
                    {
                        "cell": cell,
                        "eval_set": eset,
                        "level": level,
                        "metric": metric,
                        "primary": metric == PRIMARY_METRIC[level],
                        "queries": len(panel.query_ids),
                        "repos": panel.n_repos,
                        "seeds": data.seeds,
                        "mean": float(v.mean()),
                        "ci": _quantiles(
                            np.asarray((boot.cluster if clustered else boot.micro) @ v), ALPHA
                        ),
                        "ci_query": _quantiles(np.asarray(boot.micro @ v), ALPHA),
                        "ci_cluster": _quantiles(np.asarray(boot.cluster @ v), ALPHA)
                        if clustered
                        else None,
                        "interval": panel.interval_kind,
                        "per_seed": [float(x) for x in per_seed],
                        "seed_sd": _seed_sd(per_seed),
                        "positives_total": sum(n for n in data.n_positives if n is not None)
                        if any(n is not None for n in data.n_positives)
                        else None,
                    }
                )
    return out


def diagnostics(runs: Sequence[Mapping[str, Any]]) -> dict[str, Record]:
    """Distinct-example diagnostics per cell, carried into every table (matching rule, D42).

    A cell repeats examples when it visited more than it saw distinct, and is below the common
    distinct count when another cell of the same data family saw more distinct directories (the
    family is the cell-id prefix before the first underscore).
    """
    by_cell: dict[str, list[Mapping[str, Any]]] = {}
    for r in runs:
        by_cell.setdefault(str(r["cell"]), []).append(r)
    out: dict[str, Record] = {}
    for cell, rs in sorted(by_cell.items()):
        distinct = [int(r["distinct_directories_seen"]) for r in rs]
        seen = [int(r["examples_seen"]) for r in rs]
        out[cell] = {
            "runs": len(rs),
            "seeds": sorted(int(r["seed"]) for r in rs),
            "config_hashes": {str(r["seed"]): str(r["config_hash"]) for r in rs},
            "optimizer_updates": sorted({int(r["optimizer_updates"]) for r in rs}),
            "pool_examples": sorted({int(r["pool_examples"]) for r in rs}),
            "examples_seen": seen,
            "distinct_directories_seen": distinct,
            "distinct_min": min(distinct),
            "distinct_max": max(distinct),
            "repeats_examples": any(s > d for s, d in zip(seen, distinct, strict=True)),
        }
    for cell, rec in out.items():
        fam = cell.split("_", 1)[0]
        top = max(r["distinct_max"] for c, r in out.items() if c.split("_", 1)[0] == fam)
        rec["below_common_distinct"] = rec["distinct_min"] < top
    return out


def _jsonable(x: Any) -> Any:
    if isinstance(x, dict):
        return {str(k): _jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_jsonable(v) for v in x]
    if isinstance(x, (np.floating, float)):
        return None if not math.isfinite(float(x)) else round(float(x), 6)
    if isinstance(x, np.integer):
        return int(x)
    if isinstance(x, np.bool_):
        return bool(x)
    return x


def _estimate_record(e: Estimate, leave: Record | None, diag: Mapping[str, Record]) -> Record:
    d_a, d_b = diag.get(e.spec.arm), diag.get(e.spec.reference)
    rec: Record = {
        "contrast": e.spec.name,
        "arm": e.spec.arm,
        "reference": e.spec.reference,
        "family": e.spec.family,
        "status": e.spec.status,
        "eval_set": e.eval_set,
        "level": e.level,
        "metric": e.metric,
        "primary": e.primary,
        "queries": e.queries,
        "repos": e.repos,
        "interval": e.interval_kind,
        "clustering": "whole repositories resampled, per-query mean over seeds, paired on the query"
        if e.interval_kind == "repository-clustered"
        else "queries resampled (fewer than three repositories), paired on the query",
        "d": e.d,
        "ci_uncorrected": e.ci,
        "ci_query": e.ci_query,
        "ci_cluster": e.ci_cluster,
        "p_bootstrap": e.p,
        "per_seed": e.per_seed,
        "seed_sd_of_difference": e.seed_sd,
        "seed_sd_arm": e.sd_a,
        "seed_sd_reference": e.sd_b,
        "indistinguishable_within_seed_sd": None,
        "holm": e.holm,
        "delta": DELTA,
        "class": None,
        "harmful": None,
        "leave_largest_repo_out": leave,
        "distinct_directories_arm": d_a["distinct_directories_seen"] if d_a else None,
        "distinct_directories_reference": d_b["distinct_directories_seen"] if d_b else None,
    }
    if e.sd_a is not None and e.sd_b is not None:
        rec["indistinguishable_within_seed_sd"] = bool(
            abs(e.d) < math.sqrt((e.sd_a**2 + e.sd_b**2) / 2)
        )
    if e.holm is not None:
        rec["class"] = classify(e.d, e.holm["ci"][0], e.holm["ci"][1])
        rec["harmful"] = bool(e.holm["ci"][1] < 0)
    return rec


def analyse(
    rows: Sequence[Mapping[str, Any]],
    runs: Sequence[Mapping[str, Any]],
    *,
    source_kind: str,
    dev_analysis_id: str | None = None,
    docs_root: Path | None = None,
    contrasts: Sequence[ContrastSpec] = FINAL_CONTRASTS,
    rates: Mapping[float, Mapping[str, str]] | None = None,
    clean_cell: str | None = None,
    seed: int = BOOT_SEED,
    draws: int = DRAWS,
    intersect: bool = False,
    inputs: Sequence[Mapping[str, str]] = (),
) -> Record:
    """The whole analysis of one set of final (or pilot, or synthetic) rows as a JSON-able dict.

    ``source_kind`` is ``final``, ``pilot`` or ``synthetic``; only ``final`` may enter a headline
    table. Refuses sealed evaluation sets unless ``dev_analysis_id`` names the dev analysis entry
    (D100) and records it. ``inputs`` lists ``{path, sha256}`` of the files the rows came from.
    """
    if source_kind not in ("final", "pilot", "synthetic"):
        raise ValueError(f"unknown source_kind {source_kind!r}")
    eval_sets = sorted({str(r["eval_set"]) for r in rows})
    entry = check_sealed(eval_sets, dev_analysis_id, docs_root)
    panels = build_panels(rows, intersect=intersect)
    diag = diagnostics(runs)
    boots: dict[tuple[str, str], Boot] = {k: Boot(p.repos, seed, draws) for k, p in panels.items()}
    ests: list[Estimate] = []
    for (eset, level), panel in sorted(panels.items()):
        for spec in contrasts:
            for metric in METRICS:
                e = estimate(panel, spec, metric, boots[(eset, level)])
                if e is not None:
                    ests.append(e)
    groups: dict[tuple[str, str], list[Estimate]] = {}
    for e in ests:
        if e.primary:
            groups.setdefault((e.spec.family, e.eval_set), []).append(e)
    for g in groups.values():
        holm_group(g)
    leave: dict[tuple[str, str, str], Record | None] = {}
    for e in ests:
        if e.primary and _is_final(e.eval_set):
            leave[(e.spec.name, e.eval_set, e.level)] = _leave_out(
                panels[(e.eval_set, e.level)], e.spec, e.metric, seed, draws
            )
    claims = arm_claims(ests, leave, DELTA)
    out: Record = {
        "version": ANALYSIS_VERSION,
        "source_kind": source_kind,
        "dev_analysis_entry": entry,
        "eval_sets": eval_sets,
        "alpha": ALPHA,
        "delta": DELTA,
        "draws": draws,
        "bootstrap_seed": seed,
        "assumptions": list(ASSUMPTIONS),
        "queries_dropped_by_intersection": {
            f"{k[0]}/{k[1]}": p.queries_dropped for k, p in panels.items()
        },
        "inputs": [dict(i) for i in inputs],
        "diagnostics": diag,
        "cells": cell_summaries(panels, seed, draws),
        "contrasts": [
            _estimate_record(e, leave.get((e.spec.name, e.eval_set, e.level)), diag) for e in ests
        ],
        "claims": claims,
        "fallback": fallback(claims),
        "dose_response": dose_response(panels, rates, seed=seed, draws=draws) if rates else [],
        "calibration_sanity": calibration_sanity(
            panels, raw="inj_raw", oracle="inj_oracle", clean=clean_cell, seed=seed, draws=draws
        )
        if any("inj_raw" in p.cells for p in panels.values())
        else [],
    }
    out = _jsonable(out)
    out["analysis_hash"] = hashlib.sha256(
        json.dumps({k: v for k, v in out.items() if k != "inputs"}, sort_keys=True).encode()
    ).hexdigest()
    return out


def write_summary(summary: Mapping[str, Any], path: Path) -> str:
    """Write the machine-readable summary; return its sha256."""
    text = json.dumps(summary, sort_keys=True, indent=1) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return hashlib.sha256(text.encode()).hexdigest()


def analyse_files(
    rows_path: Path,
    runs_path: Path,
    out_path: Path,
    *,
    dev_analysis_id: str | None,
    source_kind: str = "final",
    docs_root: Path | None = None,
    seed: int = BOOT_SEED,
    draws: int = DRAWS,
) -> Record:
    """File entry point behind ``scripts/rq2_analysis.py``; hashes both inputs into the summary."""
    rows = read_rows(rows_path, dev_analysis_id=dev_analysis_id, docs_root=docs_root)
    runs = read_runs(runs_path)
    inputs = [
        {"path": str(rows_path), "sha256": sha256_file(rows_path)},
        {"path": str(runs_path), "sha256": sha256_file(runs_path)},
    ]
    summary = analyse(
        rows,
        runs,
        source_kind=source_kind,
        dev_analysis_id=dev_analysis_id,
        docs_root=docs_root,
        rates={
            0.4: {
                "raw": "inj_raw",
                "oracle": "inj_oracle",
                "filter_bm25": "inj_filter_bm25",
                "filter_srs": "inj_filter_srs",
                "weight": "inj_weight",
            }
        },
        seed=seed,
        draws=draws,
        inputs=inputs,
    )
    write_summary(summary, out_path)
    return summary
