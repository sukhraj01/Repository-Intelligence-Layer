"""Write the counts-only run log of pilots E3 to E6. Thin wrapper over ``ril.analysis.e3_run_log``.

Usage: e3_run_log.py CACHE_DIR OUT_JSON EVAL_DIR=CONFIG [EVAL_DIR=CONFIG ...] [--extra FILE.json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ril.analysis.e3_run_log import cache_summary, eval_summary  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("cache_dir")
    ap.add_argument("out_json")
    ap.add_argument("evals", nargs="+")
    ap.add_argument("--extra", default=None)
    args = ap.parse_args()
    doc: dict[str, object] = {
        "experiment": "E-GRAPH-SIGNAL, E-GRAPH-WEIGHTS, E-RECENCY (E6 not run)",
        "date": "2026-10-18",
        "seed": 0,
        "caches": cache_summary(args.cache_dir),
        "evaluations": {},
    }
    ev = {}
    for item in args.evals:
        d, cfg = item.split("=", 1)
        ev[Path(d).name] = eval_summary(d, cfg)
    doc["evaluations"] = ev
    if args.extra:
        with open(args.extra, encoding="utf-8") as handle:
            doc.update(json.load(handle))
    with open(args.out_json, "w", encoding="utf-8") as handle:
        json.dump(doc, handle, indent=1, sort_keys=True)
        handle.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
