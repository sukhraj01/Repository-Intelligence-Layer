"""The chain from a finished mined store to the mined example cache, as explicit stages.

Implements ``docs/RQ2_LAUNCH_PLAN.md`` stages 1 to 3 (E-RQ2-FULL-PREP) and is the body of
``scripts/ada/rq2_full_prep.sbatch``. Stages, in order::

    select       final mined directories by state order (``--limit N`` takes the first N)
    overlap      content-overlap audit in resumable shards, merged, drop lists at every floor
    drop         the audit's drop list taken off the training manifest (the store is not touched)
    materialise  directory layout of the kept directories on node-local scratch, byte-checked
    inputs       per reading: zip, listing and selection file (the pool-rank inputs)
    teacher      per reading: BM25 ranks of every positive (resumable per directory)
    features     per reading: K-rank feature table and the held-out selection
    cache        per reading: the example cache training reads, then the size FILTER K = 20 keeps
    check        counts per reading, held-out count of the training manifest, drop list applied

Every stage appends one row to ``stages.jsonl`` (wall time, peak resident memory of its heaviest
child, bytes written). The store is only read. The step commands are the ones the pilot used
(``scripts/mine_pilot.py``, ``scripts/train.py``, ``scripts/mine_overlap_audit.py``); nothing is
re-implemented here. Kept compatible with Python 3.10.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field
from typing import Any

from ril.data_mining import full_prep as fp

STAGES: tuple[str, ...] = (
    "select",
    "overlap",
    "drop",
    "materialise",
    "inputs",
    "teacher",
    "features",
    "cache",
    "check",
)
AUDIT_FLOORS: tuple[int, ...] = (10, 20, 50)


@dataclass
class PrepConfig:
    """Everything a run needs; written next to the outputs so the run can be repeated."""

    store: str
    out: str
    scratch: str
    index: str
    held_out: str
    rename_cache: str
    python: str = sys.executable
    repo_root: str = "."
    state: str | None = None
    limit: int | None = None
    shards: int = 1
    readings: tuple[str, ...] = ("non_test",)
    stages: tuple[str, ...] = STAGES
    teacher: str = "bm25"
    k: int = 20
    level: str = "positive"
    seed: int = 0
    form: str = "code"
    drop_list: str | None = None
    drop_sha256: str | None = None
    guard_bytes: int = 1 << 30
    cache_bytes_per_directory: int = 0
    clean_scratch: bool = False
    force: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    def state_path(self) -> str:
        return self.state or os.path.join(self.store, "state.jsonl")


def _write_json(path: str, doc: object) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(doc, handle, indent=1, sort_keys=True)
        handle.write("\n")


def _read_json(path: str) -> Any:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _write_names(path: str, names: Sequence[str]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("".join(f"{n}\n" for n in names))


def tree_bytes(path: str) -> int:
    """Total size of the files under ``path`` (a file counts as itself, a missing path as 0)."""
    if os.path.isfile(path):
        return os.path.getsize(path)
    total = 0
    for dirpath, _, fnames in os.walk(path):
        for f in fnames:
            total += os.path.getsize(os.path.join(dirpath, f))
    return total


class Runner:
    """Runs stages, times them, and keeps the step commands and their outputs in ``out``."""

    def __init__(self, cfg: PrepConfig) -> None:
        self.cfg = cfg
        self.out = cfg.out
        self.steps: list[dict[str, Any]] = []
        os.makedirs(self.out, exist_ok=True)
        os.makedirs(os.path.join(self.out, "logs"), exist_ok=True)

    # ------------------------------------------------------------------ steps

    def step(
        self,
        label: str,
        argv: Sequence[str],
        stdout_to: str | None = None,
        ok: Sequence[int] = (0,),
    ) -> dict[str, Any]:
        """Run one command, record wall time and the child's peak resident set; fail on bad exit."""
        cmd = [self.cfg.python, "-I", *argv]
        log = os.path.join(self.out, "logs", f"{label.replace('/', '_')}.err")
        sink = stdout_to or os.path.join(self.out, "logs", f"{label.replace('/', '_')}.out")
        os.makedirs(os.path.dirname(sink) or ".", exist_ok=True)
        t0 = time.perf_counter()
        with open(sink, "wb") as o, open(log, "wb") as e:
            proc = subprocess.Popen(cmd, cwd=self.cfg.repo_root, stdout=o, stderr=e)
            _, status, usage = os.wait4(proc.pid, 0)
        proc.returncode = os.waitstatus_to_exitcode(status)
        row = {
            "step": label,
            "rc": proc.returncode,
            "seconds": round(time.perf_counter() - t0, 2),
            "maxrss_kb": int(usage.ru_maxrss),
            "argv": list(argv),
        }
        self.steps.append(row)
        if proc.returncode not in ok:
            raise RuntimeError(f"step {label} exited {proc.returncode}; see {log}")
        return row

    def stage(self, name: str, body: Callable[[], dict[str, Any]], outputs: Sequence[str]) -> None:
        """Run ``body`` as stage ``name`` and append its row to ``stages.jsonl``."""
        mark = len(self.steps)
        t0 = time.perf_counter()
        info = body()
        rows = self.steps[mark:]
        rec = {
            "stage": name,
            "seconds": round(time.perf_counter() - t0, 2),
            "step_seconds": round(sum(float(r["seconds"]) for r in rows), 2),
            "maxrss_kb": max([int(r["maxrss_kb"]) for r in rows], default=0),
            "bytes_written": sum(tree_bytes(p) for p in outputs),
            "steps": [{k: r[k] for k in ("step", "seconds", "maxrss_kb", "rc")} for r in rows],
            "info": info,
        }
        with open(os.path.join(self.out, "stages.jsonl"), "a", encoding="utf-8") as handle:
            handle.write(json.dumps(rec, sort_keys=True) + "\n")

    def done(self, name: str) -> bool:
        path = os.path.join(self.out, "stages.jsonl")
        if not os.path.exists(path) or self.cfg.force:
            return False
        with open(path, encoding="utf-8") as handle:
            return any(json.loads(x)["stage"] == name for x in handle if x.strip())

    # ------------------------------------------------------------------ paths

    def p(self, *parts: str) -> str:
        return os.path.join(self.out, *parts)

    def s(self, *parts: str) -> str:
        return os.path.join(self.cfg.scratch, *parts)

    def names(self) -> list[str]:
        return fp.read_names(self.p("names.txt"))

    def kept(self) -> list[str]:
        return fp.read_names(self.p("names_kept.txt"))

    # ------------------------------------------------------------------ stages

    def do_select(self) -> dict[str, Any]:
        sel = fp.select_closed(self.cfg.state_path(), self.cfg.store, self.cfg.limit)
        _write_names(self.p("names.txt"), sel.names)
        _write_json(self.p("selection.json"), sel.to_dict())
        return sel.to_dict()

    def do_overlap(self) -> dict[str, Any]:
        names = self.names()
        parts = fp.shard_names(self.cfg.store, names, self.cfg.shards)
        shard_dirs: list[str] = []
        ran = reused = 0
        for i, part in enumerate(parts):
            d = self.p("overlap", f"shard_{i}")
            shard_dirs.append(d)
            _write_names(self.p("overlap", f"names_shard_{i}.txt"), part)
            if os.path.exists(os.path.join(d, "run.json")) and not self.cfg.force:
                reused += 1
                continue
            self.step(
                f"overlap_audit_shard_{i}",
                [
                    "scripts/mine_overlap_audit.py", "audit", self.cfg.store, self.cfg.index, d,
                    "--names-file", self.p("overlap", f"names_shard_{i}.txt"),
                ],
            )  # fmt: skip
            ran += 1
        out = self.p("overlap")
        self.step(
            "overlap_merge",
            [
                "scripts/mine_overlap_audit.py", "merge", out, *shard_dirs,
                "--index", self.cfg.index, "--store", self.cfg.store,
            ],
        )  # fmt: skip
        for f in AUDIT_FLOORS:
            self.step(
                f"overlap_apply_{f}",
                ["scripts/mine_overlap_audit.py", "apply", out, "--floor", str(f)],
            )
        self.step(
            "overlap_apply_all",
            ["scripts/mine_overlap_audit.py", "apply", out, "--floor", "20", "--positives", "all"],
        )
        self.step(
            "overlap_apply_dropflagged",
            ["scripts/mine_overlap_audit.py", "apply", out, "--floor", "20", "--drop-flagged"],
        )
        summary = _read_json(os.path.join(out, "summary.json"))
        return {
            "shards": self.cfg.shards,
            "shards_run": ran,
            "shards_reused": reused,
            "directories": summary["directories"],
            "primary": summary["cells"]["primary"],
        }

    def do_drop(self) -> dict[str, Any]:
        names = self.names()
        source = self.cfg.drop_list or self.p("overlap", "drop_f20_non_test.txt")
        digest = fp.sha256_file(source)
        if self.cfg.drop_sha256 and digest != self.cfg.drop_sha256:
            raise RuntimeError(
                f"drop list {source} hashes to {digest}, expected {self.cfg.drop_sha256}"
            )
        drop = fp.read_names(source)
        kept, dropped = fp.apply_drop_list(names, drop)
        _write_names(self.p("names_kept.txt"), kept)
        doc = {
            "drop_list": os.path.basename(source),
            "drop_list_sha256": digest,
            "drop_list_given": bool(self.cfg.drop_list),
            "names_in": len(names),
            "names_in_sha256": fp.sha256_names(names),
            "dropped": len(dropped),
            "kept": len(kept),
            "names_kept_sha256": fp.sha256_names(kept),
            "store_modified": False,
        }
        _write_json(self.p("drop_manifest.json"), doc)
        return doc

    def do_materialise(self) -> dict[str, Any]:
        kept = self.kept()
        view = self.s("view")
        self.step(
            "materialise",
            [
                "scripts/mine_pilot.py", "materialise", self.cfg.store, view,
                "--names", self.p("names_kept.txt"),
            ],
            stdout_to=self.p("materialise.json"),
        )  # fmt: skip
        # a separate process: the runner stays small, so each child's peak memory is its own
        self.step(
            "materialise_verify",
            [
                "scripts/rq2_full_prep.py", "verify-materialised", self.cfg.store, view,
                self.p("names_kept.txt"),
            ],
            stdout_to=self.p("materialise_verify.json"),
            ok=(0, 4),
        )  # fmt: skip
        res = _read_json(self.p("materialise_verify.json"))
        if not res["identical"]:
            raise RuntimeError(f"materialised directories differ: {res['mismatches'][:3]}")
        return {
            "directories": len(kept),
            "verified": res["checked"],
            "view_bytes": tree_bytes(view),
        }

    def ensure_view(self) -> None:
        if not os.path.isdir(self.s("view", "pr")):
            self.do_materialise()

    def do_inputs(self) -> dict[str, Any]:
        self.ensure_view()
        info: dict[str, Any] = {}
        for r in self.cfg.readings:
            work = self.s(f"work_{r}")
            self.step(
                f"rank_prepare_{r}",
                ["scripts/mine_pilot.py", "rank-prepare", self.s("view"), work, "--reading", r],
                stdout_to=self.p(r, "prepare.json"),
            )  # fmt: skip
            sample = _read_json(os.path.join(work, "sample.json"))["sample"]
            counts = {
                "directories": len(sample),
                "positives": sum(int(x["positives"]) for x in sample),
                "repositories": len({str(x["repo"]) for x in sample}),
                "zip_bytes": os.path.getsize(os.path.join(work, "mined.zip")),
            }
            _write_json(self.p(r, "counts.json"), counts)
            info[r] = counts
        return info

    def ensure_work(self, reading: str) -> str:
        work = self.s(f"work_{reading}")
        if not os.path.exists(os.path.join(work, "mined.listing.json")):
            self.ensure_view()
            self.step(
                f"rank_prepare_{reading}_again",
                [
                    "scripts/mine_pilot.py", "rank-prepare", self.s("view"), work,
                    "--reading", reading,
                ],
                stdout_to=self.p(reading, "prepare_again.json"),
            )  # fmt: skip
        return work

    def do_teacher(self) -> dict[str, Any]:
        info: dict[str, Any] = {}
        for r in self.cfg.readings:
            work = self.ensure_work(r)
            row = self.step(
                f"rank_bm25_{r}",
                [
                    "scripts/mine_pilot.py", "rank-bm25", work,
                    self.p(r, "ranks_bm25.jsonl"), "--form", self.cfg.form,
                ],
                stdout_to=self.p(r, "bm25.json"),
            )  # fmt: skip
            info[r] = {"seconds": row["seconds"], "maxrss_kb": row["maxrss_kb"]}
        return info

    def do_features(self) -> dict[str, Any]:
        info: dict[str, Any] = {}
        for r in self.cfg.readings:
            work = self.ensure_work(r)
            table = self.p(r, "features_mined.csv")
            self.step(
                f"features_{r}",
                [
                    "scripts/train.py", "features", self.p(r, "ranks_bm25.jsonl"), "--out", table,
                    "--teachers", self.cfg.teacher, "--held-out", self.cfg.held_out,
                    "--rename-cache", self.cfg.rename_cache,
                ],
                stdout_to=self.p(r, "features.json"),
            )  # fmt: skip
            self.step(
                f"select_{r}",
                [
                    "scripts/train.py", "select", os.path.join(work, "mined.listing.json"),
                    self.cfg.held_out, self.cfg.rename_cache, self.p(r, "selection_mined.json"),
                    "--feature-table", table, "--seed", str(self.cfg.seed),
                ],
                stdout_to=self.p(r, "select.json"),
            )  # fmt: skip
            info[r] = _read_json(self.p(r, "features.json"))
        return info

    def do_cache(self) -> dict[str, Any]:
        info: dict[str, Any] = {}
        for r in self.cfg.readings:
            work = self.ensure_work(r)
            cache = self.p(r, "mined.jsonl.gz")
            free = shutil.disk_usage(self.out).free
            need = self.cfg.cache_bytes_per_directory * len(self.kept()) + self.cfg.guard_bytes
            if free < need:
                raise RuntimeError(
                    f"cache of reading {r}: {free} bytes free, {need} needed with the guard"
                )
            self.step(
                f"cache_{r}",
                [
                    "scripts/train.py", "cache", os.path.join(work, "mined.listing.json"),
                    self.p(r, "selection_mined.json"), cache,
                    "--feature-table", self.p(r, "features_mined.csv"),
                    "--form", self.cfg.form, "--local",
                ],
                stdout_to=self.p(r, "cache.json"),
            )  # fmt: skip
            self.step(
                f"filter_size_{r}",
                [
                    "scripts/train.py", "filter-size", cache, self.p(r, "features_mined.csv"),
                    "--teacher", self.cfg.teacher, "--k", str(self.cfg.k),
                    "--level", self.cfg.level,
                ],
                stdout_to=self.p(r, "filter_size.json"),
            )  # fmt: skip
            info[r] = {
                "cache_bytes": os.path.getsize(cache),
                "written": _read_json(self.p(r, "cache.json"))["written"],
            }
        return info

    def do_check(self) -> dict[str, Any]:
        self.step(
            "check",
            [
                "scripts/rq2_full_prep.py", "check", self.out, "--held-out", self.cfg.held_out,
                "--rename-cache", self.cfg.rename_cache, "--readings", *self.cfg.readings,
            ],
            stdout_to=self.p("check.json"),
        )  # fmt: skip
        info: dict[str, Any] = _read_json(self.p("check.json"))
        return info

    # ------------------------------------------------------------------ driver

    def run(self) -> None:
        env = {
            "host": platform.node(),
            "python": sys.version.split()[0],
            "config": {k: v for k, v in asdict(self.cfg).items() if k != "extra"},
            "commit": os.environ.get("RIL_COMMIT", "none"),
            "free_out_bytes": shutil.disk_usage(self.out).free,
            "free_scratch_bytes": shutil.disk_usage(self.cfg.scratch).free
            if os.path.isdir(self.cfg.scratch)
            else None,
        }
        os.makedirs(self.cfg.scratch, exist_ok=True)
        _write_json(self.p("run_env.json"), env)
        table: dict[str, tuple[Callable[[], dict[str, Any]], list[str]]] = {
            "select": (self.do_select, [self.p("names.txt")]),
            "overlap": (self.do_overlap, [self.p("overlap")]),
            "drop": (self.do_drop, [self.p("names_kept.txt")]),
            "materialise": (self.do_materialise, [self.s("view")]),
            "inputs": (self.do_inputs, [self.s(f"work_{r}") for r in self.cfg.readings]),
            "teacher": (
                self.do_teacher,
                [self.p(r, "ranks_bm25.jsonl") for r in self.cfg.readings],
            ),
            "features": (
                self.do_features,
                [self.p(r, "features_mined.csv") for r in self.cfg.readings],
            ),
            "cache": (self.do_cache, [self.p(r, "mined.jsonl.gz") for r in self.cfg.readings]),
            "check": (self.do_check, [self.p("check.json")]),
        }
        for name in STAGES:
            if name not in self.cfg.stages:
                continue
            if self.done(name):
                continue
            body, outputs = table[name]
            self.stage(name, body, outputs)
        if self.cfg.clean_scratch:
            shutil.rmtree(self.cfg.scratch, ignore_errors=True)


