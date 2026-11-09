"""Plan-only view of the RQ2 final experiment: cell table, budget, job graph, configuration checks.

Nothing here trains, encodes or touches a GPU, and nothing needs torch: configurations are rendered
in memory from the pilot templates, validated and hashed with ``ril.training.config_io`` (the same
functions the training run uses), and the cost and job graph are computed from stated unit costs.
Implements ``docs/RQ2_PROTOCOL.md`` section 11 (O2, O7, O12, O15) and ``docs/RQ2_LAUNCH_PLAN.md``.

Every unit cost carries its source and evidence class; a changed cost is a changed constant here,
never an edit to a result. The cell list is the protocol's option E (section 5): 6 cells on the
mined set and 6 on the pool with injected noise at r = 0.4, three seeds each.

Placement, retention, the evaluation scope and the job graph follow the launch rulings D124 to D133
(``docs/RQ2_LAUNCH_PLAN.md`` section 9): mined-set cells train on account C, the injected-noise
family on account A; the 18 mined-set models are retained; training jobs score the dev set only and
the eight repositories and the executable 377 are scored once, from the retained models, after the
dev analysis; one GPU job per run.
"""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from ril.training.config_io import (
    Record,
    check_comparable,
    config_hash,
    held_identical_view,
    planned_end,
    teacher_equals_base,
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

PREP_HOURS = 3.0
OVERLAP_HOURS = 2.0
BLOCK3_CAP = 46.7
OPTION_E_TOTAL = 38.9

FAMILY_ACCOUNTS: dict[str, str] = {"mined": "C", "injected": "A"}
"""Where each data condition trains (D124): the mined store and its cache live on C, the injected
pool and its score stores on A."""
MEM_REQUEST_MB: dict[str, int] = {"mined": 30 * 1024, "injected": 24 * 1024}
"""Per-job memory request. Mined: 26 GB projected peak (17 GB decoded cache, 3 GB training, 6 GB
evaluation) against the 32,000 MB per-user limit; injected: the pilots' 24 GB (18 GB measured)."""
MEM_CEILING_MB = 32000
DENSE_TEACHER_MEASURE_GPU_H = 0.4
DENSE_TEACHER_CAP_GPU_H = 6.0
"""FILTER-SweRankEmbed-Small on the mined set runs only if the measured full-store teacher pass
costs at most this (D125): the headroom under the cap is 46.7 - 28.7 = 18.0."""


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
    "executable_377_built": Cost(
        0.388,
        "E-RQ3-UNITS: 0.377 for the five repositories' 214,285 distinct texts (job 63012) plus "
        "0.011 for the xarray build (37.9 s, job 63024), untrained encoder, 512 tokens",
        "measured",
    ),
    "executable_377_stored": Cost(
        0.292,
        "upper bound for the 36 instances with earlier stores: the whole six-folder store "
        "(114,503 distinct texts at 109 texts/s) is encoded unless a per-instance restriction "
        "is built",
        "projected",
    ),
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
    conditional: str | None = None
    """Decision that gates the cell (``D125``): the cell is planned but not launched until met."""

    @property
    def retain(self) -> bool:
        """Mined-set models are retained (D129); injected-noise models are not."""
        return self.family == "mined"


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
    Cell(
        "mined_filter_srs",
        "mined",
        "FILTER",
        _SRS,
        "exploratory",
        None,
        _filter(_SRS),
        True,
        conditional="D125",
    ),
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

OPEN_CELL_CHOICES: tuple[str, ...] = ()
"""Settled by D126 (BM25 teacher for WEIGHT and CURRICULUM on the mined set) and D128 (no
1,000-update sensitivity on the mined set); nothing is left open in the cell table."""


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


FILTER_SIZE_TOKEN = "filter_size"
"""Symbolic subsample size of a committed configuration: the count exists after the prep job."""
FILTER_SIZE_PLACEHOLDER = 1

PROTOCOL_HELD: dict[str, Any] = {
    "model": {
        "kind": "sentence_transformers",
        "encoder": "coderankembed",
        "max_tokens": 512,
        "gradient_checkpointing": True,
    },
    "batch": {"batch_size": 32, "negatives_per_example": 1, "max_positives": 1},
    "negatives": {"name": "random_repo"},
    "loss": {"form": "sum_in_numerator", "normaliser": "batch", "temperature": 0.05},
    "optimizer": {
        "name": "adamw",
        "lr": 2.0e-5,
        "weight_decay": 0.01,
        "warmup_updates": 7,
        "schedule": "linear",
        "grad_clip": 1.0,
        "precision": "amp_fp16",
    },
    "checkpoint_fixed": {"every": 100, "keep": 1, "log_every": 10, "final_dtype": "float16"},
    "budget": {"updates": 3000, "stop_after": PRIMARY_UPDATES},
    "evaluation": {
        "roles": ["dev"],
        "rrf_k": 60,
        "batch_size": 64,
        "chunks": False,
        "seed": 0,
        "baselines": [],
    },
}
"""The held-identical block of ``docs/RQ2_PROTOCOL.md`` section 3 as values (the pilots' settings,
D28, D30, D31, D68). A final configuration that differs from it anywhere is refused."""


def render_config(
    template: Mapping[str, Any],
    run: Run,
    *,
    filter_size: int | None = None,
    retain_final: bool | None = None,
    symbolic_size: bool = False,
) -> Record:
    """The configuration of a run: the template with the arm, labels, seed and update count set.

    ``template`` is a configuration of the run's data condition (``configs/experiments/rq2_final/
    _template_*.yaml``). ``filter_size`` fills the size-matched subsample of the mined set (the
    number of examples FILTER keeps, from ``train.py filter-size``); ``symbolic_size`` instead
    leaves the token ``"filter_size"`` in place (the committed form, resolved by the run job).
    ``retain_final`` defaults to the cell's rule (mined set only, D129).
    """
    cfg: Record = copy.deepcopy(dict(template))
    cell = run.cell
    arm = copy.deepcopy(dict(cell.arm_config))
    sub = arm.get("subsample")
    if sub is not None and sub["size"] == FILTER_SIZE_TOKEN and not symbolic_size:
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
    retain = cell.retain if retain_final is None else retain_final
    cfg.setdefault("checkpoint", {})["retain_final"] = bool(retain)
    if cell.noise_rate is not None:
        cfg["noise"] = {**cfg.get("noise", {}), "rate": cell.noise_rate}
    else:
        cfg.pop("noise", None)
    cfg.pop("provisional_note", None)
    return cfg


def check_protocol(cfg: Mapping[str, Any], run: Run) -> list[str]:
    """Violations of the registered design in one rendered configuration (empty = conforms).

    Held-identical block against ``PROTOCOL_HELD``; seed outside the exploratory waves (D82); FILTER
    at K = 20, positive level, with a teacher that is not the base encoder (leakage check c); BM25
    for WEIGHT and CURRICULUM on the mined set (D126); retention only on the mined set (D129); the
    dev set is the only evaluation a training job runs (D127, D100).
    """
    bad: list[str] = []
    for key, want in PROTOCOL_HELD.items():
        section = cfg["checkpoint" if key == "checkpoint_fixed" else key]
        have: dict[str, Any] = {k: section.get(k) for k in want}
        if have != want:
            bad.append(f"{key}: {have} != {want}")
    cell = run.cell
    if run.seed in WAVE_SEEDS:
        bad.append(f"seed {run.seed} is an exploratory-wave seed")
    if cfg["budget"].get("stop_after") != PRIMARY_UPDATES:
        bad.append("primary runs stop at 100 updates")
    if bool(cfg["checkpoint"].get("retain_final")) != cell.retain:
        bad.append("retain_final must be on for the mined set and off for the injected family")
    if cell.family == "mined" and "noise" in cfg:
        bad.append("the mined set carries no injected noise")
    if cell.family == "injected" and (cfg.get("noise") or {}).get("rate") != 0.4:
        bad.append("injected cells use noise rate 0.4 (D82 fresh draws, same rule)")
    arm = cfg["arm"]
    if arm.get("name") == "FILTER":
        f = arm["filter"]
        if (f.get("k"), f.get("level")) != (20, "positive"):
            bad.append("FILTER uses K = 20 at the positive level")
    if cell.family == "mined" and arm.get("name") in ("WEIGHT", "CURRICULUM"):
        t = (arm.get("weight") or arm.get("ordering") or {}).get("teacher")
        if t != "bm25":
            bad.append(f"{arm['name']} on the mined set uses the BM25 teacher (D126), not {t}")
    if cell.teacher is not None and teacher_equals_base(cfg):
        bad.append("the quality-signal teacher is the encoder being trained")
    return bad


def validate_runs(
    runs: Sequence[Run],
    templates: Mapping[str, Mapping[str, Any]],
    *,
    filter_size: int | None = None,
) -> list[Record]:
    """Render every run, check the held-identical block within each data condition, hash each.

    ``templates`` maps ``mined`` / ``injected`` to a template configuration. Raises if two runs of
    one family differ outside the arm, the labels and the seed, or if a run departs from the
    registered design (:func:`check_protocol`). Storage keys are not hashed. Without
    ``filter_size`` the subsample cells are hashed with a placeholder size and their row says
    ``hash_final: false``.
    """
    out: list[Record] = []
    by_family: dict[str, list[Record]] = {}
    for run in runs:
        size = FILTER_SIZE_PLACEHOLDER if filter_size is None else filter_size
        cfg = render_config(templates[run.cell.family], run, filter_size=size)
        problems = check_protocol(cfg, run)
        if problems:
            raise ValueError(f"{run.run_id} departs from the registered design: {problems}")
        by_family.setdefault(run.cell.family, []).append(
            {k: v for k, v in cfg.items() if k != "seed"}
        )
        end = planned_end(cfg)
        sized = "subsample" in run.cell.arm_config and (
            run.cell.arm_config["subsample"]["size"] == FILTER_SIZE_TOKEN
        )
        out.append(
            {
                "run_id": run.run_id,
                "cell": run.cell.cell_id,
                "family": run.cell.family,
                "account": FAMILY_ACCOUNTS[run.cell.family],
                "status": run.cell.status,
                "conditional": run.cell.conditional,
                "seed": run.seed,
                "config_hash": config_hash(cfg),
                "hash_final": not (sized and filter_size is None),
                "optimizer_updates": end,
                "example_visits": end * int(cfg["batch"]["batch_size"]),
                "retain_final": bool(cfg["checkpoint"].get("retain_final")),
                "memory_mb": MEM_REQUEST_MB[run.cell.family],
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


def write_configs(
    runs: Sequence[Run],
    templates: Mapping[str, Mapping[str, Any]],
    out_dir: str,
    *,
    filter_size: int | None = None,
) -> list[Record]:
    """Write one configuration file per run (``<run_id>.yaml``) and return the plan rows with paths.

    Without ``filter_size`` the size-matched subsample keeps the symbolic token (the committed
    form); with it the size is resolved (the form a run job trains from). Every written file is
    read back through ``load_train_config`` and its hash compared with the plan's.
    """
    import os

    import yaml

    from ril.training.config_io import load_train_config

    rows = validate_runs(runs, templates, filter_size=filter_size)
    os.makedirs(out_dir, exist_ok=True)
    for run, row in zip(runs, rows, strict=True):
        cfg = render_config(
            templates[run.cell.family],
            run,
            filter_size=filter_size,
            symbolic_size=filter_size is None,
        )
        path = os.path.join(out_dir, f"{run.run_id}.yaml")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(
                "# RQ2 final experiment run (rendered from the cell table by "
                "scripts/rq2_plan.py render; do not edit by hand).\n"
            )
            yaml.safe_dump(cfg, handle, sort_keys=False, width=120)
        back = load_train_config(path)
        if filter_size is not None and config_hash(back) != row["config_hash"]:
            raise ValueError(f"{path}: written file does not reproduce the planned hash")
        row["path"] = path
    return rows


def cell_table_digest(cells: Sequence[Cell] = CELLS) -> str:
    """SHA-256 of the cell table (the registration of the design, checked by the preflight)."""
    blob = json.dumps(
        [
            {
                "cell": c.cell_id,
                "family": c.family,
                "arm": dict(c.arm_config),
                "teacher": c.teacher,
                "status": c.status,
                "noise": c.noise_rate,
                "conditional": c.conditional,
            }
            for c in cells
        ],
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def unique_example_check(
    visits: int, pool_examples: int, filter_kept: int | None
) -> dict[str, Any]:
    """Whether each arm can reach ``visits`` distinct examples without repeating (G5, D42, D133).

    ``pool_examples``: directories with a positive after the held-out filter and the overlap drop;
    ``filter_kept``: examples FILTER keeps (the size-matched subsample draws the same number).
    Where an arm cannot, it cycles its own pool in a fresh seeded order per pass (D133) and the
    number of distinct examples it saw is stored with the result.
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


def retained_runs(runs: Sequence[Run]) -> list[Run]:
    """Runs whose final model is retained (the mined set, D129)."""
    return [r for r in runs if r.cell.retain]


def look_cost_per_checkpoint(basis: str) -> float:
    """GPU-hours to score one checkpoint on the executable 377 (D127).

    Measured basis: the 341 built instances (0.377, measured) plus, conservatively, the whole
    six-folder store for the 36 earlier ones (0.292, projected upper bound). Protocol basis: the
    protocol's 0.40 placeholder.
    """
    if basis == "protocol":
        return COSTS["verified_look"].value
    return COSTS["executable_377_built"].value + COSTS["executable_377_stored"].value


def budget(
    runs: Sequence[Run],
    *,
    basis: str = "measured",
    scope: str = "rulings",
    sensitivity_runs: int = 0,
) -> Record:
    """GPU-hours of the runs against Block 3 (46.7) on a stated basis and evaluation scope.

    ``basis``: ``protocol`` (the reasoned unit costs of section 5) or ``measured`` (this project's
    measured unit costs; the stored part of the 377 stays a projected upper bound).
    ``scope``: ``option_e`` (the registered design: the eight repositories for every run, one
    look per mined run, reproduces 38.9 on the protocol basis) or ``rulings`` (D127, D129: the
    eight repositories and the executable 377 are scored from the 18 retained mined models only;
    training jobs score the dev set).
    The conditional dense teacher (D125) is reported apart, never inside the total.
    """
    run_dev = COSTS["run_dev_protocol" if basis == "protocol" else "run_dev"].value
    eight = COSTS["eight_repos_protocol" if basis == "protocol" else "eight_repos"].value
    look = look_cost_per_checkpoint(basis)
    n = len(runs)
    kept = retained_runs(runs)
    if scope == "option_e":
        eight_total = n * eight
        look_total = sum(COSTS["verified_look"].value for r in runs if r.cell.verified_look)
    elif scope == "rulings":
        eight_total = len(kept) * eight
        look_total = len(kept) * look
    else:
        raise ValueError(f"unknown scope {scope!r}")
    sens = sensitivity_runs * (COSTS["run_1000"].value + eight)
    total = n * run_dev + eight_total + look_total + sens
    conditional = DENSE_TEACHER_MEASURE_GPU_H + DENSE_TEACHER_CAP_GPU_H
    return {
        "basis": basis,
        "scope": scope,
        "runs": n,
        "retained_models": len(kept) if scope == "rulings" else None,
        "train_and_dev_eval": round(n * run_dev, 2),
        "eight_repositories": round(eight_total, 2),
        "verified_look": round(look_total, 2),
        "sensitivity_1000": round(sens, 2),
        "total": round(total, 2),
        "block3_cap": BLOCK3_CAP,
        "margin": round(BLOCK3_CAP - total, 2),
        "conditional_dense_teacher_at_most": round(conditional, 2),
        "margin_with_conditional": round(BLOCK3_CAP - total - conditional, 2),
    }


@dataclass(frozen=True)
class Job:
    job_id: str
    stage: str
    kind: str  # cpu | gpu | manual
    account: str
    after: tuple[str, ...]
    """Hard dependencies (``afterok``): data the job reads."""
    gpu_hours: float
    wall_hours: float
    note: str = ""
    chain_after: tuple[str, ...] = ()
    """Order on one account (``afterany``): one GPU job at a time, a failed run does not stop the
    chain (a rerun resumes, finished runs are skipped)."""
    conditional: str | None = None


def _run_order(runs: Sequence[Run]) -> list[Run]:
    """Seed first, then the cell table's order: a whole seed is done before the next starts."""
    pos = {c.cell_id: i for i, c in enumerate(CELLS)}
    return sorted(runs, key=lambda r: (r.seed, pos.get(r.cell.cell_id, len(pos))))


def job_graph(
    runs: Sequence[Run],
    *,
    family_accounts: Mapping[str, str] | None = None,
    store_account: str = "C",
    include_conditional: bool = True,
    queue_wait_hours: float = 0.0,
) -> list[Job]:
    """Jobs from the finished mining store to the final-sets results, one GPU job per run.

    CPU stages are single jobs on the account that holds the store (``store_account``). Each run is
    one GPU job on its family's account (D124); jobs of one account are ordered by ``chain_after``.
    Injected-noise jobs wait for nothing. Mined jobs wait for the FILTER size (and the conditional
    FILTER-SweRankEmbed-Small run for the dense teacher's pass, D125). After all training and a
    manual collection of the injected results (small files, byte-verified copy) comes the dev
    analysis, then one final-sets job per retained model (the eight repositories and the executable
    377, D127, D129), ordered on the account that holds the models. ``queue_wait_hours`` is unused
    here and kept for the signature of :func:`critical_path_hours` callers.
    """
    del queue_wait_hours
    fam_acct = dict(family_accounts or FAMILY_ACCOUNTS)
    use = [r for r in runs if include_conditional or r.cell.conditional is None]
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
        store_account,
        (rep,),
        0.0,
        OVERLAP_HOURS,
        "about 2 h linear from the pilot (1,445 s for 0.44 GB); 13 min if the index is built",
    )
    prep = add(
        "prep",
        "materialise, rank inputs, BM25 teacher, feature table, cache",
        "cpu",
        store_account,
        (ov,),
        0.0,
        PREP_HOURS,
        "reasoned: pilot 695 s materialise and 1,036 s BM25 for 1,286 directories, scaled to "
        "about 5,800 and rounded up with the cache build",
    )
    fs = add(
        "filter_size", "FILTER size for the subsample", "cpu", store_account, (prep,), 0.0, 0.1
    )
    last_on: dict[str, str] = {}

    def chain(acct: str) -> tuple[str, ...]:
        return (last_on[acct],) if acct in last_on else ()

    srs = any(r.cell.conditional == "D125" for r in use)
    acct_m = fam_acct["mined"]
    if srs:  # the measurement is cheap and decides the cell: it goes first on the mined account
        last_on[acct_m] = add(
            "teacher_measure",
            "dense teacher on 100 mined directories",
            "gpu",
            acct_m,
            (prep,),
            DENSE_TEACHER_MEASURE_GPU_H,
            DENSE_TEACHER_MEASURE_GPU_H,
            "D125: measures the full-store cost before anything else is spent",
            chain(acct_m),
            "D125",
        )

    def add_run(r: Run, extra: tuple[str, ...] = ()) -> None:
        acct = fam_acct[r.cell.family]
        after: list[str] = [fs] if r.cell.family == "mined" else []
        after.extend(extra)
        last_on[acct] = add(
            f"run_{r.run_id}",
            f"train and score dev: {r.cell.family} {r.cell.cell_id}, seed {r.seed}",
            "gpu",
            acct,
            tuple(after),
            COSTS["run_dev"].value,
            COSTS["run_dev"].value,
            "retains the final model" if r.cell.retain else "",
            chain(acct),
            r.cell.conditional,
        )

    ordered = _run_order(use)
    for r in ordered:
        if r.cell.conditional is None:
            add_run(r)
    if srs:  # the pass runs only after the unconditional runs, and only if the measurement allows
        last_on[acct_m] = add(
            "teacher_pass",
            "dense teacher over the mined store (SweRankEmbed-Small)",
            "gpu",
            acct_m,
            ("teacher_measure",),
            DENSE_TEACHER_CAP_GPU_H,
            DENSE_TEACHER_CAP_GPU_H,
            "launched only if the measured full-store cost is at most 6.0 GPU-hours (D125)",
            chain(acct_m),
            "D125",
        )
        for r in ordered:
            if r.cell.conditional == "D125":
                add_run(r, ("teacher_pass",))
    train_ids = tuple(j.job_id for j in jobs if j.job_id.startswith("run_"))
    inj_accts = {fam_acct["injected"]} - {fam_acct["mined"]}
    collect = add(
        "collect_results",
        "copy the injected family's result directories to the analysis account "
        "(small named set, byte-verified, never overwrite)",
        "manual",
        store_account,
        train_ids,
        0.0,
        0.1,
        "needed only if the families trained on different accounts: "
        + ", ".join(sorted(inj_accts) or ["no"]),
    )
    da = add(
        "dev_analysis",
        "dev analysis: paired contrasts, Holm, decision rules (the final sets follow it)",
        "cpu",
        store_account,
        (collect,),
        0.0,
        0.5,
    )
    acct = fam_acct["mined"]
    per_model = COSTS["eight_repos"].value + look_cost_per_checkpoint("measured")
    for r in _run_order(retained_runs(use)):
        jid = add(
            f"final_{r.run_id}",
            f"final sets from the retained model: {r.cell.cell_id}, seed {r.seed}",
            "gpu",
            acct,
            (da,),
            round(per_model, 3),
            round(per_model, 3),
            "eight repositories and executable 377, role test, once",
            chain(acct),
            r.cell.conditional,
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
            start = max((finish(a) for a in (*j.after, *j.chain_after)), default=0.0)
            memo[jid] = start + queue_wait_hours + j.wall_hours
        return memo[jid]

    return max(finish(j.job_id) for j in jobs)
