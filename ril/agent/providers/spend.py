"""Spend guard for paid model calls. Implements ``docs/RQ3_PILOT.md`` (D114).

The driver keeps its own running cost from the billed tokens of every call (input, and output
including thought tokens, at the dated list prices of ``configs/agent/prices.yaml``) and refuses
a call whose worst case would take the total past a cap given on the command line. The worst case
of a call is its input estimated at ``CHARS_PER_TOKEN_FLOOR`` characters per token plus the full
``max_output_tokens`` billed as output. The provider-side hard cap is a second, independent layer.
"""

from __future__ import annotations

import fcntl
import json
import math
import os
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from ril.agent.providers.gemini import CallResult

CHARS_PER_TOKEN_FLOOR = 3.0
"""Characters per input token assumed for the worst case (the pilot's prompts averaged more)."""


class SpendCapReached(Exception):
    """The next call could take the spend past the cap."""


@dataclass(frozen=True)
class Price:
    model: str
    input_per_m: float
    output_per_m: float
    verified: bool
    as_of: str
    cached_input_per_m: float | None = None
    """Price of input tokens served from the provider's cache; ``None`` = no discount known, so
    cached tokens are priced like any input (never cheaper than reported)."""

    def cost(self, input_tokens: int, output_tokens: int, cached_tokens: int = 0) -> float:
        """Dollars for billed tokens (``output_tokens`` includes thought tokens).

        ``input_tokens`` is the provider's prompt token count; ``cached_tokens`` of them (as the
        provider reports) are priced at the cached-input price when one is known."""
        cached = min(max(cached_tokens, 0), input_tokens)
        rate = self.input_per_m if self.cached_input_per_m is None else self.cached_input_per_m
        return (
            (input_tokens - cached) * self.input_per_m
            + cached * rate
            + output_tokens * self.output_per_m
        ) / 1e6


def load_prices(path: str | Path) -> dict[str, Price]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if int(data["per_tokens"]) != 1_000_000:
        raise ValueError("prices must be per million tokens")
    return {
        name: Price(
            name,
            float(m["input"]),
            float(m["output"]),
            bool(m.get("verified", False)),
            str(data["as_of"]),
        )
        for name, m in data["models"].items()
    }


def price_from_limits(path: str | Path, model: str) -> Price | None:
    """The price written next to a model's limits (D155), or ``None`` if the entry has none.

    ``verified`` is true when the entry names the provider page it was read from and a date, which
    is what D155 requires of a price used for the model check."""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    entry = (data.get("models") or {}).get(model) or {}
    if "input_per_m" not in entry or "output_per_m" not in entry:
        return None
    as_of = str(entry.get("price_as_of", "UNSET"))
    source = str(entry.get("price_source", "")).strip()
    return Price(
        model,
        float(entry["input_per_m"]),
        float(entry["output_per_m"]),
        bool(source) and as_of != "UNSET" and source != "UNSET",
        as_of,
        float(entry["cached_input_per_m"]) if "cached_input_per_m" in entry else None,
    )


def price_for_run(limits_path: str | Path | None, model: str, stored: Mapping[str, Price]) -> Price:
    """The price of a run: the limits entry's (D155) if it has one, else the stored table's."""
    return (price_from_limits(limits_path, model) if limits_path else None) or price_of(
        stored, model
    )


def price_of(prices: Mapping[str, Price], model: str) -> Price:
    if model not in prices:
        raise KeyError(f"no price stored for model {model!r}; add it to configs/agent/prices.yaml")
    return prices[model]


def contents_chars(contents: Sequence[Mapping[str, Any]]) -> int:
    return sum(len(str(p.get("text", ""))) for c in contents for p in c.get("parts", []))


