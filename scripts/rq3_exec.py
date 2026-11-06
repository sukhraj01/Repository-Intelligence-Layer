"""RQ3 executable instances: specifications, sharded gold-patch runs, the subset report.

Usage:
  rq3_exec.py make-specs --parquet FILE --swebench-src DIR --out SPECS.jsonl --gold GOLD.jsonl
  rq3_exec.py pilot-list SPECS.jsonl --n 25 [--seed N] --out IDS.txt
  rq3_exec.py run-shard SPECS.jsonl GOLD.jsonl RUN_DIR --shard I --count K
                [--ids IDS.txt] [--runs 2] [--workers 1] --work-root DIR --cache-root DIR
                [--local-mirrors DIR] [--seed N]
  rq3_exec.py report SPECS.jsonl --run-dir DIR [--run-dir DIR ...] --out-dir DIR [--seed N]
  rq3_exec.py summary SPECS.jsonl --subset FILE --inventory FILE --run-dir DIR --out-dir DIR

Implements D106 (docs/RQ3_PILOT.md). Thin wrapper: the logic is in ril/evaluation/executor/.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ril.evaluation.executor import jobs, subset, swebench_specs  # noqa: E402
from ril.evaluation.executor.runner import ExecConfig  # noqa: E402
from ril.evaluation.executor.spec import InstanceSpec, load_specs, write_specs  # noqa: E402
from ril.util.log import get_logger  # noqa: E402
from ril.util.seed import set_seed  # noqa: E402

log = get_logger("rq3_exec")


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cmd_make_specs(args: argparse.Namespace) -> int:
    import pyarrow.parquet as pq

    constants = swebench_specs.load_constants(Path(args.swebench_src))
    rows = pq.read_table(args.parquet).to_pylist()
    specs, gold = swebench_specs.build_all(rows, constants)
    n = write_specs(Path(args.out), specs)
    with Path(args.gold).open("w") as out:
        for iid in sorted(gold):
            out.write(json.dumps({"instance_id": iid, "patch": gold[iid]}) + "\n")
    log.info("wrote %d specifications; parquet sha256 %s", n, _digest(Path(args.parquet))[:16])
    return 0


def cmd_pilot_list(args: argparse.Namespace) -> int:
    """Seeded draw across every repository: two per repository (one if it has one), then the
    largest repositories' extras in order until ``--n``."""
    specs = load_specs(Path(args.specs))
    rng = random.Random(args.seed)
    by_repo: dict[str, list[InstanceSpec]] = {}
    for s in specs:
        by_repo.setdefault(s.repo, []).append(s)
    picked: list[str] = []
    rest: list[tuple[str, InstanceSpec]] = []
    for repo in sorted(by_repo):
        pool = sorted(by_repo[repo], key=lambda s: s.instance_id)
        rng.shuffle(pool)
        picked += [s.instance_id for s in pool[:2]]
        rest += [(repo, s) for s in pool[2:]]
    rest.sort(key=lambda rs: (-len(by_repo[rs[0]]), rs[1].instance_id))
    rng.shuffle(rest)
    rest.sort(key=lambda rs: -len(by_repo[rs[0]]))
    for _, s in rest:
        if len(picked) >= args.n:
            break
        picked.append(s.instance_id)
    Path(args.out).write_text("\n".join(picked[: args.n]) + "\n")
    return 0


def _repo_source(local_mirrors: str | None):  # type: ignore[no-untyped-def]
    def source(repo: str) -> str:
        if local_mirrors:
            local = Path(local_mirrors) / (repo.replace("/", "__") + ".git")
            if local.exists():
                return str(local)
        return f"https://github.com/{repo}.git"

    return source


def _clean_local(*dirs: Path) -> None:
    """Remove this job's own node-local caches at exit; refuses anything outside the temp area."""
    import shutil
    import tempfile

    tmp = Path(tempfile.gettempdir()).resolve()
    for d in dirs:
        real = d.resolve()
        if tmp in real.parents and real != tmp:
            shutil.rmtree(real, ignore_errors=True)
        else:
            log.warning("not removing %s: outside %s", real, tmp)


def cmd_run_shard(args: argparse.Namespace) -> int:
    specs = load_specs(Path(args.specs))
    if args.ids:
        keep = set(Path(args.ids).read_text().split())
        specs = [s for s in specs if s.instance_id in keep]
    gold = {
        r["instance_id"]: r["patch"]
        for r in (json.loads(x) for x in Path(args.gold).read_text().splitlines() if x)
    }
    config = ExecConfig(
        work_root=Path(args.work_root),
        cache_root=Path(args.cache_root),
        repo_source=_repo_source(args.local_mirrors),
    )
    mine = jobs.shard_of(specs, args.shard, args.count)
    stats = jobs.run_shard(
        mine,
        gold,
        Path(args.run_dir),
        config,
        runs=args.runs,
        workers=args.workers,
        commit=args.commit,
    )
    log.info(
        "shard %d/%d: %d run rows written, %d instances skipped",
        args.shard,
        args.count,
        stats.done,
        stats.skipped,
    )
    return jobs.EXIT_DISK_FULL if stats.stopped_disk else 0


