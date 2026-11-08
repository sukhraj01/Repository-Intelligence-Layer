"""Tests for the label sheet text extraction (ril.data_mining.audit_pairs), synthetic repository."""

from __future__ import annotations

import gzip
import json
import os
from pathlib import Path
from typing import Any

from ril.data_mining import audit_pairs as ap
from ril.data_mining.diff import parse_comparison
from ril.data_mining.mapping import map_change
from ril.data_mining.snapshot import SnapshotError
from ril.parsing.repository_parser import parse_repository
from ril.parsing.unit_id import id_to_pool
from tests.unit._mining_fixtures import compare_doc, file_entry, make_patch

OLD = '''"""Shapes."""


def area(w, h):
    """Area of a box."""
    return w * h


def perimeter(w, h):
    return 2 * (w + h)


def describe(w, h):
    return f"{w}x{h}"
'''
NEW = OLD.replace("return w * h", "return abs(w * h)").replace(
    'return f"{w}x{h}"', 'return f"{w} by {h}"'
)


class FakeClient:
    def __init__(self, doc: dict[str, Any], title: str = "Make area absolute") -> None:
        self.doc, self.title, self.paths = doc, title, []

    def get_json(self, path: str, params: Any = None) -> Any:
        self.paths.append(path)
        if "/compare/" in path:
            return self.doc
        return {"title": self.title}


class FakeSnapshots:
    def __init__(self, files: dict[str, str], fail: bool = False) -> None:
        self.files, self.fail = files, fail

    def materialize(self, repo: str, sha: str, dest: str) -> int:
        if self.fail:
            raise SnapshotError("no network")
        for name, text in self.files.items():
            full = os.path.join(dest, name)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w", encoding="utf-8") as handle:
                handle.write(text)
        return len(self.files)

    def prefetch(self, repo: str, sha: str) -> None: ...

    def close(self) -> None: ...


def _mined_dir(tmp_path: Path) -> tuple[str, dict[str, Any]]:
    """A mined directory built from the real parser and mapping, as the miner would write it."""
    repo_dir = tmp_path / "snap"
    repo_dir.mkdir()
    (repo_dir / "shapes.py").write_text(OLD, encoding="utf-8")
    units = parse_repository(str(repo_dir), "acme/widgets").units
    patch = make_patch(OLD, NEW)
    doc = compare_doc("base" * 10, "head" * 10, [file_entry("shapes.py", patch=patch)])
    change = parse_comparison(doc).python_files()[0]
    hits = map_change([u for u in units if u.file == "shapes.py"], change).hits
    positives = [
        {
            "unit_id": h.unit.id,
            "pool_id": id_to_pool(h.unit.id),
            "path": h.unit.file,
            "unit_kind": h.unit.unit_type,
            "name": h.unit.name,
            "qualified_name": h.unit.qualified_name,
            "is_test": False,
            "removed_lines": h.removed_lines,
            "inserted_lines": h.inserted_lines,
            "in_corpus": True,
        }
        for h in hits
    ]
    meta = {
        "repo": "acme/widgets",
        "pr": 7,
        "base_commit": "b" * 40,
        "base_ref_oid": "a" * 40,
        "head_commit": "c" * 40,
        "positives": positives,
    }
    d = tmp_path / "acme__widgets-7"
    d.mkdir()
    (d / "queries.jsonl").write_text(
        json.dumps({"_id": "x", "text": "Area is negative\n\nabs please"}) + "\n", encoding="utf-8"
    )
    (d / "pr_meta.json").write_text(json.dumps(meta), encoding="utf-8")
    with gzip.open(d / "corpus.jsonl.gz", "wt", encoding="utf-8") as handle:
        for u in units:
            if u.unit_type in ("function", "method"):
                row = {
                    "_id": id_to_pool(u.id),
                    "title": "",
                    "text": f"{id_to_pool(u.id)}\n{u.source}",
                }
                handle.write(json.dumps(row) + "\n")
    return str(d), {"doc": doc, "positives": positives}


def test_hunks_are_those_that_touch_the_function(tmp_path: Path) -> None:
    d, info = _mined_dir(tmp_path)
    assert {p["name"] for p in info["positives"]} == {"area", "describe"}
    recs = ap.extract_pr(
        d,
        [p["pool_id"] for p in info["positives"]],
        client=FakeClient(info["doc"]),  # type: ignore[arg-type]
        snapshots=FakeSnapshots({"shapes.py": OLD}),
    )
    by = {r["qualified_name"]: r for r in recs}
    assert all(r["hunk_reproduced"] for r in recs)
    assert "abs(w * h)" in by["area"]["hunks"] and "by {h}" not in by["area"]["hunks"]
    assert "by {h}" in by["describe"]["hunks"] and "abs(" not in by["describe"]["hunks"]
    assert "return w * h" in by["area"]["unit_text"]
    assert by["area"]["pr_title"] == "Make area absolute"
    assert by["describe"]["other_functions"] == ["shapes.py::area"]
    assert by["area"]["query"].startswith("Area is negative")


def test_hunk_text_excludes_a_hunk_that_only_touches_another_function(tmp_path: Path) -> None:
    old = (
        OLD
        + "\n\n"
        + "\n".join(f"# filler {i}" for i in range(12))
        + "\n\n\ndef late(x):\n    return x\n"
    )
    new = old.replace("    return x\n", "    return x + 1\n")
    patch = make_patch(old, new)
    units = _units(tmp_path, old)
    late = next(u for u in units if u.name == "late")
    area = next(u for u in units if u.name == "area")
    assert ap.hunks_touching(patch, late, units) and not ap.hunks_touching(patch, area, units)


def _units(tmp_path: Path, text: str) -> list[Any]:
    d = tmp_path / "u"
    d.mkdir(exist_ok=True)
    (d / "shapes.py").write_text(text, encoding="utf-8")
    return parse_repository(str(d), "acme/widgets").units


def test_a_snapshot_failure_keeps_the_pair_and_says_why(tmp_path: Path) -> None:
    d, info = _mined_dir(tmp_path)
    pid = info["positives"][0]["pool_id"]
    recs = ap.extract_pr(
        d,
        [pid],
        client=FakeClient(info["doc"]),
        snapshots=FakeSnapshots({}, fail=True),  # type: ignore[arg-type]
    )
    assert len(recs) == 1 and recs[0]["hunk_reproduced"] is False
    assert recs[0]["hunks"].startswith("(diff not available: SnapshotError")
    assert recs[0]["unit_text"].startswith("def ")  # the stored function text is still there


def test_changed_counts_flag_a_hunk_that_does_not_reproduce(tmp_path: Path) -> None:
    d, info = _mined_dir(tmp_path)
    meta = json.loads(Path(d, "pr_meta.json").read_text(encoding="utf-8"))
    meta["positives"][0]["removed_lines"] += 5
    Path(d, "pr_meta.json").write_text(json.dumps(meta), encoding="utf-8")
    recs = ap.extract_pr(
        d,
        [meta["positives"][0]["pool_id"]],
        client=FakeClient(info["doc"]),  # type: ignore[arg-type]
        snapshots=FakeSnapshots({"shapes.py": OLD}),
    )
    assert recs[0]["hunk_reproduced"] is False and "@@" in recs[0]["hunks"]


def test_corpus_text_missing_is_none(tmp_path: Path) -> None:
    d, _ = _mined_dir(tmp_path)
    assert ap.corpus_text(os.path.join(d, "corpus.jsonl.gz"), "nope/x.py/zzz") is None
