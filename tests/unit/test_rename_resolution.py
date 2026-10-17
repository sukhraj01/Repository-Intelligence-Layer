"""Unit tests for ril.training.rename_resolution with a fake transport (no network)."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from ril.training.rename_resolution import (
    GitHubTransport,
    Response,
    alias_map,
    fork_roots,
    load_cache,
    priority_order,
    rate_limit_remaining,
    resolve_names,
    save_cache,
)


class Fake:
    """Scripted transport: ``answers[name]`` is a Response; counts calls; counts down a budget."""

    def __init__(self, answers: Mapping[str, Response], budget: int = 1000) -> None:
        self.answers = answers
        self.calls: list[str] = []
        self.budget = budget

    def get(self, path: str) -> Response:
        self.calls.append(path)
        if path == "/rate_limit":
            return Response(200, None, {"resources": {"core": {"remaining": self.budget}}})
        name = path.removeprefix("/repos/")
        if self.budget <= 0:
            return Response(403, 0, {})
        self.budget -= 1
        if name not in self.answers:
            raise OSError("network error: gaierror")
        r = self.answers[name]
        return Response(r.status, self.budget, r.body)


def found(full: str, **extra: Any) -> Response:
    return Response(200, None, {"full_name": full, **extra})


ANSWERS = {
    "pycqa/pylint": found("PyCQA-Org/Pylint-Dev"),
    "old/flask": found("pallets/Flask"),
    "gone/repo": Response(404, None, {}),
    "fork/of-django": found(
        "fork/of-django",
        fork=True,
        parent={"full_name": "x/y"},
        source={"full_name": "django/django"},
    ),
    "same/name": found("same/name"),
}


def test_resolution_records_current_name_and_status() -> None:
    cache: dict[str, dict[str, Any]] = {}
    stats = resolve_names(list(ANSWERS), cache, Fake(ANSWERS), "2026-10-17")
    assert stats.looked_up == 5 and not stats.not_checked and not stats.failed
    assert cache["old/flask"]["current"] == "pallets/flask"
    assert cache["gone/repo"] == {"status": 404, "checked": "2026-10-17"}
    assert alias_map(cache) == {
        "old/flask": "pallets/flask",
        "pycqa/pylint": "pycqa-org/pylint-dev",
    }
    assert fork_roots(cache) == {"fork/of-django": ("x/y", "django/django")}


def test_final_answers_are_not_looked_up_again() -> None:
    cache: dict[str, dict[str, Any]] = {}
    resolve_names(["old/flask", "gone/repo"], cache, Fake(ANSWERS), "2026-10-17")
    second = Fake(ANSWERS)
    stats = resolve_names(["Old/Flask", "gone/repo"], cache, second, "2026-10-18")
    assert second.calls == [] and stats.already_final == 2
    assert cache["old/flask"]["checked"] == "2026-10-17"


def test_rate_limit_stops_the_run_and_reports_the_rest() -> None:
    cache: dict[str, dict[str, Any]] = {}
    fake = Fake(ANSWERS, budget=2)
    stats = resolve_names(["old/flask", "same/name", "pycqa/pylint"], cache, fake, "d")
    assert stats.stopped_by_rate_limit
    assert set(cache) == {"old/flask", "same/name"}
    assert stats.not_checked == ("pycqa/pylint",)
    # a rerun with a fresh budget finishes only what is missing
    fake.budget = 10
    again = resolve_names(["old/flask", "same/name", "pycqa/pylint"], cache, fake, "d")
    assert again.looked_up == 1 and not again.not_checked


def test_reserve_keeps_requests_back() -> None:
    cache: dict[str, dict[str, Any]] = {}
    stats = resolve_names(
        ["old/flask", "same/name"], cache, Fake(ANSWERS, budget=5), "d", reserve=4
    )
    assert stats.looked_up == 1 and stats.stopped_by_rate_limit


def test_max_requests_is_respected() -> None:
    cache: dict[str, dict[str, Any]] = {}
    stats = resolve_names(list(ANSWERS), cache, Fake(ANSWERS), "d", max_requests=2)
    assert stats.looked_up == 2 and len(stats.not_checked) == 3


def test_network_failure_is_recorded_and_retried_later() -> None:
    cache: dict[str, dict[str, Any]] = {}
    stats = resolve_names(["unknown/repo", "old/flask"], cache, Fake(ANSWERS), "d")
    assert stats.failed == ("unknown/repo",) and "unknown/repo" not in cache


def test_server_error_is_not_cached_as_final() -> None:
    cache: dict[str, dict[str, Any]] = {}
    answers = {"a/b": Response(502, None, {})}
    stats = resolve_names(["a/b"], cache, Fake(answers), "d")
    assert stats.failed == ("a/b",) and cache == {}


def test_cache_round_trip_is_deterministic(tmp_path: Path) -> None:
    cache: dict[str, dict[str, Any]] = {}
    resolve_names(list(ANSWERS), cache, Fake(ANSWERS), "d")
    p1, p2 = tmp_path / "a.json", tmp_path / "b.json"
    save_cache(p1, cache)
    save_cache(p2, dict(reversed(list(load_cache(p1).items()))))
    assert p1.read_bytes() == p2.read_bytes()
    assert load_cache(tmp_path / "missing.json") == {}


def test_rate_limit_remaining_reads_the_core_bucket() -> None:
    assert rate_limit_remaining(Fake({}, budget=42)) == 42


def test_token_is_never_exposed() -> None:
    secret = "ghp_" + "x" * 30
    t = GitHubTransport.from_env({"GITHUB_TOKEN": secret})
    assert t.authenticated
    assert secret not in repr(t) and secret not in str(t)
    assert not GitHubTransport.from_env({}).authenticated
    assert not GitHubTransport.from_env({"GITHUB_TOKEN": ""}).authenticated


def test_priority_order_puts_same_name_parts_first() -> None:
    order = priority_order(["zed/other", "pycqa/pylint", "a/alpha"], ["pylint-dev/pylint"])
    assert order == ["pycqa/pylint", "a/alpha", "zed/other"]


@pytest.mark.parametrize("bad", ["scikit", "a/b/c"])
def test_unreadable_names_are_refused(bad: str) -> None:
    with pytest.raises(ValueError):
        resolve_names([bad], {}, Fake({}), "d")


def test_priority_order_uses_weights_for_the_rest() -> None:
    order = priority_order(
        ["a/small", "b/big", "pycqa/pylint"], ["pylint-dev/pylint"], {"b/big": 90, "a/small": 2}
    )
    assert order == ["pycqa/pylint", "b/big", "a/small"]
