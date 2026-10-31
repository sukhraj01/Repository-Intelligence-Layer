"""List dangling links, paths and numbered references in the tracked documents.

Thin driver around ``ril.util.doc_check``. Exit status 0 when nothing dangles.

Usage: python -I scripts/check_docs.py
"""

# ruff: noqa: T201

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ril.util.doc_check import check_tree  # noqa: E402


def main() -> int:
    findings = check_tree(ROOT)
    for f in findings:
        print(f.render())
    print(f"{len(findings)} dangling reference(s)")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
