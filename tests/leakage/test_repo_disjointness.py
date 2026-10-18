"""Leakage check (a): no training-pool repository is a held-out repository.

Implements leakage check (a) of the project test policy and specs/held_out_repos.md "Tests".
Must always pass.
Covers the tracked held-out list, the post-filter repository lists of every pool that has been
filtered, and any pool export placed under ``data/processed/pools/`` (checked as soon as it exists).
"""

from __future__ import annotations

import hashlib
import json

from ril.config.paths import data_root, repo_root
from ril.training.held_out import (
    canonical_repo,
    filter_pool,
    is_held_out,
    load_held_out_lists,
)
from ril.training.leakage import intersect

HELD_OUT_DIR = repo_root() / "data" / "held_out"
VERIFIED_REPOS = {
    "astropy/astropy",
    "django/django",
    "matplotlib/matplotlib",
    "mwaskom/seaborn",
    "pallets/flask",
    "psf/requests",
    "pydata/xarray",
    "pylint-dev/pylint",
    "pytest-dev/pytest",
    "scikit-learn/scikit-learn",
    "sphinx-doc/sphinx",
    "sympy/sympy",
}


def _held_out() -> dict:
    return json.loads((HELD_OUT_DIR / "held_out_repos.json").read_text(encoding="utf-8"))


def _held_set() -> set[str]:
    return set(_held_out()["repos"])


def test_list_is_canonical_sorted_and_hashed() -> None:
    raw = (HELD_OUT_DIR / "held_out_repos.json").read_bytes()
    recorded = (HELD_OUT_DIR / "held_out_repos.sha256").read_text().split()[0]
    assert hashlib.sha256(raw).hexdigest() == recorded
    doc = _held_out()
    repos = list(doc["repos"])
    assert repos == sorted(repos)
    assert doc["n_repos"] == len(repos) > 0
    assert all(canonical_repo(r) == r for r in repos)
    assert all(doc["repos"][r] for r in repos), "every repository must name its source(s)"


def test_per_source_counts_match_the_repository_map() -> None:
    doc = _held_out()
    for source, n in doc["per_source_counts"].items():
        assert sum(1 for srcs in doc["repos"].values() if source in srcs) == n


def test_swe_bench_verified_repositories_are_held_out() -> None:
    assert VERIFIED_REPOS <= _held_set()
    for repo in VERIFIED_REPOS:
        assert "Verified" in _held_out()["repos"][repo]


def test_every_corebench_folder_was_resolved() -> None:
    assert _held_out()["unresolved_folders"] == []


def test_synthetic_pool_with_a_held_out_repo_is_cleaned() -> None:
    held = sorted(_held_set())[:3]
    pool = [{"repo": held[0].upper()}, {"repo": "nobody/unrelated-project"}, {"repo": held[1]}]
    kept, dropped, rep = filter_pool(pool, _held_set(), lambda r: r["repo"])
    assert [r["repo"] for r in kept] == ["nobody/unrelated-project"]
    assert len(dropped) == 2 and rep.repos_after == 1


def _check_disjoint(repos: object) -> None:
    assert intersect((canonical_repo(r) for r in repos), _held_set()) == []  # type: ignore[attr-defined]


def test_filtered_pools_are_disjoint_from_held_out() -> None:
    """Post-filter pool lists written by scripts/build_held_out.py (untracked, regenerated)."""
    digest = (HELD_OUT_DIR / "held_out_repos.sha256").read_text().split()[0]
    for path in sorted((data_root() / "processed" / "pools").glob("*_repos.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        assert doc["held_out_sha256"] == digest, f"{path.name} was filtered against a stale list"
        _check_disjoint(doc["repositories"])


def test_list_is_schema_2_with_a_separate_loc_bench_tier() -> None:
    doc = _held_out()
    assert doc["schema_version"] == 2
    lists = load_held_out_lists(doc)
    assert lists.loc_bench, "decision D3: the Loc-Bench tier must be present"
    assert not (lists.loc_bench & lists.core), "the tier stores only repositories outside the core"
    assert lists.blocked(False) == lists.core and lists.blocked() == lists.core | lists.loc_bench


def test_filtered_pools_are_disjoint_under_current_names_and_the_loc_bench_tier() -> None:
    """The default rule set (D1 + D3) holds for every pool file written by the build script."""
    lists = load_held_out_lists(_held_out())
    blocked = set(lists.blocked())
    blocked |= {lists.aliases[b] for b in blocked if b in lists.aliases}
    from ril.training.rename_resolution import alias_map, load_cache

    aliases = {**lists.aliases, **alias_map(load_cache(HELD_OUT_DIR / "rename_cache.json"))}
    for path in sorted((data_root() / "processed" / "pools").glob("*_repos.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        bad = [r for r in doc["repositories"] if is_held_out(canonical_repo(r), blocked, aliases)]
        assert bad == [], f"{path.name} keeps held-out repositories: {bad[:5]}"


def test_rename_cache_holds_names_and_flags_only() -> None:
    doc = json.loads((HELD_OUT_DIR / "rename_cache.json").read_text(encoding="utf-8"))
    allowed = {"status", "current", "fork", "parent", "source", "checked"}
    assert all(set(e) <= allowed for e in doc["entries"].values())
    assert "token" not in json.dumps(doc).lower()


def test_unfiltered_pool_would_fail_the_check() -> None:
    """Negative control: a pool holding a held-out repository is caught by the intersection."""
    held = sorted(_held_set())[0]
    assert intersect([held, "nobody/unrelated-project"], _held_set()) == [held]
