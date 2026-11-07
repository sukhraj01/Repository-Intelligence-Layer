"""Seeded stratified draw for the gold-derived validation (D110)."""

from __future__ import annotations

import pytest

from ril.evaluation.patch_validation import draw_instances

EXEC = (
    [{"instance_id": f"big-{i}", "repo": "o/big"} for i in range(30)]
    + [{"instance_id": f"mid-{i}", "repo": "o/mid"} for i in range(6)]
    + [{"instance_id": f"small-{i}", "repo": "o/small"} for i in range(3)]
)


def test_every_large_repository_is_represented_and_size_is_exact() -> None:
    picked = draw_instances(EXEC, 8, seed=0)
    assert len(picked) == 8 == len({p["instance_id"] for p in picked})
    repos = {p["repo"] for p in picked}
    assert {"o/big", "o/mid"} <= repos
    assert sum(p["stratum"] == "repository_minimum" for p in picked) == 2


def test_draw_is_deterministic_and_seed_dependent() -> None:
    a = draw_instances(EXEC, 8, seed=0)
    assert a == draw_instances(EXEC, 8, seed=0)
    assert a != draw_instances(EXEC, 8, seed=1)


def test_too_few_places_is_rejected() -> None:
    with pytest.raises(ValueError):
        draw_instances(EXEC, 1, seed=0)
