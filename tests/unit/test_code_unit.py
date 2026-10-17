"""Unit tests for ril.parsing.code_unit (specs/code_unit.md, FROZEN v1)."""

import json
from dataclasses import fields, replace
from typing import Any

import pytest

from ril.parsing.code_unit import (
    CODEUNIT_SCHEMA_VERSION,
    UNIT_TYPES,
    CodeUnit,
    canonical_json,
    units_from_jsonl,
    units_to_jsonl,
)


def make(**over: Any) -> CodeUnit:
    base: dict[str, Any] = {
        "id": "pkg/mod.py::Cls.meth",
        "repo_id": "owner/name",
        "language": "python",
        "file": "pkg/mod.py",
        "start_line": 10,
        "end_line": 12,
        "unit_type": "method",
        "name": "meth",
        "qualified_name": "Cls.meth",
        "signature": "def meth(self, x: int) -> int",
        "docstring": "Doc.",
        "source": "def meth(self, x: int) -> int:\n    return x\n",
        "calls": ["b", "a"],
        "called_by": [],
        "tests": [],
        "configs": [],
        "is_test": False,
        "loc": 2,
        "last_modified": "",
    }
    base.update(over)
    return CodeUnit(**base)


def test_schema_version_is_v1() -> None:
    assert CODEUNIT_SCHEMA_VERSION == "v1"


def test_fields_match_spec_in_order() -> None:
    assert [f.name for f in fields(CodeUnit)] == [
        "id", "repo_id", "language", "file", "start_line", "end_line", "unit_type", "name",
        "qualified_name", "signature", "docstring", "source", "calls", "called_by", "tests",
        "configs", "is_test", "loc", "last_modified",
    ]  # fmt: skip


@pytest.mark.parametrize("unit_type", ["function", "method", "class"])
def test_valid_unit_types(unit_type: str) -> None:
    assert make(unit_type=unit_type).unit_type == unit_type


def test_unit_types_are_exactly_the_frozen_enum() -> None:
    assert UNIT_TYPES == {"function", "method", "class", "module"}


def make_module(**over: Any) -> CodeUnit:
    base: dict[str, Any] = {
        "id": "pkg/mod.py::<module>",
        "unit_type": "module",
        "name": "<module>",
        "qualified_name": "<module>",
        "signature": "",
        "docstring": None,
        "start_line": 1,
        "end_line": 40,
        "is_test": False,
    }
    base.update(over)
    return make(**base)


def test_module_unit_is_valid_and_round_trips() -> None:
    u = make_module()
    assert CodeUnit.from_json(u.to_json()) == u


def test_module_type_and_module_name_must_agree() -> None:
    with pytest.raises(ValueError):
        make_module(qualified_name="f", id="pkg/mod.py::f")
    with pytest.raises(ValueError):
        make(unit_type="function", qualified_name="<module>", id="pkg/mod.py::<module>")


@pytest.mark.parametrize(
    "over",
    [
        {"end_line": 9},
        {"unit_type": "module"},
        {"unit_type": "package"},
        {"unit_type": ""},
        {"id": ""},
        {"id": "no-separator"},
        {"id": "other/file.py::Cls.meth"},
        {"id": "pkg/mod.py::Cls.other"},
        {"loc": -1},
        {"repo_id": "Owner/Name"},
        {"repo_id": "owner/name@abc123"},
        {"repo_id": "owner__name"},
        {"language": "rust"},
        {"last_modified": "2026-10-17"},
        {"last_modified": "2026-10-17T10:00:00+05:30"},
    ],
)
def test_validation_rejects(over: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        make(**over)


def test_last_modified_accepts_empty_and_utc_z() -> None:
    assert make(last_modified="").last_modified == ""
    assert make(last_modified="2026-10-17T10:00:00Z").last_modified == "2026-10-17T10:00:00Z"


def test_ordinal_suffixed_id_is_valid() -> None:
    assert make(id="pkg/mod.py::Cls.meth#2").id.endswith("#2")


def test_boundaries_accepted() -> None:
    assert make(start_line=5, end_line=5, loc=0).loc == 0


def test_validate_catches_mutation_after_construction() -> None:
    u = make()
    u.end_line = 1
    with pytest.raises(ValueError):
        u.validate()


def test_round_trip_dict_and_json() -> None:
    u = make()
    assert CodeUnit.from_dict(u.to_dict()) == u
    assert CodeUnit.from_json(u.to_json()) == u


def test_to_dict_does_not_alias_lists() -> None:
    u = make()
    u.to_dict()["calls"].append("z")
    assert u.calls == ["b", "a"]


def test_from_dict_rejects_missing_and_unknown_keys() -> None:
    d = make().to_dict()
    missing = {k: v for k, v in d.items() if k != "loc"}
    with pytest.raises(ValueError):
        CodeUnit.from_dict(missing)
    with pytest.raises(ValueError):
        CodeUnit.from_dict({**d, "extra": 1})


def test_docstring_none_differs_from_empty() -> None:
    none_u, empty_u = make(docstring=None), make(docstring="")
    assert none_u != empty_u
    assert json.loads(none_u.to_json())["docstring"] is None
    assert json.loads(empty_u.to_json())["docstring"] == ""
    assert CodeUnit.from_json(none_u.to_json()).docstring is None
    assert CodeUnit.from_json(empty_u.to_json()).docstring == ""


def test_unicode_source_round_trips_unescaped() -> None:
    src = 'def f():\n    return "héllo wörld, 日本語, \U0001f40d"\n'
    u = make(source=src)
    text = u.to_json()
    assert "日本語" in text and "\\u" not in text
    assert CodeUnit.from_json(text).source == src


def test_canonical_json_is_key_order_independent() -> None:
    d = make().to_dict()
    shuffled = dict(reversed(list(d.items())))
    assert canonical_json(d) == canonical_json(shuffled)
    assert list(json.loads(canonical_json(d))) == sorted(d)


def test_list_order_is_preserved_not_sorted() -> None:
    assert json.loads(make(calls=["b", "a"]).to_json())["calls"] == ["b", "a"]


def test_jsonl_round_trip() -> None:
    units = [
        make(),
        replace(make(), id="pkg/mod.py::Cls.x", qualified_name="Cls.x", name="x", docstring=None),
    ]
    assert units_from_jsonl(units_to_jsonl(units)) == units
    assert units_from_jsonl(b"") == []
