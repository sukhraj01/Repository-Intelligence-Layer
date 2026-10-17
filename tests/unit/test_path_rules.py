"""Unit tests for ril.parsing.path_rules (specs/code_unit.md decision D9)."""

import pytest

from ril.parsing.path_rules import is_test_path


@pytest.mark.parametrize(
    "path",
    [
        "tests/test_app.py",
        "tests/helpers.py",
        "src/pkg/tests/unit/util.py",
        "test/foo.py",
        "pkg/test_foo.py",
        "pkg/foo_test.py",
        "conftest.py",
        "pkg/sub/conftest.py",
        "tests/__init__.py",
    ],
)
def test_test_paths(path: str) -> None:
    assert is_test_path(path)


@pytest.mark.parametrize(
    "path",
    [
        "src/flask/app.py",
        "examples/tutorial/flaskr/__init__.py",
        "docs/conf.py",
        "pkg/testing.py",
        "pkg/testutils.py",
        "pkg/contest.py",
        "pkg/attest.py",
        "pkg/test.py",
        "pkg/latest_test_data.json",
        "tests.py",
        "src/protests/x.py",
        "pkg/test_foo.txt",
    ],
)
def test_non_test_paths(path: str) -> None:
    assert not is_test_path(path)


def test_directory_named_tests_wins_over_file_name() -> None:
    assert is_test_path("tests/not_a_test_name.py")
