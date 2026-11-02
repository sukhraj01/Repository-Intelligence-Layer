"""Agreement with the published pool and the hand-check file (E-MINE-PILOT, stage M1)."""

from __future__ import annotations

import json

from ril.data_mining import agreement
from ril.data_mining.validation import render_entry


def _pos(pool_id: str, *, in_corpus: bool = True, is_test: bool = False) -> dict[str, object]:
    return {
        "pool_id": pool_id,
        "in_corpus": in_corpus,
        "is_test": is_test,
        "unit_kind": "function" if in_corpus else "module",
        "removed_lines": 1,
        "inserted_lines": 2,
        "unit_lines": 5,
    }


def _meta(positives: list[dict[str, object]]) -> dict[str, object]:
    return {
        "repo": "a/b",
        "pr": 7,
        "base_commit": "b" * 40,
        "head_commit": "h" * 40,
        "positives": positives,
        "counters": {"added_function_defs": 1},
    }


def test_path_and_test_rule_on_pool_ids() -> None:
    assert agreement.path_of("pkg/mod.py/Cls.meth") == "pkg/mod.py"
    assert agreement.is_test_id("tests/test_x.py/test_a")
    assert not agreement.is_test_id("pkg/mod.py/f")


def test_exact_match_extra_missing_and_their_reasons() -> None:
    meta = _meta(
        [
            _pos("pkg/a.py/f"),
            _pos("pkg/a.py/g"),
            _pos("tests/test_a.py/test_f", is_test=True),
            _pos("pkg/a.py/<module>", in_corpus=False),
        ]
    )
    mined_corpus = frozenset({"pkg/a.py/f", "pkg/a.py/g", "pkg/a.py/h", "tests/test_a.py/test_f"})
    pool = frozenset({"pkg/a.py/f", "pkg/a.py/h", "pkg/a.py/<module>", "pkg/gone.py/x"})
    row = agreement.compare_pr(meta, mined_corpus, pool, frozenset({"pkg/a.py/g", "pkg/a.py/f"}))
    assert row["all"]["extra"] == ["pkg/a.py/g", "tests/test_a.py/test_f"]
    assert row["all"]["missing"] == ["pkg/a.py/<module>", "pkg/a.py/h", "pkg/gone.py/x"]
    assert row["missing_why"] == {
        "pkg/a.py/<module>": "in_mined_side_table",
        "pkg/a.py/h": "in_mined_corpus_not_positive",
        "pkg/gone.py/x": "not_in_mined_corpus",
    }
    assert row["extra_why"] == {
        "pkg/a.py/g": "non_test_file",
        "tests/test_a.py/test_f": "test_file",
    }
    assert row["non_test"]["extra"] == ["pkg/a.py/g"]
    assert not row["all"]["exact"] and not row["non_test"]["exact"]
    assert row["extra_in_pool_corpus"] == ["pkg/a.py/g"]


def test_identical_sets_agree_and_empty_sets_agree() -> None:
    meta = _meta([_pos("pkg/a.py/f")])
    same = agreement.compare_pr(
        meta, frozenset({"pkg/a.py/f"}), frozenset({"pkg/a.py/f"}), frozenset()
    )
    assert same["all"]["exact"] and same["all"]["jaccard"] == 1.0
    assert agreement.jaccard(frozenset(), frozenset()) == 1.0


def test_test_positives_change_the_non_test_reading_only() -> None:
    meta = _meta([_pos("pkg/a.py/f"), _pos("tests/test_a.py/t", is_test=True)])
    row = agreement.compare_pr(
        meta,
        frozenset({"pkg/a.py/f", "tests/test_a.py/t"}),
        frozenset({"pkg/a.py/f"}),
        frozenset(),
    )
    assert not row["all"]["exact"] and row["non_test"]["exact"]
    table = agreement.summarize([row])
    assert table["all"]["exact_share"] == 0.0 and table["non_test"]["exact_share"] == 1.0
    assert table["pool_positives_in_test_files"] == 0
    share = agreement.mined_test_share([meta])
    assert share == {"mined_positives": 2, "in_test_files": 1, "share": 0.5}


def test_hand_check_entry_shows_title_hunks_and_positives() -> None:
    text = render_entry(
        _meta([_pos("pkg/a.py/f"), _pos("pkg/a.py/<module>", in_corpus=False)]),
        "Crash on empty input",
        {"pkg/a.py": "@@ -1,2 +1,2 @@\n-x\n+y\n" + "\n".join(f"+l{i}" for i in range(80))},
        3,
    )
    assert "## 3. a/b#7" in text and "Crash on empty input" in text
    assert "`pkg/a.py/f`: function, corpus" in text and "side table" in text
    assert "more lines cut" in text
    json.dumps(text)


def test_variants_drop_insertions_removals_and_functions_the_pool_corpus_lacks() -> None:
    keep = _pos("pkg/a.py/keep")
    ins = dict(_pos("pkg/a.py/ins"), removed_lines=0, inserted_lines=3)
    gone = dict(_pos("pkg/a.py/gone"), removed_lines=5, inserted_lines=0, unit_lines=5)
    asyn = _pos("pkg/a.py/asyn")
    test = _pos("tests/test_a.py/t", is_test=True)
    meta = _meta([keep, ins, gone, asyn, test])
    corpus = frozenset({"pkg/a.py/keep", "pkg/a.py/ins", "pkg/a.py/gone"})
    row = agreement.compare_pr(meta, frozenset(), frozenset({"pkg/a.py/keep"}), corpus)
    v = row["variants"]
    assert v["non_test"]["extra"] == 3 and not v["non_test"]["exact"]
    assert v["non_test_no_pure_insertion"]["extra"] == 2
    assert v["non_test_no_whole_function_removal"]["extra"] == 2
    assert v["non_test_no_insertion_no_removal"]["extra"] == 1
    assert v["non_test_no_insertion_no_removal_in_pool_corpus"]["exact"]
    table = agreement.summarize([row])
    name = "non_test_no_insertion_no_removal_in_pool_corpus"
    assert table["variants"][name]["exact_share"] == 1.0
