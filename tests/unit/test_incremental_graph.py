"""Incremental graph update: every update equals a full build of the same commit."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from ril.parsing.build import BuildConfig
from ril.parsing.incremental import full_state, state_digest, update_state

EXTRA_FILES: dict[str, str] = {
    "app.py": "from pkg import helper\n\ndef main():\n    return helper()\n",
    "pkg/user.py": "def drive(x):\n    return x.go()\n",
}


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        env={
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@example.com",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@example.com",
            "GIT_AUTHOR_DATE": "2024-01-01T00:00:00Z",
            "GIT_COMMITTER_DATE": "2024-01-01T00:00:00Z",
            "PATH": "/usr/bin:/bin",
        },
    )


def _commit(root: Path, n: int) -> None:
    _git(root, "add", "-A")
    stamp = f"2024-01-{n + 1:02d}T00:00:00Z"
    subprocess.run(
        ["git", "-C", str(root), "commit", "-q", "-m", f"c{n}"],
        check=True,
        capture_output=True,
        env={
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@example.com",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@example.com",
            "GIT_AUTHOR_DATE": stamp,
            "GIT_COMMITTER_DATE": stamp,
            "PATH": "/usr/bin:/bin",
        },
    )


def _edit(root: Path, rel: str, old: str, new: str) -> None:
    path = root / rel
    text = path.read_text(encoding="utf-8")
    assert old in text
    path.write_text(text.replace(old, new), encoding="utf-8")


# each step changes the checkout in a way that reaches other files' edges
STEPS: list[tuple[str, str, str, str]] = [
    ("edit", "pkg/util.py", "return 1", "return 2"),  # body only
    ("edit", "pkg/core.py", "def helper():", "def helper2():"),  # re-exported name goes away
    ("write", "pkg/extra.py", "class Other:\n    def go(self):\n        return 3\n", ""),
    ("edit", "pkg/broken.py", "def oops(:", "def oops():"),  # unparseable -> parseable
    ("write", "tests/__init__.py", "", ""),  # module names under tests/ change
    ("delete", "pkg/util.py", "", ""),  # an imported module disappears
    ("edit", "pkg/core.py", "class Engine(Base):", "class Engine(object):"),  # MRO changes
]


@pytest.mark.parametrize("with_history", [False, True])
def test_every_update_equals_a_full_build(mini_repo: Path, with_history: bool) -> None:
    for rel, text in EXTRA_FILES.items():
        (mini_repo / rel).write_text(text, encoding="utf-8")
    _git(mini_repo, "init", "-q")
    _commit(mini_repo, 0)
    config = BuildConfig(repo_id="acme/mini", with_history=with_history)
    state = full_state(str(mini_repo), config)
    for n, (kind, rel, a, b) in enumerate(STEPS, start=1):
        path = mini_repo / rel
        if kind == "edit":
            _edit(mini_repo, rel, a, b)
        elif kind == "write":
            path.write_text(a, encoding="utf-8")
        else:
            path.unlink()
        _commit(mini_repo, n)
        state, stats = update_state(state)
        fresh = full_state(str(mini_repo), config)
        assert state_digest(state) == state_digest(fresh), f"step {n}: {kind} {rel}"
        assert stats.files_changed + stats.files_deleted >= 1
        assert stats.files_reresolved <= len(fresh.parsed.files)


def test_a_body_edit_reresolves_only_what_depends_on_it(mini_repo: Path) -> None:
    for rel, text in EXTRA_FILES.items():
        (mini_repo / rel).write_text(text, encoding="utf-8")
    config = BuildConfig(repo_id="acme/mini", with_history=False)
    state = full_state(str(mini_repo), config)
    _edit(mini_repo, "pkg/user.py", "return x.go()", "return x.go() + 1")
    state, stats = update_state(state)
    assert stats.files_changed == 1
    # nothing imports pkg/user.py and its method names did not change
    assert stats.files_reresolved == 1
    assert state_digest(state) == state_digest(full_state(str(mini_repo), config))


def test_an_unchanged_checkout_reresolves_nothing(mini_repo: Path) -> None:
    config = BuildConfig(repo_id="acme/mini", with_history=False)
    state = full_state(str(mini_repo), config)
    again, stats = update_state(state)
    assert stats.files_changed == stats.files_deleted == stats.files_reresolved == 0
    assert state_digest(again) == state_digest(state)


def test_a_file_resolves_the_same_alone_as_in_a_full_build(tmp_path: Path) -> None:
    # ``str = str`` is a self-referencing alias: its lookup cuts a cycle, and the result must not
    # depend on which file asked first (it did before cycle-cut results stopped being cached)
    files = {
        "pkg/__init__.py": "",
        "pkg/compat.py": "builtin_str = str\nstr = str\n",
        "pkg/a.py": "from .compat import builtin_str\n\ndef f():\n    return builtin_str(1)\n",
        "pkg/b.py": "from .compat import str\n\ndef g():\n    return str(2)\n",
    }
    for rel, text in files.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(text, encoding="utf-8")
    config = BuildConfig(repo_id="acme/cyc", with_history=False)
    state = full_state(str(tmp_path), config)
    _edit(tmp_path, "pkg/b.py", "str(2)", "str(3)")
    updated, stats = update_state(state)
    assert stats.files_reresolved == 1
    assert state_digest(updated) == state_digest(full_state(str(tmp_path), config))
    for path in ("pkg/a.py", "pkg/b.py"):
        alone = {e.to_json() for e in updated.records[path].edges}
        ordered = {e.to_json() for e in updated.graph.edges if e.src.startswith(path + "::")}
        assert alone <= ordered
