"""Edge recovery of a repository's static graph against a dynamic trace (ADR-012, (a) and (b)).

Usage: edge_recovery.py ROOT OWNER/NAME TRACE.json OUT.json
A thin wrapper around ``ril.evaluation.edge_recovery``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ril.evaluation.edge_recovery import run_recovery  # noqa: E402


def main() -> int:
    root, repo_id, trace_path, out = sys.argv[1:5]
    trace = json.loads(Path(trace_path).read_text(encoding="utf-8"))
    report = run_recovery(root, repo_id, trace)
    Path(out).write_text(json.dumps(report, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
