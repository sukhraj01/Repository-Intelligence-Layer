"""No-call replay of the floor arm's stored replies (E-RQ3-FLOOR addendum, D170).

Usage (from the work directory):
  rq3_floor_replay.py replay --stage s1=DIR [--stage s2=DIR] --prepared P --specs SPECS.jsonl
      --mirror-dir DIR [--local-mirrors DIR] --out-dir OUT

Each stage DIR holds ``results/results.jsonl`` and ``log/`` of one run of the arm. No provider call
is made. Logic lives in ``ril/analysis/rq3_floor_replay.py``.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ril.util.log import get_logger  # noqa: E402
from ril.util.seed import set_seed  # noqa: E402

log = get_logger("rq3_floor_replay")


def _csv(path: Path, rows: list[dict[str, Any]]) -> None:
    keys: list[str] = []
    for r in rows:
        for k in r:
            if k not in keys:
                keys.append(k)
    with path.open("w", newline="", encoding="utf-8") as h:
        w = csv.DictWriter(h, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def cmd_replay(a: argparse.Namespace) -> int:
    from ril.agent.providers.calllog import CallLog
    from ril.agent.providers.cluster import reader_factory
    from ril.agent.providers.driver import reply_from_rows
    from ril.agent.providers.pilot_run import load_items
    from ril.agent.providers.pseudonymise import restore_text
    from ril.analysis import rq3_floor_replay as fr
    from ril.evaluation.executor.spec import load_specs

    items = {str(i["instance_id"]): i for i in load_items(a.prepared)}
    wanted: dict[str, str] = {}
    stage_rows: dict[str, list[dict[str, Any]]] = {}
    for spec in a.stage:
        label, _, d = spec.partition("=")
        res = Path(d) / "results" / "results.jsonl"
        stage_rows[label] = [
            json.loads(x) for x in res.read_text(encoding="utf-8").splitlines() if x
        ]
        for r in stage_rows[label]:
            if r["instance_id"] in wanted:
                raise SystemExit(f"{r['instance_id']} appears in two stages")
            wanted[str(r["instance_id"])] = label
    specs = {s.instance_id: s for s in load_specs(Path(a.specs)) if s.instance_id in wanted}
    local = Path(a.local_mirrors) if a.local_mirrors else None
    readers = reader_factory(specs, Path(a.mirror_dir), local)
    out_rows: list[dict[str, Any]] = []
    for spec in a.stage:
        label, _, d = spec.partition("=")
        units = CallLog(Path(d) / "log").by_unit()
        call_log = CallLog(Path(d) / "log")
        by_id = {(u[0]): rows for u, rows in units.items()}
        for r in sorted(stage_rows[label], key=lambda x: str(x["instance_id"])):
            iid = str(r["instance_id"])
            item = items[iid]
            reply = reply_from_rows(by_id[iid], call_log)
            if reply is None:
                raise SystemExit(f"{iid}: unit unfinished in the call log")
            text = restore_text(reply.text, item.get("restore"))
            issue = restore_text(fr.issue_of_prompt(str(item["prompt"])), item.get("restore"))
            row = fr.replay_reply(text, issue, readers(iid))
            out_rows.append(
                {
                    "stage": label,
                    "instance_id": iid,
                    "repo": r["repo"],
                    "outcome": r["outcome"],
                    "resolved": bool(r["resolved"]),
                    **row,
                }
            )
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    _csv(out / "rq3_floor_replay_instances.csv", out_rows)
    _csv(out / "rq3_floor_replay_summary.csv", fr.summarise(out_rows))
    _csv(out / "rq3_floor_replay_by_repo.csv", fr.resolved_by_repo(out_rows))
    sys.stdout.write(json.dumps({"replies": len(out_rows)}) + "\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("replay")
    p.add_argument("--stage", action="append", required=True)
    p.add_argument("--prepared", required=True)
    p.add_argument("--specs", required=True)
    p.add_argument("--mirror-dir", required=True)
    p.add_argument("--local-mirrors")
    p.add_argument("--out-dir", required=True)
    p.add_argument("--seed", type=int, default=0)
    p.set_defaults(fn=cmd_replay)
    args = ap.parse_args(argv)
    set_seed(args.seed)
    return int(args.fn(args))


if __name__ == "__main__":
    raise SystemExit(main())
