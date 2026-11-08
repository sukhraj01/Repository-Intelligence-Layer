"""RQ3 driver: held-out slice, prompts, calls and grading, replay test, analysis, power, cost.

Usage:
  rq3_driver.py heldout SUBSET.json OUT.json [--n 50] [--seed 0]
  rq3_driver.py prepare CTX_DIR OUT_DIR --raw RAW_ROOT --issues-parquet TABLE.parquet
                --subset SUBSET.json --heldout HELD.json
                [--budget 8000] [--arms bm25 dense rrf]
  rq3_driver.py run ITEMS_DIR LOG_DIR OUT_DIR --arm ARM --run-index K --instances IDS.txt
                --model M --cap-usd USD [--thinking-config JSON] [--max-output-tokens N]
                [--workers N] [--wait-for-daily] [--max-calls N] [exec options]
  rq3_driver.py grade ITEMS_DIR LOG_DIR OUT_DIR --arm ARM --run-index K --instances IDS.txt
                --model M [exec options]
  rq3_driver.py replay SPECS GOLD DRAW OUT_DIR --subset SUBSET.json [exec options]
  rq3_driver.py analyse OUT.json RESULT_DIR [RESULT_DIR ...] --subset SUBSET.json
                --heldout HELD.json --arms A B ... --primary A B [--estimate A B ...]
                --runs 0 1 --out-dir DIR
  rq3_driver.py model-check OUT.json NAME=RESULT_DIR [NAME=RESULT_DIR ...]
  rq3_driver.py power OUT_DIR [--n 327 ...] [--sims 400] [--seed 0]
  rq3_driver.py cost OUT_DIR --pilot-cost results/rq3_pilot/analysis/rq3_pilot_cost.csv

Exec options: --specs SPECS.jsonl --work-root DIR --cache-root DIR --mirror-dir DIR
[--local-mirrors DIR].  ``run`` refuses to start without --cap-usd.  The key is read only by the
provider client (see rq3_pilot.py) and never printed.  Implements D111 to D114
(docs/RQ3_PILOT.md).  Thin wrapper: the logic is in ril/agent/providers/ and ril/analysis/.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ril.util.log import get_logger  # noqa: E402
from ril.util.seed import set_seed  # noqa: E402

log = get_logger("rq3_driver")
ROOT = Path(__file__).resolve().parents[1]
LIMITS_FILE = ROOT / "configs" / "agent" / "gemini_limits.yaml"
PRICES_FILE = ROOT / "configs" / "agent" / "prices.yaml"
EMAIL_DIGESTS = ROOT / "configs" / "agent" / "prompt_email_digests.txt"


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields: list[str] = []
    for r in rows:
        fields += [k for k in r if k not in fields]
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def _write_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def _operator_emails() -> list[str]:
    import subprocess

    out = subprocess.run(
        ["git", "config", "user.email"], capture_output=True, text=True, check=False
    ).stdout.strip()
    extra = [a.strip() for a in os.environ.get("RIL_FORBIDDEN_EMAILS", "").split(",") if a.strip()]
    return ([out] if out else []) + extra


def _subset(path: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = json.loads(Path(path).read_text(encoding="utf-8"))["executable"]
    return rows


# ---------------------------------------------------------------------------- held-out, prepare


def cmd_heldout(args: argparse.Namespace) -> int:
    from ril.agent.providers.holdout import draw_holdout

    rec = draw_holdout(_subset(args.subset), args.n, args.seed)
    _write_json(Path(args.out), rec)
    for r in rec["by_repository"]:
        log.info("%s: %d executable, %d held out", r["repo"], r["executable"], r["held_out"])
    return 0


def cmd_prepare(args: argparse.Namespace) -> int:
    from ril.agent.providers.contexts import issues_from_core_bench
    from ril.agent.providers.holdout import split
    from ril.agent.providers.pilot_run import load_items
    from ril.agent.providers.rq3_prompts import (
        check_prefix_identity,
        issue_agreement,
        issues_from_parquet,
        prepare_screened,
        pseudonymise_report,
        rejection_table,
        rows_from_records,
    )
    from ril.agent.providers.screen import load_allowed_digests

    executable = _subset(args.subset)
    held, conf = split(executable, json.loads(Path(args.heldout).read_text(encoding="utf-8")))
    ids = {str(r["instance_id"]) for r in executable}
    folder_issues = issues_from_core_bench(os.path.expanduser(args.raw))
    issues = issues_from_parquet(os.path.expanduser(args.issues_parquet), ids)
    agreement = issue_agreement(issues, folder_issues, ids)
    if agreement["different"]:
        log.error(
            "table and folder issue texts differ for %d instances", len(agreement["different"])
        )
        return 5
    rows, skipped = rows_from_records(
        os.path.expanduser(args.ctx_dir), issues, args.budget, args.arms, ids
    )
    out = Path(args.out_dir)
    n, rejected = prepare_screened(
        rows, out, load_allowed_digests(EMAIL_DIGESTS), _operator_emails()
    )
    items = load_items(out)
    prefix = check_prefix_identity(items)
    report = {
        "budget": args.budget,
        "arms": args.arms,
        "instances_in_subset": len(ids),
        "confirmatory": len(conf),
        "held_out": len(held),
        "prompts_written": n,
        "prompts_expected": len(ids) * len(args.arms),
        "issue_source": "problem_statement of the benchmark table",
        "issue_agreement": agreement,
        "skipped": skipped,
        "rejected": len(rejected),
        "rejection_table": rejection_table(rejected),
        "prefix_identity": prefix,
        "pseudonymisation": pseudonymise_report(items, args.budget, args.token_tolerance),
    }
    _write_json(out / "prepare_report.json", report)
    _write_json(out / "rejections.json", rejected)
    (out / "ids_heldout.txt").write_text("".join(i + "\n" for i in held), encoding="utf-8")
    (out / "ids_confirmatory.txt").write_text("".join(i + "\n" for i in conf), encoding="utf-8")
    log.info(
        "prompts %d of %d, rejected %d, skipped %d, prefix identical: %s",
        n,
        report["prompts_expected"],
        len(rejected),
        len(skipped),
        prefix["identical"],
    )
    return 0


# ---------------------------------------------------------------------------- run, grade


def _exec_wiring(args: argparse.Namespace, instance_ids: set[str], subset_path: str | None = None):  # type: ignore[no-untyped-def]
    from ril.agent.providers.cluster import executor_for, reader_factory
    from ril.evaluation.executor.runner import ExecConfig
    from ril.evaluation.executor.spec import load_specs

    specs = {
        s.instance_id: s for s in load_specs(Path(args.specs)) if s.instance_id in instance_ids
    }
    local = Path(args.local_mirrors) if args.local_mirrors else None

    def source(repo: str) -> str:
        if local is not None:
            mirror = local / (repo.replace("/", "__") + ".git")
            if mirror.exists():
                return str(mirror)
        return f"https://github.com/{repo}.git"

    configs = {
        policy: ExecConfig(
            work_root=Path(args.work_root),
            cache_root=Path(args.cache_root),
            repo_source=source,
            env_policy=policy,
        )
        for policy in ("latest", "era")
    }
    policy_of: dict[str, str] = {}
    if subset_path:
        policy_of = {
            str(r["instance_id"]): str(r.get("env_policy", "latest")) for r in _subset(subset_path)
        }
    executor = executor_for(specs, configs, policy_of)
    readers = reader_factory(specs, Path(args.mirror_dir), local)
    return executor, readers, configs["latest"].config_hash(), configs["era"].config_hash()


def _selected_items(args: argparse.Namespace) -> tuple[list[dict[str, Any]], set[str]]:
    from ril.agent.providers.pilot_run import load_items

    ids = set(Path(args.instances).read_text(encoding="utf-8").split())
    items = [
        r for r in load_items(args.items_dir) if r["arm"] == args.arm and r["instance_id"] in ids
    ]
    return items, ids


def cmd_run_or_grade(args: argparse.Namespace) -> int:
    from ril.agent.providers.calllog import CallLog
    from ril.agent.providers.driver import DriverConfig, LoggedReplies, drive
    from ril.agent.providers.pilot_run import RunConfig
    from ril.agent.providers.spend import GuardedClient, SpendGuard, load_prices, price_of

    items, ids = _selected_items(args)
    if not items:
        log.error("no prepared item matches arm %s and the instance list", args.arm)
        return 2
    prices = load_prices(PRICES_FILE)
    price = price_of(prices, args.model)
    run_cfg = RunConfig(
        model=args.model,
        seed=args.seed,
        temperature=0.0,
        runs=1,
        max_calls=getattr(args, "max_calls", None),
        wait_for_daily=getattr(args, "wait_for_daily", False),
        run_indices=(args.run_index,),
    )
    call_log = CallLog(Path(args.log_dir))
    live = args.cmd == "run"
    client: Any = None
    guard: SpendGuard | None = None
    day_of = None
    thinking = json.loads(args.thinking_config) if getattr(args, "thinking_config", None) else None
    if live:
        from ril.agent.providers.gemini import (
            ApiKeyError,
            GeminiClient,
            GeminiConfig,
            load_api_key,
        )
        from ril.agent.providers.limiter import PersistentLimiter, load_limits

        limits = load_limits(args.limits, model=args.model)
        try:
            key = load_api_key()
        except ApiKeyError as err:
            log.error("%s", err)
            return 2
        limiter = PersistentLimiter(limits, Path(args.log_dir) / "limiter.jsonl")
        inner = GeminiClient(
            GeminiConfig(
                model=args.model,
                temperature=0.0,
                seed=args.seed,
                max_output_tokens=args.max_output_tokens,
                thinking_config=thinking,
            ),
            key,
            limiter,
        )
        guard = SpendGuard(args.cap_usd, price, args.max_output_tokens)
        guard.add_logged(call_log.rows())
        client = GuardedClient(inner, guard)
        day_of = limiter.day_of
    source = LoggedReplies(call_log, run_cfg, client, day_of)
    executor, readers, hash_latest, hash_era = _exec_wiring(args, ids, args.subset)
    meta = {
        "arm": args.arm,
        "run_index": args.run_index,
        "instances": len(ids),
        "cap_usd": getattr(args, "cap_usd", None),
        "prices_as_of": price.as_of,
        "prices_verified": price.verified,
        "thinking_config": thinking if thinking is not None else "provider default (none sent)",
        "max_output_tokens": getattr(args, "max_output_tokens", None),
        "exec_config_hash_latest": hash_latest,
        "exec_config_hash_era": hash_era,
        "seed": args.seed,
    }
    cfg = DriverConfig(
        model=args.model,
        run_indices=(args.run_index,),
        mode="live" if live else "logged",
        workers=args.workers,
        meta=meta,
    )
    summary = drive(items, args.out_dir, source, executor, readers, cfg, price)
    from ril.agent.providers.spend import logged_cost

    meta_path = Path(args.out_dir) / "meta.json"
    stored = json.loads(meta_path.read_text(encoding="utf-8"))
    stored["realised_cost_usd"] = round(logged_cost(call_log.rows(), price), 6)
    stored["guard_spent_usd"] = round(guard.spent, 6) if guard else None
    _write_json(meta_path, stored)
    log.info(
        "rows written %d, skipped %d, not available %d, stopped: %s, errors %d",
        summary.written,
        summary.skipped,
        summary.not_available,
        summary.stopped,
        len(summary.errors),
    )
    for e in summary.errors:
        log.warning("%s", e)
    return 0


# ---------------------------------------------------------------------------- replay


def cmd_replay(args: argparse.Namespace) -> int:
    from ril.agent.providers.cluster import reader_factory
    from ril.agent.providers.driver import DriverConfig, StoredReplies, drive, latest_rows
    from ril.agent.providers.replay_variants import build_replay_set
    from ril.evaluation.executor.spec import load_specs
    from ril.evaluation.gold_edits import derive_edits

    draw = json.loads(Path(args.draw).read_text(encoding="utf-8"))
    ids = sorted(r["instance_id"] for r in draw["instances"])
    gold = {
        r["instance_id"]: r["patch"]
        for r in (
            json.loads(x) for x in Path(args.gold).read_text(encoding="utf-8").splitlines() if x
        )
        if r["instance_id"] in set(ids)
    }
    specs = {s.instance_id: s for s in load_specs(Path(args.specs)) if s.instance_id in set(ids)}
    local = Path(args.local_mirrors) if args.local_mirrors else None
    readers_of = reader_factory(specs, Path(args.mirror_dir), local)
    readers = {i: readers_of(i) for i in ids}
    edits = {}
    for i in ids:
        derived = derive_edits(gold[i], readers[i])
        if derived.limit:
            log.error("%s: derivation limit %s", i, derived.limit)
            return 3
        edits[i] = derived.edits
    items, replies = build_replay_set(ids, edits, readers)
    if args.prepared:
        from ril.agent.providers.pilot_run import load_items
        from ril.agent.providers.pseudonymise import quote_text

        maps: dict[str, Any] = {}
        for prepared in load_items(args.prepared):  # the first touched arm of each instance
            if "restore" in prepared:
                maps.setdefault(str(prepared["instance_id"]), prepared["restore"])
        missing = [i for i in ids if i not in maps]
        if missing:
            log.error("%d replay instances have no pseudonymised prompt", len(missing))
            return 4
        for it in items:
            mapping = maps[str(it["instance_id"])]
            key = (str(it["instance_id"]), str(it["arm"]), 0)
            replies[key] = quote_text(replies[key], mapping)
            it["restore"] = mapping
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    executor, _, hash_latest, hash_era = _exec_wiring(args, set(ids), args.subset)
    cfg = DriverConfig(
        model="replay",
        mode="replay",
        workers=args.workers,
        meta={"exec_config_hash_latest": hash_latest, "exec_config_hash_era": hash_era},
    )
    summary = drive(items, out, StoredReplies(replies), executor, readers_of, cfg)
    rows = latest_rows(out / "results.jsonl")
    table = []
    for it in items:
        r = rows.get((it["instance_id"], it["arm"], 0))
        table.append(
            {
                "instance_id": it["instance_id"],
                "arm": it["arm"],
                "expected": it["expected"],
                "observed": r["outcome"] if r else "no row",
                "match": bool(r and r["outcome"] == it["expected"]),
                "failure_stage": r["failure_stage"] if r else "",
                "f2p": r["f2p"] if r else "",
                "p2p": r["p2p"] if r else "",
                "exec_seconds": r["exec_seconds"] if r else "",
            }
        )
    _write_csv(out / "replay_table.csv", table)
    ok = sum(1 for t in table if t["match"])
    log.info("replay: %d of %d match, errors %d", ok, len(table), len(summary.errors))
    for e in summary.errors:
        log.warning("%s", e)
    return 0 if ok == len(table) else 1


# ---------------------------------------------------------------------------- pseudonymisation


def cmd_pseudonym_check(args: argparse.Namespace) -> int:
    """Round trips on the prepared prompts that the transform touched (D120); no model call."""
    import random

    from ril.agent.providers.patch_convert import git_reader
    from ril.agent.providers.pilot_run import load_items
    from ril.agent.providers.pseudonym_check import (
        excerpt_round_trip,
        gold_round_trip,
        summarise,
    )
    from ril.evaluation.executor.spec import load_specs
    from ril.evaluation.gold_edits import derive_edits
    from ril.evaluation.patch_validation import ensure_bare

    touched = [r for r in load_items(args.prepared_dir) if "restore" in r]
    ids = sorted({str(r["instance_id"]) for r in touched})
    specs = {s.instance_id: s for s in load_specs(Path(args.specs)) if s.instance_id in set(ids)}
    gold = {
        r["instance_id"]: r["patch"]
        for r in (
            json.loads(x) for x in Path(args.gold).read_text(encoding="utf-8").splitlines() if x
        )
        if r["instance_id"] in set(ids)
    }
    local = Path(args.local_mirrors) if args.local_mirrors else None
    scratch = Path(args.scratch)
    scratch.mkdir(parents=True, exist_ok=True)
    excerpt_rows: list[dict[str, Any]] = []
    gold_rows: list[dict[str, Any]] = []
    mirrors: dict[str, tuple[str, Any]] = {}
    overlapping: set[str] = set()
    for iid in ids:
        spec = specs[iid]
        sources = [f"https://github.com/{spec.repo}.git"]
        if local is not None and (local / (spec.repo.replace("/", "__") + ".git")).exists():
            sources.insert(0, str(local / (spec.repo.replace("/", "__") + ".git")))
        mirror = ensure_bare(spec.repo, spec.base_commit, Path(args.mirror_dir), sources)
        if mirror is None:
            gold_rows.append({"instance_id": iid, "arm": "", "outcome": "mirror_unavailable"})
            continue
        read = git_reader(str(mirror), spec.base_commit)
        mirrors[iid] = (str(mirror), read)
        derived = derive_edits(gold[iid], read)
        for it in (t for t in touched if t["instance_id"] == iid):
            for r in excerpt_round_trip(it["prompt"], it["restore"], read):
                excerpt_rows.append({"instance_id": iid, "arm": it["arm"], **r})
            g = gold_round_trip(
                gold[iid], it["restore"], read, str(mirror), spec.base_commit, str(scratch), derived
            )
            gold_rows.append({"instance_id": iid, "arm": it["arm"], **g})
            if g["overlap"]:
                overlapping.add(iid)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    _write_csv(out / "pseudonym_roundtrip_excerpt_lines.csv", excerpt_rows)
    _write_csv(out / "pseudonym_roundtrip_gold.csv", gold_rows)
    # the replay sample: touched instances whose gold-derived blocks hold a substitution first
    rng = random.Random(args.seed)
    rest = [i for i in ids if i not in overlapping and i in mirrors]
    rng.shuffle(rest)
    pick = (sorted(overlapping) + rest)[: args.sample]
    draw = {"instances": [{"instance_id": i} for i in sorted(pick)], "seed": args.seed}
    _write_json(out / "pseudonym_draw.json", draw)
    report = {
        "touched_prompts": len(touched),
        "touched_instances": len(ids),
        "excerpt_lines": len(excerpt_rows),
        "excerpt_outcomes": summarise(excerpt_rows),
        "excerpt_writes_original": summarise(
            [r for r in excerpt_rows if "writes_original" in r], "writes_original"
        ),
        "gold_outcomes": summarise(gold_rows),
        "gold_with_overlap": sum(1 for r in gold_rows if r.get("overlap")),
        "gold_instances_with_overlap": len(overlapping),
        "replay_sample": [r["instance_id"] for r in draw["instances"]],
        "replay_sample_overlapping": len(set(pick) & overlapping),
    }
    _write_json(out / "pseudonym_check_report.json", report)
    log.info("excerpt %s, gold %s", report["excerpt_outcomes"], report["gold_outcomes"])
    return 0


# ---------------------------------------------------------------------------- analyse etc.


def _read_results(dirs: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for d in dirs:
        path = Path(d) / "results.jsonl"
        rows += [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x]
    return rows


def cmd_analyse(args: argparse.Namespace) -> int:
    from ril.agent.providers.holdout import split
    from ril.analysis.rq3_results import Plan, analyse

    executable = _subset(args.subset)
    _, conf = split(executable, json.loads(Path(args.heldout).read_text(encoding="utf-8")))
    repo_of = {str(r["instance_id"]): str(r["repo"]) for r in executable}
    rows = _read_results(args.result_dirs)
    plan = Plan(
        arms=tuple(args.arms),
        primary=(args.primary[0], args.primary[1]),
        estimates=tuple(zip(args.estimate[::2], args.estimate[1::2], strict=True)),
        runs=tuple(args.runs),
        seed=args.seed,
    )
    tables = analyse(rows, conf, repo_of, plan)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for name, table in tables.items():
        _write_csv(out / f"rq3_results_{name}.csv", table)
    _write_json(Path(args.out), {"confirmatory": len(conf), "tables": sorted(tables)})
    log.info("analysed %d confirmatory instances, %d rows", len(conf), len(rows))
    return 0


def cmd_model_check(args: argparse.Namespace) -> int:
    from ril.agent.providers.driver import latest_rows
    from ril.agent.providers.model_choice import choose
    from ril.agent.providers.spend import load_prices

    prices = load_prices(PRICES_FILE)
    cands = []
    for spec in args.candidates:
        name, _, path = spec.partition("=")
        rows = list(latest_rows(Path(path) / "results.jsonl").values())
        cands.append(
            {
                "model": name,
                "resolved": sum(1 for r in rows if r["resolved"]),
                "n": len(rows),
                "cost_usd": sum(float(r["cost_usd"]) for r in rows),
                "output_price": prices[name].output_per_m,
                "unusable": sum(1 for r in rows if r["outcome"] == "unusable"),
                "apply_failed": sum(1 for r in rows if r["outcome"].startswith("apply_failed")),
                "exec_error": sum(1 for r in rows if r["outcome"].startswith("exec_error")),
                "thought_tokens": sum(int(r["thought_tokens"]) for r in rows),
            }
        )
    result = choose(cands)
    result["detail"] = cands
    _write_json(Path(args.out), result)
    log.info("chosen %s (floor met: %s)", result["chosen"], result["floor_met"])
    return 0


def cmd_power(args: argparse.Namespace) -> int:
    from ril.analysis import rq3_power, rq3_power_noise

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    placeholder = rq3_power.build_rows(ns=tuple(args.n))
    (out / "rq3_power_placeholder.csv").write_text(rq3_power.to_csv(placeholder))
    rows: list[dict[str, Any]] = []
    mdd: list[dict[str, Any]] = []
    for n in args.n:
        cells = rq3_power_noise.power_table(
            n=n, sims=args.sims, permutations=args.permutations, seed=args.seed
        )
        rows += rq3_power_noise.to_rows(cells, n)
        mdd += [{"n": n, **m} for m in rq3_power_noise.minimum_detectable(cells)]
    _write_csv(out / "rq3_power_run_noise.csv", rows)
    _write_csv(out / "rq3_power_run_noise_mdd.csv", mdd)
    _write_json(
        out / "rq3_power_run_noise_assumptions.json",
        {
            "n": list(args.n),
            "sims": args.sims,
            "permutations": args.permutations,
            "seed": args.seed,
            "same_reply": rq3_power_noise.SAME_REPLY,
            "assumptions": rq3_power_noise.ASSUMPTIONS,
        },
    )
    log.info("power: %d rows", len(rows))
    return 0


def cmd_cost(args: argparse.Namespace) -> int:
    from ril.agent.providers.spend import load_prices
    from ril.analysis import rq3_cost

    with open(args.pilot_cost, newline="", encoding="utf-8") as fh:
        row = next(r for r in csv.DictReader(fh) if r["arm"] == "all")
    tokens = rq3_cost.unit_tokens_from_pilot(row)
    prices = list(load_prices(PRICES_FILE).values())
    rows = rq3_cost.cost_table(tokens, prices)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    _write_csv(out / "rq3_cost_model.csv", rows)
    _write_json(out / "rq3_cost_graded_check_cap.json", rq3_cost.graded_check_cap(rows))
    log.info("cost table: %d rows", len(rows))
    return 0


def _exec_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--specs", required=True)
    p.add_argument("--work-root", required=True)
    p.add_argument("--cache-root", required=True)
    p.add_argument("--mirror-dir", required=True)
    p.add_argument("--local-mirrors")
    p.add_argument("--subset", required=True)
    p.add_argument("--workers", type=int, default=1)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("heldout")
    p.add_argument("subset")
    p.add_argument("out")
    p.add_argument("--n", type=int, default=50)
    p.set_defaults(fn=cmd_heldout)
    p = sub.add_parser("prepare")
    p.add_argument("ctx_dir")
    p.add_argument("out_dir")
    p.add_argument("--raw", required=True)
    p.add_argument("--issues-parquet", required=True)
    p.add_argument("--subset", required=True)
    p.add_argument("--heldout", required=True)
    p.add_argument("--budget", type=int, default=8000)
    p.add_argument("--arms", nargs="+", default=["bm25", "dense", "rrf"])
    p.add_argument("--token-tolerance", type=float, default=0.01)
    p.set_defaults(fn=cmd_prepare)
    p = sub.add_parser("pseudonym-check")
    p.add_argument("prepared_dir")
    p.add_argument("out_dir")
    p.add_argument("--specs", required=True)
    p.add_argument("--gold", required=True)
    p.add_argument("--subset", required=True)
    p.add_argument("--mirror-dir", required=True)
    p.add_argument("--local-mirrors")
    p.add_argument("--scratch", required=True)
    p.add_argument("--sample", type=int, default=10)
    p.set_defaults(fn=cmd_pseudonym_check)
    for name in ("run", "grade"):
        p = sub.add_parser(name)
        p.add_argument("items_dir")
        p.add_argument("log_dir")
        p.add_argument("out_dir")
        p.add_argument("--arm", required=True)
        p.add_argument("--run-index", type=int, required=True)
        p.add_argument("--instances", required=True)
        p.add_argument("--model", required=True)
        _exec_args(p)
        if name == "run":
            p.add_argument("--cap-usd", type=float, required=True)
            p.add_argument("--thinking-config")
            p.add_argument("--max-output-tokens", type=int, default=4096)
            p.add_argument("--max-calls", type=int)
            p.add_argument("--limits", default=str(LIMITS_FILE))
            p.add_argument("--wait-for-daily", action="store_true")
        p.set_defaults(fn=cmd_run_or_grade)
    p = sub.add_parser("replay")
    p.add_argument("specs")
    p.add_argument("gold")
    p.add_argument("draw")
    p.add_argument("out_dir")
    p.add_argument("--work-root", required=True)
    p.add_argument("--cache-root", required=True)
    p.add_argument("--mirror-dir", required=True)
    p.add_argument("--local-mirrors")
    p.add_argument("--subset", required=True)
    p.add_argument("--workers", type=int, default=1)
    p.add_argument(
        "--prepared",
        help="quote the replies in placeholder form with this prepared "
        "directory's mappings and restore them in the driver (D120)",
    )
    p.set_defaults(fn=cmd_replay)
    p = sub.add_parser("analyse")
    p.add_argument("out")
    p.add_argument("result_dirs", nargs="+")
    p.add_argument("--subset", required=True)
    p.add_argument("--heldout", required=True)
    p.add_argument("--arms", nargs="+", required=True)
    p.add_argument("--primary", nargs=2, required=True)
    p.add_argument("--estimate", nargs="*", default=[])
    p.add_argument("--runs", nargs="+", type=int, required=True)
    p.add_argument("--out-dir", required=True)
    p.set_defaults(fn=cmd_analyse)
    p = sub.add_parser("model-check")
    p.add_argument("out")
    p.add_argument("candidates", nargs="+")
    p.set_defaults(fn=cmd_model_check)
    p = sub.add_parser("power")
    p.add_argument("out_dir")
    p.add_argument("--n", type=int, nargs="+", default=[327])
    p.add_argument("--sims", type=int, default=400)
    p.add_argument("--permutations", type=int, default=2000)
    p.set_defaults(fn=cmd_power)
    p = sub.add_parser("cost")
    p.add_argument("out_dir")
    p.add_argument("--pilot-cost", default="results/rq3_pilot/analysis/rq3_pilot_cost.csv")
    p.set_defaults(fn=cmd_cost)
    for sp in sub.choices.values():
        sp.add_argument("--seed", type=int, default=0)
    args = ap.parse_args(argv)
    set_seed(args.seed)
    return int(args.fn(args))


if __name__ == "__main__":
    raise SystemExit(main())
