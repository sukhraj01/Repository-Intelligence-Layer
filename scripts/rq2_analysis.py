"""Final RQ2 analysis: command line over ``ril.analysis.rq2_final``.

ROWS RUNS OUT [--dev-analysis-id E-...] [--source-kind final|pilot|synthetic] [--seed S] [--draws N]
Reads the per-query rows and the run table of the final runs and writes the machine-readable
summary (hashes of both inputs inside). A sealed evaluation set (the eight repositories, the
executable 377) is refused without the id of the dev-analysis entry that precedes it (D100).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("rows", type=Path)
    p.add_argument("runs", type=Path)
    p.add_argument("out", type=Path)
    p.add_argument("--dev-analysis-id", default=None)
    p.add_argument("--source-kind", default="final", choices=("final", "pilot", "synthetic"))
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--draws", type=int, default=2000)
    a = p.parse_args(argv)
    from ril.analysis import rq2_final

    summary = rq2_final.analyse_files(
        a.rows,
        a.runs,
        a.out,
        dev_analysis_id=a.dev_analysis_id,
        source_kind=a.source_kind,
        docs_root=ROOT,
        seed=a.seed,
        draws=a.draws,
    )
    sys.stdout.write(
        f"{len(summary['contrasts'])} contrasts, hash {summary['analysis_hash'][:12]}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
