"""Tests for the second-reader spot-check (ril.evaluation.spot_check)."""

from __future__ import annotations

import csv
import re
from pathlib import Path

import pytest

from ril.evaluation.spot_check import (
    LabelledItem,
    agreement,
    claim,
    cohen_kappa,
    context,
    definition_line,
    draw,
    key_records,
    load_items,
    make_source_reader,
    parse_edge_key,
    read_answers,
    render_sheet,
)


def _item(
    n: int, source: str = "call_site", stratum: str = "resolved", label: str = "correct"
) -> LabelledItem:
    key = f"r|invoke|a.py::f|a.py:{n}:4|b.py::g|name:function"
    return LabelledItem(source, "t.csv", str(n), stratum, parse_edge_key(key), label)


def test_parse_edge_key_with_candidates_and_empty_target() -> None:
    e = parse_edge_key(
        "flask|invoke|x.py::A.f|x.py:12:3|y.py::B.g|z.py::C.g|unknown-receiver:name-match"
    )
    assert e.targets == ("y.py::B.g", "z.py::C.g")
    assert e.site_path == "x.py" and e.site_line == 12
    e2 = parse_edge_key("flask|invoke|x.py::f|x.py:5:1||expr:callee-expression")
    assert e2.targets == () and e2.derivation == "expr:callee-expression"
    with pytest.raises(ValueError):
        parse_edge_key("a|b|c")


def test_draw_is_seeded_and_respects_quotas() -> None:
    pools = {
        "call_site": [_item(i) for i in range(1, 30)],
        "tests": [_item(i, "tests") for i in range(1, 10)],
    }
    a = draw(pools, {"call_site": 4, "tests": 2}, seed=7)
    b = draw(pools, {"call_site": 4, "tests": 2}, seed=7)
    assert [(i, it.row, it.source) for i, it in a.items] == [
        (i, it.row, it.source) for i, it in b.items
    ]
    assert len(a.items) == 6 and a.items[0][0] == "S01"
    assert sum(1 for _, it in a.items if it.source == "tests") == 2
    c = draw(pools, {"call_site": 4, "tests": 2}, seed=8)
    assert [it.row for _, it in c.items] != [it.row for _, it in a.items]
    with pytest.raises(ValueError):
        draw(pools, {"tests": 50}, seed=1)


def test_sheet_never_shows_labels_or_notes(tmp_path: Path) -> None:
    src = tmp_path / "repo"
    src.mkdir()
    (src / "a.py").write_text("\n".join(f"line {i}" for i in range(1, 40)))
    (src / "b.py").write_text("x = 1\n\ndef g(a):\n    return a\n")
    items = [_item(20, label="incorrect"), _item(3, "tests", label="unclear")]
    check = draw({"call_site": items[:1], "tests": items[1:]}, {"call_site": 1, "tests": 1}, seed=0)
    read = make_source_reader(
        {"r": {"name": "o/r", "commit": "c", "local": "repo"}}, tmp_path, tmp_path / "cache"
    )
    sheet = render_sheet(check, read, radius=6)
    # the answer categories appear in the instructions only, never in an item
    body = sheet.split("\n## ", 1)[1]
    assert re.search(r"\b(correct|incorrect|unclear)\b", body) is None
    assert (
        ">>    20 | line 20" in sheet
        and "    14 | line 14" in sheet
        and "    26 | line 26" in sheet
    )
    assert "    13 | line 13" not in sheet
    assert "line 3: `def g(a):`" in sheet
    key = key_records(check)
    assert {v["label"] for v in key["items"].values()} == {"incorrect", "unclear"}  # type: ignore[union-attr]


def test_claim_templates_cover_every_stratum() -> None:
    for source, stratum in [
        ("call_site", "resolved"),
        ("call_site", "external"),
        ("call_site", "unresolved"),
        ("ambiguous_set", "ambiguous"),
        ("tests", "body-invokes"),
        ("configures", "configures:file-path"),
    ]:
        assert claim(_item(1, source, stratum))
    with pytest.raises(ValueError):
        claim(_item(1, "call_site", "nonsense"))


