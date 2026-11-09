"""Full-store preparation (E-RQ2-FULL-PREP): selection, snapshot, shards, drop list, byte checks.

Synthetic stores written by the real store writer; the planted held-out function is the audit
tests' own. Nothing here needs torch or the cluster.
"""

from __future__ import annotations

import gzip
import json
import os
from pathlib import Path

import pytest

from ril.data_mining import cas, full_prep, rank_jobs
from ril.data_mining import overlap_audit as oa
from ril.data_mining.full_prep_run import PrepConfig, Runner
from ril.data_mining.miner import MinedInstance
from ril.data_mining.store import LAYOUT_DEDUP, MiningStore
from ril.training import pool_ranks as pr
from ril.training.pool_reader import read_cache, write_cache

HELD = (
    "def reconcile_pending_items(pending_items, upper_limit):\n"
    "    reconciled_output = []\n"
    "    for pending_item in pending_items:\n"
    "        if pending_item > upper_limit:\n"
    "            reconciled_output.append(pending_item * 2)\n"
    "        else:\n"
    "            reconciled_output.append(pending_item + upper_limit)\n"
    "    return sorted(reconciled_output)\n"
)


def _body(i: int) -> str:
    return (
        f"def other_{i}(a, b):\n    total = 0\n    for k in range(a):\n        if k % 2:\n"
        f"            total += k * {i}\n        else:\n            total -= b\n    return total\n"
    )


def _inst(repo: str, number: int, extra: list[tuple[str, str]], positive: str) -> MinedInstance:
    rows = [(f"lib/f.py/other_{i}", f"lib/f.py/other_{i}\n{_body(i)}") for i in range(25)]
    rows += extra
    return MinedInstance(
        repo,
        number,
        f"{repo.replace('/', '__')}-{number}",
        f"query {number}",
        "c" * 40,
        rows,
        [positive],
        {"repo": repo, "pr": number, "counters": {"positives": 1, "corpus_units": len(rows)}},
    )


PLANTED = ("lib/a.py/sync", f"lib/a.py/sync\n{HELD}")


def _store(tmp_path: Path) -> tuple[str, str]:
    """Store of six mined directories over three repositories plus a state file with other rows."""
    store = MiningStore(str(tmp_path / "store"), LAYOUT_DEDUP)
    specs = [
        ("acme/one", 1, [PLANTED], PLANTED[0]),
        ("acme/one", 2, [], "lib/f.py/other_3"),
        ("acme/two", 3, [], "lib/f.py/other_1"),
        ("acme/two", 4, [PLANTED], "lib/f.py/other_2"),
        ("acme/three", 5, [], "lib/f.py/other_4"),
        ("acme/three", 6, [], "lib/f.py/other_5"),
    ]
    for repo, n, extra, pos in specs:
        store.write_instance(_inst(repo, n, extra, pos))
    rows = [
        {"key": "acme/none#90", "status": "no_python_change"},
        {"key": "Acme/One#1", "status": "mined", "counters": {"corpus_units": 26}},
        {"key": "acme/two#91", "status": "quarantined", "reason": "patch_missing"},
        {"key": "acme/one#2", "status": "mined", "counters": {"corpus_units": 25}},
        {"key": "acme/two#3", "status": "mined", "counters": {"corpus_units": 25}},
        {"key": "acme/gone#7", "status": "mined", "counters": {"corpus_units": 9}},
        {"key": "acme/two#4", "status": "mined", "counters": {"corpus_units": 26}},
        {"key": "acme/three#5", "status": "mined", "counters": {"corpus_units": 25}},
        {"key": "acme/three#6", "status": "mined", "counters": {"corpus_units": 25}},
    ]
    state = tmp_path / "store" / "state.jsonl"
    state.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows))
    return store.root, str(state)


def _index() -> oa.HeldOutIndex:
    index = oa.HeldOutIndex()
    oa.add_unit_texts(index, "held/repo", [HELD])
    return index


def test_directory_name_follows_the_store_form() -> None:
    assert full_prep.dir_name_of_key("Acme/One#12") == "acme__one-12"


def test_selection_takes_final_mined_rows_in_state_order(tmp_path) -> None:
    root, state = _store(tmp_path)
    sel = full_prep.select_closed(state, root, 3)
    assert sel.names == ["acme__one-1", "acme__one-2", "acme__two-3"]
    assert sel.last_row == 5 and sel.state_rows == 9
    assert sel.status == {"no_python_change": 1, "mined": 3, "quarantined": 1}
    # the row with no directory is not final: counted, left out, not an error
    everything = full_prep.select_closed(state, root)
    assert len(everything.names) == 6 and everything.skipped_open == 1
    assert full_prep.select_closed(state, root, 3).used_sha256 == sel.used_sha256
    assert full_prep.select_closed(state, root, 4).used_sha256 != sel.used_sha256


