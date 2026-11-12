"""Spend guard for paid model calls. Implements ``docs/RQ3_PILOT.md`` (D114).

The driver keeps its own running cost from the billed tokens of every call (input, and output
including thought tokens, at the dated list prices of ``configs/agent/prices.yaml``) and refuses
a call whose worst case would take the total past a cap given on the command line. The worst case
of a call is its input estimated at ``CHARS_PER_TOKEN_FLOOR`` characters per token plus the full
``max_output_tokens`` billed as output. The provider-side hard cap is a second, independent layer.
"""

from __future__ import annotations

import json
import math
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

    def cost(self, input_tokens: int, output_tokens: int) -> float:
        """Dollars for billed tokens (``output_tokens`` includes thought tokens)."""
        return (input_tokens * self.input_per_m + output_tokens * self.output_per_m) / 1e6


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
    )


def price_of(prices: Mapping[str, Price], model: str) -> Price:
    if model not in prices:
        raise KeyError(f"no price stored for model {model!r}; add it to configs/agent/prices.yaml")
    return prices[model]


def contents_chars(contents: Sequence[Mapping[str, Any]]) -> int:
    return sum(len(str(p.get("text", ""))) for c in contents for p in c.get("parts", []))


@dataclass
class SpendGuard:
    """Running cost against a cap; ``spent`` starts from the cost of calls already logged."""

    cap_usd: float
    price: Price
    max_output_tokens: int
    spent: float = 0.0
    calls: int = 0
    refused: int = 0
    _unbilled: int = field(default=0, repr=False)

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

    def record(self, res: CallResult) -> None:
        self.calls += 1
        if res.input_tokens or res.output_tokens:
            self.spent += self.price.cost(res.input_tokens, res.output_tokens)
        else:
            self._unbilled += 1

    def add_logged(self, rows: Iterable[Mapping[str, Any]]) -> None:
        """Count the cost of calls already in a call log (a resumed run)."""
        for r in rows:
            self.spent += self.price.cost(int(r["input_tokens"]), int(r["output_tokens"]))


class GuardedClient:
    """Wraps a client so that every call passes the guard first and is billed after."""

    def __init__(self, inner: Any, guard: SpendGuard) -> None:
        self.inner = inner
        self.guard = guard

    def generate(
        self, contents: Sequence[Mapping[str, Any]], *, wait_for_daily: bool = False
    ) -> CallResult:
        self.guard.before(contents)
        res: CallResult = self.inner.generate(contents, wait_for_daily=wait_for_daily)
        self.guard.record(res)
        return res


def logged_cost(rows: Iterable[Mapping[str, Any]], price: Price) -> float:
    return sum(price.cost(int(r["input_tokens"]), int(r["output_tokens"])) for r in rows)


def dump(path: str | Path, obj: Mapping[str, Any]) -> None:
    Path(path).write_text(json.dumps(obj, indent=1, sort_keys=True) + "\n", encoding="utf-8")
