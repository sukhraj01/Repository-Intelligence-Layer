"""Oracle calibration arm of RQ3 (E-RQ3-ORACLE, D168): gold files, contexts, leak check, analysis.

Usage (from the work directory):
  rq3_oracle_arm.py gold-files PARQUET SUBSET OUT.json
      paths of the files the gold patch modifies, per instance of the subset (paths only, no
      patch text is written); reads the benchmark table's patch column once
  rq3_oracle_arm.py contexts CONFIG REPO_CACHE WORK OUT_DIR --gold OUT.json [--shard I K]
      oracle contexts (gold-file units first, then the untrained rrf ranking) for the subset; CPU
  rq3_oracle_arm.py leak-check PREPARED_DIR PARQUET REPORT.json [--expect-arm ARM]
      the leakage check on every prepared prompt; exit code 6 on any finding (the build fails)
  rq3_oracle_arm.py context-files CTX_DIR ARM OUT.json [--budget N]
      the file list of each instance's context of an arm (for the retrieval view)
  rq3_oracle_arm.py analyse --oracle DIR --rrf DIR --raw DIR ... --gold G.json
                       --files NAME=F.json ...
      exploratory contrasts and views from stored rows; no call

Implements ``docs/experiments/B.md`` E-RQ3-ORACLE. Logic lives in
``ril/assembly/rq3_oracle_contexts.py``, ``ril/agent/providers/oracle_leak.py`` and
``ril/analysis/rq3_oracle.py``.
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

import yaml  # noqa: E402

from ril.util.log import get_logger  # noqa: E402
from ril.util.seed import set_seed  # noqa: E402

log = get_logger("rq3_oracle_arm")
LEAK_EXIT = 6


def _print(obj: Any) -> None:
    sys.stdout.write(json.dumps(obj, indent=1, sort_keys=True, default=str) + "\n")


def _write_json(path: str | Path, obj: Any) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    tmp = f"{path}.{os.getpid()}.tmp"
    Path(tmp).write_text(json.dumps(obj, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _subset_ids(path: str) -> list[str]:
    from ril.evaluation.rq3_trained import read_subset_ids

    return sorted(read_subset_ids(path))


def _table(parquet: str, ids: set[str]) -> list[dict[str, Any]]:
    import pyarrow.parquet as pq

    cols = [
        "instance_id",
        "repo",
        "base_commit",
        "patch",
        "test_patch",
        "FAIL_TO_PASS",
        "PASS_TO_PASS",
    ]
    rows = pq.read_table(parquet, columns=cols).to_pylist()
    return [r for r in rows if str(r["instance_id"]) in ids]


def cmd_gold_files(a: argparse.Namespace) -> int:
    from ril.assembly.rq3_oracle_contexts import (
        GOLD_FILES_VERSION,
        gold_files_from_patch,
        gold_files_sha256,
    )

    ids = _subset_ids(a.subset)
    rows = {str(r["instance_id"]): r for r in _table(os.path.expanduser(a.parquet), set(ids))}
    missing = [i for i in ids if i not in rows]
    if missing:
        sys.stderr.write(f"refused: {len(missing)} instances have no patch in the table\n")
        return 3
    out: dict[str, Any] = {}
    for iid in ids:
        modified, created = gold_files_from_patch(str(rows[iid]["patch"]))
        out[iid] = {"modified": modified, "created": created}
    record = {
        "version": GOLD_FILES_VERSION,
        "source": "diff headers of the patch column of the benchmark table (paths only)",
        "instances": out,
        "sha256": gold_files_sha256({k: v["modified"] for k, v in out.items()}),
        "n_instances": len(out),
        "n_without_modified_file": sum(1 for v in out.values() if not v["modified"]),
        "n_with_created_file": sum(1 for v in out.values() if v["created"]),
    }
    _write_json(a.out, record)
    _print({k: v for k, v in record.items() if k != "instances"})
    return 0


def _read_gold(path: str) -> dict[str, dict[str, Any]]:
    rec = json.loads(Path(path).read_text(encoding="utf-8"))
    out: dict[str, dict[str, Any]] = rec["instances"]
    return out


def cmd_contexts(a: argparse.Namespace) -> int:
    from ril.assembly import rq3_trained_contexts as tc
    from ril.assembly.rq3_oracle_contexts import OracleInputs, run_build_oracle

    cfg: dict[str, Any] = yaml.safe_load(Path(a.config).read_text(encoding="utf-8"))
    spec = tc.spec_from_config(cfg)
    gold = _read_gold(a.gold)
    members = _subset_ids(a.subset or cfg["subset"])
    res = run_build_oracle(
        members,
        gold,
        OracleInputs(
            tuple(tc.groups_from_config(cfg)),
            os.path.expanduser(a.repo_cache),
            a.work,
            a.out_dir,
        ),
        spec,
        shard=(a.shard[0], a.shard[1]),
        only=a.only,
    )
    os.makedirs(a.out_dir, exist_ok=True)
    _write_json(Path(a.out_dir) / f"build_oracle_s{a.shard[0]}.json", res)
    _print({"counts": res["counts"], "failures": len(res["failures"])})
    return 0 if not res["failures"] else 2


def _base_text_factory(repo_cache: str, rows: dict[str, dict[str, Any]]) -> Any:
    """``instance -> (file -> text at the base commit or None)``, read with ``git show``."""
    import subprocess

    def for_instance(iid: str) -> Any:
        r = rows[iid]
        git_dir = os.path.join(repo_cache, str(r["repo"]).replace("/", "__") + ".git")
        base = str(r["base_commit"])
        memo: dict[str, str | None] = {}

        def text(path: str) -> str | None:
            if path not in memo:
                out = subprocess.run(
                    ["git", "--git-dir", git_dir, "show", f"{base}:{path}"],
                    capture_output=True,
                    check=False,
                )
                memo[path] = out.stdout.decode("utf-8", "replace") if out.returncode == 0 else None
            return memo[path]

        return text

    return for_instance


def cmd_leak_check(a: argparse.Namespace) -> int:
    from ril.agent.providers.oracle_leak import (
        GoldTexts,
        check_items,
        parse_test_list,
        report_json,
    )
    from ril.agent.providers.pilot_run import load_items

    items = load_items(a.prepared_dir)
    if a.expect_arm:
        wrong = [i for i in items if str(i["arm"]) != a.expect_arm]
        if wrong:
            sys.stderr.write(f"refused: {len(wrong)} items are not arm {a.expect_arm}\n")
            return 3
    ids = {str(i["instance_id"]) for i in items}
    table = _table(os.path.expanduser(a.parquet), ids)
    rows_by_id = {str(r["instance_id"]): r for r in table}
    gold = {
        str(r["instance_id"]): GoldTexts(
            str(r["patch"]),
            str(r["test_patch"]),
            tuple(parse_test_list(r["FAIL_TO_PASS"]) + parse_test_list(r["PASS_TO_PASS"])),
        )
        for r in table
    }
    base_text = None
    if a.repo_cache:
        base_text = _base_text_factory(a.repo_cache, rows_by_id)
    report = check_items(items, gold, base_text)
    Path(a.report).parent.mkdir(parents=True, exist_ok=True)
    Path(a.report).write_text(report_json(report), encoding="utf-8")
    _print({k: v for k, v in report.items() if k != "rows"})
    if not report["clean"]:
        sys.stderr.write("leakage check failed: see the report (digests only)\n")
        return LEAK_EXIT
    return 0


def cmd_context_files(a: argparse.Namespace) -> int:
    from ril.assembly.rq3_contexts import decode_record

    out: dict[str, list[str]] = {}
    inst_dir = Path(a.ctx_dir) / "instances"
    for name in sorted(os.listdir(inst_dir)):
        if not name.endswith(".gz"):
            continue
        rec = decode_record((inst_dir / name).read_bytes())
        ctx = rec["contexts"].get(f"{a.arm}|{a.budget}")
        if ctx is None:
            continue
        out[str(rec["instance"])] = sorted({e["file"] for e in ctx["manifest"]["entries"]})
    _write_json(a.out, {"arm": a.arm, "budget": a.budget, "files": out})
    _print({"instances": len(out)})
    return 0


def _read_rows(dirs: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for d in dirs:
        p = Path(d) / "results.jsonl"
        rows += [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x]
    return rows


def _csv(path: Path, rows: list[dict[str, Any]]) -> None:
    keys: list[str] = []
    for r in rows:
        for k in r:
            if k not in keys:
                keys.append(k)
    with path.open("w", newline="", encoding="utf-8") as h:
        w = csv.DictWriter(h, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow({k: (json.dumps(v) if isinstance(v, list) else v) for k, v in r.items()})


def cmd_analyse(a: argparse.Namespace) -> int:
    from ril.agent.providers.holdout import split
    from ril.analysis import rq3_oracle as ro
    from ril.analysis.rq3_agent_summary import arm_summary

    executable = json.loads(Path(a.subset).read_text(encoding="utf-8"))["executable"]
    _, conf = split(executable, json.loads(Path(a.heldout).read_text(encoding="utf-8")))
    conf = sorted(conf)
    named = {"oracle": a.oracle, "rrf": a.rrf, "raw": a.raw, "filter": a.filter_, "sub": a.sub}
    arm_dirs = {k: v for k, v in named.items() if v}
    rows: list[dict[str, Any]] = []
    arm_names: dict[str, str] = {}
    runs: dict[str, tuple[int, ...]] = {}
    for label, d in arm_dirs.items():
        part = _read_rows([os.path.join(d, "results")])
        names = {str(r["arm"]) for r in part}
        if len(names) != 1:
            raise SystemExit(f"{label}: expected one arm name in {d}, got {sorted(names)}")
        arm_names[label] = names.pop()
        # labels are the arm names in the analysis, so tables are readable
        for r in part:
            r["arm"] = label
        rows += part
        runs[label] = tuple(sorted({int(r["run"]) for r in part}))
    if runs["oracle"] != (0, 1):
        raise SystemExit(f"oracle repeats are {runs['oracle']}, expected (0, 1)")
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    tables: dict[str, list[dict[str, Any]]] = {
        "arms": ro.arm_rows(rows, conf, runs, "exact", a.seed_analysis)
        + ro.arm_rows(rows, conf, runs, "tolerant", a.seed_analysis),
        "contrasts": ro.contrasts(rows, conf, runs, seed=a.seed_analysis),
    }
    gold = {k: v["modified"] for k, v in _read_gold(a.gold).items()}
    files: dict[str, dict[str, list[str]]] = {}
    for spec in a.files or []:
        name, _, path = spec.partition("=")
        files[name] = json.loads(Path(path).read_text(encoding="utf-8"))["files"]
    miss = ro.gold_miss(files, gold, conf)
    tables["gold_miss"] = [{"instance_id": i, **miss[i]} for i in conf]
    sets = {}
    if {"rrf", "raw"} <= set(files):
        sets["rrf_and_raw_missed_all_gold_files"] = ["rrf", "raw"]
    if {"rrf", "raw", "filter", "sub"} <= set(files):
        sets["all_four_registered_arms_missed_all_gold_files"] = ["rrf", "raw", "filter", "sub"]
    tables["retrieval_vs_reasoning"] = ro.retrieval_vs_reasoning(
        rows, conf, runs, miss, sets, seed=a.seed_analysis
    )
    summaries = {}
    for label, d in arm_dirs.items():
        summaries[label] = arm_summary(
            label,
            os.path.join(d, "results", "results.jsonl"),
            os.path.join(d, "log", "calls.jsonl"),
            runs[label],
        )
    if a.mdd:
        with open(a.mdd, encoding="utf-8") as h:
            tables["minimum_detectable"] = ro.mdd_rows(list(csv.DictReader(h)))
    for name, t in tables.items():
        _csv(out / f"rq3_oracle_{name}.csv", t)
    _write_json(
        out / "oracle_summary.json",
        {
            "confirmatory": len(conf),
            "arms": summaries,
            "arm_names_in_rows": arm_names,
            "runs": runs,
        },
    )
    _print({"confirmatory": len(conf), "tables": sorted(tables)})
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("gold-files")
    p.add_argument("parquet")
    p.add_argument("subset")
    p.add_argument("out")
    p.set_defaults(fn=cmd_gold_files)

    p = sub.add_parser("contexts")
    for name in ("config", "repo_cache", "work", "out_dir"):
        p.add_argument(name)
    p.add_argument("--gold", required=True)
    p.add_argument("--shard", nargs=2, type=int, default=[0, 1])
    p.add_argument("--only", nargs="*")
    p.add_argument("--subset")
    p.set_defaults(fn=cmd_contexts)

    p = sub.add_parser("leak-check")
    p.add_argument("prepared_dir")
    p.add_argument("parquet")
    p.add_argument("report")
    p.add_argument("--expect-arm")
    p.add_argument("--repo-cache")
    p.set_defaults(fn=cmd_leak_check)

    p = sub.add_parser("context-files")
    p.add_argument("ctx_dir")
    p.add_argument("arm")
    p.add_argument("out")
    p.add_argument("--budget", type=int, default=8000)
    p.set_defaults(fn=cmd_context_files)

    p = sub.add_parser("analyse")
    p.add_argument("--oracle", required=True, help="result dir of the oracle arm (results/, log/)")
    p.add_argument("--rrf", required=True)
    p.add_argument("--raw", required=True)
    p.add_argument("--filter", dest="filter_")
    p.add_argument("--sub")
    p.add_argument("--gold", required=True)
    p.add_argument("--files", nargs="*", help="NAME=file.json from context-files (rrf, raw, ...)")
    p.add_argument("--subset", default="results/rq3_exec/executable_instances_v1.json")
    p.add_argument("--heldout", default="results/rq3_driver/heldout_v1.json")
    p.add_argument("--mdd", default="results/rq3_driver/rq3_power_measured_agreement_mdd.csv")
    p.add_argument("--out-dir", required=True)
    p.add_argument("--seed-analysis", type=int, default=0)
    p.set_defaults(fn=cmd_analyse)

    for sp in sub.choices.values():
        sp.add_argument("--seed", type=int, default=0)
    args = ap.parse_args(argv)
    set_seed(args.seed)
    return int(args.fn(args))


if __name__ == "__main__":
    raise SystemExit(main())
