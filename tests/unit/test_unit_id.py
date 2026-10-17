"""Unit tests for ril.parsing.unit_id (specs/code_unit.md decision D11)."""

import pytest

from ril.parsing.unit_id import (
    MODULE_UNIT_NAME,
    assign_ids,
    build_id,
    id_to_pool,
    parse_id,
    pool_to_id,
    unique,
)


def test_build_and_parse_round_trip() -> None:
    uid = build_id("auth.py", "TokenManager.verify_jwt")
    assert uid == "auth.py::TokenManager.verify_jwt"
    p = parse_id(uid)
    assert (p.file, p.qualified_name, p.ordinal) == ("auth.py", "TokenManager.verify_jwt", 1)


def test_ordinal_suffix_only_from_two() -> None:
    assert build_id("a/b.py", "f", 2) == "a/b.py::f#2"
    assert parse_id("a/b.py::f#3").ordinal == 3
    with pytest.raises(ValueError):
        build_id("a/b.py", "f", 0)
    with pytest.raises(ValueError):
        parse_id("a/b.py::f#1")


def test_assign_ids_is_ordinal_not_line_number() -> None:
    ids = assign_ids("m.py", ["f", "g", "f", "f", "C.f", "C.f"])
    assert ids == ["m.py::f", "m.py::g", "m.py::f#2", "m.py::f#3", "m.py::C.f", "m.py::C.f#2"]
    assert unique(ids)


def test_assign_ids_does_not_depend_on_what_precedes_a_unit_in_other_names() -> None:
    before = assign_ids("m.py", ["f", "f"])
    after = assign_ids("m.py", ["new_helper", "f", "f"])
    assert after[1:] == before  # an edit above shifts lines, never the ids


def test_module_unit_never_collides_with_a_definition() -> None:
    assert build_id("m.py", MODULE_UNIT_NAME) == "m.py::<module>"
    assert parse_id("m.py::<module>").is_module
    assert not parse_id("m.py::f").is_module


@pytest.mark.parametrize(
    "file",
    ["", "/abs.py", "a\\b.py", "a//b.py", "./a.py", "a/../b.py", "a::b.py"],
)
def test_bad_files_rejected(file: str) -> None:
    with pytest.raises(ValueError):
        build_id(file, "f")


@pytest.mark.parametrize("qual", ["", "1f", "a..b", "a b", "f#2", "a-b"])
def test_bad_qualified_names_rejected(qual: str) -> None:
    with pytest.raises(ValueError):
        build_id("m.py", qual)


@pytest.mark.parametrize("bad", ["", "m.py", "m.py::", "::f"])
def test_parse_rejects_non_ids(bad: str) -> None:
    with pytest.raises(ValueError):
        parse_id(bad)


def test_unicode_identifiers_are_allowed() -> None:
    assert parse_id(build_id("m.py", "Größe.wert")).qualified_name == "Größe.wert"


def test_pool_round_trip() -> None:
    uid = "src/pkg/mod.py::Outer.Inner.method"
    pool = id_to_pool(uid)
    assert pool == "src/pkg/mod.py/Outer/Inner/method"
    assert pool_to_id(pool) == uid
    assert pool_to_id("m.py/f") == "m.py::f"


def test_pool_form_drops_ordinal_and_maps_back_to_first_occurrence() -> None:
    assert id_to_pool("m.py::f#2") == "m.py/f"
    assert pool_to_id("m.py/f") == "m.py::f"
    assert pool_to_id("m.py/f", ordinal=2) == "m.py::f#2"


def test_pool_path_with_dotted_directory() -> None:
    assert pool_to_id("pkg.v2/sub/mod.py/C/m") == "pkg.v2/sub/mod.py::C.m"


def test_pool_module_unit() -> None:
    assert id_to_pool("m.py::<module>") == "m.py/<module>"


@pytest.mark.parametrize("bad", ["m.py", "noext/f", ""])
def test_pool_id_without_a_name_is_refused(bad: str) -> None:
    with pytest.raises(ValueError):
        pool_to_id(bad)


def test_unique_detects_duplicates() -> None:
    assert not unique(["a", "b", "a"])
