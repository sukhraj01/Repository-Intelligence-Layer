"""The path from a prepared prompt to a graded result row. Implements ``docs/RQ3_PILOT.md`` (D113).

One *unit* is (instance, arm, run index). For every unit the driver

1. obtains the final reply: a call through the client (with the pilot's follow-up policy, logged
   and resumable by ``pilot_run``), a reply already in a call log, or a stored or synthetic reply
   (replay mode, no provider);
2. converts it to the executor's patch under both readings of ``patch_convert`` (exact primary,
   tolerant sensitivity);
3. runs the patch in the instance's environment and reads FAIL_TO_PASS and PASS_TO_PASS;
4. appends one row to ``results.jsonl`` with an outcome class.

Outcome classes (a reply that does not give a resolved instance is unresolved, whichever class):

* ``unusable``: the final reply has no usable edit block (D109);
* ``apply_failed:<class>``: the edit set does not apply under the exact reading (D110), the class
  is one of ``file_missing``, ``no_match``, ``multiple_matches`` or ``git_apply``;
* ``executed_unresolved``: the patch applied and at least one named test did not pass (including
  a patch that leaves the code unable to run its tests, and an empty diff, which is not executed);
* ``resolved``: all FAIL_TO_PASS and PASS_TO_PASS tests pass;
* ``exec_error:<stage>``: the environment failed before the patch was involved. Such a row is not
  final: a restart sends the unit to the executor again (the stored reply is reused), and the
  analysis counts what is left as unresolved and reports it apart.

A step that fails on a name-resolution outage is retried with backoff and logged; a failure of
the tests themselves is never retried.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from ril.agent.providers.calllog import CallLog, Row, Unit
from ril.agent.providers.patch_convert import READINGS, Conversion, Reading, convert_reply
from ril.agent.providers.pilot_run import Generator, RunConfig, RunSummary, plan_units, run_unit
from ril.agent.providers.pseudonymise import restore_text
from ril.agent.providers.spend import Price
from ril.evaluation.executor.runner import ExecResult
from ril.util.log import get_logger

log = get_logger("providers.driver")

DRIVER_VERSION = "rq3-driver/v1"
RESULT_FILE = "results.jsonl"
NAME_RESOLUTION = re.compile(
    r"Name or service not known|Temporary failure in name resolution|Could not resolve host"
    r"|nodename nor servname|failed to lookup address|dns error|Failed to resolve",
    re.IGNORECASE,
)
ENV_RETRIES = 3
ENV_BACKOFF_S = 30.0
READ_FAULT = "unreadable_file"

ReadFile = Callable[[str], str | None]


class StopRun(Exception):
    """A reply source cannot go on (daily cap, spend cap, provider fault)."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class Reply:
    """The final reply of a unit and what it cost."""

    text: str
    usable: bool
    parse_error: str = ""
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    thought_tokens: int = 0
    call_wall_s: float = 0.0
    cached_tokens: int = 0


class ReplySource(Protocol):
    def get(self, unit: Unit, item: Mapping[str, Any]) -> Reply | None:
        """The unit's final reply, or ``None`` to skip it; raises ``StopRun`` to end the run."""


Executor = Callable[[str, str], ExecResult]
"""``(instance id, unified diff) -> ExecResult``; an empty diff is never passed."""
ReaderFactory = Callable[[str], ReadFile]
"""Instance id -> reader of base-commit file texts."""


# ---------------------------------------------------------------------------- reply sources


def reply_from_rows(rows: Sequence[Row], log_: CallLog) -> Reply | None:
    """The final reply of a unit from its call-log rows; ``None`` while the unit is unfinished."""
    replies = [r for r in rows if r["kind"] == "reply"]
    if not replies or not replies[-1]["final"]:
        return None
    last = replies[-1]
    blocked = last["format_error"] == "blocked" or last["finish_reason"] == "PROMPT_BLOCKED"
    text = "" if blocked else log_.load("responses", last["response_sha256"])
    return Reply(
        text=text,
        usable=bool(last["patch_ok"]),
        parse_error=str(last["format_error"]),
        calls=len(rows),
        input_tokens=sum(int(r["input_tokens"]) for r in rows),
        output_tokens=sum(int(r["output_tokens"]) for r in rows),
        thought_tokens=sum(int(r["thought_tokens"]) for r in rows),
        call_wall_s=sum(float(r["latency_s"]) for r in rows),
        cached_tokens=sum(int(r.get("cached_tokens", 0)) for r in rows),
    )


class LoggedReplies:
    """Replies from the pilot's call log; with a client, unfinished units are sent first."""

    def __init__(
        self,
        call_log: CallLog,
        cfg: RunConfig,
        client: Generator | None = None,
        day_of: Callable[[float], str] | None = None,
    ) -> None:
        self.log = call_log
        self.cfg = cfg
        self.client = client
        self.day_of = day_of or (lambda t: time.strftime("%Y-%m-%d", time.gmtime(t)))
        self.summary = RunSummary()
        self._done = call_log.by_unit()

    def get(self, unit: Unit, item: Mapping[str, Any]) -> Reply | None:
        if self.client is not None:
            if not run_unit(
                unit, item, self.log, self.client, self.cfg, self.day_of, self.summary, self._done
            ):
                raise StopRun(self.summary.stopped)
            self._done = self.log.by_unit()
        rows = self._done.get(unit, [])
        return reply_from_rows(rows, self.log)


