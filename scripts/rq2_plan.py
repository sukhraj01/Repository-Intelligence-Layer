"""Plan-only launcher of the RQ2 final experiment: no GPU, no model, no torch.

  plan  [--seeds S ...] [--filter-size N] [--pool-examples N] [--accounts A C ...]
        [--queue-wait-hours H] [--mined-template P] [--injected-template P]
        render the 36 configurations, check the held-identical block and the hashes, account the
        budget against Block 3 on the protocol and the measured basis, check distinct examples,
        and print the job graph and its critical path
  eval  --set NAME=E1_CONFIG:PREP:ROLES:E3_CACHE [...]
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


def cmd_plan(a: argparse.Namespace) -> int:
    import yaml

    from ril.training import rq2_plan as rp

    templates = {
        "mined": yaml.safe_load(Path(a.mined_template).read_text(encoding="utf-8")),
        "injected": yaml.safe_load(Path(a.injected_template).read_text(encoding="utf-8")),
    }
    runs = rp.plan_runs(a.seeds)
    rows = rp.validate_runs(runs, templates, filter_size=a.filter_size or 1)
    jobs = rp.job_graph(runs, train_accounts=a.accounts)
    out = {
        "version": rp.PLAN_VERSION,
        "seeds": a.seeds,
        "reused_noise_seeds": rp.fresh_noise_check(runs),
        "runs": rows,
        "budget_protocol": rp.budget(runs, basis="protocol"),
        "budget_measured": rp.budget(runs, basis="measured"),
        "unique_examples": (
            rp.unique_example_check(
                rp.PRIMARY_UPDATES * rp.BATCH_SIZE, a.pool_examples, a.filter_size
            )
            if a.pool_examples
            else None
        ),
        "open_choices": list(rp.OPEN_CELL_CHOICES),
        "jobs": [dataclasses.asdict(j) for j in jobs],
        "critical_path_hours": round(rp.critical_path_hours(jobs, a.queue_wait_hours), 1),
    }
    sys.stdout.write(json.dumps(out, indent=1, sort_keys=True) + "\n")
    return 0


def cmd_eval(a: argparse.Namespace) -> int:
    from ril.evaluation.eval_plan import EvalSet, plan_sets

    sets = []
    for spec in a.set:
        name, rest = spec.split("=", 1)
        e1, prep, roles, cache = rest.split(":")
        sets.append(EvalSet(name, e1, prep, tuple(roles.split(",")), cache))
    out = plan_sets(sets)
    sys.stdout.write(json.dumps(out, indent=1, sort_keys=True) + "\n")
    return 0 if out["ready"] else 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    pl = sub.add_parser("plan")
    pl.add_argument("--seeds", type=int, nargs="+", default=[100, 101, 102])
    pl.add_argument("--filter-size", type=int)
    pl.add_argument("--pool-examples", type=int)
    pl.add_argument("--accounts", nargs="+", default=["A"])
    pl.add_argument("--queue-wait-hours", type=float, default=0.0)
    pl.add_argument("--mined-template", default="configs/experiments/mp/mp_raw_s0.yaml")
    pl.add_argument("--injected-template", default="configs/experiments/n1/n1_r40_raw_s0.yaml")
    ev = sub.add_parser("eval")
    ev.add_argument("--set", nargs="+", required=True)
    a = p.parse_args(argv)
    return {"plan": cmd_plan, "eval": cmd_eval}[a.cmd](a)


if __name__ == "__main__":
    raise SystemExit(main())