def check_run(
    out: str, held_out: str, rename_cache: str, readings: Sequence[str]
) -> dict[str, Any]:
    """Counts per reading, held-out count of the training manifest and the cache, drop list applied.

    The cache is streamed (one example at a time), so the check's memory does not grow with it.
    """
    from ril.training.pool_rank_jobs import held_out_predicate

    pred = held_out_predicate(held_out, rename_cache)
    drop_path = os.path.join(out, "overlap", "drop_f20_non_test.txt")
    dropped = set(fp.read_names(drop_path)) if os.path.exists(drop_path) else set()
    info: dict[str, Any] = {}
    for r in readings:
        manifest = _read_json(os.path.join(out, r, "selection_mined.json"))["names"]
        summary = fp.cache_summary(os.path.join(out, r, "mined.jsonl.gz"))
        counts_path = os.path.join(out, r, "counts.json")
        counts = _read_json(counts_path) if os.path.exists(counts_path) else {}
        info[r] = {
            "directories_in_reading": counts.get("directories"),
            "positives_in_reading": counts.get("positives"),
            "manifest_names": len(manifest),
            "cache_examples": summary["examples"],
            "cache_positives": summary["positives"],
            "cache_repositories": len(summary["repos"]),
            "cache_candidates": summary["candidates"],
            "held_out_in_manifest": sum(1 for n in manifest if pred(_repo_of_dir(n))),
            "held_out_in_cache": sum(1 for x in summary["repos"] if pred(x)),
            "dropped_in_cache": sum(1 for x in summary["ids"] if x in dropped),
            "dropped_in_manifest": sum(1 for n in manifest if n in dropped),
        }
    return info


