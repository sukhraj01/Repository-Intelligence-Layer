"""Submit the RQ2 final runs of one family on its account: one GPU job per run, chained.

  python3 -I scripts/rq2_submit.py --family mined --account C --work DIR --preflight PATH
      [--retain-dir DIR] --date YYYY-MM-DD [--include-conditional] [--print-graph]
      [--confirm-launch]

One GPU job per seed (all arms of the seed in order, D141). The mined family refuses to build or
submit anything unless N, its update count, was computed from the prepared store (``--work`` holds
``rq2_updates.json`` written by ``scripts/rq2_plan.py resolve``; D140). Always prints the job graph
first. Without ``--confirm-launch`` it submits nothing and exits 2; with
it, it first checks the preflight file (passed, same account, family and RIL_COMMIT, under 48 hours
old) and that none of the jobs is already queued, then calls ``sbatch`` for each run (``afterany``
chain, one GPU job at a time per account). ``--print-graph`` prints and exits 0. Logic in
``ril/bench/rq2_launch.py``. Submitting is the engineer's action (D124).
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _run(cmd: list[str]) -> str:
    return subprocess.run(cmd, capture_output=True, text=True, check=True).stdout


def _queued() -> list[str]:
    out = subprocess.run(
        ["squeue", "-u", os.environ.get("USER", ""), "-h", "-o", "%j"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    return out.split()


def main(argv: list[str] | None = None) -> int:
    from ril.bench import rq2_launch as rl
    from ril.training import rq2_plan as rp

    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--family", choices=sorted(rp.MEM_REQUEST_MB), required=True)
    p.add_argument("--account", required=True)
    p.add_argument("--preflight")
    p.add_argument("--work", help="run work directory holding prep_summary.json (mined family)")
    p.add_argument("--retain-dir", default=os.environ.get("RETAIN_DIR"))
    p.add_argument("--include-conditional", action="store_true")
    p.add_argument("--date", required=True, help="YYYY-MM-DD naming the result directories")
    p.add_argument("--print-graph", action="store_true")
    p.add_argument("--confirm-launch", action="store_true")
    a = p.parse_args(argv)
    commit = os.environ.get("RIL_COMMIT", "")
    mined_n = None
    if a.family == "mined":
        try:
            if not a.work:
                raise rl.UpdatesError("N has not been computed from a prepared store: no --work")
            mined_n = rl.read_updates(a.work)
        except rl.UpdatesError as err:
            sys.stderr.write(f"refused: {err}\n")
            return 2
    subs = rl.submissions(
        a.family,
        commit=commit,
        retain_dir=a.retain_dir,
        date=a.date,
        include_conditional=a.include_conditional,
        mined_n=mined_n,
    )
    sys.stdout.write(rl.render_graph(subs, a.account, a.family) + "\n")
    if a.print_graph:
        return 0
    if a.account != rp.FAMILY_ACCOUNTS[a.family]:
        sys.stderr.write(f"refused: family {a.family} trains on {rp.FAMILY_ACCOUNTS[a.family]}\n")
        return 2
    if not a.confirm_launch:
        sys.stderr.write("refused: nothing submitted; --confirm-launch is required\n")
        return 2
    reasons = rl.preflight_refusals(
        a.preflight,
        account=a.account,
        family=a.family,
        commit=commit,
        include_conditional=a.include_conditional,
        updates=mined_n,
    )
    if reasons:
        sys.stderr.write("refused: " + "; ".join(reasons) + "\n")
        return 2
    try:
        ids = rl.submit(subs, runner=_run, queued_names=_queued)
    except RuntimeError as err:
        sys.stderr.write(f"refused: {err}\n")
        return 2
    for name, jid in ids:
        sys.stdout.write(f"{jid} {name}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
