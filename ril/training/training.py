"""Retriever training run: configuration, arm hooks, matched updates, budget, checkpoints, results.

Implements ``docs/08_experimental_design.md`` "Experimental design" for one run: a fixed number of
optimizer updates (the matched optimization budget), the arm entering only through its three hooks
(``ril.training.supervision``), and the budget table of ``docs/EXPERIMENTS.md`` ("RQ2 extras
recorded per run": GPU-hours, unique examples seen, effective epochs, optimizer updates).

Every training parameter comes from the run configuration (``configs/experiments/<exp_id>.yaml``);
none has a default in code. All of them (budget, learning rate and schedule, batch shape, negative
policy, loss form, temperature, base encoder) are ``provisional: ADR-001, ADR-002, ADR-006`` until
the engineer settles the ADRs, and a configuration carrying a ``provisional`` list is refused under
``configs/frozen/``.

Run layout (``docs/EXPERIMENTS.md`` "Rules every experiment follows"):
``results/<rq>/<exp_id>/<YYYY-MM-DD>_<confighash8>/`` holds ``config.yaml``, ``results.json``
(budget, filter report, plan hash, loss trace summary) and ``hardware.json``; the run log goes to
``results/logs/<exp_id>_<date>_<confighash8>.json``. Checkpoints (large) live in a work directory
on the cluster, ``<work>/<exp_id>/<confighash8>/``: ``step_<n>/`` every ``checkpoint.every`` updates
(model, optimizer, scheduler, RNG state, elapsed time), the last ``checkpoint.keep`` kept, and
``final/`` (the model directory the evaluation hook reads). A rerun of the same configuration
resumes from the newest step checkpoint by replaying the deterministic batch plan.

Kept compatible with Python 3.10.
"""

from __future__ import annotations

import copy
import glob
import hashlib
import json
import math
import os
import platform
import shutil
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

import numpy as np
import torch
import yaml
from torch.optim.adamw import AdamW
from torch.optim.optimizer import Optimizer

from ril.training.config_io import (
    ARM_KEYS as ARM_KEYS,
)
from ril.training.config_io import (
    LABEL_KEYS as LABEL_KEYS,
)
from ril.training.config_io import (
    PROVISIONAL as PROVISIONAL,
)
from ril.training.config_io import (
    REQUIRED as REQUIRED,
)
from ril.training.config_io import (
    STORAGE_KEYS as STORAGE_KEYS,
)
from ril.training.config_io import (
    TRAINING_VERSION as TRAINING_VERSION,
)
from ril.training.config_io import (
    Record as Record,
)
from ril.training.config_io import (
    _without_storage_keys as _without_storage_keys,
)
from ril.training.config_io import (
    check_comparable as check_comparable,
)
from ril.training.config_io import (
    config_hash as config_hash,
)
from ril.training.config_io import (
    held_identical_view as held_identical_view,
)
from ril.training.config_io import (
    load_train_config as load_train_config,
)
from ril.training.config_io import (
    planned_end as planned_end,
)
from ril.training.config_io import (
    teacher_equals_base as teacher_equals_base,
)
from ril.training.contrastive_loss import info_nce
from ril.training.data_loader import Batch, BatchPlanner, BatchSpec
from ril.training.encoders import TrainEncoder, build_encoder
from ril.training.negatives import Mined, make_policy, needs_mining
from ril.training.pool_reader import PoolExample
from ril.training.retention import (
    MODEL_SUBDIR,
    build_manifest,
    check_retain_dir,
    retain_requested,
    write_manifest,
)
from ril.training.supervision import Arm, NoiseKnowledge, QualitySignal, arm_from_config
from ril.util.portable import neutral_paths


class StepHook(Protocol):
    """A callback at chosen update counts (learning-curve evaluation); see :func:`train`."""

    steps: frozenset[int]

    def __call__(self, n: int, enc: TrainEncoder) -> None: ...


# --------------------------------------------------------------------------- configuration


# --------------------------------------------------------------------------- optimizer


