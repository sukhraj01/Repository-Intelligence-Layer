"""The sealed-order guard of the final evaluation sets: one function, called by every reader.

Implements D100 (``docs/RQ2_PROTOCOL.md`` section 11): the eight evaluation repositories and the
executable 377 are read only after a named dev analysis. Both the analysis module
(``ril.analysis.rq2_final``) and the final-sets scoring (``ril.evaluation.final_sets``) and the
converter of the scoring results (``ril.evaluation.final_rows``) call :func:`require_dev_analysis`
here; a test fails if any of them carries its own copy of the check or bypasses this one
(``tests/unit/test_sealed_order.py``).
"""

from __future__ import annotations

import re
from pathlib import Path

_ENTRY_ID = re.compile(r"^E-[A-Z0-9]+(?:-[A-Z0-9]+)*$")


class SealedOrderError(ValueError):
    """A final evaluation set was read without naming the dev analysis that precedes it (D100)."""


def require_dev_analysis(entry_id: str | None, docs_root: Path | None = None) -> str:
    """The id of the dev-analysis entry that precedes a look at the final sets, validated (D100).

    The id must have the form of an experiment entry id and, when ``docs_root`` is given, must be a
    registry row of ``docs/EXPERIMENTS.md`` or ``docs/experiments/*.md``.
    """
    if not entry_id or not _ENTRY_ID.match(entry_id):
        raise SealedOrderError(
            "the final evaluation sets are sealed: give the id of the dev-analysis entry that "
            "precedes them (D100)"
        )
    if docs_root is not None:
        files = [
            docs_root / "docs" / "EXPERIMENTS.md",
            *sorted((docs_root / "docs").glob("experiments/*.md")),
        ]
        needle = f"| {entry_id} |"
        if not any(f.exists() and needle in f.read_text(encoding="utf-8") for f in files):
            raise SealedOrderError(
                f"dev-analysis entry {entry_id} is not in the experiment registry"
            )
    return entry_id
