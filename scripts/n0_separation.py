"""Gate N0 of E-PILOT-NOISE: command line over ``ril.analysis.n0_tables``.

CACHE FEATURE_TABLE OUT_JSON --scores TEACHER=PATH [...] [--rates 0.2 0.4] [--seeds 0 1 2] [--k 20]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    for x in ("cache", "feature_table", "out"):
        p.add_argument(x)
    p.add_argument("--scores", nargs="+", required=True)
    p.add_argument("--rates", nargs="+", type=float, default=[0.2, 0.4])
    p.add_argument("--seeds", nargs="+", type=int, default=[0, 1, 2])
    p.add_argument("--k", type=int, default=20)
    a = p.parse_args(argv)
    from ril.analysis import n0_tables as n0
    from ril.training.noise import read_score_store
    from ril.training.pool_reader import load_feature_table, read_cache

    examples = [e for c in a.cache.split(os.pathsep) for e in read_cache(c)]
    table = load_feature_table(a.feature_table)
    out: dict[str, object] = {"version": n0.N0_TABLES_VERSION, "pairs": len(examples)}
    repro, sep = [], []
    for spec in a.scores:
        teacher, path = spec.split("=", 1)
        store = read_score_store(path)
        repro.append(n0.reproduction(examples, store, table, teacher))
        for seed in a.seeds:
            for rate in a.rates:
                sep.append(n0.separation(examples, store, teacher, rate, seed, a.k))
    out["reproduction"], out["separation"] = repro, sep
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as handle:
        json.dump(out, handle, indent=1, sort_keys=True)
    json.dump(out, sys.stdout, indent=1, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
