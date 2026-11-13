"""Agreement across the three repeats of the graded untrained arm, and the power re-run with it.

Thin wrapper over ``ril.analysis.rq3_run_agreement`` (entry E-RQ3-RUN-AGREEMENT). Reads stored
rows only. Usage: rq3_run_agreement.py [--sims 500] [--seed 0]
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from ril.analysis import rq3_power_noise
from ril.analysis import rq3_run_agreement as ra

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "results" / "rq3_driver" / "untrained_runs" / "gemini-3.8-flash" / "rrf_runs0-2"
OUT = ROOT / "results" / "rq3_driver"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sims", type=int, default=500)
    ap.add_argument("--permutations", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    rows = ra.read_jsonl(RUN / "results.jsonl")
    calls = ra.read_jsonl(RUN / "calls.jsonl")
    summary = ra.agreement_summary(ra.resolved_by_instance(rows))
    mu = float(summary["mean_resolved_rate"])
    target = float(summary["pooled_agreement"])
    cal = {k: ra.calibrate_s(target, mu, k) for k in rq3_power_noise.KAPPAS}
    scenarios: list[tuple[str, float, tuple[float, ...]]] = [
        ("assumed edit agreement", rq3_power_noise.SAME_REPLY, rq3_power_noise.KAPPAS)
    ]
    scenarios += [
        ("calibrated to measured agreement", s, (k,)) for k, s in cal.items() if s is not None
    ]
    scenarios.append(("measured agreement used directly", target, rq3_power_noise.KAPPAS))
    mdd = ra.power_rerun(scenarios, sims=args.sims, permutations=args.permutations, seed=args.seed)
    summary["calibration"] = {
        "mu": mu,
        "target_pooled_agreement": target,
        "s_for_kappa": {str(k): s for k, s in cal.items()},
        "kappa_with_s_zero": ra.kappa_alone(target, mu),
    }
    summary["settings"] = ra.settings_by_repeat(rows, calls)
    summary["power_run"] = {"sims": args.sims, "permutations": args.permutations, "seed": args.seed}
    text = json.dumps(summary, indent=1, sort_keys=True) + "\n"
    (OUT / "rq3_run_agreement.json").write_text(text)
    with open(OUT / "rq3_power_measured_agreement_mdd.csv", "w", newline="") as handle:
        w = csv.DictWriter(handle, fieldnames=list(mdd[0]))
        w.writeheader()
        w.writerows(mdd)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
