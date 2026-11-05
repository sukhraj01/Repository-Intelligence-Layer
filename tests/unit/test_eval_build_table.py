"""D100 build table: measured next to estimated, refuses a store with missing vectors."""

from __future__ import annotations

import pytest

from ril.analysis import eval_build_table as ebt

INV = {
    "o/r": {
        "units_per_snapshot": "100",
        "parse_seconds": "10.0",
        "distinct_unit_texts": "500",
        "encode_gpu_hours_at_229": "0.01",
        "encode_gpu_hours_at_178": "0.02",
    }
}
CS = {"o/r": {"snapshots": 3, "units_median": 90, "seconds": {"parse": 4.04}, "seconds_total": 9.0}}
STORES = [{"store": "units__o__r", "seconds_now": 36.0, "texts": 3600}]


def test_row_values() -> None:
    ver = {"o__r": {"distinct_hashes": 300, "missing": 0}}
    (row,) = ebt.build_rows([{"repository": "o/r", "l2_queries": 5}], INV, CS, ver, STORES)
    assert row["texts_per_second"] == 100.0
    assert row["encode_gpu_hours_measured"] == 0.01
    assert row["distinct_unit_texts_full_measured"] == 300
    assert set(row) == set(ebt.COLUMNS)


def test_missing_vectors_refused() -> None:
    ver = {"o__r": {"distinct_hashes": 300, "missing": 2}}
    with pytest.raises(ValueError):
        ebt.build_rows([{"repository": "o/r", "l2_queries": 5}], INV, CS, ver, STORES)
