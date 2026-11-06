"""RQ3 pilot: prepare prompts, send them through the rate limiter, report from the call log.

Usage:
  rq3_pilot.py prepare OUT_DIR (--contexts FILE.jsonl | --from-cache CONFIG.yaml) [--seed N]
  rq3_pilot.py run PREPARED_DIR LOG_DIR [--runs 2] [--max-calls N] [--dry-run]
                   [--wait-for-daily] [--seed N]
  rq3_pilot.py report LOG_DIR [--grades FILE.jsonl] [--out FILE.md] [--seed N]

``run`` reads the key only from ~/.ril_llm_env or GEMINI_API_KEY and never prints it.
Implements docs/RQ3_PILOT.md.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import yaml  # noqa: E402  (import after the sys.path line above)

from ril.util.log import get_logger  # noqa: E402  (same)
from ril.util.seed import set_seed  # noqa: E402  (same)

LIMITS_FILE = Path(__file__).resolve().parents[1] / "configs" / "agent" / "gemini_limits.yaml"


def cmd_prepare(args: argparse.Namespace) -> int:
    from ril.agent.providers.pilot_run import prepare_items

    log = get_logger("rq3_pilot")
    if args.contexts:
        rows = [
            json.loads(x) for x in Path(args.contexts).read_text(encoding="utf-8").splitlines() if x
        ]
    else:
        from ril.agent.providers.contexts import contexts_from_cache

        cfg = yaml.safe_load(Path(args.from_cache).read_text(encoding="utf-8"))
        for k in ("cache_dir", "dense_root", "repo_cache", "core_bench_raw", "work_dir"):
            cfg[k] = os.path.expanduser(os.path.expandvars(cfg[k]))
        from ril.agent.providers.contexts import issues_from_core_bench

        issues = issues_from_core_bench(cfg["core_bench_raw"])
        rows, failures = contexts_from_cache(
            cfg["cache_dir"],
            cfg["dense_root"],
            cfg["repo_cache"],
            cfg["work_dir"],
            issues,
            level=cfg["level"],
            budget=int(round(cfg["budget_model_tokens"] * cfg["approx_per_model_token"])),
            max_unit_tokens=int(cfg["max_unit_tokens"]),
            n_candidates=int(cfg["candidates"]),
            dense_variant=cfg["dense_variant"],
            rrf_k=int(cfg["rrf_k"]),
            roles=tuple(cfg["roles"]),
            instance_ids=cfg.get("instance_ids"),
            limit=cfg.get("limit"),
            seed=args.seed,
        )
        for f in failures:
            log.warning("skipped %s: %s", f["instance"], f["reason"])
    n = prepare_items(rows, args.out_dir)
    log.info("prepared %d items in %s", n, args.out_dir)
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    from ril.agent.providers.calllog import CallLog
    from ril.agent.providers.gemini import (
        ApiKeyError,
        GeminiClient,
        GeminiConfig,
        ProviderError,
        load_api_key,
    )
    from ril.agent.providers.limiter import PersistentLimiter, load_limits
    from ril.agent.providers.pilot_run import RunConfig, load_items, plan_units, run_units

    log = get_logger("rq3_pilot")
    limits = load_limits(args.limits)
    items = load_items(args.prepared_dir)
    units = plan_units(items, args.runs)
    done = CallLog(Path(args.log_dir)).by_unit()
    todo = sum(1 for u, _ in units if not any(r["final"] for r in done.get(u, [])))
    cap = limits.rpd_eff
    log.info(
        "units %d, unfinished %d; 1 to 3 calls each: %d to %d calls, "
        "%d to %d days at %d/day (limits as of %s)",
        len(units),
        todo,
        todo,
        3 * todo,
        math.ceil(todo / cap),
        math.ceil(3 * todo / cap),
        cap,
        limits.as_of,
    )
    if args.dry_run:
        return 0
    try:
        key = load_api_key()
    except ApiKeyError as err:
        log.error("%s", err)
        return 2
    limiter = PersistentLimiter(limits, Path(args.log_dir) / "limiter.jsonl")
    cfg = GeminiConfig(
        model=limits.model,
        temperature=0.0,
        seed=args.seed,
        max_output_tokens=args.max_output_tokens,
    )
    client = GeminiClient(cfg, key, limiter)
    rc = RunConfig(
        model=limits.model,
        seed=args.seed,
        temperature=0.0,
        runs=args.runs,
        max_calls=args.max_calls,
        wait_for_daily=args.wait_for_daily,
    )
    try:
        s = run_units(items, CallLog(Path(args.log_dir)), client, rc, limiter.day_of)
    except ProviderError as err:
        log.error("provider refused the request: %s", err)
        return 3
    log.info(
        "stopped: %s; calls this session %d; units finished %d, already finished %d",
        s.stopped,
        s.calls,
        s.units_finished,
        s.units_skipped,
    )
    if s.resume_at is not None:
        log.info(
            "daily cap reached; run the same command after epoch %.0f (next Pacific midnight)",
            s.resume_at,
        )
    for e in s.errors:
        log.warning("%s", e)
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    from ril.agent.providers.calllog import CallLog
    from ril.agent.providers.report import summarise, to_markdown

    grades = None
    if args.grades:
        grades = {}
        for line in Path(args.grades).read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                grades[(r["instance_id"], r["arm"], int(r["run_index"]))] = bool(r["resolved"])
    s = summarise(CallLog(Path(args.log_dir)), grades)
    text = to_markdown(s)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        Path(args.out).with_suffix(".json").write_text(
            json.dumps(s, indent=1, sort_keys=True, default=str), encoding="utf-8"
        )
    sys.stdout.write(text)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("out_dir")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--contexts")
    g.add_argument("--from-cache")
    p = sub.add_parser("run")
    p.add_argument("prepared_dir")
    p.add_argument("log_dir")
    p.add_argument("--runs", type=int, default=2)
    p.add_argument("--max-calls", type=int)
    p.add_argument("--max-output-tokens", type=int, default=4096)
    p.add_argument("--limits", default=str(LIMITS_FILE))
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--wait-for-daily", action="store_true")
    p = sub.add_parser("report")
    p.add_argument("log_dir")
    p.add_argument("--grades")
    p.add_argument("--out")
    for sp in sub.choices.values():
        sp.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    set_seed(args.seed)
    return {"prepare": cmd_prepare, "run": cmd_run, "report": cmd_report}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