def lr_lambda(warmup: int, total: int, schedule: str) -> Any:
    """Learning-rate multiplier at an update: linear warmup, then constant or linear decay."""
    if schedule not in ("constant", "linear"):
        raise ValueError("schedule must be 'constant' or 'linear'")

    def f(step: int) -> float:
        if warmup > 0 and step < warmup:
            return (step + 1) / warmup
        if schedule == "constant":
            return 1.0
        rest = max(1, total - warmup)
        return max(0.0, 1.0 - (step - warmup) / rest)

    return f


def build_optimizer(
    enc: TrainEncoder, cfg: Mapping[str, Any], updates: int
) -> tuple[Optimizer, torch.optim.lr_scheduler.LambdaLR]:
    """AdamW and its schedule from the ``optimizer`` section."""
    if str(cfg["name"]) != "adamw":
        raise ValueError("only 'adamw' is implemented")
    opt = AdamW(
        enc.module.parameters(), lr=float(cfg["lr"]), weight_decay=float(cfg["weight_decay"])
    )
    sched = torch.optim.lr_scheduler.LambdaLR(
        opt, lr_lambda(int(cfg["warmup_updates"]), updates, str(cfg["schedule"]))
    )
    return opt, sched


# --------------------------------------------------------------------------- one update


def batch_loss(
    enc: TrainEncoder, batch: Batch, loss_cfg: Mapping[str, Any]
) -> tuple[torch.Tensor, Record]:
    """Loss of one batch under the configured objective (shared by every arm)."""
    q = enc.embed(list(batch.queries), True)
    d = enc.embed(list(batch.docs), False)
    dev = q.device
    return info_nce(
        q,
        d,
        torch.from_numpy(batch.pos_mask).to(dev),
        torch.from_numpy(batch.valid_mask).to(dev),
        torch.from_numpy(batch.weights).to(dev),
        tau=float(loss_cfg["temperature"]),
        form=str(loss_cfg["form"]),
        normaliser=str(loss_cfg["normaliser"]),
    )


PRECISIONS = ("fp32", "amp_fp16")


class Updater:
    """One optimizer update of the shared training path (identical code for every arm).

    ``optimizer.precision``: ``fp32``, or ``amp_fp16`` (autocast to float16 with a loss scaler, GPU
    only; the loss itself is computed in float32). A memory and speed setting held identical across
    arms; ``provisional: ADR-002``.
    """

    def __init__(self, enc: TrainEncoder, cfg: Mapping[str, Any], updates: int, device: str):
        self.enc, self.cfg = enc, cfg
        self.opt, self.sched = build_optimizer(enc, cfg["optimizer"], updates)
        precision = str(cfg["optimizer"].get("precision", "fp32"))
        if precision not in PRECISIONS:
            raise ValueError(f"optimizer.precision must be one of {PRECISIONS}")
        self.amp = precision == "amp_fp16"
        if self.amp and not device.startswith("cuda"):
            raise ValueError("amp_fp16 needs a GPU")
        self.scaler = torch.amp.GradScaler("cuda") if self.amp else None  # type: ignore[attr-defined,unused-ignore]
        clip = cfg["optimizer"].get("grad_clip")
        self.clip = None if clip is None else float(clip)

    def step(self, batch: Batch) -> tuple[torch.Tensor, Record]:
        with torch.autocast("cuda", dtype=torch.float16, enabled=self.amp):
            loss, diag = batch_loss(self.enc, batch, self.cfg["loss"])
        self.opt.zero_grad(set_to_none=True)
        if self.scaler is not None:
            self.scaler.scale(loss).backward()  # type: ignore[no-untyped-call,unused-ignore]
            self.scaler.unscale_(self.opt)
        else:
            loss.backward()  # type: ignore[no-untyped-call,unused-ignore]
        if self.clip is not None:
            torch.nn.utils.clip_grad_norm_(self.enc.module.parameters(), self.clip)
        if self.scaler is not None:
            self.scaler.step(self.opt)
            self.scaler.update()
        else:
            self.opt.step()
        self.sched.step()
        return loss, diag

    def state_dict(self) -> Record:
        return {
            "optimizer": self.opt.state_dict(),
            "scheduler": self.sched.state_dict(),  # type: ignore[no-untyped-call,unused-ignore]
            "scaler": self.scaler.state_dict() if self.scaler is not None else None,
        }

    def load_state_dict(self, d: Mapping[str, Any]) -> None:
        self.opt.load_state_dict(d["optimizer"])
        self.sched.load_state_dict(d["scheduler"])  # type: ignore[no-untyped-call,unused-ignore]
        if self.scaler is not None and d.get("scaler") is not None:
            self.scaler.load_state_dict(d["scaler"])

    def lr(self) -> float:
        return float(self.sched.get_last_lr()[0])


