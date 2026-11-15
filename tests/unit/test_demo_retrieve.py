"""The retriever demonstration on a toy repository (``docs/DEMO.md``)."""

from __future__ import annotations

import io
import re
from pathlib import Path

import numpy as np
import pytest

from ril.assembly.measure import snapshot_units
from ril.assembly.rq3_contexts import ContextSpec, build_instance, default_arms
from ril.assembly.tokens import ApproxTokenizer
from ril.bench import demo_retrieve as demo
from ril.evaluation.e3_prepare import unit_graph_arrays
from ril.parsing.build import BuildConfig, build_repository
from ril.retrieval.bm25_index import BM25Index, tokenize

ISSUE = "the parser drops the trailing comma when the header value is empty"
PATCH = """diff --git a/pkg/headers.py b/pkg/headers.py
--- a/pkg/headers.py
+++ b/pkg/headers.py
@@ -1,2 +1,2 @@
 def render_header(name, value):
-    return name + ': ' + value
+    return name + ': ' + (value or '')
"""
CFG = demo.DemoConfig(rrf_k=100, candidates=50, max_unit_tokens=200, budget=400)


def _repo(root: Path) -> None:
    (root / "pkg").mkdir()
    (root / "pkg" / "__init__.py").write_text("")
    (root / "pkg" / "headers.py").write_text(
        "def render_header(name, value):\n    return name + ': ' + value\n\n\n"
        "def parse_header(line):\n    name, _, value = line.partition(':')\n"
        "    return name, value\n"
    )
    (root / "pkg" / "parser.py").write_text(
        "def parse_comma_list(text):\n    return [p for p in text.split(',') if p]\n\n\n"
        "class Parser:\n    def run(self, header):\n        return parse_comma_list(header)\n"
    )
    (root / "pkg" / "other.py").write_text(
        "def unrelated():\n    return 1\n\n\ndef another():\n    return 2\n"
    )


def _stored_sha(root: Path, arm: str, dense: np.ndarray | None) -> str:
    """Context SHA-256 from the experiments' own builder (an independent route to the bytes)."""
    result = build_repository(str(root), BuildConfig(repo_id="o/r", with_history=False, seed=0))
    units, _, _, _ = unit_graph_arrays(result)
    bm25 = BM25Index(tokenize(u.source) for u in units).scores(tokenize(ISSUE))
    spec = ContextSpec((CFG.budget,), CFG.max_unit_tokens, CFG.candidates, CFG.rrf_k)
    meta = {"instance": "o__r-1", "repo_id": "o/r", "base_commit": "abc"}
    dmap = {} if dense is None else {"dense_L2": dense}
    rec = build_instance(
        meta,
        {"scores_L2": bm25},
        dmap,
        snapshot_units(str(root), "o/r"),
        spec,
        [a for a in default_arms(CFG.rrf_k) if a.name == arm],
        ApproxTokenizer(),
    )
    import hashlib

    return hashlib.sha256(rec["contexts"][f"{arm}|{CFG.budget}"]["context"].encode()).hexdigest()


def _run(
    root: Path, dense: np.ndarray | None, sha: dict[str, str] | None
) -> tuple[demo.Report, str]:
    inputs = demo.DemoInputs(
        instance="o__r-1",
        repo_id="o/r",
        base_commit="abc",
        issue=ISSUE,
        patch=PATCH,
        root=str(root),
        dense=dense,
        stored_sha256=sha,
        chosen_by="test",
    )
    buf = io.StringIO()
    pauses: list[int] = []
    report = demo.run_demo(inputs, CFG, buf, pause=lambda: pauses.append(1))
    assert len(pauses) == 6  # one wait before each stage
    return report, buf.getvalue()


def test_select_instance_fewest_units_ties_by_identifier() -> None:
    assert demo.select_instance({"b-2": 10, "a-1": 10, "c-3": 5, "d-4": 7}) == ("c-3", 5)
    assert demo.select_instance({"b-2": 10, "a-1": 10}) == ("a-1", 10)
    with pytest.raises(ValueError):
        demo.select_instance({})


def test_unit_counts_refuses_a_partial_set(tmp_path: Path) -> None:
    table = tmp_path / "t.csv"
    table.write_text("instance,units\na-1,10\n")
    assert demo.unit_counts(["a-1"], str(table), str(tmp_path)) == {"a-1": 10}
    with pytest.raises(FileNotFoundError):
        demo.unit_counts(["a-1", "b-2"], str(table), str(tmp_path))


def test_no_dense_run_prints_every_stage_and_matches_the_stored_context(tmp_path: Path) -> None:
    _repo(tmp_path)
    sha = _stored_sha(tmp_path, "bm25", None)
    report, text = _run(tmp_path, None, {"bm25": sha})
    headings = [ln for ln in text.splitlines() if ln.startswith("== ")]
    assert len(headings) == 6
    for title, line in zip(demo.STAGE_TITLES, headings, strict=True):
        assert line.startswith(f"== {title}")
    assert all(len(ln) <= demo.WIDTH for ln in text.splitlines())
    assert all(re.search(r"\[[0-9.]+ (s|ms)\]$", ln) for ln in headings if "skipped" not in ln)
    assert report.identity == "identical"
    assert report.context_sha256 == sha
    assert "SHA-256 equals the stored record: yes" in text
    assert report.gold and report.gold[0]["unit"].endswith("render_header")
    assert report.gold[0]["bm25"] >= 1 and report.gold[0]["dense"] is None
    assert "This is one illustrative instance" in text


def test_identity_check_reports_a_difference_and_a_missing_record(tmp_path: Path) -> None:
    _repo(tmp_path)
    report, text = _run(tmp_path, None, {"bm25": "0" * 64})
    assert report.identity == "different"
    assert "equals the stored record: NO" in text
    report2, text2 = _run(tmp_path, None, {})
    assert report2.identity == "no stored context"
    assert "nothing to compare" in text2


def test_dense_run_fuses_and_assembles_the_rrf_arm(tmp_path: Path) -> None:
    _repo(tmp_path)
    result = build_repository(str(tmp_path), BuildConfig(repo_id="o/r", with_history=False, seed=0))
    n = len(unit_graph_arrays(result)[0])
    dense = np.random.default_rng(0).random(n)
    sha = _stored_sha(tmp_path, "rrf", dense)
    report, text = _run(tmp_path, dense, {"rrf": sha})
    assert report.identity == "identical"
    assert "reciprocal rank fusion, k = 100" in text
    assert report.gold[0]["dense"] is not None and report.gold[0]["fusion"] is not None
    assert "same-file" in text


def test_wrong_dense_length_is_an_error(tmp_path: Path) -> None:
    _repo(tmp_path)
    with pytest.raises(ValueError, match="dense scores"):
        _run(tmp_path, np.zeros(3), None)


def test_same_file_list_puts_seeds_first_and_keeps_every_unit_once() -> None:
    order = np.asarray([4, 0, 3, 1, 2, 5])
    file_of_unit = np.asarray([0, 0, 1, 1, 2, 2])
    full, infile = demo.expanded_list(order, file_of_unit, 2, 3)
    assert full[:2] == [4, 0]
    assert sorted(full) == [0, 1, 2, 3, 4, 5]
    assert infile == {5, 1}
