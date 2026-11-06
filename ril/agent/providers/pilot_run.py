"""Prepare, run and resume the RQ3 pilot calls. Implements ``docs/RQ3_PILOT.md``.

``prepare`` turns assembled contexts (rows with the context text, its hash and the issue) into
one prompt file per (instance, arm). ``run`` sends them through the client, ``runs`` times per
unit, in a fixed order (run index, instance, arm), with up to ``max_reasks`` follow-ups after an
unusable reply, the same for every arm. The log rows alone decide what is finished, so a run
stopped by the daily cap (or a crash) resumes without repeating a finished call.
"""

from __future__ import annotations

import json
import time
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from ril.agent.providers.calllog import CallLog, Row, Unit, sha256_text
from ril.agent.providers.gemini import CallResult, canonical
from ril.agent.providers.limiter import DailyCapReached
from ril.agent.providers.patch_format import (
    TEMPLATE_VERSION,
    build_prompt,
    edits_key,
    parse_edits,
    reask_message,
)

PREPARED_VERSION = "rq3-pilot-prepared/v1"


# ---------------------------------------------------------------------------- prepare


def prepare_items(context_rows: Iterable[Mapping[str, Any]], out_dir: str | Path) -> int:
    """Write ``items.jsonl`` and ``prompts/<sha>.txt``; return the number of items.

    A row must carry ``instance_id``, ``arm``, ``issue``, ``context``, ``context_sha256`` and
    ``files`` (the paths the context shows). The context is checked against its hash, so the bytes
    sent are the bytes the assembly stage produced.
    """
    root = Path(out_dir)
    (root / "prompts").mkdir(parents=True, exist_ok=True)
    items: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for row in context_rows:
        key = (str(row["instance_id"]), str(row["arm"]))
        if key in seen:
            raise ValueError(f"duplicate (instance, arm) {key}")
        seen.add(key)
        context = str(row["context"])
        if sha256_text(context) != row["context_sha256"]:
            raise ValueError(f"{key}: context does not match its recorded hash")
        prompt = build_prompt(str(row["issue"]), context)
        digest = sha256_text(prompt)
        (root / "prompts" / f"{digest}.txt").write_text(prompt, encoding="utf-8")
        items.append(
            {
                "instance_id": key[0],
                "arm": key[1],
                "first_stage": row.get("first_stage", key[1]),
                "budget": row.get("budget"),
                "tokenizer": row.get("tokenizer"),
                "context_sha256": row["context_sha256"],
                "issue_sha256": sha256_text(str(row["issue"])),
                "prompt_sha256": digest,
                "paths": sorted(set(row["files"])),
                "template_version": TEMPLATE_VERSION,
            }
        )
    items.sort(key=lambda r: (r["instance_id"], r["arm"]))
    (root / "items.jsonl").write_text(
        "".join(json.dumps(r, sort_keys=True) + "\n" for r in items), encoding="utf-8"
    )
    return len(items)


def load_items(prepared_dir: str | Path) -> list[dict[str, Any]]:
    root = Path(prepared_dir)
    rows = [
        json.loads(x) for x in (root / "items.jsonl").read_text(encoding="utf-8").splitlines() if x
    ]
    for r in rows:
        r["prompt"] = (root / "prompts" / f"{r['prompt_sha256']}.txt").read_text(encoding="utf-8")
    return rows


# ---------------------------------------------------------------------------- run


class Generator(Protocol):
    """What ``run_units`` needs of a client: a model string, a seed and ``generate``."""

    def generate(
        self, contents: Sequence[Mapping[str, Any]], *, wait_for_daily: bool = False
    ) -> CallResult: ...


@dataclass(frozen=True)
class RunConfig:
    model: str
    seed: int
    temperature: float
    runs: int = 2
    max_reasks: int = 2
    max_calls: int | None = None
    wait_for_daily: bool = False


@dataclass
class RunSummary:
    calls: int = 0
    units_finished: int = 0
    units_skipped: int = 0
    stopped: str = ""
    resume_at: float | None = None
    errors: list[str] = field(default_factory=list)


