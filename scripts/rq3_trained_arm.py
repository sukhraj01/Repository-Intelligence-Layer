"""Trained arms of RQ3: plan, encode, contexts, check, analysis plan. Thin wrapper.

Usage (from the work directory; every stage prints JSON):
  rq3_trained_arm.py plan --retained-root DIR [--only RUN_ID ...] [--order protocol|primary_first]
                     [--cap 6.0] [--spent 0.377] [--cost-per-model 0.68]
      jobs and cost against Block 4; submits and encodes nothing; needs no id
  rq3_trained_arm.py encode --retained-root DIR --only RUN_ID --follows-dev-analysis ID
                     --dev-record PATH --out DIR --home DIR --work DIR [--device cuda]
      one retained model: encode the executable 377, write per-instance scores; refuses without
      the id of the finished dev analysis (D100, D127); GPU
      (--dry-run-dev --ids ID ...: the same path on the dev set, never a final set, no id needed)
  rq3_trained_arm.py contexts CONFIG SCORES_ROOT REPO_CACHE WORK OUT_ROOT [--models RUN_ID ...]
                     [--untrained] [--shard I K] [--only ID ...] [--members ID ...]
      contexts of the models whose scores exist (one parse per instance for all of them); CPU
  rq3_trained_arm.py verify-untrained CONFIG REPO_CACHE WORK STORED_CTX OUT [--n 30]
      rebuild stored instances with the untrained arms through the new path and compare bytes; CPU
  rq3_trained_arm.py analysis-plan SCORES_ROOT OUT.json --runs 0 1 2 [--models RUN_ID ...]
      arm list, primary pair and estimates for ``rq3_driver.py analyse --plan``

Implements ``docs/RQ3_PILOT.md`` ("Trained arms"). Logic lives in ``ril/evaluation/rq3_trained.py``,
``ril/assembly/rq3_trained_contexts.py`` and ``ril/agent/providers/trained_arms.py``.
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

log = get_logger("rq3_trained_arm")


def _print(obj: Any) -> None:
    sys.stdout.write(json.dumps(obj, indent=1, sort_keys=True, default=str) + "\n")


def cmd_plan(a: argparse.Namespace) -> int:
    from ril.evaluation import rq3_trained as rt

    models = rt.models_from_root(a.retained_root, a.only)
    _print(
        rt.plan_jobs(models, order=a.order, cap=a.cap, spent=a.spent, per_model=a.cost_per_model)
    )
    return 0


def cmd_encode(a: argparse.Namespace) -> int:
    from ril.evaluation import eval_sets
    from ril.evaluation import final_sets as fs
    from ril.evaluation import rq3_trained as rt

    folders = [m.folder for m in rt.models_from_root(a.retained_root, a.only)]
    if len(folders) != 1:
        sys.stderr.write("refused: one model per job (give exactly one --only RUN_ID)\n")
        return 3
    commit = os.environ.get("RIL_COMMIT", "")
    if not commit:
        sys.stderr.write("refused: RIL_COMMIT is not set\n")
        return 3
    try:
        rid = fs.retained_run_id(fs.read_manifest(folders[0]))
        if a.dry_run_dev:
            if not a.ids:
                sys.stderr.write("refused: a dry run names its instances (--ids)\n")
                return 3
            row = rt.encode_model(
                folders[0],
                ids=a.ids,
                out_root=a.out,
                home=a.home,
                work=a.work,
                follows="dry run on the dev set (no final set read)",
                record={"runs": [rid]},
                commit=commit,
                device=a.device,
                spec=eval_sets.get("dev"),
                dry_run=True,
            )
        else:
            record = fs.load_dev_analysis_record(a.dev_record, a.follows_dev_analysis, [rid])
            row = rt.encode_model(
                folders[0],
                ids=rt.read_subset_ids(a.subset),
                out_root=a.out,
                home=a.home,
                work=a.work,
                follows=str(a.follows_dev_analysis),
                record=record,
                commit=commit,
                device=a.device,
            )
    except (fs.FinalSetsRefused, rt.TrainedArmsRefused) as err:
        sys.stderr.write(f"refused: {err}\n")
        return 3
    _print(row)
    return 0


def _read_cfg(path: str) -> dict[str, Any]:
    out: dict[str, Any] = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return out


def _members(cfg: dict[str, Any], subset: str | None, ids: list[str] | None = None) -> list[str]:
    from ril.evaluation.rq3_trained import read_subset_ids

    return sorted(ids) if ids else read_subset_ids(subset or cfg["subset"])


def _model_targets(scores_root: str, run_ids: list[str] | None) -> list[Any]:
    from ril.assembly.rq3_trained_contexts import trained_target
    from ril.evaluation import rq3_trained as rt

    if run_ids is None:
        run_ids = sorted(
            n
            for n in os.listdir(scores_root)
            if os.path.isfile(os.path.join(scores_root, n, rt.DONE_NAME))
        )
    out = []
    for rid in run_ids:
        if not os.path.isfile(os.path.join(scores_root, rid, rt.DONE_NAME)):
            raise rt.TrainedArmsRefused(f"no finished scores for {rid!r} under {scores_root}")
        out.append(trained_target(rid, rt.arm_name(rid), rt.scores_dir(scores_root, rid)))
    return out


def cmd_contexts(a: argparse.Namespace) -> int:
    from ril.assembly import rq3_trained_contexts as tc

    cfg = _read_cfg(a.config)
    spec = tc.spec_from_config(cfg)
    targets = _model_targets(a.scores_root, a.models)
    if a.untrained:
        targets = [tc.untrained_target(cfg, spec), *targets]
    if not targets:
        sys.stderr.write("refused: no model with finished scores and no --untrained\n")
        return 3
    res = tc.run_build_targets(
        _members(cfg, a.subset, a.members),
        tc.groups_from_config(cfg),
        os.path.expanduser(a.repo_cache),
        a.work,
        a.out_root,
        targets,
        spec,
        shard=(a.shard[0], a.shard[1]),
        only=a.only,
    )
    os.makedirs(a.out_root, exist_ok=True)
    Path(a.out_root, f"build_trained_s{a.shard[0]}.json").write_text(
        json.dumps(res, indent=1, sort_keys=True), encoding="utf-8"
    )
    _print({"counts": res["counts"], "failures": len(res["failures"])})
    return 0 if not res["failures"] else 2


def cmd_verify_untrained(a: argparse.Namespace) -> int:
    from ril.assembly import rq3_trained_contexts as tc
    from ril.assembly.rq3_contexts import draw_instances

    cfg = _read_cfg(a.config)
    spec = tc.spec_from_config(cfg)
    target = tc.untrained_target(cfg, spec, "untrained_rebuilt")
    members = _members(cfg, a.subset)
    drawn = draw_instances(members, a.n, int(cfg["verify"]["seed"]))
    res = tc.run_build_targets(
        members,
        tc.groups_from_config(cfg),
        os.path.expanduser(a.repo_cache),
        a.work,
        a.out,
        [target],
        spec,
        only=drawn,
    )
    cmp = tc.compare_with_stored(a.stored_ctx, a.out, target, drawn)
    cmp["build"] = res["counts"]
    os.makedirs(a.out, exist_ok=True)
    Path(a.out, "untrained_equality.json").write_text(
        json.dumps(cmp, indent=1, sort_keys=True), encoding="utf-8"
    )
    _print({"n": cmp["n"], "differ": cmp["differ"], "build": res["counts"]})
    return 0 if cmp["differ"] == 0 and not res["failures"] else 2


def cmd_analysis_plan(a: argparse.Namespace) -> int:
    from ril.agent.providers import trained_arms as ta
    from ril.evaluation import rq3_trained as rt

    run_ids = a.models or sorted(
        n
        for n in os.listdir(a.scores_root)
        if os.path.isfile(os.path.join(a.scores_root, n, rt.DONE_NAME))
    )
    records = [
        json.loads(Path(a.scores_root, rid, rt.MODEL_RECORD).read_text(encoding="utf-8"))
        for rid in run_ids
    ]
    plan = ta.build_plan(ta.arms_from_records(records), a.runs, seed=a.seed)
    Path(a.out).write_text(json.dumps(plan, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    _print({"arms": plan["arms"], "primary": plan["primary"], "estimates": len(plan["estimates"])})
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("plan")
    p.add_argument("--retained-root", required=True)
    p.add_argument("--only", nargs="*")
    p.add_argument("--order", default="protocol", choices=["protocol", "primary_first"])
    p.add_argument("--cap", type=float, default=6.0)
    p.add_argument("--spent", type=float, default=0.377)
    p.add_argument("--cost-per-model", type=float, default=0.68)
    p.set_defaults(fn=cmd_plan)

    p = sub.add_parser("encode")
    p.add_argument("--retained-root", required=True)
    p.add_argument("--only", nargs="+", required=True)
    p.add_argument("--follows-dev-analysis")
    p.add_argument("--dev-record", default="")
    p.add_argument(
        "--dry-run-dev",
        action="store_true",
        help="prove the path on the dev set (never a final set) with the instances of --ids",
    )
    p.add_argument("--ids", nargs="*")
    p.add_argument("--out", required=True)
    p.add_argument("--home", required=True)
    p.add_argument("--work", required=True)
    p.add_argument("--device", default="cuda")
    p.add_argument("--subset", default="results/rq3_exec/executable_instances_v1.json")
    p.set_defaults(fn=cmd_encode)

    p = sub.add_parser("contexts")
    for name in ("config", "scores_root", "repo_cache", "work", "out_root"):
        p.add_argument(name)
    p.add_argument("--models", nargs="*")
    p.add_argument("--untrained", action="store_true")
    p.add_argument("--shard", nargs=2, type=int, default=[0, 1])
    p.add_argument("--only", nargs="*")
    p.add_argument("--subset")
    p.add_argument("--members", nargs="*", help="instance ids replacing the subset (dry runs)")
    p.set_defaults(fn=cmd_contexts)

    p = sub.add_parser("verify-untrained")
    for name in ("config", "repo_cache", "work", "stored_ctx", "out"):
        p.add_argument(name)
    p.add_argument("--n", type=int, default=30)
    p.add_argument("--subset")
    p.set_defaults(fn=cmd_verify_untrained)

    p = sub.add_parser("analysis-plan")
    p.add_argument("scores_root")
    p.add_argument("out")
    p.add_argument("--runs", nargs="+", type=int, required=True)
    p.add_argument("--models", nargs="*")
    p.set_defaults(fn=cmd_analysis_plan)

    for sp in sub.choices.values():
        sp.add_argument("--seed", type=int, default=0)
    args = ap.parse_args(argv)
    set_seed(args.seed)
    return int(args.fn(args))


if __name__ == "__main__":
    raise SystemExit(main())