# --------------------------------------------------------------------------- checkpoints


def _step_dirs(ckpt_root: str) -> list[str]:
    return sorted(glob.glob(os.path.join(ckpt_root, "step_*[0-9]")))


def save_checkpoint(
    ckpt_root: str,
    update: int,
    enc: TrainEncoder,
    upd: Updater,
    state: Record,
    keep: int,
) -> str:
    """Write ``step_<update>/`` atomically and prune to the newest ``keep``."""
    final = os.path.join(ckpt_root, f"step_{update:09d}")
    tmp = f"{final}.tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp)
    blob = {
        "model": enc.module.state_dict(),
        **upd.state_dict(),
        "torch_rng": torch.random.get_rng_state(),
        "cuda_rng": torch.cuda.get_rng_state_all() if torch.cuda.is_available() else [],
    }
    torch.save(blob, os.path.join(tmp, "state.pt"))
    with open(os.path.join(tmp, "state.json"), "w", encoding="utf-8") as handle:
        json.dump({**state, "update": update}, handle, sort_keys=True)
    shutil.rmtree(final, ignore_errors=True)
    os.replace(tmp, final)
    for old in _step_dirs(ckpt_root)[:-keep]:
        shutil.rmtree(old, ignore_errors=True)
    return final


def load_latest(
    ckpt_root: str,
    enc: TrainEncoder,
    upd: Updater,
) -> Record | None:
    """Restore the newest step checkpoint; ``None`` if there is none."""
    dirs = _step_dirs(ckpt_root)
    if not dirs:
        return None
    path = dirs[-1]
    blob = torch.load(os.path.join(path, "state.pt"), map_location="cpu", weights_only=False)
    enc.module.load_state_dict(blob["model"])
    upd.load_state_dict(blob)
    torch.random.set_rng_state(blob["torch_rng"])
    if blob["cuda_rng"] and torch.cuda.is_available():
        torch.cuda.set_rng_state_all(blob["cuda_rng"])
    with open(os.path.join(path, "state.json"), encoding="utf-8") as handle:
        state: Record = json.load(handle)
    return state


# --------------------------------------------------------------------------- the run


@dataclass(frozen=True)
class RunPaths:
    """Where one run writes."""

    result_dir: str
    log_path: str
    ckpt_root: str

    @classmethod
    def of(cls, cfg: Mapping[str, Any], results_root: str, work_root: str, date: str) -> RunPaths:
        h8 = config_hash(cfg)[:8]
        exp = str(cfg["exp_id"])
        return cls(
            result_dir=os.path.join(results_root, str(cfg["rq"]), exp, f"{date}_{h8}"),
            log_path=os.path.join(results_root, "logs", f"{exp}_{date}_{h8}.json"),
            ckpt_root=os.path.join(work_root, exp, h8),
        )


