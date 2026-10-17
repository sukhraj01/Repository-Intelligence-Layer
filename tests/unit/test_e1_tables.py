"""Label sets, treatments and the conclusion table of pilot E2 on hand-built records."""

from __future__ import annotations

from ril.analysis.e1_tables import (
    chunk_scores_under,
    keep_positive,
    unit_gold,
    unit_scores_under,
)


def _pos(rank: int | None) -> dict:  # type: ignore[type-arg]
    return {"protocol": rank, "filter_first": rank, "lo": rank, "hi": rank}


FLAGS = {
    "imp": {"status": "found", "noise_class": "import_only", "edit_overlap": False},
    "code": {"status": "found", "noise_class": "other", "edit_overlap": True},
    "ctx": {"status": "found", "noise_class": "other", "edit_overlap": False},
    "lost": {"status": "missing", "noise_class": "unmatched"},
}


def test_keep_rules_and_unlocated_positives_stay() -> None:
    assert keep_positive(FLAGS["imp"], "base")
    assert not keep_positive(FLAGS["imp"], "clean_content")
    assert not keep_positive(FLAGS["ctx"], "edit_overlap")
    assert not keep_positive(FLAGS["imp"], "clean_both") and keep_positive(
        FLAGS["code"], "clean_both"
    )
    assert keep_positive(FLAGS["lost"], "clean_both") and keep_positive(None, "edit_overlap")


def test_removed_positive_above_a_kept_one_shifts_rank_only_when_ignored() -> None:
    row = {"n_positives": 2, "positives": {"imp": _pos(1), "code": _pos(2)}}
    neg = chunk_scores_under(row, FLAGS, "protocol", "clean_content", "neg")
    ign = chunk_scores_under(row, FLAGS, "protocol", "clean_content", "ignored")
    assert neg is not None and ign is not None
    assert neg[2] == 2 and ign[2] == 1  # first rank of the kept positive
    assert ign[0] > neg[0]


def test_a_query_whose_positives_are_all_removed_is_dropped() -> None:
    row = {"n_positives": 1, "positives": {"imp": _pos(3)}}
    assert chunk_scores_under(row, FLAGS, "protocol", "clean_content", "neg") is None


def test_positives_missing_from_the_corpus_stay_in_the_denominator() -> None:
    row = {"n_positives": 3, "positives": {"code": _pos(1), "ctx": _pos(2)}}
    res = chunk_scores_under(row, FLAGS, "protocol", "base", "neg")
    assert res is not None and res[3] == 3
    assert res[1] == 2 / 3 or abs(res[1] - 2 / 3) < 1e-9


def _unit_row() -> dict:  # type: ignore[type-arg]
    return {
        "positives": [
            {
                "corpus_id": "imp",
                "status": "found",
                "noise_class": "import_only",
                "units": ["a.py::<module>"],
                "units_all": ["a.py::<module>"],
            },
            {
                "corpus_id": "code",
                "status": "found",
                "noise_class": "other",
                "units": ["a.py::f"],
                "units_all": ["a.py::f", "a.py::K"],
            },
        ],
        "unit_edit": {"a.py::<module>": False, "a.py::f": True, "a.py::K": False},
        "unit_ranks": {
            "with_module": {
                "a.py::<module>": {"rank": 1},
                "a.py::f": {"rank": 4},
                "a.py::K": {"rank": 9},
            },
            "without_module": {"a.py::f": {"rank": 3}, "a.py::K": {"rank": 8}},
        },
    }


def test_unit_gold_follows_label_sets_and_readings() -> None:
    row = _unit_row()
    assert unit_gold(row, "units", "base") == {"a.py::<module>", "a.py::f"}
    assert unit_gold(row, "units", "clean_content") == {"a.py::f"}
    assert unit_gold(row, "units_all", "edit_overlap") == {"a.py::f"}


def test_without_the_module_unit_a_module_only_query_scores_zero_on_the_same_gold() -> None:
    row = _unit_row()
    row["positives"] = row["positives"][:1]
    with_m = unit_scores_under(row, "with_module", "units", "base", "neg")
    without = unit_scores_under(row, "without_module", "units", "base", "neg")
    assert with_m is not None and with_m[0] == 1.0
    assert without is not None and without[:2] == (0.0, 0.0)  # gold unit not in this index
    # as a distractor only: module units leave the gold set, nothing is left to score
    assert (
        unit_scores_under(row, "with_module", "units", "base", "neg", non_module_gold=True) is None
    )
