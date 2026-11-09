"""Record the two launch facts the preflight reads (CPU; one small JSON each in the work dir).

  registration --work DIR [--protocol docs/RQ2_PROTOCOL.md]
        the digest of the cell table (and of the protocol text): run once, by the engineer, after
        the cell list and the decision rules are read and before the first run
  leakage --work DIR --pytest-output FILE
        the leakage tests' result on this commit, read from the last line of a pytest run on the
        cluster (``tests/leakage``); refuses a run with a failure or an error

Logic in ``ril/bench/rq2_launch.py``. ``RIL_COMMIT`` must be set for ``leakage``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main(argv: list[str] | None = None) -> int:
    from ril.bench import rq2_launch as rl

    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("registration")
    r.add_argument("--work", required=True)
    r.add_argument("--protocol")
    lk = sub.add_parser("leakage")
    lk.add_argument("--work", required=True)
    lk.add_argument("--pytest-output", required=True)
    a = p.parse_args(argv)
    if a.cmd == "registration":
        out = rl.record_registration(a.work, a.protocol)
    else:
        commit = os.environ.get("RIL_COMMIT", "")
        if not commit:
            sys.stderr.write("refused: RIL_COMMIT is not set\n")
            return 2
        try:
            out = rl.record_leakage(
                a.work, commit, Path(a.pytest_output).read_text(encoding="utf-8")
            )
        except ValueError as err:
            sys.stderr.write(f"refused: {err}\n")
            return 2
    sys.stdout.write(json.dumps(out, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
