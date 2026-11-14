"""CPU-only dry run of the final-sets scoring path; nothing is encoded (DEV-043 addendum).

Usage: rq2_final_dryrun.py --retained-root DIR --home HOME --dev-record FILE --out-root DIR
       --scratch DIR --follows ID --report OUT.json [--only RUN ...]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
DEFAULT_SUBSET = (
    Path(__file__).resolve().parents[1] / "results/rq3_exec/executable_instances_v1.json"
)


def main(argv: list[str] | None = None) -> int:
    from ril.bench import rq2_final_dryrun as dr
    from ril.evaluation import score_retention as sr

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--retained-root", required=True)
    p.add_argument("--home", required=True)
    p.add_argument("--dev-record", required=True)
    p.add_argument("--out-root", required=True)
    p.add_argument("--scratch", required=True)
    p.add_argument("--follows", required=True)
    p.add_argument("--report", required=True)
    p.add_argument("--only", nargs="*")
    p.add_argument("--subset", default=str(DEFAULT_SUBSET))
    p.add_argument("--expected-l3", type=int)
    p.add_argument("--scores-root")
    a = p.parse_args(argv)
    report = dr.dry_run(
        home=a.home,
        retained_root=a.retained_root,
        dev_record_path=a.dev_record,
        subset_path=a.subset,
        out_root=a.out_root,
        scores_root=a.scores_root or sr.default_scores_root(a.retained_root),
        scratch=a.scratch,
        follows=a.follows,
        only=a.only,
        expected_l3=a.expected_l3,
    )
    Path(a.report).write_text(dr.to_json(report) + "\n", encoding="utf-8")
    sys.stdout.write(f"problems: {report['problems']}\n")
    return 0 if report["problems"] == 0 else 4


if __name__ == "__main__":
    raise SystemExit(main())
