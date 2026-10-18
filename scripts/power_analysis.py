"""Write the power-analysis tables (exact McNemar, run noise, paired bootstrap, seeds).

Thin wrapper around ``ril.evaluation.power``. Usage:
  power_analysis.py OUT_DIR --seed 0 [--sim-reps N] [--boot-reps N] [--boot-draws N] [--log FILE]
Writes ``OUT_DIR/x_power_<table>.csv`` and, with --log, a JSON run log (hash, seed, hardware).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ril.evaluation import power  # noqa: E402
from ril.util.log import get_logger  # noqa: E402
from ril.util.seed import set_seed  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("out_dir")
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--sim-reps", type=int, default=20000)
    ap.add_argument("--boot-reps", type=int, default=400)
    ap.add_argument("--boot-draws", type=int, default=1000)
    ap.add_argument("--log", default=None)
    args = ap.parse_args()
    set_seed(args.seed)
    log = get_logger("power")
    config = {
        "version": power.POWER_VERSION,
        "alpha": power.ALPHA,
        "power": power.POWER_TARGET,
        "ns": power.NS,
        "discordances": power.DISCORDANCES,
        "effects": power.EFFECTS,
        "baselines": power.BASELINES,
        "sigmas_points": power.SIGMAS_PTS,
        "deltas_points": power.DELTAS_PTS,
        "runs": power.RUNS,
        "boot_ns": power.BOOT_NS,
        "boot_sds": power.BOOT_SDS,
        "boot_rhos": power.BOOT_RHOS,
        "seed_ks": power.SEED_KS,
        "seed_rhos": power.SEED_RHOS,
        "seed": args.seed,
        "sim_reps": args.sim_reps,
        "boot_reps": args.boot_reps,
        "boot_draws": args.boot_draws,
    }
    chash = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
    log.info("config hash %s", chash)
    t0 = time.time()
    tables = power.build_tables(args.seed, args.sim_reps, args.boot_reps, args.boot_draws)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    digests: dict[str, str] = {}
    for name, rows in tables.items():
        path = out / f"x_power_{name}.csv"
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        digests[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        log.info("wrote %s (%d rows)", path, len(rows))
    if args.log:
        record = {
            "run": "x-power-analysis",
            "label": "calculation (no data); assumptions in the config",
            "config": config,
            "config_hash": chash,
            "seed": args.seed,
            "hardware": {
                "platform": platform.platform(),
                "python": platform.python_version(),
                "machine": platform.machine(),
            },
            "seconds": round(time.time() - t0, 1),
            "table_sha256": digests,
            "validation": tables["validation"],
        }
        Path(args.log).write_text(json.dumps(record, indent=1, sort_keys=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
