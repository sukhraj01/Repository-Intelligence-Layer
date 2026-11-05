"""Totals and shares of the A2b logs, written next to the tables they summarise (session A2b).

Usage: a_resolver_summary.py [--breakdown LOG] [--static LOG] [--dynamic LOG] --out SUMMARY.json
Reads stored logs only; nothing is rebuilt. The logic is in ``ril.bench.resolver_pilot.summary``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ril.bench.resolver_pilot import summary  # noqa: E402 (path set above)


def _load(path: str) -> dict[str, Any] | None:
    return json.loads(Path(path).read_text(encoding="utf-8")) if path else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--breakdown", default="")
    ap.add_argument("--static", default="")
    ap.add_argument("--dynamic", default="")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    record = {
        "experiment": "a2b-summary",
        "sources": {k: v for k, v in vars(args).items() if k != "out" and v},
        **summary(_load(args.breakdown), _load(args.static), _load(args.dynamic)),
    }
    Path(args.out).write_text(json.dumps(record, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
