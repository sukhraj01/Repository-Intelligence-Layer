"""Retrieved contexts of the executable subset of Verified. Thin wrapper.

Usage (cluster, from the work directory):
  rq3_contexts.py build CONFIG REPO_CACHE WORK OUT [--shard I K] [--only ID ...]
  rq3_contexts.py verify CONFIG REPO_CACHE WORK OUT OUT2
  rq3_contexts.py tables OUT TABLE_PREFIX
  rq3_contexts.py archive OUT ARCHIVE.tar.gz --budget 8000
Implements ``docs/RQ3_PILOT.md`` (D108). Logic lives in ``ril/assembly/rq3_contexts.py``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import yaml  # noqa: E402

from ril.util.log import get_logger  # noqa: E402
from ril.util.seed import set_seed  # noqa: E402


def _setup(cfg_path: str) -> tuple[Any, Any, Any, list[str]]:
    from ril.assembly.rq3_contexts import ContextSpec, InputGroup, default_arms

    cfg = yaml.safe_load(Path(cfg_path).read_text(encoding="utf-8"))
    a = cfg["assembly"]
    if a.get("tokenizer", "approx") != "approx":
        raise ValueError("the contexts are counted with the approximate tokenizer")
    spec = ContextSpec(
        budgets=tuple(int(b) for b in a["budgets"]),
        max_unit_tokens=int(a["max_unit_tokens"]),
        candidates=int(a["candidates"]),
        rrf_k=int(a["rrf_k"]),
        query_level=str(a["query_level"]),
    )
    arms = tuple(x for x in default_arms(spec.rrf_k, cfg["dense_key"]) if x.name in cfg["arms"])
    groups = tuple(
        InputGroup(os.path.expanduser(g["cache_dir"]), os.path.expanduser(g["dense_dir"]))
        for g in cfg["groups"]
    )
    subset = json.loads(Path(cfg["subset"]).read_text(encoding="utf-8"))
    members = sorted(str(m["instance_id"]) for m in subset["executable"])
    return cfg, (spec, arms), groups, members


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("stage", choices=["build", "verify", "tables", "archive"])
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--shard", nargs=2, type=int, default=[0, 1])
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--budget", type=int, default=8000)
    ap.add_argument("--subset", default="results/rq3_exec/executable_instances_v1.json")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    set_seed(args.seed)
    log = get_logger("rq3_contexts")
    from ril.assembly import rq3_contexts as rc

    if args.stage in ("build", "verify"):
        cfg_path, repo_cache, work, out = args.paths[:4]
        cfg, (spec, arms), groups, members = _setup(cfg_path)
        repo_cache = os.path.expanduser(repo_cache)
        if args.stage == "build":
            res = rc.run_build(
                members, groups, repo_cache, work, out, spec, arms,
                shard=(args.shard[0], args.shard[1]), only=args.only,
            )  # fmt: skip
            Path(out, f"build_s{args.shard[0]}.json").write_text(
                json.dumps(res, indent=1, sort_keys=True), encoding="utf-8"
            )
            log.info("%s failures %d", res["counts"], len(res["failures"]))
            return 0 if not res["failures"] else 2
        out2 = args.paths[4]
        drawn = rc.draw_instances(
            members, int(cfg["verify"]["instances"]), int(cfg["verify"]["seed"])
        )
        res = rc.run_build(members, groups, repo_cache, work, out2, spec, arms, only=drawn)
        cmp = rc.compare_dirs(out, out2, drawn)
        cmp["second_build"] = res["counts"]
        Path(out2, "determinism.json").write_text(
            json.dumps(cmp, indent=1, sort_keys=True), encoding="utf-8"
        )
        log.info("drawn %d, differ %d", cmp["n"], cmp["differ"])
        return 0 if cmp["differ"] == 0 and not res["failures"] else 2
    from ril.analysis import rq3_contexts_tables as rt
    from ril.analysis.x2_tables import write_csv

    if args.stage == "tables":
        out, prefix = args.paths[:2]
        records = rt.load_records(out)
        write_csv(f"{prefix}_coverage.csv", rt.coverage_summary(records))
        write_csv(f"{prefix}_size.csv", rt.size_summary(records))
        write_csv(f"{prefix}_contexts.csv", rt.context_rows(records))
        write_csv(f"{prefix}_manifest.csv", rt.file_manifest(out))
        log.info("%d instance records", len(records))
        return 0
    out, archive = args.paths[:2]
    res = rc.write_archive(out, archive, args.budget)
    log.info("%s", res)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
