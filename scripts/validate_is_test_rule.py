"""Compare the ``is_test`` path rule (decision D9) with what pytest collects.

For each source tree: list every ``*.py`` file, ask ``ril.parsing.path_rules.is_test_path`` about
it, run ``pytest --collect-only`` in the tree and read which files pytest collects tests from (or
fails to import, which still names a test module). Reports counts only, per repository:

* collected modules the rule flags (recall of the rule against pytest) and misses;
* files the rule flags that pytest does not collect from (helpers, ``conftest.py``, package
  ``__init__`` files under ``tests/``: expected, because D9 labels test code, not test modules).

Usage: validate_is_test_rule.py OUT.json NAME=DIR [NAME=DIR ...]
Stdlib only apart from ``ril`` (on the path) and pytest (in the interpreter running this script).
"""
# ruff: noqa: T201

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ril.parsing.path_rules import is_test_path  # noqa: E402

_ITEM = re.compile(r"^([^\s:]+\.py)::")
_ERR = re.compile(r"^(?:ERROR|FAILED)\s+([^\s:]+\.py)")


def collect(tree: Path) -> tuple[set[str], set[str], str]:
    """Return (files with collected items, files that failed to collect, pytest summary line)."""
    env = dict(os.environ)
    src = tree / "src"
    env["PYTHONPATH"] = os.pathsep.join(
        [str(src) if src.is_dir() else str(tree), env.get("PYTHONPATH", "")]
    )
    proc = subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "-p",
            "no:cacheprovider",
            "--continue-on-collection-errors",
            "-o",
            "addopts=",
        ],  # fmt: skip
        cwd=tree,
        env=env,
        capture_output=True,
        text=True,
        timeout=1800,
        check=False,
    )
    items: set[str] = set()
    errors: set[str] = set()
    last = ""
    for line in proc.stdout.splitlines():
        if m := _ITEM.match(line):
            items.add(m.group(1))
        elif m := _ERR.match(line):
            errors.add(m.group(1))
        if line.strip():
            last = line.strip()
    return items, errors, last


def main() -> None:
    out = Path(sys.argv[1])
    doc: dict[str, object] = {}
    for spec in sys.argv[2:]:
        name, _, d = spec.partition("=")
        tree = Path(d)
        files = sorted(p.relative_to(tree).as_posix() for p in tree.rglob("*.py"))
        flagged = {f for f in files if is_test_path(f)}
        items, errors, last = collect(tree)
        collected = items | errors
        doc[name] = {
            "py_files": len(files),
            "rule_flagged": len(flagged),
            "pytest_files_with_items": len(items),
            "pytest_files_collection_error": len(errors),
            "pytest_summary": last,
            "collected_flagged_by_rule": len(collected & flagged),
            "collected_missed_by_rule": sorted(collected - flagged),
            "flagged_not_collected": len(flagged - collected),
            "flagged_not_collected_kinds": {
                "conftest": sum(1 for f in flagged - collected if f.endswith("conftest.py")),
                "package_init": sum(1 for f in flagged - collected if f.endswith("__init__.py")),
                "other": sorted(
                    f for f in flagged - collected if not f.endswith(("conftest.py", "__init__.py"))
                )[:25],
            },  # fmt: skip
        }
        print(
            name,
            json.dumps({k: v for k, v in doc[name].items() if not isinstance(v, (list, dict))}),
        )  # type: ignore[union-attr]
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
