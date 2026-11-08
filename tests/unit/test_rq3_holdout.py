"""D111: stratified held-out draw, allocation rule, split."""

from __future__ import annotations

import pytest

from ril.agent.providers.holdout import allocate, draw_holdout, split

SIZES = {
    "django/django": 228,
    "sympy/sympy": 75,
    "pytest-dev/pytest": 19,
    "pydata/xarray": 18,
    "astropy/astropy": 15,
    "sphinx-doc/sphinx": 11,
    "psf/requests": 4,
    "pylint-dev/pylint": 4,
    "mwaskom/seaborn": 2,
    "pallets/flask": 1,
}


def executable() -> list[dict[str, str]]:
    return [
        {"instance_id": f"{repo.split('/')[1]}-{i}", "repo": repo}
        for repo, n in SIZES.items()
        for i in range(n)
    ]


def test_allocation_sums_and_respects_the_minimum_of_large_repositories() -> None:
    places = allocate(SIZES, 50)
    assert sum(places.values()) == 50
    for repo, size in SIZES.items():
        if size >= 5:
            assert places[repo] >= 2
        assert places[repo] <= size
    assert places["django/django"] > places["sympy/sympy"] > places["pytest-dev/pytest"]


def test_allocation_is_proportional_when_no_minimum_binds() -> None:
    assert allocate({"a": 100, "b": 100}, 10) == {"a": 5, "b": 5}
    assert allocate({"a": 300, "b": 100}, 8) == {"a": 6, "b": 2}


def test_allocation_rejects_impossible_requests() -> None:
    with pytest.raises(ValueError):
        allocate(SIZES, 0)
    with pytest.raises(ValueError):
        allocate({"a": 6, "b": 6, "c": 6}, 5)


def test_draw_is_seeded_sorted_and_stratified() -> None:
    a = draw_holdout(executable(), 50, seed=0)
    b = draw_holdout(list(reversed(executable())), 50, seed=0)
    c = draw_holdout(executable(), 50, seed=1)
    assert a == b
    assert a["instances"] != c["instances"]
    assert len(a["instances"]) == 50 == len({r["instance_id"] for r in a["instances"]})
    per_repo = {r["repo"]: r["held_out"] for r in a["by_repository"]}
    got = {repo: sum(1 for r in a["instances"] if r["repo"] == repo) for repo in SIZES}
    assert got == per_repo


def test_split_partitions_the_executable_subset() -> None:
    ex = executable()
    hold = draw_holdout(ex, 50, seed=0)
    held, conf = split(ex, hold)
    assert len(held) == 50 and len(conf) == len(ex) - 50
    assert not set(held) & set(conf)
    with pytest.raises(ValueError):
        split(ex[:10], hold)