def cmd_report(args: argparse.Namespace) -> int:
    specs = load_specs(Path(args.specs))
    paths = [p / jobs.RESULT_FILE for d in args.run_dir for p in sorted(Path(d).glob("shard_*"))]
    paths += [
        Path(d) / jobs.RESULT_FILE for d in args.run_dir if (Path(d) / jobs.RESULT_FILE).exists()
    ]
    rows = subset.read_rows(p for p in paths if p.exists())
    metas = [
        json.loads(p.read_text())
        for d in args.run_dir
        for p in Path(d).glob("**/" + jobs.META_FILE)
    ]
    if args.only_ids:
        keep = set(Path(args.only_ids).read_text().split())
        specs = [s for s in specs if s.instance_id in keep]
    doc = subset.build_subset(
        specs,
        rows,
        run_id=args.run_id,
        config_hash=",".join(sorted({m["config_hash"] for m in metas})),
        commit=",".join(sorted({m["commit"] for m in metas})),
        spec_digest=_digest(Path(args.specs))[:16],
    )
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / args.name).write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n")
    table = subset.repo_table(doc, specs)
    (out / "repo_table.csv").write_text(subset.table_csv(table))
    log.info("%s", json.dumps(doc["counts"], sort_keys=True))
    return 0


def cmd_summary(args: argparse.Namespace) -> int:
    """Subset against the 500, cost per instance, coverage, build estimate and power at N."""
    from ril.analysis import rq3_power
    from ril.evaluation.executor import coverage, summary

    specs = load_specs(Path(args.specs))
    doc = json.loads(Path(args.subset).read_text())
    inv = json.loads(Path(args.inventory).read_text())
    members = doc["executable"]
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    shift = summary.distribution_shift(specs, members, inv["l2"], inv["l3"])
    (out / "subset_vs_500.csv").write_text(subset.table_csv(shift))
    rows = subset.read_rows(
        p for d in args.run_dir for p in sorted(Path(d).glob("**/" + jobs.RESULT_FILE))
    )
    (out / "cost_per_instance.json").write_text(
        json.dumps(summary.cost_summary(rows, [m["instance_id"] for m in members]), indent=1) + "\n"
    )
    insts = [{"instance_id": s.instance_id, "repo": s.repo} for s in specs]
    cov = coverage.coverage_rows(members, inv["l2"], inv["l3"], inv["unit_records"], insts)
    (out / "coverage_table.csv").write_text(subset.table_csv(cov))
    n = len(members)
    pw = rq3_power.build_rows((n,), rq3_power.DISCORDANCES)
    (out / "power_at_n.csv").write_text(rq3_power.to_csv(pw))
    log.info("subset %d; power rows %d", n, len(pw))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--seed", type=int, default=0)
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("make-specs")
    a.add_argument("--parquet", required=True)
    a.add_argument("--swebench-src", required=True)
    a.add_argument("--out", required=True)
    a.add_argument("--gold", required=True)
    b = sub.add_parser("pilot-list")
    b.add_argument("specs")
    b.add_argument("--n", type=int, default=25)
    b.add_argument("--out", required=True)
    c = sub.add_parser("run-shard")
    c.add_argument("specs")
    c.add_argument("gold")
    c.add_argument("run_dir")
    c.add_argument("--shard", type=int, required=True)
    c.add_argument("--count", type=int, required=True)
    c.add_argument("--ids")
    c.add_argument("--runs", type=int, default=2)
    c.add_argument("--workers", type=int, default=1)
    c.add_argument("--work-root", required=True)
    c.add_argument("--cache-root", required=True)
    c.add_argument("--local-mirrors")
    c.add_argument("--commit", default="")
    c.add_argument("--clean-cache", action="store_true")
    d = sub.add_parser("report")
    d.add_argument("specs")
    d.add_argument("--run-dir", action="append", required=True)
    d.add_argument("--out-dir", required=True)
    d.add_argument("--run-id", default="")
    d.add_argument("--name", default="executable_instances_v1.json")
    d.add_argument("--only-ids")
    e = sub.add_parser("summary")
    e.add_argument("specs")
    e.add_argument("--subset", required=True)
    e.add_argument("--inventory", required=True)
    e.add_argument("--run-dir", action="append", required=True)
    e.add_argument("--out-dir", required=True)
    args = p.parse_args(argv)
    set_seed(args.seed)
    return {
        "make-specs": cmd_make_specs,
        "pilot-list": cmd_pilot_list,
        "run-shard": cmd_run_shard,
        "report": cmd_report,
        "summary": cmd_summary,
    }[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
