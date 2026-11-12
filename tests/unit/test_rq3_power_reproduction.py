"""The stored power simulation (run-to-run noise, N = 327) is the one the report quotes.

Implements ``docs/RQ3_PILOT.md`` (D113). The fast tests read the stored rows and check the
statements the report makes about them; the slow test reruns the seeded simulation and compares
every stored row at N = 327.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

from ril.analysis import rq3_power_noise

ROOT = Path(__file__).resolve().parents[2]
DRIVER = ROOT / "results" / "rq3_driver"

STORED_SHA256 = {
    "rq3_power_run_noise.csv": ("efab8f2f5491dacda10bc0d963084ce4bd197a1008f11fe0aa5c02434a8a19b8"),
    "rq3_power_run_noise_mdd.csv": (
        "2b2130c9fed1bd1557e412270a2051fa782a650ffb5b640c084f64460c092363"
    ),
    "rq3_power_run_noise_assumptions.json": (
        "1784b3ff4ecc6b6b58c4489bed734b5df85c776d82845be01b5dd24b81c70722"
    ),
}


def _rows(name: str) -> list[dict[str, str]]:
    with open(DRIVER / name, encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_stored_outputs_have_their_recorded_hashes() -> None:
    for name, digest in STORED_SHA256.items():
        assert hashlib.sha256((DRIVER / name).read_bytes()).hexdigest() == digest, name


def test_stored_settings_are_the_ones_of_the_module() -> None:
    cfg = json.loads((DRIVER / "rq3_power_run_noise_assumptions.json").read_text())
    assert cfg["seed"] == 0
    assert cfg["sims"] == 500
    assert cfg["permutations"] == 2000
    assert cfg["same_reply"] == rq3_power_noise.SAME_REPLY
    assert 327 in cfg["n"]


def test_report_range_and_the_four_point_statement_hold_on_the_rows() -> None:
    mdd = [r for r in _rows("rq3_power_run_noise_mdd.csv") if r["n"] == "327"]
    values = [float(r["mdd_points"]) for r in mdd]
    assert len(values) == 18
    assert round(min(values), 1) == 4.4
    assert round(max(values), 1) == 9.7
    rows = [r for r in _rows("rq3_power_run_noise.csv") if r["n"] == "327"]
    at_four = [float(r["power"]) for r in rows if r["effect_points"] == "4.0"]
    assert len(at_four) == 18
    assert max(at_four) < rq3_power_noise.TARGET
    size = [float(r["power"]) for r in rows if r["effect_points"] == "0.0"]
    assert 0.024 <= min(size) and max(size) <= 0.05


@pytest.mark.slow
def test_rerun_reproduces_every_stored_row_at_327() -> None:
    cells = rq3_power_noise.power_table(n=327, sims=500, permutations=2000, seed=0)
    fresh = rq3_power_noise.to_rows(cells, 327)
    stored = [r for r in _rows("rq3_power_run_noise.csv") if r["n"] == "327"]
    assert len(fresh) == len(stored)
    for a, b in zip(fresh, stored, strict=True):
        assert {k: str(v) for k, v in a.items()} == b
    mdd = [{"n": 327, **m} for m in rq3_power_noise.minimum_detectable(cells)]
    stored_mdd = [r for r in _rows("rq3_power_run_noise_mdd.csv") if r["n"] == "327"]
    assert len(mdd) == len(stored_mdd)
    for a, b in zip(mdd, stored_mdd, strict=True):
        assert float(a["mdd_points"]) == float(b["mdd_points"])
