"""Label-noise readings: line kinds, span classes and the edited lines of a patch (pilot E2)."""

from __future__ import annotations

from ril.evaluation.label_noise import classify_span, edited_lines, line_kinds, span_overlaps

SRC = (
    '"""Module doc."""\n'  # 1
    "import os\n"  # 2
    "from a import (\n"  # 3
    "    b,\n"  # 4
    ")\n"  # 5
    "# a comment\n"  # 6
    "\n"  # 7
    "def f(x):\n"  # 8
    '    """Doc of f."""\n'  # 9
    "    return x\n"  # 10
)


def _cls(start: int, end: int, path: str = "m.py") -> str:
    return classify_span(path, line_kinds(SRC), SRC.splitlines(), start, end)


def test_line_kinds_find_imports_comments_and_docstrings() -> None:
    k = line_kinds(SRC)
    assert k.imports == {2, 3, 4, 5}
    assert k.comments == {6}
    assert k.docstrings == {1, 9}


def test_span_classes() -> None:
    assert _cls(2, 5) == "import_only"
    assert _cls(1, 7) == "import_only"  # docstring, imports, comment
    assert _cls(6, 7) == "comment_only"
    assert _cls(9, 9) == "comment_only"
    assert _cls(8, 10) == "other"
    assert _cls(2, 8) == "other"  # reaches into code
    assert classify_span("docs/x.rst", None, ["a"], 1, 1) == "docs_file"
    assert classify_span("conf.cfg", None, ["a"], 1, 1) == "other"


def test_unparseable_file_keeps_comment_detection_only() -> None:
    k = line_kinds("def broken(:\n# c\n")
    assert k.imports == frozenset() and k.comments == {2}


PATCH = (
    "diff --git a/pkg/a.py b/pkg/a.py\n"
    "--- a/pkg/a.py\n"
    "+++ b/pkg/a.py\n"
    "@@ -10,4 +10,5 @@ def f():\n"
    " ctx1\n"
    "-old line 11\n"
    "+new line\n"
    "+another new\n"
    " ctx2\n"
    "@@ -30,2 +31,3 @@\n"
    " ctx\n"
    "+pure insertion\n"
    " ctx\n"
    "diff --git a/new.py b/new.py\n"
    "--- /dev/null\n"
    "+++ b/new.py\n"
    "@@ -0,0 +1,2 @@\n"
    "+x\n"
    "+y\n"
)


def test_edited_lines_cover_changes_and_the_neighbours_of_pure_insertions() -> None:
    e = edited_lines(PATCH)
    assert set(e) == {"pkg/a.py"}  # the created file has no base lines
    assert e["pkg/a.py"] == {11, 30, 31}  # removed 11; insertion between old 30 and 31
    assert span_overlaps(e["pkg/a.py"], 25, 30) and not span_overlaps(e["pkg/a.py"], 12, 29)


def test_a_removed_line_that_looks_like_a_file_header_is_not_a_header() -> None:
    patch = "--- a/x.py\n+++ b/x.py\n@@ -1,2 +1,1 @@\n--- not a header\n keep\n"
    assert edited_lines(patch) == {"x.py": frozenset({1})}
