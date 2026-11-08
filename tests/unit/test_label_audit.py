"""Tests for the label sheet (ril.evaluation.label_audit): draw, rules, sheets, key."""

from __future__ import annotations

import csv
import io
from typing import Any

import pytest

from ril.evaluation import label_audit as la


def _population(n_kept: int = 60, n_dropped: int = 90) -> list[la.Candidate]:
    out = []
    for i in range(n_kept):
        out.append(la.Candidate(f"o__r-{i // 3}", f"a/f{i}.py/fn{i}", 1 + i % 20, 1 + i % 20))
    for i in range(n_dropped):
        out.append(la.Candidate(f"o__s-{i // 3}", f"b/g{i}.py/fn{i}", 21 + i, 21 + i))
    return out


def test_stratum_boundary_is_k20() -> None:
    assert la.Candidate("d", "p", 20, 20).stratum == la.STRATUM_KEPT
    assert la.Candidate("d", "p", 21, 21).stratum == la.STRATUM_DROPPED


def test_draw_is_deterministic_and_seed_dependent() -> None:
    pop = _population()
    a = la.draw(pop, seed=1, per_stratum=40, overlap_total=20)
    b = la.draw(list(reversed(pop)), seed=1, per_stratum=40, overlap_total=20)
    c = la.draw(pop, seed=2, per_stratum=40, overlap_total=20)
    assert a.overlap == b.overlap and a.own == b.own and a.pairs == b.pairs
    assert a.pairs != c.pairs


def test_draw_counts_and_split() -> None:
    d = la.draw(_population(), seed=0, per_stratum=40, overlap_total=20)
    assert d.sample == {la.STRATUM_KEPT: 40, la.STRATUM_DROPPED: 40}
    assert d.population == {la.STRATUM_KEPT: 60, la.STRATUM_DROPPED: 90}
    assert len(d.overlap) == 20 and len(d.ids) == 80
    r1, r2 = d.own["reader_1"], d.own["reader_2"]
    assert len(r1) == len(r2) == 30
    assert set(r1) | set(r2) | set(d.overlap) == set(d.ids)
    assert not (set(r1) & set(r2)) and not (set(r1) & set(d.overlap))
    # the overlap and each reader's own pairs have equal stratum mixes
    for ids in (d.overlap, r1, r2):
        kinds = [d.ids[i].stratum for i in ids]
        assert kinds.count(la.STRATUM_KEPT) == kinds.count(la.STRATUM_DROPPED)


def test_draw_reports_a_short_stratum() -> None:
    d = la.draw(_population(n_kept=30), seed=0, per_stratum=40, overlap_total=20)
    assert d.sample[la.STRATUM_KEPT] == 30 and d.sample[la.STRATUM_DROPPED] == 40


def test_pair_ids_are_opaque_and_unique() -> None:
    d = la.draw(_population(), seed=0, per_stratum=40, overlap_total=20)
    assert len(set(d.ids)) == len(d.ids)
    assert all(len(i) == 10 and all(ch in "0123456789abcdef" for ch in i) for i in d.ids)


def test_truncate_states_the_rule() -> None:
    assert la.truncate("abc", 5) == "abc"
    cut = la.truncate("x" * 12, 5)
    assert cut.startswith("xxxxx\n[... truncated, 7 characters omitted]")


def test_other_functions_cap() -> None:
    names = [f"p::f{i}" for i in range(la.OTHER_FUNCTIONS_MAX + 4)]
    text = la.other_functions_text(names).split("\n")
    assert len(text) == la.OTHER_FUNCTIONS_MAX + 1 and text[-1] == "(+4 more)"


@pytest.mark.parametrize("lead", ["=", "+", "-", "@"])
def test_formula_leaders_are_defused(lead: str) -> None:
    assert la.spreadsheet_safe(f"{lead}1+1") == f" {lead}1+1"
    assert la.spreadsheet_safe("plain") == "plain"


