"""Locating chunk text in a snapshot and mapping spans to units (decisions D6, D7)."""

from __future__ import annotations

from pathlib import Path

from ril.evaluation.chunk_mapping import (
    LineIndex,
    locate_chunk,
    map_span,
    non_python_kind,
    positive_kind,
    prefix_span,
    wave1_style_category,
)
from ril.parsing.build import BuildConfig, build_repository

SOURCE = (
    "import os\n"  # 1
    "\n"  # 2
    "X = 1\n"  # 3
    "\n"  # 4
    "\n"  # 5
    "def alpha(x):\n"  # 6
    "    def inner():\n"  # 7
    "        return 1\n"  # 8
    "    return inner() + x\n"  # 9
    "\n"  # 10
    "\n"  # 11
    "class K:\n"  # 12
    '    """doc"""\n'  # 13
    "    attr = 2\n"  # 14
    "\n"  # 15
    "    def m1(self):\n"  # 16
    "        return alpha(1)\n"  # 17
    "\n"  # 18
    "    def m2(self):\n"  # 19
    "        return self.m1()\n"  # 20
    "\n"  # 21
    "Y = 2\n"  # 22
)


def _units(tmp_path: Path) -> list:  # type: ignore[type-arg]
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "a.py").write_text(SOURCE, encoding="utf-8")
    result = build_repository(str(tmp_path), BuildConfig(repo_id="acme/mini", with_history=False))
    return [u for u in result.parsed.units if u.file == "pkg/a.py"]


def test_exact_match_reports_one_location_and_its_lines() -> None:
    files = {"pkg/a.py": SOURCE}
    res = locate_chunk("def alpha(x):\n    def inner():\n        return 1\n", files)
    assert (res.status, res.tier, res.n_locations) == ("found", "exact", 1)
    loc = res.locations[0]
    assert (loc.path, loc.start_line, loc.end_line) == ("pkg/a.py", 6, 8)


def test_trimmed_tier_ignores_surrounding_whitespace() -> None:
    files = {"pkg/a.py": SOURCE}
    res = locate_chunk("\n\n  X = 1  \n\n", files)
    assert (res.status, res.tier) == ("found", "trimmed")
    assert (res.locations[0].start_line, res.locations[0].end_line) == (3, 3)


def test_line_endings_tier_and_line_numbers_with_crlf() -> None:
    crlf = SOURCE.replace("\n", "\r\n")
    res = locate_chunk("def m1(self):\n        return alpha(1)", {"pkg/a.py": crlf})
    assert (res.status, res.tier) == ("found", "eol_normalised")
    loc = res.locations[0]
    assert (loc.start_line, loc.end_line) == (16, 17)
    assert crlf[loc.start : loc.end].startswith("def m1")
    assert crlf[loc.start : loc.end].endswith("alpha(1)")


def test_whitespace_different_chunk_is_found_at_the_last_tier() -> None:
    """Adversarial: tabs, a reflowed line break and doubled blanks; same tokens, other layout."""
    chunk = "def\talpha(x):\n\n   def inner():   return 1\n  return inner() + x"
    res = locate_chunk(chunk, {"pkg/a.py": SOURCE})
    assert (res.status, res.tier, res.n_locations) == ("found", "whitespace_normalised", 1)
    loc = res.locations[0]
    assert (loc.start_line, loc.end_line) == (6, 9)
    assert SOURCE[loc.start : loc.end].startswith("def alpha")
    assert SOURCE[loc.start : loc.end].endswith("inner() + x")


def test_text_in_two_files_and_twice_in_one_file_is_reported_with_every_location() -> None:
    body = "def gamma():\n    return 3\n"
    files = {"a.py": body + "\n" + body, "b.py": "x = 1\n" + body}
    res = locate_chunk(body, files)
    assert (res.status, res.n_locations) == ("found", 3)
    assert [loc.path for loc in res.locations] == ["a.py", "a.py", "b.py"]
    assert [loc.start_line for loc in res.locations] == [1, 4, 2]