def plan_units(
    items: Sequence[Mapping[str, Any]], runs: int
) -> list[tuple[Unit, Mapping[str, Any]]]:
    """Units in the fixed order (run index, instance, arm)."""
    ordered = sorted(items, key=lambda r: (r["instance_id"], r["arm"]))
    return [((r["instance_id"], r["arm"], k), r) for k in range(runs) for r in ordered]


def _user(text: str) -> dict[str, Any]:
    return {"role": "user", "parts": [{"text": text}]}


def _model(text: str) -> dict[str, Any]:
    return {"role": "model", "parts": [{"text": text}]}


def run_units(
    items: Sequence[Mapping[str, Any]],
    log: CallLog,
    client: Generator,
    cfg: RunConfig,
    day_of: Any,
) -> RunSummary:
    """Send every unfinished unit; stop cleanly at the daily cap, ``max_calls`` or a provider fault.

    ``day_of`` maps an epoch time to the Pacific date string (the limiter's ``day_of``).
    """
    summary = RunSummary()
    done = log.by_unit()
    for unit, item in plan_units(items, cfg.runs):
        prior = done.get(unit, [])
        if prior and any(r["final"] for r in prior):
            summary.units_skipped += 1
            continue
        replies = [r for r in prior if r["kind"] == "reply"]
        contents: list[dict[str, Any]] = [_user(str(item["prompt"]))]
        for r in replies:
            contents += [
                _model(log.load("responses", r["response_sha256"])),
                _user(reask_message(r["format_error"])),
            ]
        attempt = len(replies)
        while True:
            if cfg.max_calls is not None and summary.calls >= cfg.max_calls:
                summary.stopped = "max_calls"
                return summary
            t_start = time.time()
            try:
                res = client.generate(contents, wait_for_daily=cfg.wait_for_daily)
            except DailyCapReached as stop:
                summary.stopped = "daily_cap"
                summary.resume_at = stop.resume_at
                return summary
            summary.calls += 1
            prompt_sha = log.store("prompts", canonical(contents))
            row: Row = {
                "instance_id": unit[0],
                "arm": unit[1],
                "run_index": unit[2],
                "attempt": attempt,
                "model": cfg.model,
                "seed": cfg.seed,
                "temperature": cfg.temperature,
                "date_pacific": day_of(t_start),
                "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t_start)),
                "input_tokens": res.input_tokens,
                "output_tokens": res.output_tokens,
                "thought_tokens": res.thought_tokens,
                "latency_s": round(res.latency_s, 3),
                "finish_reason": res.finish_reason,
                "http_status": res.status,
                "retries": res.retries,
                "n_429": res.n_429,
                "n_5xx": res.n_5xx,
                "prompt_sha256": prompt_sha,
                "request_sha256": res.request_sha256,
                "response_sha256": "",
                "budget": item.get("budget"),
                "first_stage": item.get("first_stage"),
                "template_version": item.get("template_version"),
                "format_error": res.error or "",
                "patch_ok": False,
                "edits_sha256": "",
                "final": False,
                "kind": "failed",
            }
            if res.error == "retries_exhausted":
                log.append(row)
                summary.stopped = "provider_unavailable"
                summary.errors.append(f"{unit}: retries exhausted (last status {res.status})")
                return summary
            row["kind"] = "reply"
            row["response_sha256"] = log.store("responses", res.text)
            if res.error == "blocked":
                row["final"] = True
            else:
                code = "empty_reply" if res.error == "malformed_response" else None
                edits, err = ((), code) if code else parse_edits(res.text, item["paths"])
                row["format_error"] = err or ""
                row["patch_ok"] = err is None
                if err is None:
                    row["edits_sha256"] = sha256_text(edits_key(edits))
                row["final"] = err is None or attempt >= cfg.max_reasks
            log.append(row)
            if row["final"]:
                summary.units_finished += 1
                break
            contents += [_model(res.text), _user(reask_message(str(row["format_error"])))]
            attempt += 1
    summary.stopped = summary.stopped or "complete"
    return summary
