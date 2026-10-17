"""Integration: pilot E1/E2 from benchmark-shaped folders and a checkout to ranks and tables."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

from ril.analysis.e1_tables import (
    chunk_query_rows,
    chunk_summary,
    conclusion_table,
    load_chunk_runs,
    load_unit_runs,
    noise_tables,
    protocol_vs_filter,
    unit_query_rows,
    unit_summary,
)
from ril.evaluation.e1_run import config_hash, run_chunk_level, run_unit_level

SOURCE = (
    "import os\n"  # 1
    "\n\n"
    "def read_config(path):\n"  # 4
    "    return open(path).read()\n"  # 5
    "\n\n"
    "def render_template(name):\n"  # 8
    "    return name.upper()\n"  # 9
    "\n\n"
    "class Pool:\n"  # 12
    "    def timeout(self):\n"  # 13
    "        return 30\n"  # 14
)

PATCH = (
    "--- a/pkg/a.py\n+++ b/pkg/a.py\n@@ -5,1 +5,1 @@\n"
    "-    return open(path).read()\n+    return path\n"
)

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


def _folder(
    root: Path,
    level: str,
    dataset: str,
    name: str,
    chunks: dict[str, str],
    qtext: str,
    pos: list[str],
) -> None:
    f = root / "data" / level / dataset / name
    f.mkdir(parents=True)
    (f / "corpus.jsonl").write_text(
        "\n".join(json.dumps({"_id": i, "text": t}) for i, t in chunks.items()) + "\n",
        encoding="utf-8",
    )
    (f / "queries.jsonl").write_text(
        json.dumps({"_id": "acme__mini-1", "text": qtext, "filtered_corpus_id": list(chunks)})
        + "\n",
        encoding="utf-8",
    )
    (f / "qrels.jsonl").write_text(
        "\n".join(json.dumps({"query_id": "acme__mini-1", "corpus_id": c, "score": 1}) for c in pos)
        + "\n",
        encoding="utf-8",
    )


@pytest.fixture()
def world(tmp_path: Path) -> dict[str, Any]:
    src = tmp_path / "src"
    (src / "pkg").mkdir(parents=True)
    (src / "pkg" / "a.py").write_text(SOURCE, encoding="utf-8")
    (src / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    _git(src, "init", "-q")
    _git(src, "add", "-A")
    _git(src, "commit", "-q", "-m", "base")
    commit = _git(src, "rev-parse", "HEAD")
    cache = tmp_path / "cache"
    cache.mkdir()
    subprocess.run(
        ["git", "clone", "-q", "--bare", str(src), str(cache / "acme__mini.git")], check=True
    )
    chunks = {
        "c_imp": "import os\n",
        "c_cfg": "def read_config(path):\n    return open(path).read()\n",
        "c_tpl": "def render_template(name):\n    return name.upper()\n",
        "c_pool": "class Pool:\n    def timeout(self):\n        return 30\n",
    }
    root = tmp_path / "bench"
    _folder(
        root,
        "LEVEL-2",
        "SWE-bench_Verified",
        "pallets__flask",
        chunks,
        "read_config path open error",
        ["c_imp", "c_cfg"],
    )
    cfg = {
        "seed": 0,
        "bm25": {"k1": 1.5, "b": 0.75},
        "prefilter_k": 10000,
        "folders": [
            {
                "role": "test",
                "dataset": "SWE-bench_Verified",
                "folder": "pallets__flask",
                "repo": "acme/mini",
                "levels": ["L2"],
                "units": True,
            }
        ],
    }
    meta = {"acme__mini-1": {"base_commit": commit, "patch": PATCH}}
    return {
        "cfg": cfg,
        "root": str(root),
        "meta": meta,
        "cache": str(cache),
        "work": str(tmp_path / "work"),
        "out": str(tmp_path / "out"),
    }


def test_chunk_and_unit_stages_to_tables(world: dict[str, Any]) -> None:
    run_chunk_level(world["cfg"], world["root"], world["out"])
    fails = run_unit_level(
        world["cfg"], world["root"], world["meta"], world["cache"], world["work"], world["out"]
    )
    assert fails == {"pallets__flask": []}
    chunk_runs, unit_runs = load_chunk_runs(world["out"]), load_unit_runs(world["out"])
    rows = chunk_query_rows(chunk_runs)
    summary = chunk_summary(rows, 0, 50)
    assert {r["reading"] for r in summary} == {"protocol", "filter_first"}
    assert protocol_vs_filter(rows, 0, 50)[0]["positives_beyond_prefilter"] == 0

    inst = unit_runs[0]
    by_chunk = {p["corpus_id"]: p for p in inst["positives"]}
    assert (
        by_chunk["c_imp"]["noise_class"] == "import_only"
        and by_chunk["c_imp"]["kind"] == "module_residual"
    )
    assert (
        by_chunk["c_cfg"]["units"] == ["pkg/a.py::read_config"]
        and by_chunk["c_cfg"]["edit_overlap"]
    )
    assert not by_chunk["c_imp"]["edit_overlap"]
    urows = unit_query_rows(unit_runs)
    assert unit_summary(urows, 0, 50)
    tables = noise_tables(rows, unit_runs, urows, 0, 50)
    base = [r for r in tables["chunk"] if r["label_set"] == "base" and r["group"] == "verified6"]
    clean = [
        r
        for r in tables["chunk"]
        if r["label_set"] == "clean_content" and r["group"] == "verified6"
    ]
    assert base and clean and base[0]["queries_kept"] == clean[0]["queries_kept"] == 1
    assert conclusion_table(rows, unit_runs, urows, 0, 50)


def _strip(s: str) -> dict[str, Any]:
    drop = ("hardware",)
    return {k: v for k, v in json.loads(s).items() if not k.endswith("seconds") and k not in drop}


def test_reruns_are_identical_and_hash_covers_the_split(
    world: dict[str, Any], tmp_path: Path
) -> None:
    run_chunk_level(world["cfg"], world["root"], world["out"])
    run_chunk_level(world["cfg"], world["root"], str(tmp_path / "out2"))
    a = (Path(world["out"]) / "chunk" / "L2__SWE-bench_Verified__pallets__flask.json").read_text()
    b = (tmp_path / "out2" / "chunk" / "L2__SWE-bench_Verified__pallets__flask.json").read_text()
    assert _strip(a) == _strip(b)
    other = yaml.safe_load(yaml.safe_dump(world["cfg"]))
    other["folders"][0]["role"] = "dev"
    assert config_hash(other) != config_hash(world["cfg"])


def test_no_text_leaves_the_records(world: dict[str, Any]) -> None:
    run_chunk_level(world["cfg"], world["root"], world["out"])
    run_unit_level(
        world["cfg"], world["root"], world["meta"], world["cache"], world["work"], world["out"]
    )
    blob = "".join(p.read_text() for p in Path(world["out"]).rglob("*.json"))
    assert "return open(path)" not in blob and "read_config path open error" not in blob
