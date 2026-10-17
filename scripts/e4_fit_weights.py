"""Fit edge-family weights for pilot E4 and write the evaluation configuration.

Usage: e4_fit_weights.py REACH_CSV E3_EVAL_DIR OUT_YAML OUT_CSV
Two fits from the reach table of pilot M (reach, excess), and one leave-one-repository-out fit per
development repository from the expansions of pilot E3 (share of added units that are gold, over the
other repositories). Fits are written before any evaluation of E4.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import yaml  # noqa: E402

from ril.analysis.e3_tables import load_eval_dir  # noqa: E402
from ril.analysis.fitted_weights import fit_from_precision, fit_from_reach  # noqa: E402
from ril.evaluation.e3_eval import FAMILIES  # noqa: E402

SEEDS, GAMMA, HOPS = 5, 0.5, 2


def main() -> int:
    reach_csv, eval_dir, out_yaml, out_csv = sys.argv[1:5]
    sets = {
        "fit_reach": fit_from_reach(reach_csv, statistic="reach"),
        "fit_excess": fit_from_reach(reach_csv, statistic="excess"),
    }
    tab = load_eval_dir(eval_dir)
    repos = sorted({r["repo"] for r in tab.rows})
    for held in repos:
        mask = tab.mask() & ~tab.mask(repo=held)
        w = fit_from_precision(tab, mask, families=FAMILIES, seeds=SEEDS, gamma=GAMMA, hops=HOPS)
        sets[f"loro_{held.replace('/', '__')}"] = w
    with open(out_csv, "w", newline="", encoding="utf-8") as handle:
        wr = csv.writer(handle)
        wr.writerow(["set", *FAMILIES])
        for name, w in sets.items():
            wr.writerow([name, *[w[f] for f in FAMILIES]])
    cfg = {
        "experiment_id": "E-GRAPH-WEIGHTS",
        "stage": "dev",
        "status": "exploratory pilot",
        "date": "2026-10-18",
        "seed": 0,
        "roles": ["dev"],
        "confirm": False,
        "note": (
            "One weight per edge family, multiplied along the path; the best family of a fit gets "
            "the hand-set decay 0.5 (the hand-set run of E3 gives every family 0.5). fit_reach and "
            "fit_excess come from pilot M's reach table (flask, requests, seaborn; none is a dev "
            "repository); loro_<repo> sets are fitted on the other dev repositories from E3 "
            "expansions and are evaluated only on the repository they were not fitted on."
        ),
        "graph": {
            "variants": ["list", "rrf"],
            "subsets": ["all", "core"],
            "seeds": [SEEDS],
            "gammas": [GAMMA],
            "hops": [HOPS],
            "cap": 50,
            "controls": ["rand_whole", "rand_files"],
            "draws": 3,
            "rrf_k": 60,
        },
        "weights": {
            "subsets": ["all", "core"],
            "seeds": [SEEDS],
            "hops": [HOPS],
            "sets": sets,
        },
    }
    with open(out_yaml, "w", encoding="utf-8") as handle:
        yaml.safe_dump(cfg, handle, sort_keys=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
