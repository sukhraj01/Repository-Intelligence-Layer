"""Patch parsing and hunk-to-unit mapping against hand-built fixtures (E-MINE-PILOT, M0 gate).

Each case states the old file, the new file and, written by hand, the unit ids that must be
positive. The patch is generated from the two texts with ``difflib`` in the compare endpoint's form.
"""

from __future__ import annotations

import pytest

from ril.data_mining.diff import (
    COMPARE_FILE_CAP,
    PatchError,
    parse_comparison,
    parse_patch,
)
from ril.data_mining.mapping import map_change
from tests.unit._mining_fixtures import compare_doc, file_entry, make_patch, units_of

BASE = """\
import os

LIMIT = 3


def helper(x):
    return x + 1


@register
def decorated(y):
    return y


class Widget:
    size = 3

    def area(self):
        return self.size * 2

    def perimeter(self):
        def inner(z):
            return z * 4
        return inner(self.size)


def tail():
    return 0
"""


def positives(tmp_path, old: str, new: str, status: str = "modified", **kw) -> set[str]:
    units = units_of(tmp_path, {"m.py": old})
    entry = file_entry(kw.get("filename", "m.py"), status, make_patch(old, new), kw.get("previous"))
    change = parse_comparison(compare_doc("a" * 40, "b" * 40, [entry])).files[0]
    return {h.unit.id for h in map_change(units, change).hits}


def test_function_modified(tmp_path) -> None:
    new = BASE.replace("return x + 1", "return x + 2")
    assert positives(tmp_path, BASE, new) == {"m.py::helper"}


def test_method_modified_not_its_class(tmp_path) -> None:
    new = BASE.replace("self.size * 2", "self.size * 3")
    assert positives(tmp_path, BASE, new) == {"m.py::Widget.area"}


def test_nested_function_belongs_to_enclosing_method(tmp_path) -> None:
    new = BASE.replace("return z * 4", "return z * 5")
    assert positives(tmp_path, BASE, new) == {"m.py::Widget.perimeter"}


def test_class_body_edit_is_the_class(tmp_path) -> None:
    new = BASE.replace("    size = 3", "    size = 4")
    assert positives(tmp_path, BASE, new) == {"m.py::Widget"}


def test_decorator_changed_and_decorator_added(tmp_path) -> None:
    changed = BASE.replace("@register\n", "@register(1)\n")
    assert positives(tmp_path, BASE, changed) == {"m.py::decorated"}
    added = BASE.replace("@register\n", "@other\n@register\n")
    assert positives(tmp_path, BASE, added) == {"m.py::decorated"}


def test_module_level_edit_is_the_module_unit(tmp_path) -> None:
    new = BASE.replace("LIMIT = 3", "LIMIT = 4")
    assert positives(tmp_path, BASE, new) == {"m.py::<module>"}


def test_statement_appended_to_method_body(tmp_path) -> None:
    new = BASE.replace(
        "        return inner(self.size)\n",
        "        return inner(self.size)\n        # tail\n        x = 1\n",
    )
    assert positives(tmp_path, BASE, new) == {"m.py::Widget.perimeter"}


def test_new_function_is_not_a_positive(tmp_path) -> None:
    new = BASE + "\n\ndef fresh():\n    return 1\n"
    units = units_of(tmp_path, {"m.py": BASE})
    entry = file_entry("m.py", "modified", make_patch(BASE, new))
    change = parse_comparison(compare_doc("a" * 40, "b" * 40, [entry])).files[0]
    mapping = map_change(units, change)
    assert mapping.hits == ()
    assert mapping.added_defs == ("fresh",)


def test_new_method_added_to_class_is_not_a_class_edit(tmp_path) -> None:
    new = BASE.replace(
        "        return self.size * 2\n",
        "        return self.size * 2\n\n    def extra(self):\n        return 1\n",
    )
    assert positives(tmp_path, BASE, new) == set()


def test_file_added_has_no_positive_but_counts_functions(tmp_path) -> None:
    units = units_of(tmp_path, {"m.py": BASE})
    new_src = "def one():\n    return 1\n\n\ndef two():\n    return 2\n"
    entry = file_entry("n.py", "added", make_patch("", new_src))
    change = parse_comparison(compare_doc("a" * 40, "b" * 40, [entry])).files[0]
    mapping = map_change([], change)
    assert mapping.hits == () and mapping.added_defs == ("one", "two")
    assert units  # the base file exists and is untouched


def test_file_deleted_touches_every_unit(tmp_path) -> None:
    units = units_of(tmp_path, {"m.py": BASE})
    entry = file_entry("m.py", "removed", make_patch(BASE, ""))
    change = parse_comparison(compare_doc("a" * 40, "b" * 40, [entry])).files[0]
    got = {h.unit.id for h in map_change(units, change).hits}
    assert got == {u.id for u in units}
    assert all(h.whole_file_deleted for h in map_change(units, change).hits)


