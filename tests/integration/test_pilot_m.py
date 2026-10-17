"""Integration: pilot M from a git repository and benchmark-shaped files to mapping and reach."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest

from ril.analysis.reach_tables import (
    category_folder_rows,
    category_rows,
    exclusion_rows,
    incidence_rows,
    kind_rows,
    match_rows,
    reach_rows,
)
from ril.evaluation.chunk_unit_pilot import checkout_commit, run_pilot

FILES_V1 = {
    "pkg/__init__.py": "",
    "pkg/a.py": (
        "import os\n\n\n"
        "def alpha(x):\n    return x + 1\n\n\n"
        "def lone():\n    return 99\n\n\n"
        "class K:\n    def m1(self):\n        return alpha(1)\n"
    ),
    "pkg/b.py": "from pkg.a import alpha\n\n\ndef beta():\n    return alpha(2)\n",
    "pkg/c.py": "def far_away():\n    return 7\n",
    "pkg/dup1.py": "def twin():\n    return 'same text'\n",
    "pkg/dup2.py": "def twin():\n    return 'same text'\n",
    "tests/test_a.py": "from pkg.a import alpha\n\n\ndef test_alpha():\n    assert alpha(1) == 2\n",
    "docs/guide.rst": "Guide\n=====\n\nUse alpha to add one to a number.\n",
    "setup.cfg": "[options.entry_points]\nconsole_scripts =\n    tool = pkg.b:beta\n",
}

ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.org",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.org",
}


def _git(cwd: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", *args], cwd=cwd, env=ENV, capture_output=True, text=True, check=True
    )
    return done.stdout.strip()


def _write(root: Path, files: dict[str, str]) -> None:
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


@pytest.fixture
def origin(tmp_path: Path) -> tuple[Path, str]:
    """A bare clone with two commits touching a.py and b.py together; returns it and commit 2."""
    work = tmp_path / "seed_repo"
    work.mkdir()
    _git(work, "init", "-q", "-b", "main")
    _write(work, FILES_V1)
    _git(work, "add", "-A")
    _git(work, "commit", "-q", "-m", "first")
    (work / "pkg/a.py").write_text(FILES_V1["pkg/a.py"] + "\n# edit\n", encoding="utf-8")
    (work / "pkg/b.py").write_text(FILES_V1["pkg/b.py"] + "\n# edit\n", encoding="utf-8")
    _git(work, "add", "-A")
    _git(work, "commit", "-q", "-m", "second")
    commit = _git(work, "rev-parse", "HEAD")
    bare = tmp_path / "cache" / "acme__mini.git"
    bare.parent.mkdir()
    _git(tmp_path, "clone", "-q", "--bare", str(work), str(bare))
    return bare, commit


def _benchmark_files(root: Path, base: str) -> str:
    """Write L2 and L3 sample folders for one instance; positives are text windows of files."""
    a, b = FILES_V1["pkg/a.py"], FILES_V1["pkg/b.py"]
    l2 = {
        "p2a": "def alpha(x):\n    return x + 1\n",  # one unit
    }
    l3 = {
        "p3same": "def alpha(x):\n    return x + 1\n",  # text identical to an L2 positive
        "p3method": "    def m1(self):\n        return alpha(1)\n",  # method, new
        "p3caller": "def beta():\n    return alpha(2)\n",  # function in b.py, new
        "p3far": "def far_away():\n    return 7\n",  # function in c.py, new
        "p3imports": "import os\n",  # module residual
        "p3test": "def test_alpha():\n    assert alpha(1) == 2\n",  # test unit
        "p3twin": "def twin():\n    return 'same text'\n",  # two locations
        "p3docs": "Use alpha to add one to a number.\n",  # docs
        "p3cfg": "tool = pkg.b:beta\n",  # configuration
        "p3ws": "def  lone():\n\treturn   99\n",  # whitespace-different
        "p3gone": "text that is in no file of this repository at all\n",  # unmatched
        "p3span": a[a.index("def lone") : a.index("class K")] + "class K:\n    def m1(self):\n",
    }
    assert b and a
    for n, rows in ((2, l2), (3, l3)):
        folder = root / "data" / f"LEVEL-{n}" / "SWE-bench_Verified" / "acme__mini"
        folder.mkdir(parents=True)
        (folder / "corpus.jsonl").write_text(
            "".join(json.dumps({"_id": cid, "text": t}) + "\n" for cid, t in rows.items()),
            encoding="utf-8",
        )
        (folder / "qrels.jsonl").write_text(
            "".join(
                json.dumps({"query_id": "acme__mini-1", "corpus_id": cid, "score": 1}) + "\n"
                for cid in rows
            ),
            encoding="utf-8",
        )
    return "acme__mini-1"


def _run(tmp_path: Path, origin_info: tuple[Path, str], out: str = "out") -> dict[str, Any]:
    bare, commit = origin_info
    instance = (
        _benchmark_files(tmp_path / "bench", commit)
        if not (tmp_path / "bench").exists()
        else "acme__mini-1"
    )
    return run_pilot(
        data_root=str(tmp_path / "bench"),
        repos=["acme__mini"],
        base_commits={instance: commit},
        cache_dir=str(bare.parent),
        work_dir=str(tmp_path / "work"),
        out_dir=str(tmp_path / out),
        seed=0,
        draws=50,
    )


def test_mapping_and_reach_end_to_end(tmp_path: Path, origin: tuple[Path, str]) -> None:
    doc = _run(tmp_path, origin)
    assert doc["failures"] == []
    inst = doc["instances"][0]
    by_id = {r["corpus_id"]: r for r in inst["positives"]}

    assert by_id["p2a"]["category"] == "one_unit"
    assert by_id["p3method"]["kind"] == "method" and by_id["p3method"]["tier"] == "exact"
    assert by_id["p3imports"]["kind"] == "module_residual"
    assert by_id["p3test"]["kind"] == "test_unit"
    assert by_id["p3twin"]["n_locations"] == 2 and by_id["p3twin"]["n_files"] == 2
    assert by_id["p3docs"]["kind"] == "non_python_docs"
    assert by_id["p3cfg"]["kind"] == "non_python_config"
    assert by_id["p3ws"]["tier"] == "whitespace_normalised" and by_id["p3ws"]["kind"] == "function"
    assert by_id["p3gone"]["status"] == "not_found" and by_id["p3gone"]["kind"] == "unmatched"
    assert by_id["p3span"]["category"] == "several_units"

    reach = inst["reach"]["positives"]
    assert reach["p3same"]["status"] == "covered_by_l2" and reach["p3same"]["same_text_as_l2"]
    assert reach["p3docs"]["status"] == "no_graph_node"
    assert "p3gone" not in reach or reach["p3gone"]["status"] != "ok"
    caller = reach["p3caller"]["reach"]
    assert caller["invoke_both"]["d"] == 1  # beta calls alpha
    assert caller["invoke_fwd"]["d"] is None  # alpha does not call beta
    assert caller["invoke_rev"]["d"] == 1
    assert caller["co_change_n2"]["d"] is None  # co-change joins files, not their functions
    assert caller["co_change_n2_contain"]["d"] == 3  # unit - file - (co-change) - file - unit
    assert caller["contain"]["d"] == 4  # unit - file - dir - file - unit
    far = reach["p3far"]["reach"]
    assert far["invoke_both"]["d"] is None and far["all"]["d"] is not None
    cfg = reach["p3cfg"]["reach"]
    assert cfg["configures"]["d"] is None  # no L2 unit is linked to the file by that family alone
    assert cfg["all"]["d"] == 2  # alpha - beta (invoke), beta - setup.cfg (configures)
    assert cfg["all"]["ctrl"]["whole_repo"] is None  # a file is not drawn like a unit
    method = reach["p3method"]["reach"]
    assert method["contain"]["d"] == 3  # alpha - file - class K - method m1

    match = {(r["repo"], r["level"]): r for r in match_rows(doc["instances"])}
    assert match[("all", "L3")]["found_several_locations"] == 1
    assert match[("all", "L3")]["not_found"] == 1
    assert "p3gone" not in json.dumps(exclusion_rows(doc["instances"]))
    kinds = {(r["level"], r["repo"]): r for r in kind_rows(doc["instances"])}
    assert kinds[("L3", "all")]["test_unit"] == 1
    assert category_rows(doc["instances"])[-2]["category"] == "total_located"
    inc = {(r["group"], r["family"]): r for r in incidence_rows(doc["instances"])}
    assert inc[("all_python", "invoke")]["positives_with_edge"] > 0
    assert 0 < inc[("all_python", "invoke")]["units_with_edge_in_snapshot"] < 1
    ref = {"LEVEL-3/acme__mini": {"one_leaf_unit": 7, "two_plus_leaf_units": 1}}
    folder = [
        r for r in category_folder_rows(doc["instances"], ref) if r["folder"].startswith("LEVEL-3")
    ]
    assert {r["category"]: r["first_sample"] for r in folder}["one_unit"] == 7
    python_found = [
        r
        for r in inst["positives"]
        if r["level"] == "L3" and r["status"] == "found" and r["path"].endswith(".py")
    ]
    assert sum(r["frozen_full"] for r in folder) == len(python_found)  # docs and config excluded
    rows = reach_rows(doc["instances"], seed=0, draws=100)
    assert rows and all(r["analysis"] == "primary" for r in rows)
    assert not any("p3twin" in json.dumps(r) for r in rows)
    sens = reach_rows(doc["instances"], seed=0, draws=100, label="sensitivity_several_locations")

    def n_of(table: list[dict[str, Any]]) -> set[int]:
        return {r["n"] for r in table if r["group"] == "all_python" and r["subset"] == "core"}

    assert n_of(sens) == {n + 1 for n in n_of(rows)}  # the one two-location positive comes back


def test_records_hold_no_chunk_text(tmp_path: Path, origin: tuple[Path, str]) -> None:
    _run(tmp_path, origin)
    blob = (tmp_path / "out" / "records.json").read_text(encoding="utf-8")
    for fragment in ("return x + 1", "same text", "return 7", "Use alpha to add"):
        assert fragment not in blob


def test_rerun_reads_finished_instances_and_missing_commit_is_reported(
    tmp_path: Path, origin: tuple[Path, str]
) -> None:
    first = _run(tmp_path, origin)
    second = _run(tmp_path, origin)
    assert first["instances"] == second["instances"]
    bare, _ = origin
    status = checkout_commit(str(bare), str(tmp_path / "work2"), "0" * 40)
    assert status == "base_commit_not_available" or status.startswith("git_error")
