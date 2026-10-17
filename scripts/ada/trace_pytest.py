"""Run a repository's test suite under the function-level tracer and write the trace as JSON.

Usage: trace_pytest.py ROOT OUT.json [pytest args ...]
Run with the interpreter of the repository's environment (the one where its dependencies and
pytest are installed); the working directory is changed to ROOT. Needs only the standard library
plus ``ril/evaluation/dynamic_trace.py`` (copied next to the repository on the cluster).
"""

from __future__ import annotations

import collections
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ril.evaluation.dynamic_trace import Tracer, write_trace  # noqa: E402


class _Outcomes:
    def __init__(self) -> None:
        self.counts: collections.Counter[str] = collections.Counter()

    def pytest_runtest_logreport(self, report: object) -> None:
        when = getattr(report, "when", "")
        outcome = getattr(report, "outcome", "")
        if when == "call" or (when == "setup" and outcome != "passed"):
            self.counts[f"{when}:{outcome}"] += 1

    def pytest_collectreport(self, report: object) -> None:
        if getattr(report, "outcome", "") == "failed":
            self.counts["collect:failed"] += 1


def main() -> int:
    root, out, *pytest_args = sys.argv[1:]
    out = os.path.abspath(out)
    root = os.path.abspath(root)
    import pytest

    os.chdir(root)
    outcomes = _Outcomes()
    tracer = Tracer(root)
    t0 = time.perf_counter()
    tracer.start()
    try:
        code = int(pytest.main(pytest_args, plugins=[outcomes]))
    finally:
        tracer.stop()
    seconds = time.perf_counter() - t0
    write_trace(
        tracer,
        out,
        {
            "pytest_exit_code": code,
            "pytest_args": pytest_args,
            "outcomes": dict(sorted(outcomes.counts.items())),
            "seconds_traced": round(seconds, 2),
            "pytest": pytest.__version__,
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
