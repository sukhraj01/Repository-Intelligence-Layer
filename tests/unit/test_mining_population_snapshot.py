"""Population selection, selection analysis, git snapshot provider (E-MINE-PILOT, M0 gate)."""

from __future__ import annotations

import os
import subprocess

import pytest

from ril.data_mining.population import (
    first_repos,
    select_population,
    selection_rows,
    selection_summary,
)
from ril.data_mining.snapshot import GitSnapshots, SnapshotError, safe_member_path

NAMES = [
    "acme__widgets-1",
    "acme__widgets-2",
    "acme__widgets-3",
    "beta__tools-10",
    "beta__tools-11",
    "gamma__lib-5",
    "django__django-100",
]


def test_population_applies_the_filter_then_takes_the_seeded_first_n() -> None:
    held = {"django/django"}
    pop = select_population(NAMES, is_held_out=lambda r: r in held, seed=0, pool_size=4)
    assert pop.counts["directories_listed"] == 7 and pop.counts["directories_held_out"] == 1
    assert pop.counts["repos_held_out"] == 1 and pop.counts["directories_selected"] == 4
    assert len(pop.directories) == 4 and "django__django-100" not in pop.directories
    assert set(pop.repos) == set(pop.published)
    again = select_population(NAMES, is_held_out=lambda r: r in held, seed=0, pool_size=4)
    assert again == pop
    other = select_population(NAMES, is_held_out=lambda r: r in held, seed=1, pool_size=4)
    assert other.directories != pop.directories or other.repos != pop.repos
    assert first_repos(pop, 2) == list(pop.repos[:2])


def test_unreadable_directory_name_is_an_error_not_a_drop() -> None:
    with pytest.raises(ValueError):
        select_population(["nodash"], is_held_out=lambda r: False, seed=0, pool_size=1)


def test_selection_rows_report_the_pool_share_and_extras() -> None:
    linked = {"a/b": [1, 2, 3, 4], "c/d": [7]}
    published = {"a/b": frozenset({2, 4, 99}), "c/d": frozenset()}
    rows = selection_rows(linked, published)
    assert [(r.repo, r.linked_prs, r.kept_by_pool, r.published_in_selection) for r in rows] == [
        ("a/b", 4, 2, 1),
        ("c/d", 1, 0, 0),
    ]
    assert rows[0].kept_share == 0.5
    summary = selection_summary(rows)
    assert summary["linked_prs"] == 5 and summary["kept_by_pool"] == 2
    assert summary["published_not_linked"] == 1


def test_tar_member_paths_cannot_escape() -> None:
    assert safe_member_path("a/b.py") == "a/b.py"
    assert safe_member_path("../x.py") is None and safe_member_path("/etc/x.py") is None
    assert safe_member_path("a/../../x.py") is None


def git(cwd: str, *args: str) -> str:
    env = dict(
        os.environ,
        GIT_AUTHOR_NAME="t",
        GIT_AUTHOR_EMAIL="t@example.org",
        GIT_COMMITTER_NAME="t",
        GIT_COMMITTER_EMAIL="t@example.org",
    )
    done = subprocess.run(["git", "-C", cwd, *args], capture_output=True, check=True, env=env)
    return done.stdout.decode().strip()


def test_git_snapshot_writes_only_python_files_of_the_commit(tmp_path) -> None:
    src = str(tmp_path / "src")
    os.makedirs(src)
    git(src, "init", "-q")
    git(src, "config", "uploadpack.allowAnySHA1InWant", "true")
    os.makedirs(os.path.join(src, "pkg"))
    with open(os.path.join(src, "pkg", "a.py"), "w") as f:
        f.write("def a():\n    return 1\n")
    with open(os.path.join(src, "README.md"), "w") as f:
        f.write("# readme\n")
    with open(os.path.join(src, "blob.bin"), "wb") as f:
        f.write(b"\x00\x01")
    git(src, "add", ".")
    git(src, "commit", "-q", "-m", "one")
    first = git(src, "rev-parse", "HEAD")
    with open(os.path.join(src, "pkg", "a.py"), "w") as f:
        f.write("def a():\n    return 2\n")
    git(src, "commit", "-q", "-am", "two")
    snaps = GitSnapshots(str(tmp_path / "work"), remote="file://" + src)
    dest = str(tmp_path / "dest")
    os.makedirs(dest)
    assert snaps.materialize("acme/widgets", first, dest) == 1
    assert sorted(os.listdir(dest)) == ["pkg"]
    with open(os.path.join(dest, "pkg", "a.py")) as f:
        assert "return 1" in f.read()
    with pytest.raises(SnapshotError):
        snaps.materialize("acme/widgets", "0" * 40, str(tmp_path / "dest2"))
    assert os.listdir(str(tmp_path / "work")) == []  # the commit's bare repository is removed


