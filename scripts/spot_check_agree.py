"""Score a second reader's spot-check answers against the first reader's key.

Usage: python -I scripts/spot_check_agree.py ANSWERS.csv [--key data/review/spot_check_key.json]
ANSWERS.csv has the header ``item,label`` (label: correct, incorrect or unclear). Prints raw
agreement, Cohen's kappa, the confusion table and the disagreements as JSON. A thin wrapper around
``ril.evaluation.spot_check``.
"""

# ruff: noqa: T201

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ril.evaluation.spot_check import agreement, read_answers  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("answers", type=Path)
    ap.add_argument("--key", type=Path, default=ROOT / "data/review/spot_check_key.json")
    args = ap.parse_args()
    key = json.loads(args.key.read_text(encoding="utf-8"))
    report = agreement(key["items"], read_answers(args.answers))
    report["seed"] = key.get("seed")
    print(json.dumps(report, indent=2))
    return 0 if report.get("n_answered") else 1


if __name__ == "__main__":
    raise SystemExit(main())
