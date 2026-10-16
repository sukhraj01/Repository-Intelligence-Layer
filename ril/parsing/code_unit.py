"""The CodeUnit: the only data type shared across component boundaries.

Implements ``specs/code_unit.md`` (DRAFT v0, not frozen) and
``docs/09_architecture.md`` ("The CodeUnit"). Fields, names and types follow the spec
field for field. The meaning of several fields (what ``calls`` holds, the ``id`` format,
the ``repo_id`` form, ``is_test`` rule, ...) is deliberately not fixed here: those are the
open questions listed in the spec, and this module stores whatever strings it is given.

Serialization is canonical: keys sorted, compact separators, UTF-8 without ASCII escaping,
list order preserved exactly as given (the producer is responsible for a stable order), so
that identical units always serialize to identical bytes.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from typing import Any

CODEUNIT_SCHEMA_VERSION = "v0-draft"
"""Recorded with every index (``specs/code_unit.md``, "Settled")."""

UNIT_TYPES: frozenset[str] = frozenset({"function", "method", "class"})

_LIST_FIELDS = ("calls", "called_by", "tests", "configs")


@dataclass
class CodeUnit:
    """One function, method or class of a repository, per ``specs/code_unit.md``."""

    # identity
    id: str
    repo_id: str
    language: str

    # location
    file: str
    start_line: int
    end_line: int

    # structure
    unit_type: str
    name: str
    qualified_name: str
    signature: str
    docstring: str | None

    # content
    source: str

    # relationships
    calls: list[str]
    called_by: list[str]
    tests: list[str]
    configs: list[str]

    # metadata
    is_test: bool
    loc: int
    last_modified: str

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Raise ``ValueError`` if the unit breaks a rule stated in the spec."""
        if not self.id:
            raise ValueError("id must be non-empty")
        if self.unit_type not in UNIT_TYPES:
            raise ValueError(f"unit_type {self.unit_type!r} not in {sorted(UNIT_TYPES)}")
        if self.end_line < self.start_line:
            raise ValueError(f"end_line {self.end_line} < start_line {self.start_line}")
        if self.loc < 0:
            raise ValueError(f"loc must be >= 0, got {self.loc}")

    def to_dict(self) -> dict[str, Any]:
        """Plain-dict form (lists copied so the caller cannot mutate the unit through it)."""
        d = asdict(self)
        for name in _LIST_FIELDS:
            d[name] = list(d[name])
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CodeUnit:
        """Inverse of :meth:`to_dict`. Missing or unknown keys are an error (no silent drift)."""
        expected = {f.name for f in fields(cls)}
        got = set(data)
        if got != expected:
            raise ValueError(
                f"CodeUnit keys mismatch: missing={sorted(expected - got)} "
                f"unknown={sorted(got - expected)}"
            )
        kwargs = dict(data)
        for name in _LIST_FIELDS:
            kwargs[name] = list(kwargs[name])
        return cls(**kwargs)

    def to_json(self) -> str:
        """Canonical JSON text for this unit."""
        return canonical_json(self.to_dict())

    @classmethod
    def from_json(cls, text: str) -> CodeUnit:
        return cls.from_dict(json.loads(text))


def canonical_json(obj: Any) -> str:
    """Deterministic JSON: sorted keys, compact separators, no ASCII escaping."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def units_to_jsonl(units: list[CodeUnit]) -> bytes:
    """One canonical JSON object per line, UTF-8, in the order given."""
    return "".join(u.to_json() + "\n" for u in units).encode("utf-8")


def units_from_jsonl(data: bytes) -> list[CodeUnit]:
    """Inverse of :func:`units_to_jsonl`."""
    return [CodeUnit.from_json(line) for line in data.decode("utf-8").splitlines() if line]