def test_deleted_file_without_patch_text_still_maps(tmp_path) -> None:
    units = units_of(tmp_path, {"m.py": BASE})
    entry = file_entry("m.py", "removed", None, changes=40)
    comp = parse_comparison(compare_doc("a" * 40, "b" * 40, [entry]))
    assert not comp.files[0].patch_missing
    assert {h.unit.id for h in map_change(units, comp.files[0]).hits} == {u.id for u in units}


def test_rename_maps_through_the_old_path(tmp_path) -> None:
    units = units_of(tmp_path, {"m.py": BASE})
    new = BASE.replace("return x + 1", "return x + 2")
    entry = file_entry("pkg/n.py", "renamed", make_patch(BASE, new), previous="m.py")
    change = parse_comparison(compare_doc("a" * 40, "b" * 40, [entry])).files[0]
    assert change.old_path == "m.py"
    assert {h.unit.id for h in map_change(units, change).hits} == {"m.py::helper"}


def test_pure_rename_touches_nothing(tmp_path) -> None:
    units = units_of(tmp_path, {"m.py": BASE})
    entry = file_entry("n.py", "renamed", None, previous="m.py", changes=0)
    change = parse_comparison(compare_doc("a" * 40, "b" * 40, [entry])).files[0]
    assert not change.patch_missing and "renamed-only" in change.notes
    assert map_change(units, change).hits == ()


def test_binary_and_non_python_files_are_ignored() -> None:
    entries = [
        file_entry("logo.png", "modified", None, changes=0),
        file_entry("README.md", "modified", "@@ -1 +1 @@\n-a\n+b"),
    ]
    comp = parse_comparison(compare_doc("a" * 40, "b" * 40, entries))
    assert comp.python_files() == ()
    assert not any(f.patch_missing for f in comp.files)


def test_python_file_without_patch_is_flagged_missing() -> None:
    comp = parse_comparison(
        compare_doc("a" * 40, "b" * 40, [file_entry("big.py", "modified", None, changes=5000)])
    )
    assert comp.files[0].patch_missing


def test_huge_diff_maps_and_the_file_cap_is_flagged(tmp_path) -> None:
    body = "".join(f"    v{i} = {i}\n" for i in range(4000))
    old = f"def big():\n{body}\n\ndef other():\n    return 1\n"
    new_body = "".join(f"    v{i} = {i + 1}\n" for i in range(4000))
    new = f"def big():\n{new_body}\n\ndef other():\n    return 1\n"
    units = units_of(tmp_path, {"m.py": old})
    entry = file_entry("m.py", "modified", make_patch(old, new))
    change = parse_comparison(compare_doc("a" * 40, "b" * 40, [entry])).files[0]
    hits = map_change(units, change).hits
    assert {h.unit.id for h in hits} == {"m.py::big"}
    assert hits[0].removed_lines == 4000
    many = [
        file_entry(f"f{i}.py", "modified", "@@ -1 +1 @@\n-a\n+b") for i in range(COMPARE_FILE_CAP)
    ]
    assert parse_comparison(compare_doc("a" * 40, "b" * 40, many)).truncated


def test_hunk_lines_touched_counts_removed_and_inserted(tmp_path) -> None:
    new = BASE.replace(
        "        return self.size * 2\n", "        total = 1\n        return self.size * 2\n"
    )
    units = units_of(tmp_path, {"m.py": BASE})
    entry = file_entry("m.py", "modified", make_patch(BASE, new))
    change = parse_comparison(compare_doc("a" * 40, "b" * 40, [entry])).files[0]
    (hit,) = map_change(units, change).hits
    assert hit.unit.id == "m.py::Widget.area"
    assert (hit.removed_lines, hit.inserted_lines, hit.hunk_lines_touched) == (0, 1, 1)


def test_parse_patch_rejects_malformed_text() -> None:
    with pytest.raises(PatchError):
        parse_patch("not a hunk")
    with pytest.raises(PatchError):
        parse_patch("@@ -1,3 +1,3 @@\n a\n-b")  # ends inside the hunk
    with pytest.raises(PatchError):
        parse_comparison({"files": []})  # no merge base


def test_parse_patch_zero_length_old_range() -> None:
    fp = parse_patch("@@ -0,0 +1,2 @@\n+def a():\n+    pass")
    assert fp.removed == () and fp.insertions[0].after_old_line == 0
    assert fp.added_defs == ("a",)


def test_moved_function_is_not_counted_as_added() -> None:
    fp = parse_patch("@@ -1,2 +1,2 @@\n-def a():\n+def a():\n     pass")
    assert fp.added_defs == () and fp.removed_defs == ()