def test_context_clips_at_file_edges() -> None:
    lines = [str(i) for i in range(1, 6)]
    rows = context(lines, 2, radius=6)
    assert [r[0] for r in rows] == [1, 2, 3, 4, 5] and rows[1][2] is True
    assert context(lines, 0) == [] and context([], 3) == []


def test_definition_line_matches_whole_name_only() -> None:
    lines = ["def gx():", "    pass", "class G:", "    def g(self):", "        pass"]
    assert definition_line(lines, "m.py::G.g") == (4, "    def g(self):")
    assert definition_line(lines, "m.py::G") == (3, "class G:")
    assert definition_line(lines, "m.py::<module>") is None


def test_cached_fetch_is_used_once(tmp_path: Path) -> None:
    calls: list[str] = []

    def fetch(url: str) -> bytes:
        calls.append(url)
        return b"a\nb\n"

    read = make_source_reader(
        {"r": {"name": "o/r", "commit": "abc"}}, tmp_path, tmp_path / "c", fetch
    )
    assert read("r", "x/y.py") == ["a", "b", ""]
    assert read("r", "x/y.py") == ["a", "b", ""]
    assert calls == ["https://raw.githubusercontent.com/o/r/abc/x/y.py"]
    assert read("unknown", "x.py") is None


def test_cohen_kappa_known_values() -> None:
    assert cohen_kappa(["a", "b", "a", "b"], ["a", "b", "a", "b"]) == 1.0
    # classic 2x2 example: po = 0.7, pe = 0.5 -> kappa 0.4
    a = ["y"] * 5 + ["n"] * 5
    b = ["y"] * 4 + ["n"] + ["y"] * 2 + ["n"] * 3
    assert cohen_kappa(a, b) == pytest.approx(0.4)
    assert cohen_kappa(["c", "c"], ["c", "c"]) == 1.0
    with pytest.raises(ValueError):
        cohen_kappa([], [])


def test_read_answers_and_agreement(tmp_path: Path) -> None:
    p = tmp_path / "answers.csv"
    with p.open("w", newline="") as h:
        w = csv.writer(h)
        w.writerow(["item", "label"])
        w.writerows([["S01", "Correct "], ["S02", "incorrect"], ["S09", "correct"]])
    ans = read_answers(p)
    assert ans == {"S01": "correct", "S02": "incorrect", "S09": "correct"}
    key = {
        "S01": {"label": "correct", "source": "tests"},
        "S02": {"label": "correct", "source": "call_site"},
        "S03": {"label": "unclear", "source": "call_site"},
    }
    rep = agreement(key, ans)
    assert rep["n_answered"] == 2 and rep["missing"] == ["S03"] and rep["unknown_items"] == ["S09"]
    assert rep["agreement"] == 0.5
    bad = tmp_path / "bad.csv"
    bad.write_text("item,label\nS01,maybe\n")
    with pytest.raises(ValueError):
        read_answers(bad)


def test_load_items_splits_ambiguous_rows(tmp_path: Path) -> None:
    def write(name: str, header: list[str], rows: list[list[str]]) -> None:
        with (tmp_path / name).open("w", newline="") as h:
            w = csv.writer(h)
            w.writerow(header)
            w.writerows(rows)

    k = "r|invoke|a.py::f|a.py:3:1|b.py::g|d"
    write(
        "p_edge_inspection_sample.csv",
        ["n", "repo", "stratum", "edge_key", "label", "truth", "note"],
        [
            ["1", "r", "ambiguous", k, "incorrect", "external", "x"],
            ["2", "r", "resolved", k, "correct", "in_repo", ""],
        ],
    )
    write(
        "p_tests_edges_precision_sample.csv",
        ["n", "repo", "stratum", "edge_key", "label", "note"],
        [["1", "r", "body-invokes", k, "unclear", ""]],
    )
    write(
        "p_configures_edges_precision_sample.csv",
        ["n", "repo", "stratum", "edge_key", "label", "note"],
        [["1", "r", "configures:file-path", k, "correct", ""]],
    )
    pools = load_items(tmp_path)
    assert [len(pools[s]) for s in ("call_site", "ambiguous_set", "tests", "configures")] == [
        1,
        1,
        1,
        1,
    ]
