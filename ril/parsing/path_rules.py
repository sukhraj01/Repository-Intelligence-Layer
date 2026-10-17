"""The ``is_test`` rule: a file-level path rule.

Implements ``specs/code_unit.md`` decision D9. A file is a test file if any directory component
of its repo-relative posix path is ``tests`` or ``test``, or its file name is ``test_*.py``,
``*_test.py`` or ``conftest.py``. The rule looks at the path only (no parsing, no framework
markers), so it is cheap and deterministic; ``examples/`` and ``docs/`` are not tests.
Agreement with pytest collection is measured by ``scripts/validate_is_test_rule.py``.
"""

from __future__ import annotations

from pathlib import PurePosixPath

TEST_DIR_NAMES: frozenset[str] = frozenset({"tests", "test"})


def is_test_path(path: str) -> bool:
    """True if ``path`` (repo-relative, posix) is a test file under the D9 rule."""
    p = PurePosixPath(path)
    if any(part in TEST_DIR_NAMES for part in p.parts[:-1]):
        return True
    name = p.name
    if not name.endswith(".py"):
        return False
    return name == "conftest.py" or name.startswith("test_") or name.endswith("_test.py")