def test_published_covers_every_pool_directory_of_a_selected_repository() -> None:
    pop = select_population(NAMES, is_held_out=lambda r: False, seed=0, pool_size=2)
    assert len(pop.directories) == 2
    for repo in pop.repos:
        every = {n for name in NAMES for r, n in [_split(name)] if r == repo}
        assert set(pop.published[repo]) == every
    assert set(pop.published) == set(pop.repos)


def _split(name: str) -> tuple[str, int]:
    from ril.training.pool_check import split_instance_dir

    split = split_instance_dir(name)
    assert split is not None
    return split


def test_git_snapshot_keeps_files_marked_export_ignore_and_skips_symlinks(tmp_path) -> None:
    src = str(tmp_path / "src")
    os.makedirs(os.path.join(src, "tests"))
    git(src, "init", "-q")
    git(src, "config", "uploadpack.allowAnySHA1InWant", "true")
    with open(os.path.join(src, ".gitattributes"), "w") as f:
        f.write("tests export-ignore\n*.py export-subst\n")
    with open(os.path.join(src, "tests", "test_a.py"), "w") as f:
        f.write("def test_a():\n    assert True\n")
    with open(os.path.join(src, "a.py"), "w") as f:
        f.write('V = "$Format:%H$"\né = 1\n')
    os.symlink("a.py", os.path.join(src, "link.py"))
    git(src, "add", ".")
    git(src, "commit", "-q", "-m", "one")
    sha = git(src, "rev-parse", "HEAD")
    dest = str(tmp_path / "dest")
    os.makedirs(dest)
    snaps = GitSnapshots(str(tmp_path / "work"), remote="file://" + src)
    assert snaps.materialize("acme/widgets", sha, dest) == 2
    assert sorted(os.listdir(dest)) == ["a.py", "tests"]
    with open(os.path.join(dest, "a.py"), encoding="utf-8") as f:
        assert "$Format:%H$" in f.read()  # export-subst is not applied
    assert os.path.exists(os.path.join(dest, "tests", "test_a.py"))


def test_prefetch_gives_the_same_files_and_close_removes_unused_fetches(tmp_path) -> None:
    src = str(tmp_path / "src")
    os.makedirs(src)
    git(src, "init", "-q")
    git(src, "config", "uploadpack.allowAnySHA1InWant", "true")
    shas = []
    for i in range(3):
        with open(os.path.join(src, "a.py"), "w") as f:
            f.write(f"def a():\n    return {i}\n")
        git(src, "add", ".")
        git(src, "commit", "-q", "-m", str(i))
        shas.append(git(src, "rev-parse", "HEAD"))
    plain = GitSnapshots(str(tmp_path / "w1"), remote="file://" + src)
    ahead = GitSnapshots(str(tmp_path / "w2"), remote="file://" + src, workers=3)
    for sha in shas:
        ahead.prefetch("acme/widgets", sha)
    for i, sha in enumerate(shas):
        d1, d2 = str(tmp_path / f"p{i}"), str(tmp_path / f"q{i}")
        os.makedirs(d1)
        os.makedirs(d2)
        assert plain.materialize("acme/widgets", sha, d1) == 1
        assert ahead.materialize("acme/widgets", sha, d2) == 1
        assert open(os.path.join(d1, "a.py")).read() == open(os.path.join(d2, "a.py")).read()
        assert f"return {i}" in open(os.path.join(d2, "a.py")).read()
    ahead.prefetch("acme/widgets", shas[0])
    ahead.close()
    assert os.listdir(str(tmp_path / "w2")) == []
    bad = GitSnapshots(str(tmp_path / "w3"), remote="file://" + src)
    bad.prefetch("acme/widgets", "0" * 40)
    with pytest.raises(SnapshotError):
        bad.materialize("acme/widgets", "0" * 40, str(tmp_path / "w3d"))
    bad.close()
