"""Unit tests for ril.parsing.repository_parser (specs/parse_one_repo.md, specs/code_unit.md)."""

from pathlib import Path

import pytest

from ril.parsing.repository_parser import (
    ParseOptions,
    discover_python_files,
    module_names,
    parse_repository,
    split_lines,
)


def test_skip_rules_are_applied_and_counted(mini_repo: Path) -> None:
    paths, skipped, skipped_files = discover_python_files(str(mini_repo))
    assert "pkg/__pycache__/skipme.py" not in paths
    assert "pkg/vendor/lib.py" not in paths
    assert "pkg/gen_pb2.py" not in paths
    assert skipped["dir:cache-or-build"] == 1
    assert skipped["dir:vendored"] == 1
    assert ("pkg/gen_pb2.py", "generated") in skipped_files


def test_unparseable_file_is_listed_not_dropped(mini_repo: Path) -> None:
    parsed = parse_repository(str(mini_repo), "acme/mini")
    assert [p for p, _ in parsed.unparseable] == ["pkg/broken.py"]
    assert "pkg/broken.py" not in parsed.files


def test_units_for_nested_decorated_and_inherited_definitions(mini_repo: Path) -> None:
    parsed = parse_repository(str(mini_repo), "acme/mini")
    units = parsed.unit_by_id()
    # nested def folds into its parent: no unit for ``inner``
    assert "pkg/core.py::helper" in units
    assert not any(u.name == "inner" for u in parsed.units)
    # methods and the decorated property are units; the decorator is inside the span
    size = units["pkg/core.py::Engine.size"]
    assert size.unit_type == "method"
    assert size.end_line - size.start_line == 2  # decorator, def and return lines
    assert size.source.startswith("    @property")
    assert units["pkg/core.py::Engine"].signature == "class Engine(Base)"
    # every unit satisfies the schema validation
    for u in parsed.units:
        u.validate()


def test_module_unit_holds_residual_lines(mini_repo: Path) -> None:
    parsed = parse_repository(str(mini_repo), "acme/mini")
    mod = parsed.unit_by_id()["pkg/util.py::<module>"]
    assert mod.unit_type == "module"
    assert mod.docstring == "Utilities."
    assert "def fmt" not in mod.source
    assert '"""Utilities."""' in mod.source
    assert mod.start_line == 1


def test_collision_ordinals_follow_source_order(mini_repo: Path) -> None:
    parsed = parse_repository(str(mini_repo), "acme/mini")
    ids = [u.id for u in parsed.units if u.name == "twice"]
    assert ids == ["pkg/core.py::twice", "pkg/core.py::twice#2"]
    assert parsed.id_collisions >= 1


def test_class_source_header_option(mini_repo: Path) -> None:
    full = parse_repository(str(mini_repo), "acme/mini").unit_by_id()["pkg/core.py::Engine"]
    head = parse_repository(
        str(mini_repo), "acme/mini", options=ParseOptions(class_source="header")
    ).unit_by_id()["pkg/core.py::Engine"]
    assert head.source == "class Engine(Base):"
    assert len(full.source) > len(head.source)
    with pytest.raises(ValueError):
        ParseOptions(class_source="nope")


def test_is_test_and_last_modified(mini_repo: Path) -> None:
    parsed = parse_repository(
        str(mini_repo), "acme/mini", last_modified={"pkg/util.py": "2020-01-02T03:04:05Z"}
    )
    units = parsed.unit_by_id()
    assert units["tests/test_core.py::test_run"].is_test is True
    assert units["pkg/util.py::fmt"].last_modified == "2020-01-02T03:04:05Z"
    assert units["pkg/core.py::helper"].last_modified == ""


def test_module_names_follow_package_chain() -> None:
    names, is_pkg, collisions = module_names(
        ["src/flask/__init__.py", "src/flask/app.py", "tests/test_basic.py", "setup.py"]
    )
    assert names["src/flask/app.py"] == "flask.app"
    assert names["src/flask/__init__.py"] == "flask"
    assert is_pkg["src/flask/__init__.py"] is True
    assert names["tests/test_basic.py"] == "test_basic"
    assert collisions == []


def test_split_lines_counts_like_the_tokenizer() -> None:
    assert split_lines("a\r\nb\rc\n") == ["a", "b", "c"]
    assert split_lines("a\x0cb\n") == ["a\x0cb"]  # form feed is not a line break for ast
    assert split_lines("") == []
