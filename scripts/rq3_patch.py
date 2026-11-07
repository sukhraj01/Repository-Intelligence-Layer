"""Edit blocks to the executor's patch: convert one reply, tabulate stored replies, validate.

Usage:
  rq3_patch.py convert REPLY --mirror BARE.git --commit SHA [--reading exact|tolerant] [--out DIFF]
  rq3_patch.py needed LOG_DIR PREPARED_DIR OUT.json
  rq3_patch.py snapshot NEEDED.json CACHE_DIR MIRROR_DIR OUT.jsonl
  rq3_patch.py table LOG_DIR PREPARED_DIR SNAPSHOTS.jsonl OUT_DIR
  rq3_patch.py draw SUBSET.json OUT.json [--n 20] [--seed 0]
  rq3_patch.py derive SPECS GOLD DRAW.json OUT_DIR --mirror-dir DIR [--local-mirrors DIR]

Implements D110 (docs/RQ3_PILOT.md). Thin wrapper: the logic is in ril/agent/providers/
patch_convert.py, ril/evaluation/{gold_edits,patch_validation}.py, ril/analysis/rq3_patch_apply.py.
`convert` prints the outcome class only, never any text of the reply.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ril.agent.providers.patch_convert import READINGS, convert_reply, git_reader  # noqa: E402
from ril.analysis import rq3_patch_apply as apply  # noqa: E402
from ril.evaluation import patch_validation  # noqa: E402
from ril.evaluation.executor.spec import load_specs  # noqa: E402
from ril.util.log import get_logger  # noqa: E402
from ril.util.seed import set_seed  # noqa: E402

log = get_logger("rq3_patch")


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    fields: list[str] = []
    for r in rows:
        fields += [k for k in r if k not in fields]
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def cmd_convert(args: argparse.Namespace) -> int:
    reply = Path(args.reply).read_text(encoding="utf-8")
    res = convert_reply(reply, git_reader(args.mirror, args.commit), args.reading)
    detail = f" block={res.failure.block}" if res.failure and res.failure.block >= 0 else ""
    sys.stdout.write(f"outcome={res.outcome} blocks={res.n_blocks}{detail}\n")
    if args.out and res.diff:
        Path(args.out).write_text(res.diff, encoding="utf-8")
    return 0 if res.applied else 1


def cmd_needed(args: argparse.Namespace) -> int:
    units = apply.load_units(Path(args.log_dir), Path(args.prepared_dir))
    needed = apply.needed_files(units)
    Path(args.out).write_text(json.dumps(needed, indent=1, sort_keys=True) + "\n")
    log.info("%d instances, %d files", len(needed), sum(len(v) for v in needed.values()))
    return 0


def cmd_snapshot(args: argparse.Namespace) -> int:
    needed = json.loads(Path(args.needed).read_text())
    counts = apply.write_snapshots(
        needed, Path(args.cache_dir), Path(args.mirror_dir), Path(args.out)
    )
    log.info("snapshots: %s", counts)
    return 0


def cmd_table(args: argparse.Namespace) -> int:
    units = apply.load_units(Path(args.log_dir), Path(args.prepared_dir))
    snaps = apply.read_snapshots(Path(args.snapshots))
    urows, brows = apply.unit_rows(units, snaps)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    _write_csv(out / "rq3_patch_apply_by_arm.csv", apply.outcome_table(urows, units))
    _write_csv(out / "rq3_patch_apply_rescue.csv", apply.rescue_table(urows))
    _write_csv(out / "rq3_patch_apply_blocks.csv", apply.block_table(brows))
    _write_csv(out / "rq3_patch_apply_units.csv", urows)
    log.info("%d usable units, %d blocks, readings %s", len(urows), len(brows), READINGS)
    return 0


def cmd_draw(args: argparse.Namespace) -> int:
    set_seed(args.seed)
    subset = json.loads(Path(args.subset).read_text())
    picked = patch_validation.draw_instances(subset["executable"], args.n, args.seed)
    Path(args.out).write_text(
        json.dumps({"seed": args.seed, "n": args.n, "instances": picked}, indent=1) + "\n"
    )
    return 0


def cmd_derive(args: argparse.Namespace) -> int:
    draw = json.loads(Path(args.draw).read_text())
    ids = [r["instance_id"] for r in draw["instances"]]
    specs = [s for s in load_specs(Path(args.specs)) if s.instance_id in set(ids)]
    gold = {
        r["instance_id"]: r["patch"]
        for r in (json.loads(x) for x in Path(args.gold).read_text().splitlines() if x)
        if r["instance_id"] in set(ids)
    }
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    rows, patches = patch_validation.derive_all(
        specs,
        gold,
        Path(args.mirror_dir),
        Path(args.local_mirrors) if args.local_mirrors else None,
        out / "scratch",
        args.reading,
    )
    _write_csv(out / "derive_table.csv", rows)
    with (out / "converted_patches.jsonl").open("w", encoding="utf-8") as fh:
        for iid, patch in sorted(patches.items()):
            fh.write(json.dumps({"instance_id": iid, "patch": patch}) + "\n")
    policy = {r["instance_id"]: r["env_policy"] for r in draw["instances"]}
    for name in sorted(set(policy.values())):
        ids = sorted(i for i in patches if policy[i] == name)
        (out / f"ids_converted_{name}.txt").write_text("".join(i + "\n" for i in ids))
    log.info("%d drawn, %d converted", len(specs), len(patches))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("convert")
    c.add_argument("reply")
    c.add_argument("--mirror", required=True)
    c.add_argument("--commit", required=True)
    c.add_argument("--reading", choices=READINGS, default="exact")
    c.add_argument("--out")
    c.set_defaults(fn=cmd_convert)
    n = sub.add_parser("needed")
    n.add_argument("log_dir")
    n.add_argument("prepared_dir")
    n.add_argument("out")
    n.set_defaults(fn=cmd_needed)
    s = sub.add_parser("snapshot")
    s.add_argument("needed")
    s.add_argument("cache_dir")
    s.add_argument("mirror_dir")
    s.add_argument("out")
    s.set_defaults(fn=cmd_snapshot)
    t = sub.add_parser("table")
    t.add_argument("log_dir")
    t.add_argument("prepared_dir")
    t.add_argument("snapshots")
    t.add_argument("out_dir")
    t.set_defaults(fn=cmd_table)
    d = sub.add_parser("draw")
    d.add_argument("subset")
    d.add_argument("out")
    d.add_argument("--n", type=int, default=20)
    d.add_argument("--seed", type=int, default=0)
    d.set_defaults(fn=cmd_draw)
    v = sub.add_parser("derive")
    v.add_argument("specs")
    v.add_argument("gold")
    v.add_argument("draw")
    v.add_argument("out_dir")
    v.add_argument("--mirror-dir", required=True)
    v.add_argument("--local-mirrors")
    v.add_argument("--reading", choices=READINGS, default="exact")
    v.add_argument("--seed", type=int, default=0)
    v.set_defaults(fn=cmd_derive)
    args = ap.parse_args(argv)
    return int(args.fn(args))


if __name__ == "__main__":
    raise SystemExit(main())
