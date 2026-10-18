"""Tests for the function-hash probe (ril.training.contamination, contamination_index)."""

from __future__ import annotations

import gzip
import json
import subprocess
import zlib
from pathlib import Path

import pytest

from ril.training import contamination as cm
from ril.training import contamination_index as ci

FUNC = '''def add(a, b):
    """Add two numbers."""
    # comment
    total = a + b
    return total
'''


def test_text_hash_ignores_layout_not_content() -> None:
    reformatted = "\r\n".join(
        [
            "def add(a, b):  ",
            '    """Add two numbers."""',
            "",
            "    # comment",
            "    total = a + b",
            "    return total",
            "",
        ]
    )
    indented = "\n".join("    " + ln if ln else ln for ln in FUNC.split("\n"))
    assert cm.text_hash(FUNC) == cm.text_hash(reformatted) == cm.text_hash(indented)
    assert cm.text_hash(FUNC) != cm.text_hash(FUNC.replace("a + b", "a - b"))
    assert cm.text_hash("   \n\n") is None


def test_ast_hash_ignores_comments_docstring_decorators_quotes() -> None:
    variant = (
        "@decorator\ndef add(a, b):\n"
        "    'another docstring'\n    total = (a + b)\n    return total\n"
    )
    assert cm.ast_hash(FUNC) == cm.ast_hash(variant)
    assert cm.ast_hash(FUNC) != cm.ast_hash(FUNC.replace("total", "result"))  # names are kept
    assert cm.ast_hash(FUNC) != cm.ast_hash(FUNC.replace("a + b", "a - b"))


def test_ast_hash_of_method_text_and_failures() -> None:
    method = "    def run(self, x):\n        return x * 2\n"
    assert cm.ast_hash(method) is not None
    assert cm.ast_hash("print 'python two'") is None  # does not parse
    assert cm.ast_hash("x = 1\ny = 2\n") is None  # not one function
    assert cm.ast_hash("def f():\n    pass\ndef g():\n    pass\n") is None  # two functions
    assert cm.ast_hash("") is None
    assert cm.ast_hash("class C:\n    pass\n") is None


def test_docstring_only_function_hashes() -> None:
    a = cm.ast_hash('def f():\n    """only a docstring"""\n')
    b = cm.ast_hash("def f():\n    pass\n")
    assert a == b and a is not None


def _probe() -> cm.ProbeSet:
    p = cm.ProbeSet()
    p.add("o/r", cm.function_hashes(FUNC))
    return p


def test_probe_match_levels() -> None:
    p = _probe()
    t, a = p.match(cm.function_hashes(FUNC.replace("# comment", "# other")))
    assert t == set() and a == {"o/r"}  # a comment changes the text level only
    t, a = p.match(cm.function_hashes(FUNC))
    assert t == a == {"o/r"}
    assert p.match(cm.function_hashes("def other():\n    return 1\n")) == (set(), set())


def test_probe_set_json_roundtrip_is_canonical() -> None:
    p = _probe()
    blob = p.to_json()
    again = cm.ProbeSet.from_json(blob)
    assert again.to_json() == blob and again.functions == 1
    with pytest.raises(ValueError):
        cm.ProbeSet.from_json(blob.replace(cm.PROBE_VERSION, "contam-probe/v0"))


def test_scan_lines_counts_and_hits_without_text() -> None:
    rows = [
        {"query": "q", "document": FUNC, "negatives": ["def other():\n    return 1\n", FUNC]},
        {"query": "q2", "document": "def z():\n    return 0\n", "negatives": []},
        {"query": "q3", "document": 5},
    ]
    lines = [json.dumps(r) for r in rows] + ["{not json", "", "[1, 2]"]
    hits: list[dict[str, object]] = []
    c = cm.scan_lines(lines, _probe(), negatives=True, hits=hits)
    assert c.rows == 3 and c.rows_bad_json == 2
    assert c.documents == 2 and c.any_hits == 1 and c.text_hits == 1 and c.ast_hits == 1
    assert c.negatives == 2 and c.negative_text_hits == 1
    assert hits == [
        {
            "row": 0,
            "field": "document",
            "text_hash": cm.text_hash(FUNC),
            "ast_hash": cm.ast_hash(FUNC),
            "repos": ["o/r"],
        }
    ]
    assert "def add" not in json.dumps(hits)
    only_docs = cm.scan_lines(lines, _probe())
    assert only_docs.negatives == 0


def test_iter_documents_fields() -> None:
    lines = [json.dumps({"document": "a", "negatives": ["b", 3, "c"]}), "garbage"]
    assert list(cm.iter_documents(lines, ("document", "negatives"))) == [
        ("document", "a"),
        ("negatives", "b"),
        ("negatives", "c"),
    ]


def test_merge_counts() -> None:
    assert cm.merge_counts([{"a": 1, "b": 2}, {"a": 3}]) == {"a": 4, "b": 2}


def _git(cwd: Path, *args: str) -> str:
    env = {
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@t",
        "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
        "HOME": str(cwd),
    }
    return subprocess.run(
        ["git", *args], cwd=cwd, env=env, check=True, capture_output=True, text=True
    ).stdout.strip()


