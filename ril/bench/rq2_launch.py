"""Preflight and submission of the RQ2 final runs: one GPU job per run, only on confirmation.

Implements the checklist of ``docs/RQ2_LAUNCH_PLAN.md`` section 5 for the items a program can verify
(commit, registration of the cell table, fresh seeds, configurations that conform to the registered
design and reproduce the planned hashes, inputs present, prep summary, memory request, free space,
retention directory, evaluation stores, leakage record, the dense-teacher gate of D125) and the
submission of a family's runs on its account (D124). The submit step refuses without an explicit
confirmation and a preflight file that passed, was written for the same account, family and commit,
and is not stale; it prints the job graph first and never submits a run already queued.

No torch. Every check returns its detail, so a refusal says what is missing. The preflight file
contains no user names or paths outside the checkout and work directory names.
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import os
import re
import shutil
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any

import yaml

from ril.training import rq2_plan as rp
from ril.training.config_io import config_hash, load_train_config
from ril.training.retention import check_retain_dir

UTC = dt.timezone.utc  # noqa: UP017  (the cluster interpreter is Python 3.10: no datetime.UTC)
PREFLIGHT_VERSION = "rq2-preflight/v2"
UPDATES_VERSION = "rq2-updates/v1"
UPDATES_FILE = "rq2_updates.json"
MAX_AGE_HOURS = 48.0
JOB_PREFIX = "rq2f_"
SCRIPTS = {
    "mined": "scripts/ada/rq2f_mined_run.sbatch",
    "injected": "scripts/ada/rq2f_injected_run.sbatch",
}
CONFIG_DIR = "configs/experiments/rq2_final"
RUN_HOURS = 2
"""Wall hours requested per arm of a seed job (0.42 GPU-hours measured; cache load and queueing
margin). A seed job asks for this times its number of arms (D141), well under the 4-day limit."""
MIN_FREE_GB = {"mined": 10.0, "injected": 3.0}
"""Free space asked of the account home before launch: results and logs, and for the mined family
the 18 retained models (4.9 GB at 274 MB each) with margin."""
RETAINED_MODELS_GB = 4.9
INPUTS = {
    "mined": ("mined.jsonl.gz", "features_mined.csv"),
    "injected": (
        "pool_A.jsonl.gz",
        "pool_T3x.jsonl.gz",
        "scores_P5000_bm25.jsonl",
        "scores_P5000_swerankembed-small.jsonl",
    ),
}
"""Files a family's jobs read: the run directory's ``work/`` for the mined set, and for the injected
family the earlier noise pilot's work directory (``INPUTS_HOME_REL``): the 9 GB pool caches are
already on the account and are never copied (account A has 5 GB free)."""
INPUTS_HOME_REL = {"injected": "ril_n7/work"}
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
Record = dict[str, Any]


@dataclass(frozen=True)
class Check:
    id: str
    ok: bool
    detail: str


def _read_json(path: str) -> Record | None:
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


class UpdatesError(ValueError):
    """The mined family's update count was not computed from a prepared store (D140)."""


def compute_updates(work: str) -> Record:
    """Compute N from the prepared store and write ``work/rq2_updates.json`` (the launch step).

    Reads ``work/prep_summary.json`` (the prep job's output: ``filter_size`` is F, the FILTER pool
    after the held-out and overlap drops), applies ``rp.mined_updates`` and records F, N, the
    visits per arm and the sha256 of the summary it was computed from. Refuses a summary that is
    missing, has no usable ``filter_size``, or still holds held-out rows or an unapplied drop list.
    """
    path = os.path.join(work, "prep_summary.json")
    prep = _read_json(path)
    if prep is None:
        raise UpdatesError(f"{path} is missing: the prep job has not run")
    if prep.get("held_out_rows") != 0 or not prep.get("drop_list_applied"):
        raise UpdatesError("prep summary: held-out rows must be 0 and the drop list applied")
    try:
        pool = int(prep["filter_size"])
    except (KeyError, TypeError, ValueError) as err:
        raise UpdatesError("prep summary has no filter_size") from err
    n = rp.mined_updates(pool)
    with open(path, "rb") as handle:
        digest = hashlib.sha256(handle.read()).hexdigest()
    rec: Record = {
        "version": UPDATES_VERSION,
        "filter_pool": pool,
        "updates": n,
        "visits_per_arm": n * rp.UPDATE_VISITS,
        "rule": "N = min(100, floor(F / 32)) for every arm of the mined family (D140)",
        "prep_summary_sha256": digest,
    }
    with open(os.path.join(work, UPDATES_FILE), "w", encoding="utf-8") as handle:
        json.dump(rec, handle, indent=1, sort_keys=True)
        handle.write("\n")
    return rec