def test_not_found_names_a_reason() -> None:
    files = {"pkg/a.py": SOURCE}
    partial = locate_chunk(
        "def alpha(x):\n    return inner() + x\n    return something_else_entirely(x, y, z)\n",
        files,
    )
    assert (partial.status, partial.reason) == ("not_found", "partial_text_present")
    absent = locate_chunk("completely unrelated text that is long enough\n", files)
    assert absent.reason == "no_line_present"
    assert locate_chunk("short\n", files).reason == "no_line_long_enough_to_test"
    empty = locate_chunk("  \n\n", files)
    assert (empty.status, empty.reason) == ("empty", "empty-chunk")


def test_line_index_counts_all_three_line_endings() -> None:
    idx = LineIndex("a\r\nb\rc\nd")
    assert [idx.line_of(i) for i in range(8)] == [1, 1, 1, 2, 2, 3, 3, 4]


def test_map_span_categories(tmp_path: Path) -> None:
    units = _units(tmp_path)
    one = map_span(units, 17, 17)
    assert (one.category, one.primary_type) == ("one_unit", "method")
    assert one.units == ("pkg/a.py::K.m1",)
    nested = map_span(units, 7, 8)  # inside the nested def: folds into the parent
    assert nested.units == ("pkg/a.py::alpha",) and nested.category == "one_unit"
    several = map_span(units, 17, 20)
    assert several.category == "several_units" and len(several.units) == 2
    cls = map_span(units, 13, 14)
    assert (cls.category, cls.units) == ("class_only", ("pkg/a.py::K",))
    mod = map_span(units, 1, 3)
    assert (mod.category, mod.units) == ("module_residual", ("pkg/a.py::<module>",))
    straddle = map_span(units, 3, 7)  # residual line 3 plus a function: leaf wins, flag is kept
    assert straddle.category == "one_unit" and straddle.overlaps_residual
    assert map_span(units, 4, 5).category == "module_residual"  # blank lines outside any definition
    assert map_span([], 1, 2).category == "none"


def test_wave1_rule_counts_nested_definitions_as_leaf_units() -> None:
    assert wave1_style_category(SOURCE, 7, 9) == "two_plus_leaf_units"
    assert wave1_style_category(SOURCE, 17, 17) == "one_leaf_unit"
    assert wave1_style_category(SOURCE, 13, 14) == "class_only"
    assert wave1_style_category(SOURCE, 1, 3) == "zero_units"
    assert wave1_style_category("def broken(:\n", 1, 1) == "unparseable"


def test_prefix_span_covers_only_the_leading_characters() -> None:
    res = locate_chunk(SOURCE, {"pkg/a.py": SOURCE})
    loc = res.locations[0]
    first, last = prefix_span(loc, SOURCE, 30)
    assert (first, last) == (1, 6)


def test_kinds(tmp_path: Path) -> None:
    units = _units(tmp_path)
    parsed = {"pkg/a.py", "tests/test_x.py"}
    assert positive_kind("pkg/a.py", map_span(units, 17, 17), parsed) == "method"
    assert positive_kind("pkg/a.py", map_span(units, 6, 6), parsed) == "function"
    assert positive_kind("pkg/a.py", map_span(units, 13, 13), parsed) == "class"
    assert positive_kind("pkg/a.py", map_span(units, 1, 1), parsed) == "module_residual"
    assert positive_kind("tests/test_x.py", map_span(units, 17, 17), parsed) == "test_unit"
    assert positive_kind("pkg/other.py", map_span(units, 17, 17), parsed) == "python_not_parsed"
    assert positive_kind("docs/a.rst", map_span(units, 17, 17), parsed) == "non_python_docs"
    assert positive_kind("pkg/a.py", None, parsed) == "unmatched"
    assert non_python_kind("setup.cfg") == "non_python_config"
    assert non_python_kind("data/x.csv") == "non_python_data"
