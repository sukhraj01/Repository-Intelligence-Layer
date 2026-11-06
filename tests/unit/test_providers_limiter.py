"""Limiter arithmetic and resume (docs/RQ3_PILOT.md, 'Limiter'). No network, no real time."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from ril.agent.providers.limiter import DailyCapReached, Limits, PersistentLimiter, load_limits
from tests.unit._providers_fakes import FakeClock

PT = ZoneInfo("America/Los_Angeles")


def epoch(y: int, m: int, d: int, h: int, mi: int = 0, s: int = 0) -> float:
    return datetime(y, m, d, h, mi, s, tzinfo=PT).timestamp()


def limits(rpm: int = 3, tpm: int = 1000, rpd: int = 10) -> Limits:
    return Limits(model="m", rpm=rpm, tpm=tpm, rpd=rpd, as_of="2026-11-06", margin=1.0)


def test_rpm_waits_for_the_window(tmp_path: Path) -> None:
    clk = FakeClock(epoch(2026, 11, 6, 10))
    lim = PersistentLimiter(limits(rpm=3), tmp_path / "s.jsonl", clk)
    for _ in range(3):
        lim.acquire(10)
    assert clk.slept == []
    t0 = clk.now
    lim.acquire(10)  # the fourth must wait until the first leaves the 60 s window
    assert 60.0 <= clk.now - t0 <= 60.1


def test_tpm_counts_tokens_not_requests(tmp_path: Path) -> None:
    clk = FakeClock(epoch(2026, 11, 6, 10))
    lim = PersistentLimiter(limits(rpm=100, tpm=1000), tmp_path / "s.jsonl", clk)
    lim.acquire(600)
    t0 = clk.now
    lim.acquire(300)
    assert clk.now == t0  # 900 <= 1000
    lim.acquire(300)  # 1200 > 1000: waits for the first (600) to leave
    assert clk.now - t0 >= 60.0


def test_settle_replaces_the_estimate(tmp_path: Path) -> None:
    clk = FakeClock(epoch(2026, 11, 6, 10))
    lim = PersistentLimiter(limits(rpm=100, tpm=1000), tmp_path / "s.jsonl", clk)
    g = lim.acquire(900)
    lim.settle(g, 100)
    t0 = clk.now
    lim.acquire(800)  # would not fit beside the 900 estimate, fits beside the actual 100
    assert clk.now == t0


def test_request_larger_than_the_minute_budget_is_refused(tmp_path: Path) -> None:
    lim = PersistentLimiter(limits(tpm=1000), tmp_path / "s.jsonl", FakeClock(0.0))
    with pytest.raises(ValueError):
        lim.acquire(1001)


def test_daily_cap_stops_cleanly_and_resumes_after_pacific_midnight(tmp_path: Path) -> None:
    state = tmp_path / "s.jsonl"
    clk = FakeClock(epoch(2026, 11, 6, 23, 0))
    lim = PersistentLimiter(limits(rpm=100, rpd=4), state, clk)
    for _ in range(4):
        lim.acquire(1)
    with pytest.raises(DailyCapReached) as stop:
        lim.acquire(1)
    assert stop.value.resume_at == epoch(2026, 11, 7, 0)
    # a new process (new object, same state file) still knows the day's count
    again = PersistentLimiter(limits(rpm=100, rpd=4), state, FakeClock(epoch(2026, 11, 6, 23, 30)))
    assert again.used_today() == 4
    with pytest.raises(DailyCapReached):
        again.acquire(1)
    # after midnight Pacific the count restarts
    nxt = PersistentLimiter(limits(rpm=100, rpd=4), state, FakeClock(epoch(2026, 11, 7, 0, 0, 5)))
    assert nxt.used_today() == 0
    nxt.acquire(1)
    assert nxt.used_today() == 1


def test_wait_for_daily_sleeps_to_midnight(tmp_path: Path) -> None:
    clk = FakeClock(epoch(2026, 11, 6, 23, 59, 0))
    lim = PersistentLimiter(limits(rpm=100, rpd=1), tmp_path / "s.jsonl", clk)
    lim.acquire(1)
    lim.acquire(1, wait_for_daily=True)
    assert clk.now >= epoch(2026, 11, 7, 0)


def test_the_day_is_the_pacific_day_not_utc(tmp_path: Path) -> None:
    # 07:30 UTC on Nov 7 is 23:30 Pacific on Nov 6 (standard time)
    t = datetime(2026, 11, 7, 7, 30, tzinfo=ZoneInfo("UTC")).timestamp()
    lim = PersistentLimiter(limits(), tmp_path / "s.jsonl", FakeClock(t))
    assert lim.day_of(t) == "2026-11-06"


def test_margin_scales_every_limit() -> None:
    lm = Limits(model="m", rpm=15, tpm=250000, rpd=500, as_of="x", margin=0.9)
    assert (lm.rpm_eff, lm.tpm_eff, lm.rpd_eff) == (13, 225000, 450)


def test_the_limits_file_holds_the_console_values() -> None:
    cfg = Path(__file__).resolve().parents[2] / "configs" / "agent" / "gemini_limits.yaml"
    lm = load_limits(cfg)
    assert (lm.rpm, lm.tpm, lm.rpd, lm.as_of) == (15, 250000, 500, "2026-11-06")
    assert load_limits(cfg, "gemma-4-26b").rpd == 14400