def read_updates(work: str) -> int:
    """N from ``work/rq2_updates.json``, only if it was computed from the prepared store there.

    Refuses a missing file, a different version, a prep summary that has changed since, or an N
    that is not ``min(100, F // 32)`` of the recorded F (a hand-edited file).
    """
    rec = _read_json(os.path.join(work, UPDATES_FILE))
    if rec is None or rec.get("version") != UPDATES_VERSION:
        raise UpdatesError(
            f"N has not been computed from a prepared store: {UPDATES_FILE} is missing or "
            "of another version (run scripts/rq2_plan.py resolve)"
        )
    path = os.path.join(work, "prep_summary.json")
    try:
        with open(path, "rb") as handle:
            digest = hashlib.sha256(handle.read()).hexdigest()
    except OSError as err:
        raise UpdatesError("prep summary is missing; N cannot be checked against it") from err
    if rec.get("prep_summary_sha256") != digest:
        raise UpdatesError("prep summary changed since N was computed; run resolve again")
    n = rp.mined_updates(int(rec["filter_pool"]))
    if rec.get("updates") != n:
        raise UpdatesError(f"recorded N {rec.get('updates')} is not min(100, F // 32) = {n}")
    return n


def family_runs(
    family: str,
    seeds: Sequence[int] = rp.DEFAULT_SEEDS,
    include_conditional: bool = False,
    mined_n: int | None = None,
) -> list[rp.Run]:
    """The runs of one data condition, in launch order (seed, then the interleaved cell order)."""
    runs = [r for r in rp.plan_runs(seeds, mined_n=mined_n) if r.cell.family == family]
    runs = [r for r in runs if include_conditional or r.cell.conditional is None]
    return rp._run_order(runs)


