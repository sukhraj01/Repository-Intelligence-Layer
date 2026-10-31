"""Scan a branch's added lines for shortcuts; exit non-zero on a blocking finding.

Thin driver around ``ril.util.review_flags`` (rules and limits: docs/REVIEW.md).

Usage: python scripts/review_flags.py [--base main] [--head HEAD] [--no-numbers]
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ril.util.review_flags import main  # noqa: E402  # path is set on the line above

if __name__ == "__main__":
    sys.exit(main())
