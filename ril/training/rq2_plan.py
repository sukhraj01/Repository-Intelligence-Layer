"""Plan-only view of the RQ2 final experiment: cell table, budget, job graph, configuration checks.

Nothing here trains, encodes or touches a GPU, and nothing needs torch: configurations are rendered
in memory from the pilot templates, validated and hashed with ``ril.training.config_io`` (the same
functions the training run uses), and the cost and job graph are computed from stated unit costs.
Implements ``docs/RQ2_PROTOCOL.md`` section 11 (O2, O7, O12, O15) and ``docs/RQ2_LAUNCH_PLAN.md``.

Every unit cost carries its source and evidence class; a changed cost is a changed constant here,
never an edit to a result. The cell list is the protocol's option E (section 5): 6 cells on the
mined set and 6 on the pool with injected noise at r = 0.4, three seeds each.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from ril.training.config_io import (
    Record,
    check_comparable,
    config_hash,
    held_identical_view,
    planned_end,
)

PLAN_VERSION = "rq2-plan/v1"

PRIMARY_UPDATES = 100
SENSITIVITY_UPDATES = 1000
BATCH_SIZE = 32
WAVE_SEEDS = frozenset({0, 1, 2})
"""Seeds of the exploratory waves: their noise realisations are keyed on the seed (D82)."""
DEFAULT_SEEDS = (100, 101, 102)
"""Three seeds disjoint from the exploratory waves, so every noise draw is fresh (D82). The values
are a tactical choice under D82; the count (three) is O7."""

BLOCK3_CAP = 46.7
OPTION_E_TOTAL = 38.9


@dataclass(frozen=True)
class Cost:
    """A unit cost in GPU-hours with where it comes from."""

    value: float
    source: str
    evidence: str  # measured | reasoned | placeholder


COSTS: dict[str, Cost] = {
    "run_dev": Cost(
        0.42, "E-MINED-PILOT 0.41 to 0.43 per run; E-PILOT-NOISE 0.37 to 0.45", "measured"
    ),
    "run_dev_protocol": Cost(0.40, "docs/RQ2_PROTOCOL.md section 5", "reasoned"),
    "eight_repos": Cost(
        0.178, "E-EVAL-REPOS-BUILD: 69,961 texts at 109 texts/s, one 2080 Ti", "measured"
    ),
    "eight_repos_protocol": Cost(
        0.48, "8 x 0.06 (section 5, reasoned from 0.30 for five)", "reasoned"
    ),
    "verified_look": Cost(
        0.40, "placeholder; 0.43 measured for Verified-six at 1,024 tokens", "placeholder"
    ),
    "run_1000": Cost(1.06, "E-PILOT-ARMS2 stage 2", "measured"),
}


@dataclass(frozen=True)
class Cell:
    """One cell of the design: an arm on a data condition."""

    cell_id: str
    family: str  # mined | injected
    arm: str
    teacher: str | None
    status: str  # confirmatory | exploratory | control
    noise_rate: float | None
    arm_config: Mapping[str, Any]
    verified_look: bool


def _filter(teacher: str) -> dict[str, Any]:
    return {"name": "FILTER", "filter": {"teacher": teacher, "k": 20, "level": "positive"}}


_SRS = "swerankembed-small"
_WEIGHT = {"form": "power", "k": 20, "param": 1.0, "floor": 0.1}

CELLS: tuple[Cell, ...] = (
    Cell("mined_raw", "mined", "RAW", None, "confirmatory", None, {"name": "RAW"}, True),
    Cell(
        "mined_sub",
        "mined",
        "RAW_SUBSAMPLE",
        None,
        "confirmatory",
        None,
        {"name": "RAW_SUBSAMPLE", "subsample": {"size": "filter_size", "draw": 0}},
        True,
    ),
    Cell(
        "mined_filter_bm25", "mined", "FILTER", "bm25", "confirmatory", None, _filter("bm25"), True
    ),
    Cell("mined_filter_srs", "mined", "FILTER", _SRS, "exploratory", None, _filter(_SRS), True),
    Cell(
        "mined_weight",
        "mined",
        "WEIGHT",
        "bm25",
        "exploratory",
        None,
        {"name": "WEIGHT", "weight": {"teacher": "bm25", **_WEIGHT}},
        True,
    ),
    Cell(
        "mined_curriculum",
        "mined",
        "CURRICULUM",
        "bm25",
        "exploratory",
        None,
        {"name": "CURRICULUM", "ordering": {"teacher": "bm25", "buckets": 4}},
        True,
    ),
    Cell("inj_raw", "injected", "RAW", None, "control", 0.4, {"name": "RAW"}, False),
    Cell(
        "inj_oracle",
        "injected",
        "ORACLE_CLEAN",
        None,
        "control",
        0.4,
        {"name": "ORACLE_CLEAN"},
        False,
    ),
    Cell(
        "inj_sub",
        "injected",
        "RAW_SUBSAMPLE",
        None,
        "control",
        0.4,
        {"name": "RAW_SUBSAMPLE", "subsample": {"size": "match_clean", "draw": 0}},
        False,
    ),
    Cell(
        "inj_filter_bm25", "injected", "FILTER", "bm25", "exploratory", 0.4, _filter("bm25"), False
    ),
    Cell("inj_filter_srs", "injected", "FILTER", _SRS, "exploratory", 0.4, _filter(_SRS), False),
    Cell(
        "inj_weight",
        "injected",
        "WEIGHT",
        _SRS,
        "exploratory",
        0.4,
        {"name": "WEIGHT", "weight": {"teacher": _SRS, **_WEIGHT}},
        False,
    ),
)

OPEN_CELL_CHOICES = (
    "teacher of WEIGHT and CURRICULUM on the mined set (not named in the protocol)",
    "the 1,000-update sensitivity subset (O1 names no cells)",
)


@dataclass(frozen=True)
class Run:
    cell: Cell
    seed: int
    updates: int

    @property
    def run_id(self) -> str:
        return f"{self.cell.cell_id}_u{self.updates}_s{self.seed}"


def plan_runs(
    seeds: Sequence[int] = DEFAULT_SEEDS,
    updates: int = PRIMARY_UPDATES,
    cells: Sequence[Cell] = CELLS,
) -> list[Run]:
    """The 36 runs of option E at the primary update count (cells x seeds)."""
    if len(set(seeds)) != len(seeds):
        raise ValueError("duplicate seeds")
    return [Run(c, int(s), updates) for c in cells for s in seeds]


def fresh_noise_check(runs: Sequence[Run]) -> list[str]:
    """Runs on injected cells whose seed equals a seed of Waves 7 or 8 (D82: draws must be new)."""
    return [r.run_id for r in runs if r.cell.noise_rate is not None and r.seed in WAVE_SEEDS]


def render_config(
    template: Mapping[str, Any],
    run: Run,
    *,
    filter_size: int | None = None,
    retain_final: bool = True,
) -> Record:
    """The configuration of a run: the template with the arm, labels, seed and update count set.

    ``template`` is a pilot configuration of the same data condition (``mp_raw_s0`` for the mined
    set, ``n1_r40_raw_s0`` for injected noise). ``filter_size`` fills the size-matched subsample of
    the mined set (the number of examples FILTER keeps, from ``train.py filter-size``).
    """
    cfg: Record = copy.deepcopy(dict(template))
    cell = run.cell
    arm = copy.deepcopy(dict(cell.arm_config))
    sub = arm.get("subsample")
    if sub is not None and sub["size"] == "filter_size":
        if filter_size is None:
            raise ValueError(f"{cell.cell_id} needs the FILTER size (train.py filter-size)")
        sub["size"] = int(filter_size)
    cfg["arm"] = arm
    cfg["exp_id"] = f"rq2f_{cell.cell_id}"
    cfg["label"] = (
        f"RQ2 final, {cell.cell_id}, seed {run.seed}, {run.updates} updates ({cell.status})"
    )
    cfg["seed"] = run.seed
    cfg["budget"] = {**cfg["budget"], "stop_after": run.updates}
    cfg.setdefault("checkpoint", {})["retain_final"] = bool(retain_final)
    if cell.noise_rate is not None:
        cfg["noise"] = {**cfg.get("noise", {}), "rate": cell.noise_rate}
    else:
        cfg.pop("noise", None)
    cfg.pop("provisional_note", None)
    return cfg


def validate_runs(
    runs: Sequence[Run],
    templates: Mapping[str, Mapping[str, Any]],
    *,
    filter_size: int | None = 1,
) -> list[Record]:
    """Render every run, check the held-identical block within each data condition, hash each.

    ``templates`` maps ``mined`` / ``injected`` to a pilot configuration. Raises if two runs of one
    family differ outside the arm, the labels and the seed (storage keys are not hashed).
    """
    out: list[Record] = []
    by_family: dict[str, list[Record]] = {}
    for run in runs:
        cfg = render_config(templates[run.cell.family], run, filter_size=filter_size)
        by_family.setdefault(run.cell.family, []).append(
            {k: v for k, v in cfg.items() if k != "seed"}
        )
        end = planned_end(cfg)
        out.append(
            {
                "run_id": run.run_id,
                "cell": run.cell.cell_id,
                "family": run.cell.family,
                "status": run.cell.status,
                "seed": run.seed,
                "config_hash": config_hash(cfg),
                "optimizer_updates": end,
                "example_visits": end * int(cfg["batch"]["batch_size"]),
                "retain_final": bool(cfg["checkpoint"].get("retain_final")),
                "teacher": run.cell.teacher,
            }
        )
    for fam, cfgs in by_family.items():
        check_comparable(cfgs)
        if len({repr(sorted(held_identical_view(c).items())) for c in cfgs}) != 1:
            raise ValueError(f"{fam}: held-identical view differs")
    hashes = [r["config_hash"] for r in out]
    if len(set(hashes)) != len(hashes):
        raise ValueError("two runs share a configuration hash")
    return out


def unique_example_check(
    visits: int, pool_examples: int, filter_kept: int | None
) -> dict[str, Any]:
    """Whether each arm can reach ``visits`` distinct examples without repeating (G5, D42).

    ``pool_examples``: directories with a positive after the held-out filter and the overlap drop;
    ``filter_kept``: examples FILTER keeps (the size-matched subsample draws the same number).
    """
    kept = filter_kept if filter_kept is not None else pool_examples
    return {
        "visits": visits,
        "raw_passes": round(visits / pool_examples, 2) if pool_examples else None,
        "filter_passes": round(visits / kept, 2) if kept else None,
        "raw_reaches_unique": pool_examples >= visits,
        "filter_reaches_unique": kept >= visits,
        "shortfall_filter": max(0, visits - kept),
    }


def budget(
    runs: Sequence[Run],
    *,
    basis: str = "measured",
    sensitivity_runs: int = 0,
) -> Record:
    """GPU-hours of the runs against Block 3 (46.7) on a stated basis.

    ``basis``: ``protocol`` (the reasoned unit costs of section 5, reproduces 38.9 for option E) or
    ``measured`` (this project's measured unit costs; the Verified look stays a placeholder).
    """
    run_dev = COSTS["run_dev_protocol" if basis == "protocol" else "run_dev"].value
    eight = COSTS["eight_repos_protocol" if basis == "protocol" else "eight_repos"].value
    look = COSTS["verified_look"].value
    n = len(runs)
    train_eval = n * (run_dev + eight)
    verified = sum(look for r in runs if r.cell.verified_look)
    sens = sensitivity_runs * (COSTS["run_1000"].value + eight)
    total = train_eval + verified + sens
    return {
        "basis": basis,
        "runs": n,
        "train_and_dev_eval": round(n * run_dev, 2),
        "eight_repositories": round(n * eight, 2),
        "verified_look": round(verified, 2),
        "sensitivity_1000": round(sens, 2),
        "total": round(total, 2),
        "block3_cap": BLOCK3_CAP,
        "margin": round(BLOCK3_CAP - total, 2),
    }


@dataclass(frozen=True)
class Job:
    job_id: str
    stage: str
    kind: str  # cpu | gpu
    account: str
    after: tuple[str, ...]
    gpu_hours: float
    wall_hours: float
    note: str = ""


def job_graph(
    runs: Sequence[Run],
    *,
    train_accounts: Sequence[str] = ("A",),
    family_accounts: Mapping[str, str] | None = None,
    store_account: str = "C",
    cells_per_job: int = 6,
    wall_per_run_hours: float = 0.42 + 0.178,
) -> list[Job]:
    """Jobs from the finished mining store to the run results, with dependencies.

    CPU stages are single jobs on the account that holds the store; GPU training jobs batch
    ``cells_per_job`` runs of one seed (a job of six runs measured 2.4 to 2.7 GPU-hours) and are
    spread over ``train_accounts`` in order, or placed by data condition with ``family_accounts``
    (``{"mined": "C", "injected": "A"}``); one GPU job at a time per account is the scheduler's
    rule, so jobs of one account chain on each other. ``store_account`` holds the mined store and
    runs the CPU stages.
    """
    jobs: list[Job] = []

    def add(*a: Any, **k: Any) -> str:
        j = Job(*a, **k)
        jobs.append(j)
        return j.job_id

    rep = add("report", "mining report", "cpu", store_account, (), 0.0, 0.1)
    ov = add(
        "overlap",
        "overlap audit and drop list",
        "cpu",
        "C",
        (rep,),
        0.0,
        2.0,
        "about 2 h linear; 13 min index",
    )
    prep = add(
        "prep",
        "materialise, rank inputs, BM25 teacher, feature table, cache",
        "cpu",
        "C",
        (ov,),
        0.0,
        6.0,
        "reasoned: pilot 1,036 s BM25 + 695 s materialise for 1,286 directories, scaled",
    )
    fs = add(
        "filter_size", "FILTER size for the subsample", "cpu", store_account, (prep,), 0.0, 0.1
    )
    by_seed: dict[int, list[Run]] = {}
    for r in runs:
        by_seed.setdefault(r.seed, []).append(r)
    last_on: dict[str, str] = {}
    accounts = list(train_accounts)
    k = 0
    for seed in sorted(by_seed):
        rs = by_seed[seed]
        for i in range(0, len(rs), cells_per_job):
            chunk = rs[i : i + cells_per_job]
            fam1 = chunk[0].cell.family
            acct = family_accounts[fam1] if family_accounts else accounts[k % len(accounts)]
            k += 1
            mined = any(r.cell.family == "mined" for r in chunk)
            after = [fs] if mined else []
            if acct in last_on:
                after.append(last_on[acct])
            fam = "+".join(sorted({r.cell.family for r in chunk}))
            gh = len(chunk) * wall_per_run_hours
            jid = f"train_s{seed}_{k}"
            add(
                jid,
                f"train and evaluate {fam}, seed {seed}",
                "gpu",
                acct,
                tuple(after),
                round(gh, 2),
                round(gh, 2),
                f"{len(chunk)} runs",
            )
            last_on[acct] = jid
    return jobs


def critical_path_hours(jobs: Sequence[Job], queue_wait_hours: float = 0.0) -> float:
    """Longest dependency chain in wall hours, with a queue wait added to every job."""
    by_id = {j.job_id: j for j in jobs}
    memo: dict[str, float] = {}

    def finish(jid: str) -> float:
        if jid not in memo:
            j = by_id[jid]
            start = max((finish(a) for a in j.after), default=0.0)
            memo[jid] = start + queue_wait_hours + j.wall_hours
        return memo[jid]

    return max(finish(j.job_id) for j in jobs)