def _templates(repo: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for fam in ("mined", "injected"):
        with open(os.path.join(repo, CONFIG_DIR, f"_template_{fam}.yaml"), encoding="utf-8") as h:
            out[fam] = yaml.safe_load(h)
    return out


def _mem_mb(sbatch_text: str) -> int | None:
    m = re.search(r"^#SBATCH\s+--mem=(\d+)([GM])", sbatch_text, flags=re.MULTILINE)
    if not m:
        return None
    return int(m.group(1)) * (1024 if m.group(2) == "G" else 1)


def run_checks(
    *,
    family: str,
    repo: str,
    work: str,
    home: str,
    commit: str,
    retain_dir: str | None,
    include_conditional: bool = False,
    seeds: Sequence[int] = rp.DEFAULT_SEEDS,
    head_commit: str | None = None,
    free_gb: float | None = None,
) -> list[Check]:
    """Every check of the checklist that can be verified from files; none raises."""
    checks: list[Check] = []

    def add(cid: str, ok: bool, detail: str) -> None:
        checks.append(Check(cid, bool(ok), detail))

    mined_n: int | None = None
    if family == "mined":
        try:
            mined_n = read_updates(work)
            add(
                "updates_computed",
                True,
                f"N = {mined_n} updates for every arm, computed from the prepared store (D140)",
            )
        except (UpdatesError, ValueError) as err:
            add("updates_computed", False, str(err))
    runs = family_runs(family, seeds, include_conditional, mined_n)
    all_runs = rp.plan_runs(seeds, mined_n=mined_n)
    add(
        "commit_recorded",
        bool(commit) and (head_commit is None or head_commit == commit),
        f"RIL_COMMIT={commit or 'unset'}"
        + (f", checkout HEAD {head_commit}" if head_commit else ""),
    )
    reg = _read_json(os.path.join(work, "registration.json"))
    add(
        "cell_table_registered",
        bool(reg) and reg is not None and reg.get("cell_table_sha256") == rp.cell_table_digest(),
        "work/registration.json holds the digest of the current cell table"
        if reg
        else "work/registration.json is missing (registration is fixed before the first run)",
    )
    reused = rp.fresh_noise_check(all_runs)
    wave = [r.run_id for r in all_runs if r.seed in rp.WAVE_SEEDS]
    add(
        "seeds_fresh",
        not reused and not wave,
        "seeds are outside the exploratory waves; no noise draw is reused"
        if not (reused or wave)
        else f"wave seeds used: {wave or reused}",
    )

    prep = _read_json(os.path.join(work, "prep_summary.json"))
    size: int | None = None
    if family == "mined":
        ok = (
            prep is not None
            and prep.get("held_out_rows") == 0
            and bool(prep.get("drop_list_applied"))
            and int(prep.get("filter_size", 0)) >= 1
            and int(prep.get("examples", 0)) >= rp.BATCH_SIZE
        )
        add(
            "prep_summary",
            ok,
            "examples, FILTER size, 0 held-out rows and the applied drop list are recorded"
            if ok
            else "work/prep_summary.json is missing or incomplete (examples, filter_size, "
            "held_out_rows == 0, drop_list_applied)",
        )
        if ok and prep is not None:
            size = int(prep["filter_size"])
            visits = (mined_n or rp.PRIMARY_UPDATES) * rp.BATCH_SIZE
            u = rp.unique_example_check(visits, int(prep["examples"]), size)
            caveat = (
                ""
                if u["filter_reaches_unique"]
                else (
                    f"; FILTER and the subsample repeat examples (shortfall "
                    f"{u['shortfall_filter']}): N does not follow the FILTER pool (D140)"
                )
            )
            add(
                "distinct_examples_stated",
                True,
                f"RAW {u['raw_passes']} passes, FILTER {u['filter_passes']} passes{caveat}",
            )

    templates = _templates(repo)
    bad: list[str] = []
    expected = {
        r["run_id"]: r["config_hash"]
        for r in rp.validate_runs(all_runs, templates, filter_size=size)
    }
    final_hashes = family == "injected" or size is not None
    if family == "mined" and mined_n is None:
        bad.append("updates not computed: configurations cannot be matched to the plan")
    for r in runs:
        if family == "mined" and mined_n is None:
            break  # the update count is not computed: nothing to compare, the check above fails
        resolved = family == "mined"
        path = (
            os.path.join(work, "configs_resolved", f"{r.run_id}.yaml")
            if resolved
            else os.path.join(repo, CONFIG_DIR, f"{r.run_id}.yaml")
        )
        if not os.path.isfile(path):
            bad.append(
                f"{r.run_id}: not resolved (run scripts/rq2_plan.py resolve)"
                if resolved
                else f"{r.run_id}: no file"
            )
            continue
        cfg = load_train_config(path)
        sub = cfg["arm"].get("subsample")
        if sub is not None and sub["size"] == rp.FILTER_SIZE_TOKEN:
            if size is None:
                continue  # resolved by the run job once the prep summary exists
            cfg["arm"]["subsample"] = {**sub, "size": size}
        problems = rp.check_protocol(cfg, r)
        if problems:
            bad.append(f"{r.run_id}: {problems[0]}")
        elif final_hashes and config_hash(cfg) != expected[r.run_id]:
            bad.append(f"{r.run_id}: hash differs from the plan")
    add(
        "configs_conform",
        not bad,
        f"{len(runs)} configurations conform to the registered design and reproduce the "
        "planned hashes"
        if not bad
        else "; ".join(bad[:3]),
    )

    inputs_dir = os.path.join(home, INPUTS_HOME_REL[family]) if family in INPUTS_HOME_REL else work
    miss = [f for f in INPUTS[family] if not os.path.isfile(os.path.join(inputs_dir, f))]
    add(
        "inputs_present",
        not miss,
        "cache, feature table / score stores are in place" if not miss else f"missing: {miss}",
    )

    script = os.path.join(repo, SCRIPTS[family])
    try:
        with open(script, encoding="utf-8") as handle:
            mem = _mem_mb(handle.read())
    except OSError:
        mem = None
    want = rp.MEM_REQUEST_MB[family]
    cpus = rp.cpus_for_request(mem) if mem else None
    add(
        "memory_request",
        mem == want and want <= rp.MEM_CEILING_MB and cpus is not None and cpus <= rp.CPU_LIMIT,
        f"{SCRIPTS[family]} asks {mem} MB; plan {want} MB; "
        f"per-user ceiling {rp.MEM_CEILING_MB} MB; allocated {cpus} CPUs at "
        f"{rp.MEM_PER_CPU_MB} MB per CPU against {rp.CPU_LIMIT}",
    )

    free = free_gb if free_gb is not None else shutil.disk_usage(home).free / 1e9
    need = MIN_FREE_GB[family]
    add("space", free >= need, f"{free:.1f} GB free on the account home; {need:.1f} GB needed")

    if family == "mined":
        try:
            if not retain_dir:
                raise ValueError("RETAIN_DIR is not set")
            path = check_retain_dir(retain_dir)
            parent_ok = os.path.isdir(os.path.dirname(path)) or os.path.isdir(path)
            add(
                "retain_dir",
                parent_ok,
                f"retained models ({RETAINED_MODELS_GB} GB) go to {os.path.basename(path)}"
                if parent_ok
                else "parent of RETAIN_DIR does not exist",
            )
        except ValueError as err:
            add("retain_dir", False, str(err))
    else:
        add("retain_dir", not retain_dir, "injected-noise models are not retained (D129)")

    from ril.evaluation.eval_plan import EvalSet, plan_sets

    ev = plan_sets(
        [
            EvalSet(
                "dev",
                os.path.join(repo, "configs/experiments/e1_bm25_reproduction.yaml"),
                os.path.join(home, "ril_x2/prep"),
                ("dev",),
                os.path.join(home, "ril_t1/work/e3_cache"),
            )
        ]
    )
    add(
        "dev_set_ready", bool(ev["ready"]), "dev stores present" if ev["ready"] else str(ev["sets"])
    )

    leak = _read_json(os.path.join(work, "leakage_ok.json"))
    add(
        "leakage_tests",
        bool(leak)
        and leak is not None
        and leak.get("failed") == 0
        and leak.get("commit") == commit,
        "leakage tests passed on this commit"
        if leak
        else "work/leakage_ok.json is missing (make test-all on the cluster, then record it)",
    )

    if family == "mined" and include_conditional:
        tm = _read_json(os.path.join(work, "teacher_measure.json"))
        cost = None if tm is None else tm.get("full_store_gpu_hours")
        ok = isinstance(cost, (int, float)) and cost <= rp.DENSE_TEACHER_CAP_GPU_H
        header: list[str] = []
        try:
            with open(os.path.join(work, "features_mined.csv"), encoding="utf-8") as handle:
                header = next(csv.reader(handle))
        except (OSError, StopIteration):
            pass
        has = any("swerankembed-small" in h for h in header)
        add(
            "dense_teacher_gate",
            bool(ok and has),
            f"measured full-store cost {cost} GPU-h against {rp.DENSE_TEACHER_CAP_GPU_H}; "
            f"teacher columns in the feature table: {has}",
        )
    return checks


def record_registration(work: str, protocol_path: str | None = None) -> Record:
    """Write ``work/registration.json``: the digest of the cell table (and of the protocol text).

    The engineer runs this once, after reading the cell list and the decision rules, and before the
    first run; the preflight then checks that the cell table still has this digest.
    """
    import hashlib

    rec: Record = {"cell_table_sha256": rp.cell_table_digest()}
    if protocol_path:
        with open(protocol_path, "rb") as handle:
            rec["protocol_sha256"] = hashlib.sha256(handle.read()).hexdigest()
    os.makedirs(work, exist_ok=True)
    with open(os.path.join(work, "registration.json"), "w", encoding="utf-8") as handle:
        json.dump(rec, handle, indent=1, sort_keys=True)
        handle.write("\n")
    return rec


def record_leakage(work: str, commit: str, pytest_output: str) -> Record:
    """Write ``work/leakage_ok.json`` from the last summary line of a pytest run on the cluster.

    Refuses a run with failures or errors, or one whose summary line cannot be read.
    """
    last = [ln for ln in pytest_output.splitlines() if re.search(r"\bin \d", ln)]
    if not last:
        raise ValueError("no pytest summary line found")
    line = last[-1]
    passed = re.search(r"(\d+) passed", line)
    failed = sum(int(m.group(1)) for m in re.finditer(r"(\d+) (?:failed|error)", line))
    if not passed or failed:
        raise ValueError(f"leakage tests did not all pass: {line.strip()}")
    rec: Record = {"commit": commit, "passed": int(passed.group(1)), "failed": 0}
    os.makedirs(work, exist_ok=True)
    with open(os.path.join(work, "leakage_ok.json"), "w", encoding="utf-8") as handle:
        json.dump(rec, handle, indent=1, sort_keys=True)
        handle.write("\n")
    return rec


def write_preflight(
    path: str,
    *,
    account: str,
    family: str,
    commit: str,
    include_conditional: bool,
    checks: Sequence[Check],
    updates: int | None = None,
    now: dt.datetime | None = None,
) -> Record:
    now = now or dt.datetime.now(UTC)
    rec: Record = {
        "version": PREFLIGHT_VERSION,
        "account": account,
        "family": family,
        "commit": commit,
        "include_conditional": include_conditional,
        "updates": updates,
        "created_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "checks": [asdict(c) for c in checks],
        "ready": all(c.ok for c in checks),
    }
    with open(f"{path}.tmp", "w", encoding="utf-8") as handle:
        json.dump(rec, handle, indent=1, sort_keys=True)
        handle.write("\n")
    os.replace(f"{path}.tmp", path)
    return rec


def preflight_refusals(
    path: str | None,
    *,
    account: str,
    family: str,
    commit: str,
    include_conditional: bool,
    updates: int | None = None,
    now: dt.datetime | None = None,
) -> list[str]:
    """Reasons the preflight file does not allow a launch (empty = it does).

    For the mined family ``updates`` is the N read from the prepared store at submission time; the
    preflight must have been written for the same N (D140).
    """
    if not path:
        return ["no preflight file given (--preflight)"]
    rec = _read_json(path)
    if rec is None or rec.get("version") != PREFLIGHT_VERSION:
        return [f"{path} is not a {PREFLIGHT_VERSION} file"]
    out: list[str] = []
    if rec.get("account") != account or rec.get("family") != family:
        out.append(f"preflight is for account {rec.get('account')} / {rec.get('family')}")
    if not commit or rec.get("commit") != commit:
        out.append("preflight was written for another commit than RIL_COMMIT")
    if family == "mined" and (updates is None or rec.get("updates") != updates):
        out.append(
            f"preflight was written for N = {rec.get('updates')}, the prepared store gives "
            f"{updates}"
        )
    if include_conditional and not rec.get("include_conditional"):
        out.append("preflight did not check the conditional cells (D125)")
    failed = [c["id"] for c in rec.get("checks", []) if not c.get("ok")]
    if failed or not rec.get("ready"):
        out.append(f"preflight checks not passed: {failed}")
    try:
        made = dt.datetime.strptime(str(rec["created_utc"]), "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=UTC
        )
        age = ((now or dt.datetime.now(UTC)) - made).total_seconds() / 3600
        if age > MAX_AGE_HOURS or age < -0.1:
            out.append(f"preflight is {age:.1f} h old (limit {MAX_AGE_HOURS:.0f} h)")
    except (KeyError, ValueError):
        out.append("preflight has no readable creation time")
    return out


@dataclass(frozen=True)
class Submission:
    """One GPU job: one account's one seed, every arm of the seed in order (D141)."""

    seed: int
    job_name: str
    script: str
    mem_mb: int
    export: Mapping[str, str]
    run_ids: tuple[str, ...]
    gpu_hours: float

    @property
    def time_limit(self) -> str:
        return f"{RUN_HOURS * len(self.run_ids):02d}:00:00"


RUN_IDS_SEPARATOR = ":"
"""Separates run ids in the ``RUN_IDS`` variable (a comma would split ``--export``)."""


def submissions(
    family: str,
    *,
    commit: str,
    retain_dir: str | None,
    date: str,
    include_conditional: bool = False,
    seeds: Sequence[int] = rp.DEFAULT_SEEDS,
    mined_n: int | None = None,
) -> list[Submission]:
    """The ordered jobs of a family: one per seed, with the environment its script needs.

    ``date`` names the result directories (``<date>_<hash prefix>``); it is fixed once for the
    whole launch so that a resubmitted run finds its finished result and is skipped. The mined
    family needs ``mined_n``, the update count computed from the prepared store (D140); without
    it nothing is built.
    """
    if not DATE_PATTERN.match(date):
        raise ValueError(f"date must be YYYY-MM-DD, got {date!r}")
    if family == "mined" and mined_n is None:
        raise UpdatesError("N has not been computed from a prepared store (D140)")
    out: list[Submission] = []
    groups = rp.seed_jobs(family_runs(family, seeds, include_conditional, mined_n), family)
    for seed, group in groups.items():
        ids = tuple(r.run_id for r in group)
        env = {
            "SEED": str(seed),
            "RUN_IDS": RUN_IDS_SEPARATOR.join(ids),
            "RIL_COMMIT": commit,
            "DATE": date,
        }
        if family == "mined":
            if retain_dir:
                env["RETAIN_DIR"] = retain_dir
            env["UPDATES"] = str(mined_n)
        out.append(
            Submission(
                seed,
                f"{JOB_PREFIX}{family}_s{seed}",
                SCRIPTS[family],
                rp.MEM_REQUEST_MB[family],
                env,
                ids,
                round(len(ids) * rp.COSTS["run_dev"].value, 3),
            )
        )
    return out


def render_graph(subs: Sequence[Submission], account: str, family: str) -> str:
    """The job graph a family would submit, as text (printed before anything is submitted)."""
    lines = [
        f"account {account}, family {family}: {len(subs)} GPU jobs, one per seed, one at a time "
        f"(each after the previous: afterany), {sum(s.gpu_hours for s in subs):.2f} GPU-hours",
    ]
    prev = "(start)"
    for i, s in enumerate(subs, 1):
        lines.append(
            f"{i:3d}. {s.job_name:<24} {len(s.run_ids)} arms  mem {s.mem_mb} MB  "
            f"wall {s.time_limit}  after {prev}"
        )
        for rid in s.run_ids:
            lines.append(f"       - {rid}")
        prev = s.job_name
    return "\n".join(lines)


def submit(
    subs: Sequence[Submission],
    *,
    runner: Callable[[list[str]], str],
    queued_names: Callable[[], Sequence[str]],
) -> list[tuple[str, str]]:
    """Submit the jobs chained with ``afterany``; return (job name, job id).

    Refuses if any of the jobs is already queued or running on this account (a seed job is never
    submitted twice; a finished run inside a resubmitted job is skipped by the job itself).
    ``runner`` runs one ``sbatch`` command line and returns its stdout (``--parsable``: the id).
    """
    already = sorted({s.job_name for s in subs} & set(queued_names()))
    if already:
        raise RuntimeError(f"already queued or running, not submitting again: {already[:3]}")
    ids: list[tuple[str, str]] = []
    prev: str | None = None
    for s in subs:
        cmd = [
            "sbatch",
            "--parsable",
            f"--job-name={s.job_name}",
            f"--mem={s.mem_mb}M",
            f"--time={s.time_limit}",
        ]
        if prev:
            cmd.append(f"--dependency=afterany:{prev}")
        cmd.append("--export=ALL," + ",".join(f"{k}={v}" for k, v in sorted(s.export.items())))
        cmd.append(s.script)
        prev = runner(cmd).strip().split(";")[0]
        ids.append((s.job_name, prev))
    return ids
