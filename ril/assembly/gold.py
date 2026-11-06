"""Is the gold in the context? Implements ``specs/assembly.md`` ("Gold in context").

The retrieval-versus-reasoning split of RQ3 (``docs/02_research_questions.md``): an instance whose
gold is absent from the context failed in retrieval or assembly; one whose gold is present and
unresolved failed in reasoning (or in the edit).
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass

from ril.assembly.assemble import Manifest


@dataclass(frozen=True)
class GoldInContext:
    """Counts of gold units and gold files found in a context.

    A gold file is in the context when at least one included unit lies in it. A gold unit is in
    the context when it is included (``units_intact`` counts those not cut by the unit cap).
    """

    n_units: int
    units_in: int
    units_intact: int
    n_files: int
    files_in: int

    @property
    def unit_share(self) -> float:
        return self.units_in / self.n_units if self.n_units else float("nan")

    @property
    def file_share(self) -> float:
        return self.files_in / self.n_files if self.n_files else float("nan")

    @property
    def no_gold_file(self) -> bool:
        """True when gold exists and none of its files is in the context."""
        return self.n_files > 0 and self.files_in == 0


def gold_in_context(
    manifest: Manifest, gold_units: Collection[str], gold_files: Collection[str]
) -> GoldInContext:
    """Compare the manifest with the gold unit ids and gold file paths (duplicates ignored)."""
    units = set(gold_units)
    files = set(gold_files)
    included = {e.unit_id: e for e in manifest.entries}
    hit = [u for u in units if u in included]
    intact = [u for u in hit if not included[u].truncated]
    return GoldInContext(
        n_units=len(units),
        units_in=len(hit),
        units_intact=len(intact),
        n_files=len(files),
        files_in=len(files & manifest.files()),
    )
