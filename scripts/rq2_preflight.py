"""Preflight of an RQ2 final launch on one account (CPU, read-only apart from the preflight file).

  python3 -I scripts/rq2_preflight.py --family mined --account C --work $HOME/ril_rq2f/work \\
      --home $HOME --out $HOME/ril_rq2f/preflight_C.json [--retain-dir DIR] [--include-conditional]

Verifies what a program can of the launch checklist (``docs/RQ2_LAUNCH_PLAN.md`` section 5), prints
every check with its detail and writes the file ``scripts/rq2_submit.py`` requires. Exit 0 when
every check passed, 1 otherwise. Logic in ``ril/bench/rq2_launch.py``.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))


def main(argv: list[str] | None = None) -> int:
    from ril.bench import rq2_launch as rl
    from ril.training import rq2_plan as rp

    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--family", choices=sorted(rp.MEM_REQUEST_MB), required=True)
    p.add_argument("--account", required=True)
    p.add_argument("--work", required=True)
    p.add_argument("--home", default=os.path.expanduser("~"))
    p.add_argument("--out", required=True)
    p.add_argument("--retain-dir", default=os.environ.get("RETAIN_DIR") or None)
    p.add_argument("--include-conditional", action="store_true")
    a = p.parse_args(argv)
    if a.account != rp.FAMILY_ACCOUNTS[a.family]:
        sys.stderr.write(f"family {a.family} trains on account {rp.FAMILY_ACCOUNTS[a.family]}\n")
        return 2
    commit = os.environ.get("RIL_COMMIT", "")
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True, check=False
    ).stdout.strip()
    checks = rl.run_checks(
        family=a.family,
        repo=str(REPO),
        work=a.work,
        home=a.home,
        commit=commit,
        retain_dir=a.retain_dir,
        include_conditional=a.include_conditional,
        head_commit=head or None,
    )
    rec = rl.write_preflight(
        a.out,
        account=a.account,
        family=a.family,
        commit=commit,
        include_conditional=a.include_conditional,
        checks=checks,
    )
    sys.stdout.write(json.dumps(rec, indent=1) + "\n")
    return 0 if rec["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
