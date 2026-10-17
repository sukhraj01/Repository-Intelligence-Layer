"""Unit tests: name normalisation, held-out builder, filter_pool (specs/held_out_repos.md)."""

from __future__ import annotations

import pytest

from ril.training.held_out import (
    build_held_out,
    canonical_json,
    canonical_repo,
    filter_pool,
    filter_repo_counts,
    repo_from_instance_id,
    sha256_hex,
)


def test_name_spellings_collapse() -> None:
    forms = ["Owner/Repo", "owner__repo", "owner/repo", "https://github.com/Owner/Repo.git"]
    assert {canonical_repo(f) for f in forms} == {"owner/repo"}


@pytest.mark.parametrize("bad", ["scikit", "", "a/b/c", "/repo", "owner/"])
def test_unreadable_names_are_refused(bad: str) -> None:
    with pytest.raises(ValueError):
        canonical_repo(bad)


@pytest.mark.parametrize(
    ("instance_id", "expected"),
    [
        ("pallets__flask-5014", "pallets/flask"),
        ("django-helpdesk__django-helpdesk-1289", "django-helpdesk/django-helpdesk"),
        ("owner__name-2-77", "owner/name-2"),
        ("instance_NodeBB__NodeBB-0123456789abcdef0123456789abcdef01234567", "nodebb/nodebb"),
        (
            "instance_ansible__ansible-0123456789abcdef0123456789abcdef01234567-v1a2b3c",
            "ansible/ansible",
        ),
        ("noowner-12", None),
    ],
)
def test_repo_from_instance_id(instance_id: str, expected: str | None) -> None:
    assert repo_from_instance_id(instance_id) == expected


def test_build_is_deterministic_and_records_sources() -> None:
    src = {"L3": ["b/b", "A/a"], "L2": ["a__a", "c/c"], "V": []}
    first = build_held_out(src)
    second = build_held_out(dict(reversed(list(src.items()))))
    assert canonical_json(first) == canonical_json(second)
    assert sha256_hex(canonical_json(first)) == sha256_hex(canonical_json(second))
    assert first["repos"] == {"a/a": ["L2", "L3"], "b/b": ["L3"], "c/c": ["L2"]}
    assert first["n_repos"] == 3
    assert first["per_source_counts"] == {"L2": 2, "L3": 2, "V": 0}


def test_filter_drops_held_out_repo_and_reports_it() -> None:
    pool = [
        {"repo": "Django/Django", "id": 1},
        {"repo": "django__django", "id": 2},
        {"repo": "x/y", "id": 3},
        {"repo": "x/z", "id": 4},
    ]
    kept, dropped, rep = filter_pool(pool, ["django/django"], lambda r: r["repo"])
    assert [r["id"] for r in kept] == [3, 4]
    assert [r["id"] for r in dropped] == [1, 2]
    assert (rep.instances_before, rep.instances_after) == (4, 2)
    assert (rep.repos_before, rep.repos_after) == (3, 2)
    assert rep.dropped_repos == {"django/django": 2}
    assert rep.instances_surviving_pct == 50.0
    assert rep.top_dropped(1) == [("django/django", 2)]


def test_filter_empty_pool_and_unreadable_record() -> None:
    kept, dropped, rep = filter_pool([], ["a/b"], lambda r: r)
    assert kept == dropped == [] and rep.instances_surviving_pct == 0.0
    with pytest.raises(ValueError):
        filter_pool(["scikit"], ["a/b"], lambda r: r)


def test_filter_repo_counts_matches_expanded_filter() -> None:
    counts = {"Django/Django": 3, "django__django": 1, "x/y": 2}
    kept, rep = filter_repo_counts(counts, ["django/django"])
    assert kept == {"x/y": 2}
    assert rep.instances_before == 6 and rep.instances_after == 2
    assert rep.repos_before == 2 and rep.repos_after == 1
    assert rep.dropped_repos == {"django/django": 4}


# --- list schema 2: current-name resolution (D1), Loc-Bench tier (D3), fork sensitivity ----------

from ril.training.held_out import (  # noqa: E402
    HeldOutLists,
    is_held_out,
    load_held_out_lists,
    rule_counts,
)

_LISTS = HeldOutLists(
    core=frozenset({"pylint-dev/pylint", "pallets/flask"}),
    loc_bench=frozenset({"extra/locbench-repo"}),
    aliases={},
)
_POOL = {
    "pylint-dev/pylint": 5,  # exact
    "pycqa/pylint": 3,  # renamed into a held-out repository
    "extra/locbench-repo": 2,  # Loc-Bench tier
    "someone/flask-fork": 4,  # fork of a held-out repository
    "nobody/unrelated": 10,
}


def test_rule_counts_are_cumulative_and_fork_is_sensitivity_only() -> None:
    rows = {
        r.rule: r
        for r in rule_counts(
            _POOL,
            _LISTS,
            pool_aliases={"pycqa/pylint": "pylint-dev/pylint"},
            pool_forks={"someone/flask-fork": ("pallets/flask",)},
        )
    }
    assert rows["exact"].instances_after == 24 - 5
    assert rows["+current_name"].instances_after == 24 - 5 - 3
    assert rows["+loc_bench"].instances_after == 24 - 5 - 3 - 2
    assert rows["sensitivity: +fork_network"].instances_after == 24 - 5 - 3 - 2 - 4
    assert rows["+loc_bench"].repos_after == 2


def test_without_aliases_the_current_name_rule_changes_nothing() -> None:
    rows = {r.rule: r for r in rule_counts(_POOL, _LISTS, {}, {})}
    assert rows["exact"].instances_after == rows["+current_name"].instances_after


def test_held_out_side_rename_is_matched_through_its_alias() -> None:
    lists = HeldOutLists(frozenset({"old/name"}), frozenset(), {"old/name": "new/name"})
    kept, dropped, _ = filter_pool(
        [{"r": "new/name"}, {"r": "other/x"}], lists.core, lambda x: x["r"], lists.aliases
    )
    assert [d["r"] for d in dropped] == ["new/name"] and len(kept) == 1


def test_filter_repo_counts_with_aliases() -> None:
    kept, rep = filter_repo_counts(
        {"pycqa/pylint": 3, "a/b": 1}, ["pylint-dev/pylint"], {"pycqa/pylint": "pylint-dev/pylint"}
    )
    assert kept == {"a/b": 1} and rep.instances_after == 1


def test_is_held_out_is_false_for_unknown_names() -> None:
    assert not is_held_out("a/b", {"c/d"}, {"x/y": "c/d"})
    assert is_held_out("x/y", {"c/d"}, {"x/y": "c/d"})


def test_loader_reads_tiers_and_switches_loc_bench_off() -> None:
    doc = {
        "schema_version": 2,
        "repos": {"a/a": ["Verified"]},
        "tiers": {"loc_bench": {"repos": {"b/b": ["Loc-Bench_V1"]}}},
        "aliases": {"a/old": "a/a"},
    }
    lists = load_held_out_lists(doc)
    assert lists.blocked() == {"a/a", "b/b"} and lists.blocked(False) == {"a/a"}
    assert lists.aliases == {"a/old": "a/a"}
    with pytest.raises(ValueError):
        load_held_out_lists({"repos": {}})
