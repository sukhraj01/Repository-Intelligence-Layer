"""Unit tests for the helper checks behind tests/leakage/ (leakage checks b, c and d)."""

from __future__ import annotations

from pathlib import Path

import pytest

from ril.training.leakage import (
    assert_distinct_encoders,
    find_patch_leak,
    forbidden_reachable,
    patch_lines,
)

PATCH = """--- a/mod.py
+++ b/mod.py
@@ -1,3 +1,3 @@
-    value = compute_the_old_thing(argument_one, argument_two)
+    value = compute_the_new_thing(argument_one, argument_two)
     return value
"""


def test_patch_lines_strip_markers_and_headers() -> None:
    assert patch_lines(PATCH) == [
        "value = compute_the_old_thing(argument_one, argument_two)",
        "value = compute_the_new_thing(argument_one, argument_two)",
    ]


def test_patch_text_in_query_is_detected() -> None:
    query = "The bug: value = compute_the_new_thing(argument_one,   argument_two) is wrong."
    assert find_patch_leak(query, PATCH) == [
        "value = compute_the_new_thing(argument_one, argument_two)"
    ]


def test_clean_query_and_short_lines_pass() -> None:
    assert find_patch_leak("Calling compute raises KeyError on empty input.", PATCH) == []
    assert find_patch_leak("return value", "-return value\n+return value\n") == []


def test_same_encoder_is_refused() -> None:
    with pytest.raises(ValueError):
        assert_distinct_encoders("Org/Model@abc", "org/model/")
    with pytest.raises(ValueError):
        assert_distinct_encoders("", "org/model")
    assert_distinct_encoders("org/pretrained", "org/trained")


def test_forbidden_reachability_detects_an_import(tmp_path: Path) -> None:
    pkg = tmp_path / "ril"
    (pkg / "training").mkdir(parents=True)
    (pkg / "evaluation").mkdir()
    for d in (pkg, pkg / "training", pkg / "evaluation"):
        (d / "__init__.py").write_text("")
    (pkg / "evaluation" / "metrics.py").write_text("X = 1\n")
    (pkg / "training" / "loader.py").write_text("from ril.evaluation import metrics\n")
    assert forbidden_reachable(tmp_path) == ["ril.evaluation", "ril.evaluation.metrics"]
    (pkg / "training" / "loader.py").write_text("import json\n")
    assert forbidden_reachable(tmp_path) == []
