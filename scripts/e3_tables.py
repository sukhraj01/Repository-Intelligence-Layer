"""Turn evaluation files of pilots E3 to E5 into tables (wrapper over ``ril.analysis.e3_tables``).

Usage:
  e3_tables.py EVAL_DIR OUT_PREFIX [--kind graph|recency] [--groups pooled repo dataset]
               [--setting C=3,gamma=0.5,hops=2] [--select SUBSET ...] [--seed 0]
Writes OUT_PREFIX_compare.csv, OUT_PREFIX_expansion.csv (graph) and, with --select, prints the
dev setting chosen by the stated criterion. Numbers only.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ril.analysis.e1_tables import write_csv  # noqa: E402
from ril.analysis.e3_tables import (  # noqa: E402
    add_heldout_keys,
    aux_rows,
    compare,
    graph_cells,
    load_eval_dir,
    recency_cells,
    select_setting,
)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("eval_dir")
    ap.add_argument("out_prefix")
    ap.add_argument("--kind", choices=["graph", "recency"], default="graph")
    ap.add_argument("--groups", nargs="+", default=["pooled"])
    ap.add_argument("--setting", default="")
    ap.add_argument("--select", nargs="*", default=[])
    ap.add_argument("--heldout", action="store_true", help="merge loro_<repo> weight sets")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    tab = load_eval_dir(args.eval_dir)
    if args.heldout:
        add_heldout_keys(tab)
    cells = graph_cells(tab) if args.kind == "graph" else recency_cells(tab)
    if args.setting:
        want = dict(kv.split("=") for kv in args.setting.split(","))
        cells = [c for c in cells if all(str(c.labels.get(k)) == v for k, v in want.items())]
    masks = {}
    roles = sorted({r["role"] for r in tab.rows})
    if "pooled" in args.groups:
        for role in roles:
            masks[f"{role}_all"] = tab.mask(role=role)
    if "dataset" in args.groups:
        for ds in sorted({r["dataset"] for r in tab.rows}):
            masks[f"dataset:{ds}"] = tab.mask(dataset=ds)
    if "repo" in args.groups:
        for repo in sorted({r["repo"] for r in tab.rows}):
            masks[f"repo:{repo}"] = tab.mask(repo=repo)
    rows = []
    aux = []
    for group, mask in masks.items():
        for level in ("L2", "L3"):
            rows += compare(tab, mask, group, level, cells, args.seed)
            if args.kind == "graph":
                aux += aux_rows(tab, mask, group, level)
    write_csv(f"{args.out_prefix}_compare.csv", rows)
    if aux:
        write_csv(f"{args.out_prefix}_expansion.csv", aux)
    out = {"rows": len(rows), "queries": len(tab.rows)}
    if args.select and args.kind == "graph":
        pooled = [r for r in rows if r["group"] == "dev_all"]
        out["selection"] = {
            f"{variant}|{subset}": select_setting(pooled, subset, variant)
            for subset in args.select
            for variant in ("list", "rrf")
        }
    sys.stdout.write(json.dumps(out, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