class StoredReplies:
    """Stored or synthetic replies by unit (replay mode); no provider, no follow-up."""

    def __init__(self, replies: Mapping[Unit, str]) -> None:
        self.replies = dict(replies)

    def get(self, unit: Unit, item: Mapping[str, Any]) -> Reply | None:
        from ril.agent.providers.patch_format import parse_edits

        text = self.replies.get(unit)
        if text is None:
            return None
        edits, err = parse_edits(text, item.get("paths"))
        return Reply(text=text, usable=err is None and bool(edits), parse_error=err or "")


# ---------------------------------------------------------------------------- one unit


@dataclass(frozen=True)
class DriverConfig:
    model: str
    runs: int = 1
    run_indices: tuple[int, ...] | None = None
    mode: str = "live"
    workers: int = 1
    adjacent_repeats: bool = False
    env_retries: int = ENV_RETRIES
    env_backoff_s: float = ENV_BACKOFF_S
    meta: Mapping[str, Any] = field(default_factory=dict)


def run_with_retry(
    executor: Executor,
    instance_id: str,
    diff: str,
    retries: int,
    backoff_s: float,
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[ExecResult, list[dict[str, Any]]]:
    """Execute; repeat only a failure that names a name-resolution outage (and ran no tests)."""
    trail: list[dict[str, Any]] = []
    for attempt in range(retries + 1):
        res = executor(instance_id, diff)
        outage = (
            res.failure_stage != ""
            and not res.tests_ran
            and NAME_RESOLUTION.search(res.failure_detail or "") is not None
        )
        if not outage or attempt == retries:
            return res, trail
        wait = backoff_s * 2**attempt
        trail.append({"attempt": attempt, "stage": res.failure_stage, "waited_s": wait})
        log.warning(
            "%s: name-resolution failure in %s, retry in %.0f s",
            instance_id,
            res.failure_stage,
            wait,
        )
        sleep(wait)
    raise AssertionError("unreachable")


def classify(res: ExecResult) -> str:
    """Outcome class of one execution (the patch is known to apply as a diff)."""
    if res.resolved:
        return "resolved"
    if res.failure_stage == "patch_apply_failed":
        return "apply_failed:git_apply"
    if res.patch_applied:
        return "executed_unresolved"
    return f"exec_error:{res.failure_stage or 'unknown'}"


def _diff_of(conv: Conversion) -> str:
    return conv.diff or ""


def process_unit(
    unit: Unit,
    item: Mapping[str, Any],
    reply: Reply,
    reader: ReadFile,
    executor: Executor,
    cfg: DriverConfig,
    price: Price | None,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Convert (both readings), execute and classify; return the result row."""
    t0 = time.perf_counter()
    iid, arm, run = unit
    row: dict[str, Any] = {
        "instance_id": iid,
        "arm": arm,
        "run": run,
        "repo": item.get("repo", ""),
        "model": cfg.model,
        "mode": cfg.mode,
        "driver": DRIVER_VERSION,
        "calls": reply.calls,
        "input_tokens": reply.input_tokens,
        "output_tokens": reply.output_tokens,
        "thought_tokens": reply.thought_tokens,
        "cached_tokens": reply.cached_tokens,
        "cost_usd": (
            round(price.cost(reply.input_tokens, reply.output_tokens, reply.cached_tokens), 6)
            if price
            else 0.0
        ),
        "call_wall_s": round(reply.call_wall_s, 3),
        "usable": reply.usable,
        "parse_error": reply.parse_error,
        "outcome": "",
        "outcome_tolerant": "",
        "resolved": False,
        "resolved_tolerant": False,
        "n_blocks": 0,
        "empty_diff": False,
        "env_retries": 0,
        "env_retry_log": [],
        "failure_stage": "",
        "f2p": [0, 0],
        "p2p": [0, 0],
        "exec_seconds": 0.0,
    }
    if "expected" in item:
        row["expected"] = item["expected"]
    if not reply.usable:
        row["outcome"] = row["outcome_tolerant"] = "unusable"
        return _finish(row, t0, item)
    paths = item.get("paths")
    text = restore_text(
        reply.text, item.get("restore")
    )  # placeholders back to the original text (D120)
    convs: dict[Reading, Conversion] = {}
    try:
        for reading in READINGS:
            convs[reading] = convert_reply(text, reader, reading, paths)
    except (UnicodeDecodeError, ValueError) as err:
        row["outcome"] = row["outcome_tolerant"] = f"exec_error:{READ_FAULT}"
        row["failure_stage"] = type(err).__name__
        return _finish(row, t0, item)
    row["n_blocks"] = convs["exact"].n_blocks
    results: dict[str, ExecResult] = {}  # by diff text, so one diff runs once
    trail: list[dict[str, Any]] = []
    for reading in READINGS:
        conv = convs[reading]
        key = "outcome" if reading == "exact" else "outcome_tolerant"
        if conv.failure is not None:
            row[key] = f"apply_failed:{conv.failure.kind}"
            continue
        diff = _diff_of(conv)
        if not diff:
            row[key] = "executed_unresolved"
            row["empty_diff"] = True
            continue
        if diff not in results:
            res, steps = run_with_retry(
                executor, iid, diff, cfg.env_retries, cfg.env_backoff_s, sleep
            )
            results[diff] = res
            trail += [{**s, "reading": reading} for s in steps]
        res = results[diff]
        row[key] = classify(res)
        if reading == "exact":
            row.update(
                failure_stage=res.failure_stage,
                f2p=[res.f2p_passed, res.f2p_total],
                p2p=[res.p2p_passed, res.p2p_total],
                exec_seconds=round(res.seconds.get("total", 0.0), 3),
            )
    if not row["outcome"]:
        raise AssertionError("exact reading left no outcome")
    row["env_retries"] = len(trail)
    row["env_retry_log"] = trail
    return _finish(row, t0, item)


def _finish(row: dict[str, Any], t0: float, item: Mapping[str, Any]) -> dict[str, Any]:
    row["resolved"] = row["outcome"] == "resolved"
    row["resolved_tolerant"] = row["outcome_tolerant"] == "resolved"
    row["wall_s"] = round(row["call_wall_s"] + (time.perf_counter() - t0), 3)
    if "expected" in row:
        row["match"] = row["outcome"] == row["expected"]
    return row


# ---------------------------------------------------------------------------- the loop


def final_keys(path: Path) -> set[Unit]:
    """Units with a finished row (``exec_error`` rows are not finished)."""
    done: set[Unit] = set()
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                if not str(r["outcome"]).startswith("exec_error"):
                    done.add((r["instance_id"], r["arm"], int(r["run"])))
    return done


def latest_rows(path: Path) -> dict[Unit, dict[str, Any]]:
    """The last row of every unit in a result file."""
    out: dict[Unit, dict[str, Any]] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                out[(r["instance_id"], r["arm"], int(r["run"]))] = r
    return out


@dataclass
class DriveSummary:
    written: int = 0
    skipped: int = 0
    not_available: int = 0
    stopped: str = "complete"
    errors: list[str] = field(default_factory=list)


def drive(
    items: Sequence[Mapping[str, Any]],
    out_dir: str | Path,
    source: ReplySource,
    executor: Executor,
    reader_for: ReaderFactory,
    cfg: DriverConfig,
    price: Price | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> DriveSummary:
    """Run every unfinished unit in the order (run index, instance, arm); resumable.

    Replies come from ``source`` one unit at a time (so the rate limiter and the spend guard
    pace the calls); conversion and execution of finished replies run on ``cfg.workers`` threads.
    """
    root = Path(out_dir)
    root.mkdir(parents=True, exist_ok=True)
    result_path = root / RESULT_FILE
    done = final_keys(result_path)
    summary = DriveSummary()
    lock = threading.Lock()
    readers: dict[str, ReadFile] = {}

    def reader(iid: str) -> ReadFile:
        with lock:
            if iid not in readers:
                readers[iid] = reader_for(iid)
            return readers[iid]

    def work(unit: Unit, item: Mapping[str, Any], reply: Reply) -> None:
        try:
            row = process_unit(unit, item, reply, reader(unit[0]), executor, cfg, price, sleep)
        except Exception as err:  # noqa: BLE001  (one unit's fault must not end the run; it is logged and the unit stays unfinished)
            with lock:
                summary.errors.append(f"{unit}: {type(err).__name__}: {err}"[:300])
            log.error("%s: %s", unit, type(err).__name__)
            return
        with lock:
            with result_path.open("a", encoding="utf-8") as out:
                out.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
                out.flush()
                os.fsync(out.fileno())
            summary.written += 1

    futures: list[Future[None]] = []
    with ThreadPoolExecutor(max_workers=max(1, cfg.workers)) as pool:
        for unit, item in plan_units(items, cfg.runs, cfg.run_indices, cfg.adjacent_repeats):
            if unit in done:
                summary.skipped += 1
                continue
            try:
                reply = source.get(unit, item)
            except StopRun as stop:
                summary.stopped = stop.reason
                break
            if reply is None:
                summary.not_available += 1
                continue
            if cfg.workers <= 1:
                work(unit, item, reply)
            else:
                futures.append(pool.submit(work, unit, item, reply))
        for f in futures:
            f.result()
    (root / "meta.json").write_text(
        json.dumps(
            {
                **dict(cfg.meta),
                "driver": DRIVER_VERSION,
                "model": cfg.model,
                "mode": cfg.mode,
                "runs": cfg.runs,
                "run_indices": list(cfg.run_indices) if cfg.run_indices is not None else None,
                "schedule": "adjacent_repeats" if cfg.adjacent_repeats else "run_major",
                "stopped": summary.stopped,
                "written_this_session": summary.written,
            },
            indent=1,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return summary
