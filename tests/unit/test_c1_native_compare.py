"""Unit tests for the native-versus-reported comparison (E-C-CATCHUP)."""

from __future__ import annotations

from pathlib import Path

import pytest

from ril.analysis import c1_native_compare as cmp


def _cell(mean: float, low: float, high: float, n: int = 10, repos: int = 2) -> dict[str, object]:
    return {
        "level": "L2",
        "condition": "original",
        "metric": "ndcg10",
        "n": n,
        "repositories": repos,
        "mean": mean,
        "low": low,
        "high": high,
    }


def test_equal_cells_agree() -> None:
    rows = cmp.compare_cells([_cell(0.2, 0.1, 0.3)], [_cell(0.2, 0.1, 0.3)])
    assert rows[0]["verdict"] == "agree"
    assert rows[0]["diff_mean"] == 0.0


def test_interval_difference_is_not_rounded_away() -> None:
    rows = cmp.compare_cells([_cell(0.2, 0.1, 0.31)], [_cell(0.2, 0.1, 0.3)])
    assert rows[0]["verdict"] == "point_only"


def test_point_or_sample_difference_is_a_difference() -> None:
    assert (
        cmp.compare_cells([_cell(0.21, 0.1, 0.3)], [_cell(0.2, 0.1, 0.3)])[0]["verdict"] == "differ"
    )
    assert (
        cmp.compare_cells([_cell(0.2, 0.1, 0.3, n=11)], [_cell(0.2, 0.1, 0.3)])[0]["verdict"]
        == "differ"
    )


def test_missing_or_duplicate_cell_is_an_error() -> None:
    other = {**_cell(0.2, 0.1, 0.3), "metric": "recall100"}
    with pytest.raises(ValueError):
        cmp.compare_cells([_cell(0.2, 0.1, 0.3), other], [_cell(0.2, 0.1, 0.3)])
    with pytest.raises(ValueError):
        cmp.compare_cells([_cell(0.2, 0.1, 0.3)] * 2, [_cell(0.2, 0.1, 0.3)] * 2)


def test_paired_deltas_and_listing(tmp_path: Path) -> None:
    def row(cond: str, nd: float, rc: float) -> dict[str, object]:
        return {
            "level": "L2",
            "dataset": "d",
            "folder": "f",
            "repo": "a/b",
            "query_id": "q1",
            "condition": cond,
            "ndcg10": nd,
            "recall100": rc,
        }

    rows = [row("original", 0.2, 0.4), row("rewrite", 0.5, 0.4)]
    deltas = cmp.paired_deltas(rows)
    assert deltas["L2:ndcg10"] == pytest.approx(0.3)
    assert deltas["L2:recall100"] == 0.0
    (tmp_path / "x.txt").write_text("abc")
    listing = cmp.run_file_listing(tmp_path)
    assert listing == [
        {
            "path": "x.txt",
            "bytes": 3,
            "sha256": "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
        }
    ]


def test_load_reported_requires_twelve_cells(tmp_path: Path) -> None:
    import json

    path = tmp_path / "summary.json"
    cells = [{**_cell(0.2, 0.1, 0.3), "metric": f"m{i}"} for i in range(12)]
    path.write_text(json.dumps({"reported_cli_summary": {"metrics": cells}}))
    assert len(cmp.load_reported(path)) == 12
    path.write_text(json.dumps({"reported_cli_summary": {"metrics": cells[:11]}}))
    with pytest.raises(ValueError):
        cmp.load_reported(path)