def test_snapshot_is_a_byte_copy_that_audits_like_the_original(tmp_path) -> None:
    root, state = _store(tmp_path)
    sel = full_prep.select_closed(state, root, 4)
    dest = str(tmp_path / "trial")
    doc = full_prep.snapshot_store(root, state, dest, sel)
    assert doc["selection"]["directories"] == 4 and doc["repositories"] == 2
    assert full_prep.verify_snapshot(dest) == {"files": doc["files"], "missing": [], "changed": []}
    names = cas.instance_names(dest)
    assert names == sorted(sel.names)
    a = {r["directory"]: r for r in oa.audit_store(root, _index(), names=names)}
    b = {r["directory"]: r for r in oa.audit_store(dest, _index(), names=names)}
    assert a == b
    # the state copy stops at the last row used
    assert len(full_prep.read_state_rows(os.path.join(dest, "state.jsonl"))) == sel.last_row
    # a second copy is idempotent; a changed destination file is never replaced
    assert full_prep.snapshot_store(root, state, dest, sel)["bytes"] == doc["bytes"]
    victim = os.path.join(dest, "pr", sel.names[0], "queries.jsonl")
    Path(victim).write_text("changed")
    with pytest.raises(cas.StoreError):
        full_prep.snapshot_store(root, state, dest, sel)
    assert Path(victim).read_text() == "changed"
    assert full_prep.verify_snapshot(dest)["changed"]


def test_shards_partition_by_repository_and_merge_to_the_unsharded_records(tmp_path) -> None:
    root, state = _store(tmp_path)
    names = full_prep.select_closed(state, root).names
    parts = full_prep.shard_names(root, names, 3)
    assert sorted(n for p in parts for n in p) == sorted(names)
    for p in parts:
        repos = {cas._repo_of(os.path.join(root, "pr", n)) for n in p}
        assert all(
            full_prep.shard_of(r, 3) == full_prep.shard_of(next(iter(repos)), 3) for r in repos
        )
    dirs = []
    for i, p in enumerate(parts):
        d = tmp_path / f"shard_{i}"
        d.mkdir()
        with open(d / "records.jsonl", "w", encoding="utf-8") as handle:
            for rec in oa.audit_store(root, _index(), names=p):
                handle.write(json.dumps(rec, sort_keys=True) + "\n")
        dirs.append(str(d))
    merged = full_prep.merge_audit_records(dirs)
    whole = list(oa.audit_store(root, _index()))
    assert merged == whole
    assert oa.apply_rule(merged, oa.Rule()) == oa.apply_rule(whole, oa.Rule())
    with pytest.raises(ValueError):
        full_prep.merge_audit_records([dirs[0], dirs[0]]) if parts[0] else (_ for _ in ()).throw(
            ValueError("empty")
        )
    with pytest.raises(ValueError):
        full_prep.shard_names(root, names, 0)


def test_drop_list_leaves_the_manifest_not_the_store(tmp_path) -> None:
    names = ["a-1", "a-2", "b-3"]
    assert full_prep.apply_drop_list(names, ["a-2"]) == (["a-1", "b-3"], ["a-2"])
    assert full_prep.apply_drop_list(names, []) == (names, [])
    with pytest.raises(ValueError, match="not in the manifest"):
        full_prep.apply_drop_list(names, ["z-9"])


def test_materialise_check_catches_a_changed_byte(tmp_path) -> None:
    root, state = _store(tmp_path)
    names = full_prep.select_closed(state, root).names
    view = str(tmp_path / "view")
    cas.materialise(root, view, names)
    assert full_prep.verify_materialised(root, view, names)["identical"]
    corpus = os.path.join(view, "pr", names[0], "corpus.jsonl.gz")
    with gzip.open(corpus, "rb") as handle:
        data = handle.read()
    with gzip.open(corpus, "wb") as handle:
        handle.write(data.replace(b"total", b"totaL", 1))
    res = full_prep.verify_materialised(root, view, names)
    assert res["identical"] is False and res["mismatches"] == [names[0]]


