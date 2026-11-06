"""Persistent rate limiter for a hosted model with per-minute and per-day quotas.

Implements ``docs/RQ3_PILOT.md`` ("Limiter"). Three limits are honoured: requests per minute, tokens
per minute (a sliding 60-second window) and requests per day, where the day is the Pacific-time
calendar day because the quota resets at midnight Pacific. Every granted request is appended to a
JSON-lines file before it is sent, so a stopped run resumes the next day (or after a crash) with the
day's count intact and never exceeds the cap by restarting. A request counts against the day when it
is sent, whatever its outcome (a 429 or 5xx still used quota), which is the conservative reading.
"""

from __future__ import annotations

import json
import math
import os
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol
from zoneinfo import ZoneInfo

import yaml

WINDOW_SECONDS = 60.0
_EPS = 0.01


class Clock(Protocol):
    def time(self) -> float: ...

    def sleep(self, seconds: float) -> None: ...


class SystemClock:
    def time(self) -> float:
        return time.time()

    def sleep(self, seconds: float) -> None:
        time.sleep(max(0.0, seconds))


class DailyCapReached(Exception):
    """The day's quota is used; ``resume_at`` is the next Pacific midnight (epoch seconds)."""

    def __init__(self, resume_at: float, used: int, cap: int) -> None:
        super().__init__(
            f"daily request cap reached ({used}/{cap}); resume after epoch {resume_at:.0f}"
        )
        self.resume_at = resume_at
        self.used = used
        self.cap = cap


@dataclass(frozen=True)
class Limits:
    """Quotas of one model, as read from the console on ``as_of`` (not guaranteed)."""

    model: str
    rpm: int
    tpm: int
    rpd: int
    as_of: str
    timezone: str = "America/Los_Angeles"
    margin: float = 0.9

    def __post_init__(self) -> None:
        if min(self.rpm, self.tpm, self.rpd) <= 0 or not 0 < self.margin <= 1:
            raise ValueError("limits must be positive and the margin in (0, 1]")

    @property
    def rpm_eff(self) -> int:
        return max(1, math.floor(self.rpm * self.margin))

    @property
    def tpm_eff(self) -> int:
        return max(1, math.floor(self.tpm * self.margin))

    @property
    def rpd_eff(self) -> int:
        return max(1, math.floor(self.rpd * self.margin))


def load_limits(path: str | Path, model: str | None = None) -> Limits:
    """Read the limits of ``model`` (default: the file's selected model) from a YAML file."""
    cfg: dict[str, Any] = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    name = model or str(cfg["selected_model"])
    if name not in cfg["models"]:
        raise KeyError(f"model {name!r} has no limits in {path}")
    m = cfg["models"][name]
    return Limits(
        model=name,
        rpm=int(m["rpm"]),
        tpm=int(m["tpm"]),
        rpd=int(m["rpd"]),
        as_of=str(cfg["as_of"]),
        timezone=str(cfg.get("timezone", "America/Los_Angeles")),
        margin=float(cfg.get("margin", 0.9)),
    )


@dataclass(frozen=True)
class Grant:
    grant_id: int
    estimated_tokens: int


@dataclass
class _Entry:
    t: float
    day: str
    tokens: int


class PersistentLimiter:
    """Grants requests within the three quotas; state lives in a JSON-lines file."""

    def __init__(self, limits: Limits, state_path: str | Path, clock: Clock | None = None) -> None:
        self.limits = limits
        self.path = Path(state_path)
        self.clock: Clock = clock or SystemClock()
        self._tz = ZoneInfo(limits.timezone)
        self._entries: dict[int, _Entry] = {}
        self._next_id = 1
        self._load()

    # ---------------------------------------------------------------- persistence

    def _load(self) -> None:
        if not self.path.exists():
            return
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            gid = int(row["id"])
            if row["kind"] == "grant":
                self._entries[gid] = _Entry(float(row["t"]), str(row["day"]), int(row["tokens"]))
            elif gid in self._entries:
                self._entries[gid].tokens = int(row["tokens"])
            self._next_id = max(self._next_id, gid + 1)

    def _append(self, row: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    # ---------------------------------------------------------------- arithmetic

    def day_of(self, t: float) -> str:
        return datetime.fromtimestamp(t, self._tz).date().isoformat()

    def next_midnight(self, t: float) -> float:
        d = datetime.fromtimestamp(t, self._tz).date() + timedelta(days=1)
        return datetime.combine(d, datetime.min.time(), tzinfo=self._tz).timestamp()

    def used_today(self, now: float | None = None) -> int:
        day = self.day_of(self.clock.time() if now is None else now)
        return sum(1 for e in self._entries.values() if e.day == day)

    def remaining_today(self, now: float | None = None) -> int:
        return max(0, self.limits.rpd_eff - self.used_today(now))

    def _wait_for_window(self, now: float, est_tokens: int) -> float:
        """Seconds until the minute window admits one more request of ``est_tokens`` (0 if now)."""
        window = sorted(
            (e for e in self._entries.values() if e.t > now - WINDOW_SECONDS), key=lambda e: e.t
        )
        count = len(window)
        tokens = sum(e.tokens for e in window)
        for e in window:
            if count + 1 <= self.limits.rpm_eff and tokens + est_tokens <= self.limits.tpm_eff:
                return 0.0
            count -= 1
            tokens -= e.tokens
            wait = e.t + WINDOW_SECONDS - now + _EPS
            if count + 1 <= self.limits.rpm_eff and tokens + est_tokens <= self.limits.tpm_eff:
                return max(wait, _EPS)
        return 0.0

    # ---------------------------------------------------------------- public

    def acquire(self, est_tokens: int, *, wait_for_daily: bool = False) -> Grant:
        """Block until a request is allowed, then record it. Stops cleanly at the daily cap."""
        if est_tokens > self.limits.tpm_eff:
            raise ValueError(
                f"one request of about {est_tokens} tokens exceeds the per-minute budget "
                f"{self.limits.tpm_eff}"
            )
        while True:
            now = self.clock.time()
            if self.used_today(now) >= self.limits.rpd_eff:
                resume = self.next_midnight(now)
                if not wait_for_daily:
                    raise DailyCapReached(resume, self.used_today(now), self.limits.rpd_eff)
                self.clock.sleep(resume - now + _EPS)
                continue
            wait = self._wait_for_window(now, est_tokens)
            if wait > 0:
                self.clock.sleep(wait)
                continue
            gid = self._next_id
            self._next_id += 1
            entry = _Entry(now, self.day_of(now), est_tokens)
            self._entries[gid] = entry
            self._append(
                {"id": gid, "kind": "grant", "t": now, "day": entry.day, "tokens": est_tokens}
            )
            return Grant(gid, est_tokens)

    def settle(self, grant: Grant, actual_tokens: int) -> None:
        """Replace the estimate by the token count the provider reported."""
        if grant.grant_id in self._entries:
            self._entries[grant.grant_id].tokens = actual_tokens
            self._append({"id": grant.grant_id, "kind": "settle", "tokens": actual_tokens})


def pacific_date(t: float, tz: str = "America/Los_Angeles") -> date:
    return datetime.fromtimestamp(t, ZoneInfo(tz)).date()
