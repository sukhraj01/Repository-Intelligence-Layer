"""The mining report renders the tracked pilot summary (per-repository rows omitted there)."""

from __future__ import annotations

import json
from pathlib import Path

from ril.data_mining import report


def test_render_pilot_summary_without_per_repository_rows() -> None:
    path = Path(__file__).resolve().parents[2] / "results/mining/m2_summary.json"
    text = report.render(json.loads(path.read_text(encoding="utf-8")))
    assert "Selection by the published pool" in text
    assert "Median per-repository kept share" in text