def test_compare_ignores_timing_and_gzip_time_but_nothing_else(tmp_path) -> None:
    def write(root: Path, seconds: float, mtime: int, rank: int) -> None:
        root.mkdir()
        row = {"dir": "d", "ranks": [{"rank": rank}], "seconds": seconds, "teacher": "bm25"}
        (root / "ranks.jsonl").write_text(json.dumps(row) + "\n")
        (root / "run.json").write_text(
            json.dumps({"seconds": seconds, "n": 3, "host": f"h{mtime}"})
        )
        with (
            open(root / "c.jsonl.gz", "wb") as raw,
            gzip.GzipFile(fileobj=raw, mode="wb", mtime=mtime) as gz,
        ):
            gz.write(b'{"x": 1}\n')

    write(tmp_path / "a", 1.0, 1, 5)
    write(tmp_path / "b", 2.0, 2, 5)
    assert full_prep.compare_outputs(str(tmp_path / "a"), str(tmp_path / "b"))["identical"]
    # a run's own paths and the hash of a listing that holds one are not content
    (tmp_path / "a" / "p.json").write_text(
        json.dumps({"out": "/x/a", "listing_sha256": "1", "n": 1})
    )
    (tmp_path / "b" / "p.json").write_text(
        json.dumps({"out": "/x/b", "listing_sha256": "2", "n": 1})
    )
    assert full_prep.compare_outputs(str(tmp_path / "a"), str(tmp_path / "b"))["identical"]
    (tmp_path / "b" / "p.json").write_text(
        json.dumps({"out": "/x/b", "listing_sha256": "2", "n": 2})
    )
    assert full_prep.compare_outputs(str(tmp_path / "a"), str(tmp_path / "b"))["differing"] == [
        "p.json"
    ]
    (tmp_path / "b" / "p.json").write_text(
        json.dumps({"out": "/x/a", "listing_sha256": "1", "n": 1})
    )
    write(tmp_path / "c", 2.0, 2, 6)
    res = full_prep.compare_outputs(str(tmp_path / "a"), str(tmp_path / "c"))
    assert res["differing"] == ["ranks.jsonl"]


def test_cache_bytes_do_not_depend_on_the_clock(tmp_path) -> None:
    from tests.unit._training_fixtures import synthetic_examples

    exs = synthetic_examples(repos=1, prs=2)
    a, b = str(tmp_path / "a.jsonl.gz"), str(tmp_path / "b.jsonl.gz")
    write_cache(a, exs)
    import time

    time.sleep(1.1)
    write_cache(b, exs)
    assert full_prep.sha256_file(a) == full_prep.sha256_file(b)
    assert read_cache(a) == exs


def test_streamed_summary_and_shared_strings_agree_with_the_plain_reader(tmp_path) -> None:
    from ril.training.pool_reader import read_cache_shared
    from tests.unit._training_fixtures import synthetic_examples

    exs = synthetic_examples(repos=2, prs=3)
    path = str(tmp_path / "c.jsonl.gz")
    write_cache(path, exs)
    assert read_cache_shared(path) == read_cache(path) == exs
    got = full_prep.cache_summary(path)
    assert got["examples"] == len(exs)
    assert got["positives"] == sum(len(e.positive_ids) for e in exs)
    assert got["candidates"] == sum(len(e.candidate_ids) for e in exs)
    assert got["repos"] == sorted({e.repo for e in exs})
    assert got["ids"] == [e.instance_id for e in exs]


def test_rank_comparison_on_the_common_directories(tmp_path) -> None:
    def rows(dirs: list[str], rank: int = 3) -> list[dict]:
        return [
            {"dir": d, "teacher": "bm25", "functions": 9, "ranks": [
                {"positive": "p", "rank": rank, "rank_all": rank, "ties": 0}]}
            for d in dirs
        ]  # fmt: skip

    def write(path: Path, rs: list[dict]) -> str:
        path.write_text("".join(json.dumps(r) + "\n" for r in rs))
        return str(path)

    old = write(tmp_path / "old.jsonl", rows(["a", "b", "c"]))
    new = write(tmp_path / "new.jsonl", rows(["b", "c", "d"]))
    assert rank_jobs.reproduces([new], old)["exact"] is False
    res = rank_jobs.reproduces([new], old, common_only=True)
    assert res["exact"] and res["compared"] == 2 and res["identical"] == 2
    bad = write(tmp_path / "bad.jsonl", rows(["b", "c"], rank=4))
    assert rank_jobs.reproduces([bad], old, common_only=True)["exact"] is False
    none = write(tmp_path / "none.jsonl", rows(["z"]))
    assert rank_jobs.reproduces([none], old, common_only=True)["exact"] is False
    assert pr.read_jsonl(new)