def test_index_from_git_snapshots(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-q")
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "a.py").write_text(
        "def f(x):\n    return x + 1\n\nclass C:\n    def m(self):\n        return 2\n"
    )
    (tmp_path / "pkg" / "bad.py").write_text("def broken(:\n")
    (tmp_path / "vendor").mkdir()
    (tmp_path / "vendor" / "v.py").write_text("def vendored():\n    return 0\n")
    (tmp_path / "gen_pb2.py").write_text("def gen():\n    return 0\n")
    (tmp_path / "notes.txt").write_text("def not_python(): pass\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "one")
    c1 = _git(tmp_path, "rev-parse", "HEAD")
    (tmp_path / "pkg" / "a.py").write_text(
        "def f(x):\n    return x + 2\n\nclass C:\n    def m(self):\n        return 2\n"
    )
    _git(tmp_path, "commit", "-q", "-am", "two")
    c2 = _git(tmp_path, "rev-parse", "HEAD")

    probe, stats = ci.build_probe({"o/r": str(tmp_path / ".git")}, {"o/r": [c2, c1, c1]})
    assert stats.snapshots == 2  # a repeated commit is added once
    assert stats.blobs_unparseable == 1 and stats.blobs_skipped_by_rule == 2
    # blobs: a.py twice (two versions) parsed; the method m is identical in both versions
    assert stats.blobs_parsed == 2 and stats.functions == 4
    assert probe.match(cm.function_hashes("def f(x):\n    return x + 1\n"))[1] == {"o/r"}
    assert probe.match(cm.function_hashes("def f(x):\n    return x + 2\n"))[1] == {"o/r"}
    assert probe.match(cm.function_hashes("def vendored():\n    return 0\n")) == (set(), set())
    assert probe.match(cm.function_hashes("def m(self):\n    return 2\n"))[1] == {
        "o/r"
    }  # method unit


def test_path_rules() -> None:
    assert ci.path_is_probed("a/b.py", b"")
    assert not ci.path_is_probed("a/vendor/b.py", b"")
    assert not ci.path_is_probed("build/x.py", b"")
    assert not ci.path_is_probed("a/b.txt", b"")
    assert not ci.path_is_probed("a/b_pb2.py", b"")
    assert not ci.path_is_probed("a/b.py", b"# DO NOT EDIT\n")


def test_read_blobs_rejects_unknown_object(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-q")
    with pytest.raises(ValueError):
        ci.read_blobs(str(tmp_path / ".git"), ["0" * 40])


def test_gz_lines_chunk_boundaries_and_partial_tail() -> None:
    lines = [json.dumps({"document": f"def f{i}():\n    return {i}\n"}) for i in range(50)]
    blob = gzip.compress(("\n".join(lines) + "\n").encode())
    for size in (1, 7, 64, len(blob)):
        chunks = [blob[i : i + size] for i in range(0, len(blob), size)]
        assert list(cm.gz_lines(chunks)) == lines
    cut = blob[: len(blob) // 2]
    got = list(cm.gz_lines([cut], drop_partial=True))
    assert got == lines[: len(got)] and 0 < len(got) < 50
    kept = list(cm.gz_lines([cut], drop_partial=False))
    assert len(kept) == len(got) + 1  # the cut line is kept when asked
    with pytest.raises(zlib.error):
        list(cm.gz_lines([b"not gzip at all"]))


def test_gz_lines_invalid_utf8_does_not_raise() -> None:
    blob = gzip.compress(b"ok\n\xff\xfe bad\n")
    assert list(cm.gz_lines([blob]))[1].endswith("bad")


def test_node_counts_separate_trivial_from_large_functions() -> None:
    tiny = cm.function_hashes("def __repr__(self):\n    return 'x'\n")
    big = cm.function_hashes(FUNC)
    assert 0 < tiny.nodes < big.nodes
    p = cm.ProbeSet()
    p.add("o/r", big)
    again = cm.ProbeSet.from_json(p.to_json())
    assert again.nodes[big.ast or ""] == big.nodes
    assert cm.function_hashes("not python (").nodes == 0


def test_summarize_scan_buckets_and_repos() -> None:
    shards = [
        {
            "counts": {"rows": 10, "any_hits": 3},
            "hits": [
                {"row": 0, "ast_hash": "a", "text_hash": None, "repos": ["x/y"]},
                {"row": 1, "ast_hash": "b", "text_hash": "t", "repos": ["x/y", "p/q"]},
                {"row": 2, "ast_hash": None, "text_hash": "t2", "repos": ["p/q"]},
            ],
        },
        {"counts": {"rows": 5, "any_hits": 0}, "hits": []},
    ]
    out = cm.summarize_scan(shards, {"a": 5, "b": 120})
    assert out["totals"] == {"rows": 15, "any_hits": 3}
    assert out["hits_by_node_bucket"]["under 20 nodes"] == 1
    assert out["hits_by_node_bucket"]["100 or more"] == 1
    assert out["hits_by_node_bucket"]["no ast hash"] == 1
    assert out["hit_records_with_several_repos"] == 1 and out["distinct_hit_ast_hashes"] == 2
    assert out["hits_by_repo"] == {"p/q": 2, "x/y": 2}
    assert cm.summarize_scan([], {})["shards"] == 0


def test_deeply_nested_function_does_not_raise() -> None:
    deep = "def f():\n    return " + "(" * 90 + "1" + ")" * 90 + "\n"
    nested = "def g():\n    return " + "[" * 150 + "]" * 150 + "\n"
    for src in (deep, nested):
        h = cm.function_hashes(src)  # may or may not hash, must not raise
        assert h.text is not None
