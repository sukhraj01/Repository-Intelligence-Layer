"""The snapshot the assembler reads: unit text from the parser. Implements ``specs/assembly.md``."""

from __future__ import annotations

from collections.abc import Iterable

from ril.assembly.assemble import UnitText, snapshot_of
from ril.parsing.code_unit import CodeUnit


def unit_text_of(unit: CodeUnit) -> UnitText:
    """The assembler's view of a parsed unit (its ``source`` as the parser produced it)."""
    return UnitText(
        unit_id=unit.id,
        file=unit.file,
        start_line=unit.start_line,
        end_line=unit.end_line,
        unit_type=unit.unit_type,
        qualified_name=unit.qualified_name,
        source=unit.source,
    )


def snapshot_from_units(units: Iterable[CodeUnit]) -> dict[str, UnitText]:
    """Index parsed units by id. Build them with ``class_source="header"`` (D102): the methods
    of a class are units of their own, so the class block carries no copy of them."""
    return snapshot_of(unit_text_of(u) for u in units)
