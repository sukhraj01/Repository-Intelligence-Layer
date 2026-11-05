"""Tests for the label-sheet scorer (ril.evaluation.label_audit_score), synthetic filled sheets."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from ril.evaluation import label_audit as la
from ril.evaluation import label_audit_score as sc

K, D = la.STRATUM_KEPT, la.STRATUM_DROPPED
POP = {K: 1000, D: 3000}


def _key(n_per: int = 20, overlap_per: int = 10) -> dict[str, sc.KeyRow]:
    key = {}
    for s in (K, D):
        for i in range(n_per):
            pid = f"{'k' if s == K else 'd'}{i:02d}"
            key[pid] = sc.KeyRow(pid, s, f"dir{i // 2}-{s}", i < overlap_per, POP[s], None)
    return key


def _answers(
    reader: str, verdict: dict[str, str], missing: dict[str, str] | None = None
) -> sc.Answers:
    return sc.Answers(reader, dict(verdict), dict(missing or {}), {})


def test_wilson_matches_known_value() -> None:
    interval = sc.wilson(5, 10)
    assert interval is not None
    assert interval[0] == pytest.approx(0.2366, abs=1e-3)
    assert interval[1] == pytest.approx(0.7634, abs=1e-3)
    assert sc.wilson(0, 0) is None
    zero = sc.wilson(0, 20)
    assert zero is not None and zero[0] == 0.0 and 0 < zero[1] < 0.2


def test_perfect_agreement_and_a_known_disagreement() -> None:
    key = _key()
    ids = [p for p, k in key.items() if k.in_overlap]
    a = {i: la.RELEVANT if n % 2 else la.NOT_RELEVANT for n, i in enumerate(ids)}
    same = sc.agreement(_answers("r1", a), _answers("r2", a), "verdict", key, seed=0, draws=200)
    assert same["agreement"] == 1.0 and same["kappa"] == 1.0 and same["disagreements"] == []
    b = dict(a)
    for i in ids[:5]:
        b[i] = la.RELEVANT if a[i] == la.NOT_RELEVANT else la.NOT_RELEVANT
    diff = sc.agreement(_answers("r1", a), _answers("r2", b), "verdict", key, seed=0, draws=200)
    assert diff["n_both_answered"] == 20
    assert diff["agreement"] == pytest.approx(15 / 20)
    assert diff["kappa"] == pytest.approx(0.5)  # po 0.75, pe 0.5
    assert len(diff["disagreements"]) == 5
    lo, hi = diff["kappa_bootstrap95"]
    assert lo < 0.5 < hi


def test_cannot_tell_is_unresolved_and_disagreement_is_disputed() -> None:
    r1 = _answers(
        "r1", {"a": la.RELEVANT, "b": la.CANNOT_TELL, "c": la.NOT_RELEVANT, "d": la.RELEVANT}
    )
    r2 = _answers("r2", {"c": la.NOT_RELEVANT, "d": la.NOT_RELEVANT})
    final = sc.combine([r1, r2], "verdict")
    assert final == {
        "a": la.RELEVANT,
        "b": la.CANNOT_TELL,
        "c": la.NOT_RELEVANT,
        "d": sc.DISPUTED,
    }


def test_two_way_agreement_leaves_out_cannot_tell() -> None:
    key = _key()
    ids = [p for p, k in key.items() if k.in_overlap]
    a = {i: la.RELEVANT for i in ids}
    b = dict(a)
    b[ids[0]] = la.CANNOT_TELL
    rep = sc.agreement(_answers("r1", a), _answers("r2", b), "verdict", key, seed=0, draws=50)
    assert rep["agreement"] == pytest.approx(19 / 20)
    assert rep["two_way_without_cannot_tell"]["n"] == 19
    assert rep["two_way_without_cannot_tell"]["agreement"] == 1.0


def test_rate_readings_bracket_the_excluded_value() -> None:
    key = _key()
    final: dict[str, str] = {}
    for pid, k in key.items():
        n = int(pid[-2:])
        if k.stratum == K:
            final[pid] = la.NOT_RELEVANT if n < 4 else (la.CANNOT_TELL if n < 6 else la.RELEVANT)
        else:
            final[pid] = la.NOT_RELEVANT if n < 12 else (la.CANNOT_TELL if n < 14 else la.RELEVANT)
    t = sc.rate_table(final, key, la.NOT_RELEVANT, la.RELEVANT, population=POP, seed=0, draws=300)
    kept = {r: t["readings"][r]["by_stratum"][K] for r in sc.READINGS}
    assert (kept["excluded"]["events"], kept["excluded"]["n"]) == (4, 18)
    assert (kept["lower"]["events"], kept["lower"]["n"]) == (4, 20)
    assert (kept["upper"]["events"], kept["upper"]["n"]) == (6, 20)
    dropped = {r: t["readings"][r]["by_stratum"][D] for r in sc.READINGS}
    assert dropped["excluded"]["share"] == pytest.approx(12 / 18)
    w = {r: t["readings"][r]["population_weighted"] for r in sc.READINGS}
    assert w["excluded"]["overall_weighted"]["value"] == pytest.approx(
        0.25 * 4 / 18 + 0.75 * 12 / 18
    )
    assert (
        w["lower"]["overall_weighted"]["value"]
        <= w["excluded"]["overall_weighted"]["value"]
        <= w["upper"]["overall_weighted"]["value"]
    )
    p_k, p_d = 4 / 18, 12 / 18
    expect = 3000 * p_d / (3000 * p_d + 1000 * p_k)
    assert w["excluded"]["noisy_dropped_share"]["value"] == pytest.approx(expect)
    lo, hi = w["excluded"]["noisy_dropped_share"]["bootstrap95"]
    assert lo <= expect <= hi
    assert t["n_unresolved_by_stratum"] == {K: 2, D: 2}


def test_all_clean_sample_gives_zero_rates_and_no_findability() -> None:
    key = _key()
    final = {p: la.RELEVANT for p in key}
    t = sc.rate_table(final, key, la.NOT_RELEVANT, la.RELEVANT, population=POP, seed=0, draws=50)
    r = t["readings"]["excluded"]
    assert r["population_weighted"]["overall_weighted"]["value"] == 0.0
    assert r["population_weighted"]["noisy_dropped_share"]["value"] is None
    assert r["by_stratum"][K]["wilson95"][0] == 0.0


def test_a_stratum_with_no_answers_is_reported_as_none() -> None:
    key = _key()
    final = {p: la.NOT_RELEVANT for p, k in key.items() if k.stratum == K}
    t = sc.rate_table(final, key, la.NOT_RELEVANT, la.RELEVANT, population=POP, seed=0, draws=20)
    r = t["readings"]["excluded"]
    assert r["by_stratum"][D]["share"] is None and r["by_stratum"][D]["wilson95"] is None
    assert r["population_weighted"]["overall_weighted"]["value"] is None


def test_full_report_end_to_end_with_text() -> None:
    key = _key()
    ids = sorted(key)
    r1 = _answers("reader_1", {i: la.RELEVANT for i in ids}, {i: la.NO for i in ids})
    shared = [i for i in ids if key[i].in_overlap]
    r2 = _answers("reader_2", {i: la.RELEVANT for i in shared}, {i: la.NO for i in shared})
    r2.verdict[ids[0]] = la.NOT_RELEVANT
    rep = sc.score(key, [r1, r2], seed=0, draws=100)
    assert rep["agreement_verdict"]["n_both_answered"] == 20
    assert rep["verdict_counts"][sc.DISPUTED] == 1
    assert "measured on a sample" in rep["wrong_positive"]["evidence"]
    text = sc.format_text(rep)
    assert "kappa" in text and "measured on a sample" in text


def _write_sheet(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        w = csv.DictWriter(handle, fieldnames=list(la.SHEET_COLUMNS))
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in la.SHEET_COLUMNS})


def test_read_sheet_normalises_case_and_rejects_bad_values(tmp_path: Path) -> None:
    key = _key()
    p = tmp_path / "s.csv"
    _write_sheet(
        p,
        [
            {
                "pair_id": "k00",
                "verdict": " Not Relevant ",
                "issue_function_not_edited": "YES",
                "reader_id": "reader_1",
            },
            {"pair_id": "k01", "verdict": "cannot_tell", "reader_id": "reader_1"},
            {"pair_id": "k02", "reader_id": "reader_1"},
        ],
    )
    a = sc.read_sheet(str(p), key)
    assert a.verdict == {"k00": la.NOT_RELEVANT, "k01": la.CANNOT_TELL}
    assert a.missing == {"k00": la.YES}
    _write_sheet(p, [{"pair_id": "k00", "verdict": "maybe", "reader_id": "reader_1"}])
    with pytest.raises(sc.SheetError, match="not one of"):
        sc.read_sheet(str(p), key)
    _write_sheet(p, [{"pair_id": "nope", "verdict": "relevant"}])
    with pytest.raises(sc.SheetError, match="not a pair"):
        sc.read_sheet(str(p), key)
    _write_sheet(
        p, [{"pair_id": "k00", "verdict": "relevant"}, {"pair_id": "k00", "verdict": "relevant"}]
    )
    with pytest.raises(sc.SheetError, match="twice"):
        sc.read_sheet(str(p), key)
    _write_sheet(p, [{"pair_id": "k00", "reader_id": "a"}, {"pair_id": "k01", "reader_id": "b"}])
    with pytest.raises(sc.SheetError, match="several reader ids"):
        sc.read_sheet(str(p), key)


def test_key_round_trip_through_the_real_writer(tmp_path: Path) -> None:
    pop = [
        la.Candidate(f"o__r-{i}", f"a/f{i}.py/fn", 1 + i, 1 + i, 5 if i % 2 else None)
        for i in range(30)
    ]
    pop += [la.Candidate(f"o__s-{i}", f"b/g{i}.py/fn", 25 + i, 25 + i) for i in range(30)]
    d = la.draw(pop, seed=3, per_stratum=15, overlap_total=10)
    path = tmp_path / "key.csv"
    path.write_bytes(la.key_csv(d, {}))
    key = sc.read_key(str(path))
    assert len(key) == 30
    assert {k.population for k in key.values() if k.stratum == K} == {20}
    assert sum(k.in_overlap for k in key.values()) == 10
