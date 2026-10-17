"""CodeUnit identifiers: the id builder and the converter to and from the pool form.

Implements ``specs/code_unit.md`` decision D11. A unit id is

    <repo-relative posix path>::<Qual.name>            first occurrence in the file
    <repo-relative posix path>::<Qual.name>#<n>        n-th occurrence, n >= 2

The suffix is an ordinal in source order, not a line number, so ids survive edits above a unit.
``Qual.name`` is dotted: ``Class.method``, ``Outer.Inner.method`` or ``function``. The residual
unit that holds the lines of a file outside every definition (decision D6) has the qualified name
``<module>``, which no Python identifier can equal, so it never collides with a definition.

The training pool (``gangiswag/train_data``, function level) writes the same unit as
``<path>/<Class>/<function>``: the qualified name split on dots and joined to the path with
slashes. Python identifiers contain no dots, so the path always ends at the last segment that
contains a dot (``.py``); everything after it is the qualified name. The pool form carries no
ordinal, so converting an id with a ``#n`` suffix to the pool form drops it, and converting a pool
id back gives the unsuffixed (first-occurrence) id.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

MODULE_UNIT_NAME = "<module>"
"""Qualified name of the residual per-file ``module`` unit (decision D6)."""

ID_SEPARATOR = "::"
_ORDINAL_RE = re.compile(r"^(?P<qual>.+?)#(?P<n>[0-9]+)$")
_IDENT_RE = re.compile(r"^[^\W\d]\w*$")


@dataclass(frozen=True)
class ParsedId:
    """The three parts of a unit id."""

    file: str
    qualified_name: str
    ordinal: int  # 1 for the first occurrence

    @property
    def is_module(self) -> bool:
        """True for the residual module unit of a file."""
        return self.qualified_name == MODULE_UNIT_NAME


def _check_file(file: str) -> None:
    if not file or file.startswith("/") or "\\" in file or ID_SEPARATOR in file:
        raise ValueError(f"file must be a non-empty repo-relative posix path, got {file!r}")
    if any(part in ("", ".", "..") for part in file.split("/")):
        raise ValueError(f"file has an empty or relative path component: {file!r}")


def _check_qualified_name(qual: str) -> None:
    if qual == MODULE_UNIT_NAME:
        return
    parts = qual.split(".")
    if not parts or not all(_IDENT_RE.match(p) for p in parts):
        raise ValueError(f"qualified name must be dotted identifiers or <module>, got {qual!r}")


def build_id(file: str, qualified_name: str, ordinal: int = 1) -> str:
    """Return the unit id for ``qualified_name`` in ``file``; ``ordinal`` >= 2 adds ``#n``."""
    _check_file(file)
    _check_qualified_name(qualified_name)
    if ordinal < 1:
        raise ValueError(f"ordinal must be >= 1, got {ordinal}")
    suffix = "" if ordinal == 1 else f"#{ordinal}"
    return f"{file}{ID_SEPARATOR}{qualified_name}{suffix}"


def parse_id(unit_id: str) -> ParsedId:
    """Inverse of :func:`build_id`. Raises ``ValueError`` for anything that is not a unit id."""
    file, sep, rest = unit_id.partition(ID_SEPARATOR)
    if not sep or not rest:
        raise ValueError(f"not a unit id (no '::'): {unit_id!r}")
    ordinal = 1
    m = _ORDINAL_RE.match(rest)
    if m:
        ordinal = int(m.group("n"))
        rest = m.group("qual")
        if ordinal < 2:
            raise ValueError(f"an ordinal suffix starts at #2, got {unit_id!r}")
    _check_file(file)
    _check_qualified_name(rest)
    return ParsedId(file=file, qualified_name=rest, ordinal=ordinal)


def assign_ids(file: str, qualified_names: Sequence[str]) -> list[str]:
    """Ids for the units of one file, given their qualified names in source order.

    The first occurrence of a name is unsuffixed; the second and later get ``#2``, ``#3``, ...
    (decision D11). The ordinal counts occurrences of the same qualified name only.
    """
    seen: dict[str, int] = {}
    ids: list[str] = []
    for qual in qualified_names:
        seen[qual] = seen.get(qual, 0) + 1
        ids.append(build_id(file, qual, seen[qual]))
    return ids


def id_to_pool(unit_id: str) -> str:
    """Convert a unit id to the pool form ``path/Class/function`` (the ordinal is dropped)."""
    p = parse_id(unit_id)
    return (
        "/".join([p.file, *p.qualified_name.split(".")])
        if not p.is_module
        else (f"{p.file}/{MODULE_UNIT_NAME}")
    )


def pool_to_id(pool_id: str, ordinal: int = 1) -> str:
    """Convert a pool id ``path/Class/function`` to a unit id.

    The path is everything up to and including the last segment that contains a dot; the rest is
    the qualified name. A pool id without a qualified name (a bare file) is refused.
    """
    segments = pool_id.split("/")
    last_dotted = max((i for i, s in enumerate(segments) if "." in s), default=-1)
    if last_dotted < 0 or last_dotted == len(segments) - 1:
        raise ValueError(
            f"pool id has no path ending in a dotted file name plus a name: {pool_id!r}"
        )
    file = "/".join(segments[: last_dotted + 1])
    qual = ".".join(segments[last_dotted + 1 :])
    return build_id(file, qual, ordinal)


def unique(ids: Iterable[str]) -> bool:
    """True if no id occurs twice (a parser invariant: ids are keys)."""
    seen: set[str] = set()
    for i in ids:
        if i in seen:
            return False
        seen.add(i)
    return True
