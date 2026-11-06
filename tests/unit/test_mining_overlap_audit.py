"""Content-overlap audit of the mined corpora against the held-out corpora (D105).

Synthetic stores: a planted held-out function in a positive, in a non-positive, in vendored code,
in a test file, and a directory with no match; thresholds at the boundary; determinism; the store
is never written.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from ril.data_mining import cas
from ril.data_mining import overlap_audit as oa
from ril.data_mining.miner import MinedInstance
from ril.data_mining.store import LAYOUT_DEDUP, MiningStore
from ril.training.contamination import ProbeSet, ast_hash_and_size, function_hashes

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
"""A held-out function above the floor of 20 syntax-tree nodes."""
SMALL = "def tiny(x, y):\n    return (x + 1) * y - 2\n"


def _body(i: int) -> str:
    return (
        f"def other_{i}(a, b):\n"
        "    total = 0\n"
        "    for k in range(a):\n"
        "        if k % 2:\n"
        f"            total += k * {i}\n"
        "        else:\n"
        "            total -= b\n"
        "    return total\n"
    )


def _row(pid: str, source: str) -> tuple[str, str]:
    return pid, f"{pid}\n{source}"


def _renamed_copy(source: str) -> str:
    """The held-out function with a docstring and a decorator added: same syntax-tree hash."""
    head, _, rest = source.partition("\n")
    return f"@cache\n{head}\n    '''copy'''\n{rest}"


def _instance(repo: str, number: int, rows: list[tuple[str, str]], positives: list[str]):
    return MinedInstance(
        repo,
        number,
        f"{repo.replace('/', '__')}-{number}",
        f"query {number}",
        "c" * 40,
        rows,
        positives,
        {"repo": repo, "pr": number},
    )


def _index() -> oa.HeldOutIndex:
    index = oa.HeldOutIndex()
    oa.add_unit_texts(index, "held/repo", [HELD, SMALL, "class Not:\n    pass\n"])
    return index


def _store(tmp_path: Path) -> str:
    store = MiningStore(str(tmp_path / "store"), LAYOUT_DEDUP)
    filler = [_row(f"lib/f.py/other_{i}", _body(i)) for i in range(30)]
    copy = _renamed_copy(HELD)
    for inst in (
        # a: the positive is a copy of a held-out function
        _instance("acme/fork", 1, [*filler, _row("lib/a.py/sync", copy)], ["lib/a.py/sync"]),
        # b: the copy is in the corpus only; the positive is unrelated
        _instance("acme/fork", 2, [*filler, _row("lib/a.py/sync", copy)], ["lib/f.py/other_3"]),
        # c: vendored code, 3 of 30 distinct functions (10%) match, no positive does
        _instance(
            "acme/vendor",
            3,
            [
                *filler[:15],
                _row("v/a.py/one", HELD),
                _row("v/b.py/two", HELD.replace("reconcile_pending_items", "other_x")),
                _row("v/c.py/three", copy),
                _row("v/d.py/small", SMALL),
            ],
            ["lib/f.py/other_1"],
        ),
        # d: nothing matches
        _instance("acme/clean", 4, filler, ["lib/f.py/other_2"]),
        # e: the matching positive sits in a test file
        _instance(
            "acme/tested",
            5,
            [*filler, _row("tests/test_a.py/sync", copy)],
            ["tests/test_a.py/sync", "lib/f.py/other_4"],
        ),
        # f: the positive is a held-out function below the floor
        _instance("acme/small", 6, [*filler, _row("lib/s.py/tiny", SMALL)], ["lib/s.py/tiny"]),
    ):
        store.write_instance(inst)
    return store.root


def _records(root: str, floors: tuple[int, ...] = oa.SENSITIVITY_FLOORS) -> dict[str, dict]:
    return {r["directory"]: r for r in oa.audit_store(root, _index(), floors)}


def test_held_out_function_and_planted_copy_share_the_hash() -> None:
    assert ast_hash_and_size(HELD)[0] == ast_hash_and_size(_renamed_copy(HELD))[0]
    assert ast_hash_and_size(HELD)[1] >= oa.FLOOR > ast_hash_and_size(SMALL)[1]


def test_planted_positive_drops_the_directory(tmp_path) -> None:
    recs = _records(_store(tmp_path))
    rule = oa.Rule()
    assert oa.classify(recs["acme__fork-1"], rule) == "drop"
    assert [m["id"] for m in recs["acme__fork-1"]["positive_matches"]] == ["lib/a.py/sync"]
    assert recs["acme__fork-1"]["positive_matches"][0]["heldout_repos"] == ["held/repo"]


def test_a_match_in_a_non_positive_does_not_drop(tmp_path) -> None:
    recs = _records(_store(tmp_path))
    rec = recs["acme__fork-2"]
    assert rec["positive_matches"] == []
    # 1 matching function of 31 distinct functions at the floor: under 5%
    assert rec["matched_ge"]["20"] == 1 and rec["distinct_ge"]["20"] == 31
    assert oa.classify(rec, oa.Rule()) == "keep"


def test_vendored_corpus_overlap_is_flagged_not_dropped(tmp_path) -> None:
    recs = _records(_store(tmp_path))
    rec = recs["acme__vendor-3"]
    assert rec["positive_matches"] == []
    # HELD and its copy are one hash; the renamed HELD is another hash that does not match;
    # SMALL matches too but is under the floor: 15 fillers + HELD + renamed = 17 at the floor
    assert rec["matched_ge"]["20"] == 1 and rec["distinct_ge"]["20"] == 17
    assert oa.corpus_share(rec, 20) == pytest.approx(1 / 17)
    assert oa.classify(rec, oa.Rule()) == "flag"
    assert oa.classify(rec, oa.Rule(drop_flagged=True)) == "drop"


def test_clean_directory_is_kept(tmp_path) -> None:
    rec = _records(_store(tmp_path))["acme__clean-4"]
    assert rec["matched_ge"] == {"10": 0, "20": 0, "50": 0}
    assert oa.classify(rec, oa.Rule()) == "keep"


def test_test_file_positive_counts_only_in_the_all_reading(tmp_path) -> None:
    rec = _records(_store(tmp_path))["acme__tested-5"]
    assert rec["positives"] == 2 and rec["positives_non_test"] == 1
    assert oa.classify(rec, oa.Rule()) == "keep"
    assert oa.classify(rec, oa.Rule(positives="all")) == "drop"
    # the test-file function is not part of the primary corpus either
    assert rec["matched_ge"]["20"] == 0


def test_floor_boundary(tmp_path) -> None:
    n = ast_hash_and_size(SMALL)[1]
    recs = _records(_store(tmp_path), floors=(10, 20, 50, n, n + 1))
    small = recs["acme__small-6"]
    assert small["positive_matches"][0]["nodes"] == n
    assert 10 <= n < 20  # below the primary floor, above the sensitivity floor
    assert oa.classify(small, oa.Rule(floor=20)) == "keep"
    assert oa.classify(small, oa.Rule(floor=10)) == "drop"
    assert oa.classify(small, oa.Rule(floor=n)) == "drop"  # nodes >= floor
    assert oa.classify(small, oa.Rule(floor=n + 1)) == "keep"
    # the size class is reported even below the floor
    summ = oa.positive_match_summary(list(recs.values()), "non_test")
    assert summ["matches"] == 2 and summ["by_size"]["under 20"] == 1


def test_share_threshold_boundary() -> None:
    rec = {
        "distinct_ge": {"20": 20},
        "matched_ge": {"20": 1},
        "positive_matches": [],
        "positives_non_test": 1,
        "positives": 1,
        "directory": "d",
        "repo": "r",
    }
    assert oa.classify(rec, oa.Rule(corpus_share=0.05)) == "flag"  # exactly 5%
    assert oa.classify(rec, oa.Rule(corpus_share=0.0500001)) == "keep"
    with pytest.raises(KeyError):
        oa.corpus_share(rec, 99)


def test_apply_rule_counts_directory_and_repository_level(tmp_path) -> None:
    recs = list(_records(_store(tmp_path)).values())
    res = oa.apply_rule(recs, oa.Rule())
    assert res["directories"] == 6
    assert res["dropped_directories"] == ["acme__fork-1"]
    assert res["flagged_directories"] == ["acme__vendor-3"]
    # acme/fork keeps directory 2, so the repository is affected but not lost
    assert res["repositories_with_a_dropped_directory"] == 1
    assert res["repositories_with_every_directory_dropped"] == 0
    assert res["pool_like_directories"] == 6 and res["pool_like_after"] == 5
    assert res["pool_like_positives"] == 6 and res["pool_like_positives_after"] == 5
    drop_all = oa.apply_rule(recs, oa.Rule(positives="all", drop_flagged=True))
    assert set(drop_all["dropped_directories"]) == {
        "acme__fork-1",
        "acme__tested-5",
        "acme__vendor-3",
    }


def test_rows_are_hashed_once_per_repository_and_results_repeat(tmp_path) -> None:
    root = _store(tmp_path)
    a = [json.dumps(r, sort_keys=True) for r in oa.audit_store(root, _index())]
    b = [json.dumps(r, sort_keys=True) for r in oa.audit_store(root, _index())]
    assert a == b


def test_the_store_is_not_written(tmp_path) -> None:
    root = _store(tmp_path)

    def snapshot() -> dict[str, tuple[int, float]]:
        out = {}
        for dirpath, _, files in os.walk(root):
            for f in files:
                p = os.path.join(dirpath, f)
                out[p] = (os.path.getsize(p), os.path.getmtime(p))
        return out

    before = (snapshot(), cas.directory_digest(root))
    list(oa.audit_store(root, _index()))
    assert (snapshot(), cas.directory_digest(root)) == before


def test_names_restrict_the_audit(tmp_path) -> None:
    root = _store(tmp_path)
    got = [r["directory"] for r in oa.audit_store(root, _index(), names=["acme__clean-4"])]
    assert got == ["acme__clean-4"]


def test_line_hash_reading_is_reported(tmp_path) -> None:
    recs = _records(_store(tmp_path))
    # the copy shares its body lines with the held-out text; the filler has under 3 long lines
    assert recs["acme__fork-1"]["line_covered"] >= 1
    assert recs["acme__clean-4"]["line_covered"] == 0
    summ = oa.line_reading(list(recs.values()), oa.Rule(), share=0.0001)
    assert summ["directories_at_or_above"] >= 1


def test_summary_is_recomputable_from_records(tmp_path) -> None:
    recs = list(_records(_store(tmp_path)).values())
    summ = oa.summarise(recs, oa.SENSITIVITY_FLOORS, oa.Rule())
    assert set(summ["floor_sensitivity"]) == {"10", "20", "50"}
    assert summ["cells"]["primary"]["dropped"] == 1
    assert summ["cells"]["positives_all"]["dropped"] == 2
    assert summ["cells"]["drop_flagged"]["dropped"] == 2
    assert summ["positive_matches_all"]["matches"] == 3
    assert summ["positive_matches_non_test"]["matches"] == 2
    json.dumps(summ)  # plain JSON


def test_sample_is_seeded_and_only_counted_matches(tmp_path) -> None:
    recs = list(_records(_store(tmp_path)).values())
    one = oa.sample_matches(recs, oa.Rule(), n=5, seed=0)
    assert one == oa.sample_matches(recs, oa.Rule(), n=5, seed=0)
    assert [r["directory"] for r in one] == ["acme__fork-1"]  # the only match at floor 20, non-test
    assert len(oa.sample_matches(recs, oa.Rule(positives="all"), n=1)) == 1


def test_index_round_trip_and_text_store_names(tmp_path) -> None:
    store = tmp_path / "texts"
    store.mkdir()
    (store / "Held__Repo.s0.jsonl").write_text(
        "".join(json.dumps({"h": str(i), "t": t}) + "\n" for i, t in enumerate([HELD, SMALL]))
    )
    (store / "Held__Repo.s1.jsonl").write_text(json.dumps({"h": "9", "t": HELD}) + "\n")
    probe = ProbeSet()
    probe.add("Other/Repo", function_hashes(_body(1)))
    pfile = tmp_path / "probe.json"
    pfile.write_text(probe.to_json())
    index = oa.build_held_out_index([str(pfile)], [str(p) for p in sorted(store.glob("*.jsonl"))])
    assert index.match(ast_hash_and_size(HELD)[0])[1] == ("held/repo",)
    assert index.match(ast_hash_and_size(_body(1))[0])[1] == ("other/repo",)
    manifest = oa.save_index(index, str(tmp_path / "idx"))
    assert manifest["repositories_lines"] == ["held/repo"]
    again = oa.load_index(str(tmp_path / "idx"))
    assert again.probe.ast == index.probe.ast and again.lines == index.lines
    # same inputs, same bytes
    oa.save_index(index, str(tmp_path / "idx2"))
    assert (tmp_path / "idx" / "lines.bin").read_bytes() == (
        tmp_path / "idx2" / "lines.bin"
    ).read_bytes()
    assert (tmp_path / "idx" / "ast.json.gz").read_bytes() == (
        tmp_path / "idx2" / "ast.json.gz"
    ).read_bytes()


def test_rule_rejects_unknown_positives_reading() -> None:
    with pytest.raises(ValueError):
        oa.Rule(positives="some")
