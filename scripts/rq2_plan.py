"""Plan-only launcher of the RQ2 final experiment: no GPU, no model, no torch.

  plan    [--seeds S ...] [--filter-size N] [--updates N] [--pool-examples N]
          [--family-accounts mined=C injected=A]
          [--queue-wait-hours H] [--drop-conditional] [--mined-template P] [--injected-template P]
          render the 45 configurations in memory, check the held-identical block and the registered
          design, hash them, account the budget on both bases and both evaluation scopes, check
          distinct examples, print the job graph and its critical path
  render  --out DIR [--filter-size N] [--updates N] [--seeds S ...]
          write the configurations (``<run_id>.yaml``); without --filter-size the size-matched
          subsample keeps the symbolic token (committed form), with it the size is resolved;
          --updates N sets the mined family's update count (D140), the injected family keeps 100
  resolve --work DIR [--out DIR] [--seeds S ...]
          the launch step (D140): read the prepared store's summary, compute F and
          N = min(100, F // 32), write DIR/rq2_updates.json and the resolved configurations and
          their hashes (default OUT = DIR/configs_resolved). Nothing is submitted
  eval    --set NAME=E1_CONFIG:PREP:ROLES:E3_CACHE[:gz] [...]  (gz: unit texts stored gzipped)
          list the stores and the cost of the evaluation sets a checkpoint is scored on

Logic in ``ril/training/rq2_plan.py`` and ``ril/evaluation/eval_plan.py``. Every stage prints JSON.
Implements ``docs/RQ2_LAUNCH_PLAN.md``.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

TEMPLATES = {
    "mined": "configs/experiments/rq2_final/_template_mined.yaml",
    "injected": "configs/experiments/rq2_final/_template_injected.yaml",
}


def _templates(a: argparse.Namespace) -> dict[str, dict[str, object]]:
    import yaml

    return {
        "mined": yaml.safe_load(Path(a.mined_template).read_text(encoding="utf-8")),
        "injected": yaml.safe_load(Path(a.injected_template).read_text(encoding="utf-8")),
    }


def cmd_plan(a: argparse.Namespace) -> int:
    from ril.training import rq2_plan as rp

    runs = rp.plan_runs(a.seeds, mined_n=a.updates)
    if a.drop_conditional:
        runs = [r for r in runs if r.cell.conditional is None]
    rows = rp.validate_runs(runs, _templates(a), filter_size=a.filter_size)
    family_accounts = dict(kv.split("=", 1) for kv in a.family_accounts) or None
    jobs = rp.job_graph(runs, family_accounts=family_accounts)
    out = {
        "version": rp.PLAN_VERSION,
        "seeds": a.seeds,
        "cell_table_sha256": rp.cell_table_digest(),
        "reused_noise_seeds": rp.fresh_noise_check(runs),
        "runs": rows,
        "budget": {
            f"{b}_{s}": rp.budget(runs, basis=b, scope=s)
            for b in ("measured", "protocol")
            for s in ("rulings", "option_e")
        },
        "unique_examples": (
            rp.unique_example_check(
                rp.PRIMARY_UPDATES * rp.BATCH_SIZE, a.pool_examples, a.filter_size
            )
            if a.pool_examples
            else None
        ),
        "jobs": [dataclasses.asdict(j) for j in jobs],
        "critical_path_hours": round(rp.critical_path_hours(jobs, a.queue_wait_hours), 1),
    }
    sys.stdout.write(json.dumps(out, indent=1, sort_keys=True) + "\n")
    return 0


def cmd_render(a: argparse.Namespace) -> int:
    from ril.training import rq2_plan as rp

    rows = rp.write_configs(
        rp.plan_runs(a.seeds, mined_n=a.updates), _templates(a), a.out, filter_size=a.filter_size
    )
    sys.stdout.write(json.dumps({"written": len(rows), "runs": rows}, indent=1) + "\n")
    return 0


def cmd_resolve(a: argparse.Namespace) -> int:
    from ril.bench import rq2_launch as rl
    from ril.training import rq2_plan as rp

    try:
        rec = rl.compute_updates(a.work)
    except rl.UpdatesError as err:
        sys.stderr.write(f"refused: {err}\n")
        return 2
    out = a.out or str(Path(a.work) / "configs_resolved")
    rows = rp.write_configs(
        rp.plan_runs(a.seeds, mined_n=rec["updates"]),
        _templates(a),
        out,
        filter_size=rec["filter_pool"],
    )
    summary = {"updates_record": rec, "written": len(rows), "runs": rows}
    sys.stdout.write(json.dumps(summary, indent=1, sort_keys=True) + "\n")
    return 0


def cmd_eval(a: argparse.Namespace) -> int:
    from ril.evaluation.eval_plan import EvalSet, plan_sets

    sets = []
    for spec in a.set:
        name, rest = spec.split("=", 1)
        e1, prep, roles, cache, *flag = rest.split(":")
        sets.append(EvalSet(name, e1, prep, tuple(roles.split(",")), cache, flag == ["gz"]))
    out = plan_sets(sets)
    sys.stdout.write(json.dumps(out, indent=1, sort_keys=True) + "\n")
    return 0 if out["ready"] else 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    pl = sub.add_parser("plan")
    rd = sub.add_parser("render")
    rs = sub.add_parser("resolve")
    for q in (pl, rd, rs):
        q.add_argument("--seeds", type=int, nargs="+", default=[100, 101, 102])
        q.add_argument("--mined-template", default=TEMPLATES["mined"])
        q.add_argument("--injected-template", default=TEMPLATES["injected"])
    rs.add_argument("--work", required=True)
    rs.add_argument("--out")
    for q in (pl, rd):
        q.add_argument("--filter-size", type=int)
        q.add_argument("--updates", type=int, help="mined-family updates (D140); default 100")
    pl.add_argument("--pool-examples", type=int)
    pl.add_argument("--family-accounts", nargs="*", default=[], metavar="FAMILY=ACCOUNT")
    pl.add_argument("--queue-wait-hours", type=float, default=0.0)
    pl.add_argument("--drop-conditional", action="store_true")
    rd.add_argument("--out", required=True)
    ev = sub.add_parser("eval")
    ev.add_argument("--set", nargs="+", required=True)
    a = p.parse_args(argv)
    return {"plan": cmd_plan, "render": cmd_render, "resolve": cmd_resolve, "eval": cmd_eval}[
        a.cmd
    ](a)


if __name__ == "__main__":
    raise SystemExit(main())
