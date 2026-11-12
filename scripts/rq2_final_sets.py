"""Score retained RQ2 models on the final sets (the eight repositories, the executable 377).

  plan  --retained-root DIR [--set eight exec377] --out DIR
        list the (model, set part) pairs that would be scored; scores nothing, needs no id
  run   --retained-root DIR --follows-dev-analysis ID --dev-record PATH --out DIR --home DIR
        --work DIR [--set ...] [--only RUN_ID ...] [--device cuda]
        [--no-retain-scores] [--scores-root DIR] [--subset FILE]
        score the retained models once; keeps the per-instance scores of the executable 377 (the
        eight repositories are not kept) under <retained-root>/exec377_scores unless told not to;
        refuses to start without the id of the dev-analysis entry
        it follows, a matching complete record that covers the runs, and verified model folders

Logic in ``ril/evaluation/final_sets.py`` (D100, D127). Every stage prints JSON. A GPU job.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
DEFAULT_SUBSET = (
    Path(__file__).resolve().parents[1] / "results/rq3_exec/executable_instances_v1.json"
)


def _folders(root: str, only: list[str] | None) -> list[str]:
    from ril.evaluation import final_sets as fs
    from ril.training import retention

    folders = retention.list_retained(root)
    if only:
        folders = [f for f in folders if fs.retained_run_id(fs.read_manifest(f)) in set(only)]
    return folders


def main(argv: list[str] | None = None) -> int:
    from ril.evaluation import final_sets as fs

    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("plan", "run"):
        q = sub.add_parser(name)
        q.add_argument("--retained-root", required=True)
        q.add_argument("--set", nargs="+", default=["eight", "exec377"])
        q.add_argument("--only", nargs="*")
        q.add_argument("--out", required=True)
    r = sub.choices["run"]
    r.add_argument("--follows-dev-analysis")
    r.add_argument("--dev-record", required=True)
    r.add_argument("--home", required=True)
    r.add_argument("--work", required=True)
    r.add_argument("--device", default="cuda")
    r.add_argument(
        "--retain-scores",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="keep the executable-377 scores with the checkpoint hash and a SHA-256 (default on)",
    )
    r.add_argument("--scores-root", help="default: <retained-root>/exec377_scores")
    r.add_argument("--subset", default=str(DEFAULT_SUBSET))
    a = p.parse_args(argv)
    folders = _folders(a.retained_root, a.only)
    if a.cmd == "plan":
        sys.stdout.write(json.dumps(fs.plan(folders, a.set, a.out), indent=1) + "\n")
        return 0
    try:
        ids = [fs.retained_run_id(fs.read_manifest(f)) for f in folders]
        record = fs.load_dev_analysis_record(a.dev_record, a.follows_dev_analysis, ids)
    except fs.FinalSetsRefused as err:
        sys.stderr.write(f"refused: {err}\n")
        return 3
    os.makedirs(a.out, exist_ok=True)
    commit = os.environ.get("RIL_COMMIT", "")
    if not commit:
        sys.stderr.write("refused: RIL_COMMIT is not set\n")
        return 3
    retain: str | None = None
    subset_ids: list[str] | None = None
    if a.retain_scores and "exec377" in a.set:
        from ril.evaluation import score_retention as sr

        retain = a.scores_root or sr.default_scores_root(a.retained_root)
        subset_ids = sr.read_subset_ids(a.subset)
    rows = []
    for folder in folders:
        for name in a.set:
            rows += fs.evaluate_retained(
                folder,
                name,
                out_root=a.out,
                home=a.home,
                work=a.work,
                follows=str(a.follows_dev_analysis),
                record=record,
                commit=commit,
                device=a.device,
                retain_scores=retain,
                subset_ids=subset_ids,
            )
    sys.stdout.write(json.dumps({"scored": len(rows), "rows": rows}, indent=1, default=str) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