def hardware_info(device: str) -> Record:
    """Machine and device description recorded with every run."""
    info: Record = {
        "host": platform.node(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "torch": torch.__version__,
        "cpus_visible": os.cpu_count(),
        "device": device,
        "slurm_job_id": os.environ.get("SLURM_JOB_ID"),
    }
    if device.startswith("cuda") and torch.cuda.is_available():
        info["gpu"] = torch.cuda.get_device_name(0)
        info["gpu_capability"] = list(torch.cuda.get_device_capability(0))
        info["cuda"] = torch.version.cuda
    return info


def _dump(path: str, obj: Any) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(f"{path}.tmp", "w", encoding="utf-8") as handle:
        json.dump(obj, handle, indent=1, sort_keys=True, default=str)
        handle.write("\n")
    os.replace(f"{path}.tmp", path)


def _weight_summary(weights: Sequence[float]) -> Record:
    w = np.asarray(weights, dtype=np.float64)
    if not len(w):
        return {"n": 0}
    return {
        "n": int(len(w)),
        "min": float(w.min()),
        "mean": float(w.mean()),
        "max": float(w.max()),
        "share_below_1": float((w < 1.0).mean()),
    }


def prepare_arm(
    cfg: Mapping[str, Any],
    examples: Sequence[PoolExample],
    signals: Mapping[str, QualitySignal],
    ledger: NoiseKnowledge | None = None,
) -> tuple[Arm, list[PoolExample], list[float], Record]:
    """Apply the arm's filter and weigher: the arm, kept examples, weights, filter report."""
    arm = arm_from_config(cfg["arm"], signals, int(cfg["seed"]), ledger)
    kept, report = arm.filter.apply(examples)
    weights = [arm.weigher.weight(e) for e in kept]
    return arm, kept, weights, report.to_dict()


def make_planner(
    cfg: Mapping[str, Any],
    arm: Arm,
    kept: Sequence[PoolExample],
    weights: Sequence[float],
    mined: Mapping[str, Mined] | None,
) -> BatchPlanner:
    """The shared batch planner of a configuration (identical code for every arm)."""
    b = cfg["batch"]
    spec = BatchSpec(int(b["batch_size"]), int(b["negatives_per_example"]), int(b["max_positives"]))
    policy = make_policy(cfg["negatives"], pilot=bool(cfg.get("pilot", False)))
    if needs_mining(policy) and not mined:
        raise ValueError("the negative policy needs mined teacher scores")
    return BatchPlanner(kept, weights, arm.ordering, policy, spec, int(cfg["seed"]), mined)


def train(
    cfg: Mapping[str, Any],
    examples: Sequence[PoolExample],
    *,
    results_root: str,
    work_root: str,
    date: str,
    device: str = "cpu",
    signals: Mapping[str, QualitySignal] | None = None,
    mined: Mapping[str, Mined] | None = None,
    stop_after: int | None = None,
    extra_log: Mapping[str, Any] | None = None,
    hook: StepHook | None = None,
    ledger: NoiseKnowledge | None = None,
    retain_dir: str | None = None,
    commit: str | None = None,
) -> Record:
    """Run (or resume) one training run; returns the results record.

    ``retain_dir`` (the job's ``RETAIN_DIR``): with ``checkpoint.retain_final`` on, the finished
    model is also written there in half precision with a manifest (``ril.training.retention``).
    The switch on and no directory raises before the first update, not after the last. With the
    switch off the run, its outputs and its record are those of a run without this option.
    ``commit`` goes into the manifest only.

    ``ledger`` is the injected-noise indicator of a noised pool; only the ORACLE_CLEAN arm and a
    size-matched subsample read it (``ril.training.noise``).

    ``stop_after`` ends the process after that many updates have been done in total (a test of
    resumption, or a time-boxed job); the run is then incomplete and a rerun continues it.

    ``hook`` (a learning curve): called as ``hook(n, enc)`` when ``n`` updates are done, for every
    ``n`` in ``hook.steps`` (0 = before the first update). It runs after the step's checkpoint is
    written, and again on entry when a resumed run starts exactly at such an ``n`` (the hook must
    be idempotent); it must not change the encoder. Its time is not counted in the run's GPU time.
    """
    seed = int(cfg["seed"])
    updates = int(cfg["budget"]["updates"])
    end = planned_end(cfg)
    retain_to: str | None = None
    if retain_requested(cfg):
        if not retain_dir:
            raise ValueError("checkpoint.retain_final is on but no retention directory is set")
        retain_to = check_retain_dir(retain_dir)
    paths = RunPaths.of(cfg, results_root, work_root, date)
    torch.manual_seed(seed)
    np.random.seed(seed)
    if device == "cpu":
        torch.use_deterministic_algorithms(True)
    arm, kept, weights, freport = prepare_arm(cfg, examples, signals or {}, ledger)
    planner = make_planner(cfg, arm, kept, weights, mined)
    enc = build_encoder(cfg["model"], device=device, seed=seed)
    enc.module.train()
    upd = Updater(enc, cfg, updates, device)
    os.makedirs(paths.ckpt_root, exist_ok=True)
    state = load_latest(paths.ckpt_root, enc, upd) or {
        "update": -1,
        "elapsed_s": 0.0,
        "trace": [],
    }
    start = int(state["update"]) + 1
    elapsed = float(state["elapsed_s"])
    trace: list[Record] = list(state["trace"])
    plan = hashlib.sha256()
    ck = cfg["checkpoint"]
    every, keep, log_every = int(ck["every"]), int(ck["keep"]), int(ck.get("log_every", 1))
    done_now = 0
    if hook is not None and start in hook.steps:
        hook(start, enc)
    for batch in planner.batches(updates):
        plan.update(batch.fingerprint().encode())
        u = batch.update
        if u < start:
            continue  # replay to the checkpoint: the plan is deterministic
        if u >= end:
            break  # planned stop (budget.stop_after): the schedule stays that of ``updates``
        if stop_after is not None and u >= stop_after:
            break
        if device.startswith("cuda"):
            torch.cuda.synchronize()
        t0 = time.perf_counter()
        loss, diag = upd.step(batch)
        if device.startswith("cuda"):
            torch.cuda.synchronize()
        elapsed += time.perf_counter() - t0
        done_now += 1
        if u % log_every == 0 or u == end - 1:
            trace.append(
                {
                    "update": u,
                    "loss": float(loss.detach()),
                    **diag,
                    "lr": upd.lr(),
                }
            )
        if (u + 1) % every == 0 or u == end - 1:
            save_checkpoint(
                paths.ckpt_root, u, enc, upd, {"elapsed_s": elapsed, "trace": trace}, keep
            )
        if hook is not None and (u + 1) in hook.steps:
            hook(u + 1, enc)
    last = _step_dirs(paths.ckpt_root)
    finished = bool(last) and last[-1].endswith(f"step_{end - 1:09d}")
    record: Record = {
        "version": TRAINING_VERSION,
        "provisional": PROVISIONAL,
        "exp_id": cfg["exp_id"],
        "config_hash": config_hash(cfg),
        "seed": seed,
        "arm": arm.describe(),
        "teacher_equals_base": teacher_equals_base(cfg),
        "finished": finished,
        "filter": freport,
        "weights": _weight_summary(weights),
        "budget": budget_record(cfg, planner, elapsed, device, finished),
        "plan_sha256": plan.hexdigest() if finished else None,
        "updates_this_process": done_now,
        "loss_first": trace[0] if trace else None,
        "loss_last": trace[-1] if trace else None,
        "result_dir": paths.result_dir,
        "checkpoint_root": paths.ckpt_root,
    }
    if finished:
        final = os.path.join(paths.ckpt_root, "final")
        shutil.rmtree(final, ignore_errors=True)
        final_dtype = str(ck.get("final_dtype", "float32"))
        if final_dtype == "float16":
            enc.module.half()  # disk: a half-precision copy for evaluation (X2 encodes in float16)
        elif final_dtype != "float32":
            raise ValueError("checkpoint.final_dtype must be 'float32' or 'float16'")
        enc.save(final)
        record["final_model"] = final
        record["final_dtype"] = final_dtype
        if retain_to is not None:
            record["retained"] = _retain_final(
                cfg, record, enc, retain_to, updates_done=end, commit=commit
            )
        write_run(cfg, record, paths, device, trace, extra_log or {})
    return record


def _retain_final(
    cfg: Mapping[str, Any],
    record: Mapping[str, Any],
    enc: TrainEncoder,
    retain_to: str,
    *,
    updates_done: int,
    commit: str | None,
) -> Record:
    """Write the half-precision copy and the manifest of a finished run; returns a summary.

    The copy is made from a deep copy of the encoder, so the in-memory model (and the float32 or
    float16 ``final`` folder written before) is not touched. The folder is named by the cell and
    the configuration hash and is replaced atomically on a rerun.
    """
    h8 = str(record["config_hash"])[:8]
    folder = os.path.join(retain_to, f"{cfg['exp_id']}__s{int(cfg['seed'])}__{h8}")
    tmp = f"{folder}.tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    half = copy.deepcopy(enc)
    half.module.half()
    half.save(os.path.join(tmp, MODEL_SUBDIR))
    manifest = build_manifest(
        cfg,
        config_hash=str(record["config_hash"]),
        arm=record["arm"],
        updates_done=updates_done,
        model_dir=os.path.join(tmp, MODEL_SUBDIR),
        dtype="float16",
        commit=commit,
    )
    write_manifest(tmp, manifest)
    shutil.rmtree(folder, ignore_errors=True)
    os.replace(tmp, folder)
    return {
        "folder": os.path.basename(folder),
        "sha256": manifest["sha256"],
        "bytes": manifest["bytes"],
    }


def budget_record(
    cfg: Mapping[str, Any], planner: BatchPlanner, elapsed_s: float, device: str, finished: bool
) -> Record:
    """Budget table of one run (``docs/EXPERIMENTS.md``: GPU-hours, unique examples seen,
    effective epochs, optimizer updates).

    Exposure counts are those of the full plan (a resumed run replays it). GPU-hours here are the
    training loop's device time on one GPU (synchronised); the job's GPU-hours from ``sacct`` are
    recorded per job in ``docs/COMPUTE.md`` and are the ones charged to the budget.
    """
    counts = planner.counts.to_dict() if finished else {}
    hours = elapsed_s / 3600.0
    return {
        "optimizer_updates": planned_end(cfg),
        "schedule_updates": int(cfg["budget"]["updates"]),
        "batch_size": int(cfg["batch"]["batch_size"]),
        "gpu_hours_train_loop": hours if device.startswith("cuda") else 0.0,
        "wall_hours_train_loop": hours,
        **counts,
    }


def write_run(
    cfg: Mapping[str, Any],
    record: Record,
    paths: RunPaths,
    device: str,
    trace: Sequence[Record],
    extra_log: Mapping[str, Any],
) -> None:
    """Write the result directory and the run log.

    Stored copies spell home-directory paths as ``/home/<user>/...`` (``ril.util.portable``); the
    ``record`` returned to callers keeps the real paths.
    """
    os.makedirs(paths.result_dir, exist_ok=True)
    stored: Record = neutral_paths(record)
    with open(os.path.join(paths.result_dir, "config.yaml"), "w", encoding="utf-8") as handle:
        yaml.safe_dump(dict(cfg), handle, sort_keys=True)
    hw = hardware_info(device)
    _dump(os.path.join(paths.result_dir, "hardware.json"), hw)
    results_path = os.path.join(paths.result_dir, "results.json")
    old: Record = {}
    if os.path.exists(results_path):
        with open(results_path, encoding="utf-8") as handle:
            old = json.load(handle)
    _dump(results_path, {**old, "training": stored})
    _dump(
        paths.log_path,
        neutral_paths(
            {
                "exp_id": cfg["exp_id"],
                "config_hash": record["config_hash"],
                "seed": record["seed"],
                "hardware": hw,
                "training": record,
                "loss_trace": list(trace),
                **dict(extra_log),
            }
        ),
    )


def merge_results(result_dir: str, key: str, value: Any) -> None:
    """Add one section (e.g. the evaluation) to a run's ``results.json``."""
    path = os.path.join(result_dir, "results.json")
    old: Record = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as handle:
            old = json.load(handle)
    old[key] = value
    _dump(path, old)


def is_finite_record(rec: Mapping[str, Any]) -> bool:
    """Whether the loss trace of a record is finite (a diverged run is flagged, not hidden)."""
    for k in ("loss_first", "loss_last"):
        v = rec.get(k)
        if v is not None and not math.isfinite(float(v["loss"])):
            return False
    return True