class SharedSpend:
    """One total guard that several arm jobs read and update (atomic, on a shared file system).

    The ledger is a JSON file holding ``committed`` (dollars billed by every arm so far) and
    ``reserved`` (the worst case of each call in flight, by owner). Every read-modify-write holds
    an exclusive ``flock`` on a lock file next to the ledger and replaces the ledger by a rename,
    so two jobs can never both pass a check that only one of them fits under. A call is checked
    against ``committed + sum(reserved) + its worst case``; its reservation is replaced by the
    billed cost when the call returns and dropped if it fails. ``cap_usd`` is fixed when the ledger
    is created and cannot be raised by a job (D114, D167). A job that restarts clears its own
    reservations first (a crash leaves none that count).
    """

    def __init__(self, path: str | Path, owner: str, cap_usd: float | None = None) -> None:
        self.path = Path(path)
        self.owner = owner
        self.lock_path = self.path.with_name(self.path.name + ".lock")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._locked() as state:
            if state is None:
                if cap_usd is None or not math.isfinite(cap_usd) or cap_usd <= 0:
                    raise ValueError("a new shared ledger needs a positive cap")
                self._write(
                    {"cap_usd": float(cap_usd), "committed": 0.0, "reserved": {}, "by_owner": {}}
                )
            elif cap_usd is not None and abs(float(state["cap_usd"]) - cap_usd) > 1e-9:
                raise ValueError(
                    f"the shared ledger's cap is {state['cap_usd']}, not {cap_usd}; "
                    "a job cannot change it"
                )
            self._clear_own_reservation()

    def _read(self) -> dict[str, Any] | None:
        if not self.path.exists():
            return None
        data: dict[str, Any] = json.loads(self.path.read_text(encoding="utf-8"))
        return data

    def _write(self, state: Mapping[str, Any]) -> None:
        tmp = self.path.with_name(self.path.name + f".tmp{os.getpid()}")
        tmp.write_text(json.dumps(state, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        with tmp.open("rb") as fh:
            os.fsync(fh.fileno())
        os.replace(tmp, self.path)

    def _locked(self) -> _Locked:
        return _Locked(self)

    def _clear_own_reservation(self) -> None:
        state = self._read()
        if state is not None and self.owner in state["reserved"]:
            state["reserved"].pop(self.owner)
            self._write(state)

    def reserve(self, bound: float) -> None:
        """Hold ``bound`` dollars for one call or raise ``SpendCapReached`` when it does not fit."""
        with self._locked() as state:
            assert state is not None
            held = sum(float(v) for v in state["reserved"].values())
            if float(state["committed"]) + held + bound > float(state["cap_usd"]):
                raise SpendCapReached(
                    f"shared total: committed ${state['committed']:.4f}, in flight ${held:.4f}, "
                    f"the next call may cost up to ${bound:.4f}, shared cap ${state['cap_usd']:.2f}"
                )
            state["reserved"][self.owner] = float(state["reserved"].get(self.owner, 0.0)) + bound
            self._write(state)

    def settle(self, bound: float, billed: float) -> None:
        """Replace one call's reservation ``bound`` by the cost ``billed`` (0 when it failed)."""
        with self._locked() as state:
            assert state is not None
            left = max(0.0, float(state["reserved"].get(self.owner, 0.0)) - bound)
            if left > 1e-12:
                state["reserved"][self.owner] = left
            else:
                state["reserved"].pop(self.owner, None)
            state["committed"] = float(state["committed"]) + billed
            by = state.setdefault("by_owner", {})
            by[self.owner] = float(by.get(self.owner, 0.0)) + billed
            self._write(state)

    def snapshot(self) -> dict[str, Any]:
        with self._locked() as state:
            assert state is not None
            return dict(state)


class _Locked:
    """Context manager: exclusive lock on the ledger's lock file, yields the current state."""

    def __init__(self, ledger: SharedSpend) -> None:
        self.ledger = ledger
        self._fh: Any = None

    def __enter__(self) -> dict[str, Any] | None:
        self._fh = self.ledger.lock_path.open("a")
        fcntl.flock(self._fh, fcntl.LOCK_EX)
        return self.ledger._read()

    def __exit__(self, *exc: object) -> None:
        fcntl.flock(self._fh, fcntl.LOCK_UN)
        self._fh.close()


@dataclass
class SpendGuard:
    """Running cost against a cap; ``spent`` starts from the cost of calls already logged.

    With ``shared`` the guard also reserves each call's worst case in the shared total ledger and
    settles it with the billed cost, so several jobs together stay under one total. Calls already
    in a resumed run's log are not added to the shared ledger (they were added when they ran)."""

    cap_usd: float
    price: Price
    max_output_tokens: int
    spent: float = 0.0
    calls: int = 0
    refused: int = 0
    shared: SharedSpend | None = None
    _unbilled: int = field(default=0, repr=False)
    _held: list[float] = field(default_factory=list, repr=False)

    def __post_init__(self) -> None:
        if not math.isfinite(self.cap_usd) or self.cap_usd <= 0:
            raise ValueError("a positive spend cap is required")

    def worst_case(self, contents: Sequence[Mapping[str, Any]]) -> float:
        est_in = math.ceil(contents_chars(contents) / CHARS_PER_TOKEN_FLOOR)
        return self.price.cost(est_in, self.max_output_tokens)

    def before(self, contents: Sequence[Mapping[str, Any]]) -> None:
        bound = self.worst_case(contents)
        if self.spent + bound > self.cap_usd:
            self.refused += 1
            raise SpendCapReached(
                f"spent ${self.spent:.4f}, the next call may cost up to ${bound:.4f}, "
                f"cap ${self.cap_usd:.2f}"
            )
        if self.shared is not None:
            try:
                self.shared.reserve(bound)
            except SpendCapReached:
                self.refused += 1
                raise
            self._held.append(bound)

    def record(self, res: CallResult) -> None:
        self.calls += 1
        billed = 0.0
        if res.input_tokens or res.output_tokens:
            billed = self.price.cost(res.input_tokens, res.output_tokens, res.cached_tokens)
            self.spent += billed
        else:
            self._unbilled += 1
        if self.shared is not None and self._held:
            self.shared.settle(self._held.pop(), billed)

    def abandon(self) -> None:
        """Release the reservation of a call that raised before it was billed."""
        if self.shared is not None and self._held:
            self.shared.settle(self._held.pop(), 0.0)

    def add_logged(self, rows: Iterable[Mapping[str, Any]]) -> None:
        """Count the cost of calls already in a call log (a resumed run)."""
        for r in rows:
            self.spent += self.price.cost(
                int(r["input_tokens"]), int(r["output_tokens"]), int(r.get("cached_tokens", 0))
            )


class GuardedClient:
    """Wraps a client so that every call passes the guard first and is billed after."""

    def __init__(self, inner: Any, guard: SpendGuard) -> None:
        self.inner = inner
        self.guard = guard

    def generate(
        self, contents: Sequence[Mapping[str, Any]], *, wait_for_daily: bool = False
    ) -> CallResult:
        self.guard.before(contents)
        try:
            res: CallResult = self.inner.generate(contents, wait_for_daily=wait_for_daily)
        except BaseException:
            self.guard.abandon()
            raise
        self.guard.record(res)
        return res


def logged_cost(rows: Iterable[Mapping[str, Any]], price: Price) -> float:
    return sum(
        price.cost(int(r["input_tokens"]), int(r["output_tokens"]), int(r.get("cached_tokens", 0)))
        for r in rows
    )


def dump(path: str | Path, obj: Mapping[str, Any]) -> None:
    Path(path).write_text(json.dumps(obj, indent=1, sort_keys=True) + "\n", encoding="utf-8")
