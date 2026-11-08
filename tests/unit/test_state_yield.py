"""Yield and gate G2 from a state log (``ril.data_mining.state_yield``)."""

from __future__ import annotations

import json
from pathlib import Path

from ril.data_mining import state_yield as sy


def _row(key: str, status: str, reason: str = "", positives: int = 0) -> dict:
    return {"key": key, "status": status, "reason": reason, "counters": {"positives": positives}}


def test_counts_reasons_and_projection(tmp_path: Path) -> None:
    rows = (
        [_row(f"a/b#{i}", "mined", positives=5) for i in range(6)]
        + [_row("a/b#7", "no_positive"), _row("c/d#1", "no_python_change")]
        + [
            _row("c/d#2", "quarantined", "snapshot_timeout"),
            _row("c/d#3", "quarantined", "corpus_error:ValueError"),
            _row("c/d#4", "quarantined", "changed_file_unparseable:python2-print"),
        ]
    )
    path = tmp_path / "state.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    rep = sy.yield_report(sy.read_state(str(path)), target_attempted=1000)
    assert rep["attempted"] == 11 and rep["status"]["mined"] == 6
    assert rep["timeout_quarantined"] == 1
    assert rep["quarantine_by_reason"]["corpus_error:ValueError"] == 1
    assert rep["positives_unrestricted"] == 30
    assert rep["projection"]["positives_unrestricted"] == round(30 * 1000 / 11)
    assert rep["projection"]["g2_met_unrestricted"] is False
    assert rep["g2_pilot_directories_met"] is False


def test_empty_log_does_not_divide() -> None:
    rep = sy.yield_report([], target_attempted=10)
    assert rep["attempted"] == 0 and rep["mined_share"] is None and "projection" not in rep
