"""The CodeUnit: the only data type shared across component boundaries.

Implements ``specs/code_unit.md`` (FROZEN v1) and ``docs/09_architecture.md`` ("The
CodeUnit"). Fields, names and types follow the spec field for field. The meaning of the
fields is fixed by the spec's decision log: ``id`` is built by ``ril.parsing.unit_id`` (D11),
``repo_id`` by ``ril.parsing.repo_id`` (D5), ``is_test`` by ``ril.parsing.path_rules`` (D9),
and ``calls`` / ``called_by`` / ``tests`` / ``configs`` hold resolved unit ids only (D4).
Changing any field needs an ADR, a version bump and a re-index plan.

Serialization is canonical: keys sorted, compact separators, UTF-8 without ASCII escaping,
list order preserved exactly as given (the producer is responsible for a stable order), so
that identical units always serialize to identical bytes.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, fields
from typing import Any

from ril.parsing.repo_id import is_normalized_repo_id
from ril.parsing.unit_id import MODULE_UNIT_NAME, parse_id

CODEUNIT_SCHEMA_VERSION = "v1"
"""Recorded with every index (``specs/code_unit.md``, "Settled")."""

LANGUAGES: frozenset[str] = frozenset({"python"})
"""The project is Python only."""

_LAST_MODIFIED_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

UNIT_TYPES: frozenset[str] = frozenset({"function", "method", "class", "module"})

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
        parsed = parse_id(self.id)
        if parsed.file != self.file or parsed.qualified_name != self.qualified_name:
            raise ValueError(
                f"id {self.id!r} does not match file {self.file!r} and "
                f"qualified_name {self.qualified_name!r}"
            )
        if not is_normalized_repo_id(self.repo_id):
            raise ValueError(f"repo_id must be a case-folded owner/name, got {self.repo_id!r}")
        if self.language not in LANGUAGES:
            raise ValueError(f"language {self.language!r} not in {sorted(LANGUAGES)}")
        if self.last_modified and not _LAST_MODIFIED_RE.match(self.last_modified):
            raise ValueError(
                f"last_modified must be '' or YYYY-MM-DDTHH:MM:SSZ, got {self.last_modified!r}"
            )
        if (self.unit_type == "module") != (self.qualified_name == MODULE_UNIT_NAME):
            raise ValueError("unit_type 'module' and qualified_name '<module>' go together")
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
