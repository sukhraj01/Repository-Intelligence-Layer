"""Smoke-pilot tables (E-PILOT-K, E-PILOT-NEG, E-PILOT-LEAK): thin command line over
``ril.analysis.t2_tables``.

  pilots SPEC RESULTS_ROOT OUT_DIR LOG [--seed S]   (SPEC: YAML with a ``pilots`` list)
  teachers RANKS [RANKS ...] --teachers T [T ...] --k K [K ...] --out-dir D --log L [--seed S]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("pilots")
    for x in ("spec", "results_root", "out_dir", "log"):
        a.add_argument(x)
    a.add_argument("--seed", type=int, default=0)
    t = sub.add_parser("teachers")
    t.add_argument("ranks", nargs="+")
    t.add_argument("--teachers", nargs="+", required=True)
    t.add_argument("--k", nargs="+", type=int, required=True)
    t.add_argument("--out-dir", required=True)
    t.add_argument("--log", required=True)
    t.add_argument("--seed", type=int, default=0)
    t.add_argument("--draws", type=int, default=2000)
    args = p.parse_args(argv)

    import yaml

    from ril.analysis import t2_tables as tt
    from ril.analysis.x2_tables import write_csv

    if args.cmd == "pilots":
        with open(args.spec, encoding="utf-8") as handle:
            spec = yaml.safe_load(handle)
        out = {
            "spec": args.spec,
            "pilots": [
                tt.pilot_tables(args.results_root, pl, args.out_dir, args.seed)
                for pl in spec["pilots"]
            ],
        }
    else:
        shares, agree = tt.teacher_rows(args.ranks, args.teachers, args.k, args.draws, args.seed)
        write_csv(f"{args.out_dir}/t2_teacher_shares.csv", shares)
        write_csv(f"{args.out_dir}/t2_teacher_agreement.csv", agree)
        out = {"shares": shares, "agreement": agree, "ranks": args.ranks, "seed": args.seed}
    Path(args.log).parent.mkdir(parents=True, exist_ok=True)
    with open(args.log, "w", encoding="utf-8") as handle:
        json.dump(out, handle, indent=1, sort_keys=True, default=str)
        handle.write("\n")
    json.dump(out, sys.stdout, indent=1, sort_keys=True, default=str)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
