"""Parse a repository checkout, build its graph, print ten CodeUnits and the statistics.

Usage: parse_repo.py PATH --repo-id owner/name --seed N [--out DIR] [--stats-json FILE]
A thin wrapper: the logic is in ``ril.parsing``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ril.parsing.build import BuildConfig, build_repository, write_artifacts  # noqa: E402
from ril.parsing.report import build_stats, select_units, unit_summary  # noqa: E402
from ril.util.seed import set_seed  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("path")
    ap.add_argument("--repo-id", required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--out", default="")
    ap.add_argument("--stats-json", default="")
    ap.add_argument("--class-source", default="full", choices=("full", "header"))
    ap.add_argument("--no-history", action="store_true")
    args = ap.parse_args()
    set_seed(args.seed)
    cfg = BuildConfig(
        repo_id=args.repo_id,
        class_source=args.class_source,
        with_history=not args.no_history,
        seed=args.seed,
    )
    result = build_repository(args.path, cfg)
    stats = build_stats(result)
    stats["config_hash"] = cfg.config_hash()
    stats["seed"] = args.seed
    if args.out:
        stats["artifact_sha256"] = write_artifacts(result, args.out)
    out = sys.stdout
    out.write(f"== ten CodeUnits (seed {args.seed}) ==\n")
    for u in select_units(result.parsed.units, args.seed):
        out.write(json.dumps(unit_summary(u), indent=1, ensure_ascii=False, sort_keys=True) + "\n")
    out.write("== statistics ==\n")
    out.write(json.dumps(stats, indent=1, sort_keys=True, default=dict) + "\n")
    if args.stats_json:
        Path(args.stats_json).write_text(
            json.dumps(stats, indent=1, sort_keys=True, default=dict) + "\n", encoding="utf-8"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