def test_projection_is_linear_and_names_its_basis() -> None:
    rows = [{"stage": "x", "step_seconds": 10.0, "maxrss_kb": 2048, "bytes_written": 100}]
    out = full_prep.project_chain(
        rows,
        trial_directories=10,
        full_directories=100,
        trial_units=[1.0] * 10,
        full_units=[2.0] * 100,
    )
    s = out["stages"][0]
    assert s["full_seconds_per_directory"] == 100.0 and s["full_seconds_per_corpus_unit"] == 200.0
    assert out["quarter_means_full"] == [2.0] * 4 and "no interval" in out["basis"]
    assert full_prep.quarter_means([1, 2, 3, 4, 5, 6, 7, 8]) == [1.5, 3.5, 5.5, 7.5]
    with pytest.raises(ValueError):
        full_prep.project_stage(1.0, 0, 5)


def test_runner_select_and_drop_write_the_manifest_without_touching_the_store(tmp_path) -> None:
    root, state = _store(tmp_path)
    before = full_prep.sha256_file(state)
    out = tmp_path / "out"
    cfg = PrepConfig(
        store=root, out=str(out), scratch=str(tmp_path / "scr"), index="i", held_out="h",
        rename_cache="r", repo_root=str(tmp_path), limit=4,
    )  # fmt: skip
    r = Runner(cfg)
    r.stage("select", r.do_select, [r.p("names.txt")])
    assert r.names() == ["acme__one-1", "acme__one-2", "acme__two-3", "acme__two-4"]
    (out / "overlap").mkdir()
    (out / "overlap" / "drop_f20_non_test.txt").write_text("acme__one-1\n")
    r.stage("drop", r.do_drop, [r.p("names_kept.txt")])
    doc = json.loads((out / "drop_manifest.json").read_text())
    assert doc["dropped"] == 1 and doc["kept"] == 3 and doc["store_modified"] is False
    assert r.kept() == ["acme__one-2", "acme__two-3", "acme__two-4"]
    assert r.done("select") and r.done("drop") and not r.done("cache")
    rows = [json.loads(x) for x in (out / "stages.jsonl").read_text().splitlines()]
    assert [x["stage"] for x in rows] == ["select", "drop"]
    assert full_prep.sha256_file(state) == before
    # a drop list with the wrong hash is refused
    bad = PrepConfig(**{**cfg.__dict__, "drop_list": str(out / "overlap" / "drop_f20_non_test.txt"),
                        "drop_sha256": "0" * 64})  # fmt: skip
    with pytest.raises(RuntimeError, match="hashes to"):
        Runner(bad).do_drop()


def test_a_named_subset_replaces_the_first_n_and_must_be_final(tmp_path) -> None:
    root, _ = _store(tmp_path)
    names = tmp_path / "names.txt"
    names.write_text("acme__three-6\nacme__one-1\n")
    cfg = PrepConfig(
        store=root, out=str(tmp_path / "o"), scratch=str(tmp_path / "t"), index="i",
        held_out="h", rename_cache="r", repo_root=str(tmp_path), names_file=str(names),
    )  # fmt: skip
    r = Runner(cfg)
    r.stage("select", r.do_select, [r.p("names.txt")])
    assert r.names() == ["acme__three-6", "acme__one-1"]
    doc = json.loads((tmp_path / "o" / "selection.json").read_text())
    assert doc["names_file_sha256"] == full_prep.sha256_file(str(names))
    names.write_text("acme__nowhere-1\n")
    with pytest.raises(RuntimeError, match="not final"):
        Runner(cfg).do_select()


def test_a_failing_step_stops_the_stage_and_names_the_log(tmp_path) -> None:
    cfg = PrepConfig(
        store="s", out=str(tmp_path / "o"), scratch=str(tmp_path / "t"), index="i",
        held_out="h", rename_cache="r", repo_root=str(tmp_path),
    )  # fmt: skip
    r = Runner(cfg)
    (tmp_path / "boom.py").write_text("import sys; sys.exit(7)\n")
    with pytest.raises(RuntimeError, match="exited 7"):
        r.step("boom", ["boom.py"])
    (tmp_path / "ok.py").write_text("print('{}')\n")
    row = r.step("ok", ["ok.py"], stdout_to=str(tmp_path / "o" / "ok.json"))
    assert row["rc"] == 0 and row["maxrss_kb"] > 0