def cache_memory(path: str, variant: str) -> dict[str, Any]:
    """Resident memory after reading a whole example cache, plain or with equal strings shared.

    ``plain`` is :func:`ril.training.pool_reader.read_cache` as training reads it. ``shared`` reads
    the same rows but keeps one copy of each distinct text and id (function texts repeat across the
    pull requests of one repository), so the examples compare equal to the plain ones. The peak is
    the process's own: run each variant in a fresh process.
    """
    import resource

    from ril.training.pool_reader import read_cache, read_cache_shared

    t0 = time.perf_counter()
    examples = read_cache(path) if variant == "plain" else read_cache_shared(path)
    seconds = time.perf_counter() - t0
    text_bytes = sum(len(t.encode("utf-8")) for e in examples for t in e.candidate_texts)
    return {
        "variant": variant,
        "examples": len(examples),
        "candidate_text_bytes": text_bytes,
        "peak_rss_kb": int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss),
        "seconds": round(seconds, 2),
        "cache_bytes": os.path.getsize(path),
    }


def _repo_of_dir(directory: str) -> str:
    """``owner/name`` of a directory name ``owner__name-<PR>`` (lower case)."""
    stem = directory.rsplit("-", 1)[0]
    return stem.replace("__", "/", 1)


def compare_with_pilot(
    ranks_new: str, features_new: str, ranks_pilot: str, features_pilot: str
) -> dict[str, Any]:
    """Rank rows and feature rows of the directories both runs hold, compared for equality.

    The pilot's files are the stored values of E-MINED-PILOT; the new files come from the chain on
    the full store. Only directories in both are compared; the counts say how many that is.
    """
    import csv

    from ril.data_mining import rank_jobs

    ranks = rank_jobs.reproduces([ranks_new], ranks_pilot, common_only=True)

    def table(path: str) -> dict[tuple[str, str], tuple[str, ...]]:
        with open(path, encoding="utf-8", newline="") as handle:
            return {
                (r["instance_id"], r["positive_key"]): (
                    r["repo"], r["held_out"], r["functions"], r["positives_in_instance"],
                    r["rank_bm25"], r["rank_all_bm25"],
                )
                for r in csv.DictReader(handle)
            }  # fmt: skip

    new, old = table(features_new), table(features_pilot)
    common_dirs = {d for d, _ in new} & {d for d, _ in old}
    new_c = {k: v for k, v in new.items() if k[0] in common_dirs}
    old_c = {k: v for k, v in old.items() if k[0] in common_dirs}
    differing = sorted(k for k in new_c if k in old_c and new_c[k] != old_c[k])
    return {
        "ranks": {
            k: ranks[k] for k in ("old_directories", "compared", "identical", "differing", "exact")
        },
        "features": {
            "common_directories": len(common_dirs),
            "rows_new": len(new_c),
            "rows_pilot": len(old_c),
            "rows_only_in_one": len(set(new_c) ^ set(old_c)),
            "rows_differing": len(differing),
            "equal": not differing and set(new_c) == set(old_c) and bool(common_dirs),
        },
    }


def main_stage_list(text: str) -> tuple[str, ...]:
    """Parse ``--stages`` (``all``, or names split on commas or colons) into chain order."""
    if text == "all":
        return STAGES
    wanted = [x for x in text.replace(":", ",").split(",") if x]
    bad = [x for x in wanted if x not in STAGES]
    if bad:
        raise ValueError(f"unknown stage(s) {bad}; use {STAGES}")
    return tuple(s for s in STAGES if s in wanted)