def _record(i: str) -> dict[str, Any]:
    return {
        "query": "Title here\n\nBody " + "w" * 5000,
        "repo": "o/r",
        "pr_title": "Fix it",
        "path": "a/f.py",
        "qualified_name": "C.fn",
        "unit_kind": "method",
        "unit_text": "def fn():\n    return 1\n",
        "hunks": "@@ -1,2 +1,2 @@\n-    return 1\n+    return 2",
        "other_functions": ["a/g.py::g"],
    }


def test_sheet_row_applies_rules_and_leaves_reader_columns_blank() -> None:
    row = la.sheet_row(_record("x"), "abc", "reader_1")
    assert row["issue_title"] == "Title here"
    assert "truncated, 2005 characters omitted" in row["issue_body"]
    assert row["diff_hunk"].startswith(" @@")  # defused for spreadsheets
    assert row["verdict"] == row["reason"] == row["issue_function_not_edited"] == ""
    assert row["reader_id"] == "reader_1"


def test_sheets_have_no_stratum_or_rank_and_a_bom() -> None:
    d = la.draw(_population(), seed=0, per_stratum=40, overlap_total=20)
    sheets = la.build_sheets(d, {i: _record(i) for i in d.ids})
    assert set(sheets) == {"reader_overlap.csv", "reader_1.csv", "reader_2.csv"}
    for data in sheets.values():
        assert data.startswith(b"\xef\xbb\xbf")
        text = data.decode("utf-8-sig")
        header = next(csv.reader(io.StringIO(text)))
        assert tuple(header) == la.SHEET_COLUMNS
        for secret in ("stratum", "rank", "bm25", "kept", "dropped"):
            assert secret not in "".join(header)
    rows1 = list(csv.DictReader(io.StringIO(sheets["reader_1.csv"].decode("utf-8-sig"))))
    rows2 = list(csv.DictReader(io.StringIO(sheets["reader_2.csv"].decode("utf-8-sig"))))
    assert len(rows1) == len(rows2) == 20 + 30
    ids1 = [r["pair_id"] for r in rows1]
    ids2 = [r["pair_id"] for r in rows2]
    assert set(ids1) & set(ids2) == set(d.overlap)
    shared1 = [i for i in ids1 if i in set(d.overlap)]
    shared2 = [i for i in ids2 if i in set(d.overlap)]
    assert shared1 != shared2  # independent shuffles


def test_sheets_are_reproducible() -> None:
    d = la.draw(_population(), seed=0, per_stratum=40, overlap_total=20)
    recs = {i: _record(i) for i in d.ids}
    assert la.build_sheets(d, recs) == la.build_sheets(d, recs)


def test_missing_record_is_an_error() -> None:
    d = la.draw(_population(), seed=0, per_stratum=40, overlap_total=20)
    with pytest.raises(ValueError, match="no extracted record"):
        la.build_sheets(d, {})


def test_key_has_every_pair_and_the_overlap_flag() -> None:
    d = la.draw(_population(), seed=0, per_stratum=40, overlap_total=20)
    key = list(csv.DictReader(io.StringIO(la.key_csv(d, {}).decode("utf-8"))))
    assert len(key) == 80
    assert sum(int(r["in_overlap"]) for r in key) == 20
    assert {r["assignment"] for r in key} == {"overlap", "reader_1", "reader_2"}
    assert {r["stratum_population"] for r in key if r["stratum"] == la.STRATUM_KEPT} == {"60"}


def test_dense_rank_is_attached_only_where_it_exists() -> None:
    bm25 = [
        {
            "dir": "d1",
            "ranks": [
                {"positive": "p1", "rank": 3, "rank_all": 3},
                {"positive": "p2", "rank": 30, "rank_all": 31},
            ],
        }
    ]
    dense = [{"dir": "d1", "ranks": [{"positive": "p1", "rank": 25, "rank_all": 25}]}]
    cands = la.candidates_from_ranks(bm25, dense)
    assert [(c.positive, c.dense_rank) for c in cands] == [("p1", 25), ("p2", None)]
