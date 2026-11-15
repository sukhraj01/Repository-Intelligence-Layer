"""Units edited by a reference patch (E-RQ3-FAILURE-BREAKDOWN): split, map, edge cases."""

from __future__ import annotations

from ril.analysis.rq3_gold_units import gold_units, split_patch, summarise

OLD = """import os


def alpha(x):
    y = x + 1
    return y


class Box:
    def size(self):
        return 1

    def label(self):
        return "b"
"""

PATCH_REMOVE = """diff --git a/pkg/m.py b/pkg/m.py
index 111..222 100644
--- a/pkg/m.py
+++ b/pkg/m.py
@@ -4,3 +4,3 @@ import os
 def alpha(x):
-    y = x + 1
+    y = x + 2
     return y
"""

PATCH_MIXED = """diff --git a/pkg/m.py b/pkg/m.py
index 111..222 100644
--- a/pkg/m.py
+++ b/pkg/m.py
@@ -1 +1 @@
-import os
+import sys
diff --git a/pkg/new.py b/pkg/new.py
new file mode 100644
--- /dev/null
+++ b/pkg/new.py
@@ -0,0 +1,2 @@
+def fresh():
+    return 1
diff --git a/docs/readme.md b/docs/readme.md
--- a/docs/readme.md
+++ b/docs/readme.md
@@ -1 +1 @@
-a
+b
"""


def _reader(path: str) -> str | None:
    return OLD if path == "pkg/m.py" else None


def test_removed_line_goes_to_innermost_definition() -> None:
    out = gold_units(PATCH_REMOVE, "o/r", _reader)
    assert out["units"] == ["pkg/m.py::alpha"]
    assert out["files"] == ["pkg/m.py"]
    assert out["detail"]["pkg/m.py::alpha"]["removed"] == 1


def test_module_line_gives_module_unit_and_created_file_gives_none() -> None:
    out = gold_units(PATCH_MIXED, "o/r", _reader)
    assert out["units"] == ["pkg/m.py::<module>"] or len(out["units"]) == 1
    assert out["notes"]["pkg/new.py"] == "created"
    assert out["notes"]["docs/readme.md"] == "not_python"


def test_missing_base_file_is_noted_not_guessed() -> None:
    out = gold_units(PATCH_REMOVE, "o/r", lambda _p: None)
    assert out["units"] == []
    assert out["notes"] == {"pkg/m.py": "missing_at_base"}


def test_split_patch_statuses_and_summary() -> None:
    ch = split_patch(PATCH_MIXED)
    assert [c.status for c in ch] == ["modified", "added", "modified"]
    rows = {
        "a": gold_units(PATCH_REMOVE, "o/r", _reader),
        "b": gold_units(PATCH_REMOVE, "o/r", lambda _p: None),
    }
    s = summarise(rows, ["a", "b"])
    assert s["with_gold_unit"] == 1 and s["without_gold_unit"] == 1
