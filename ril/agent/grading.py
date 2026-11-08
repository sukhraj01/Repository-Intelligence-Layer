"""Execute trusted fixture checks in a fresh directory; grade patches independently."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path

from ril.agent.contracts import FileEdit, Grade, Task, validate_path


class FixtureTestGrader:
    """Local subprocess isolation is for trusted fixtures, not a sandbox for live agent code."""

    def __init__(self, test_source: str, timeout_s: float = 5.0):
        if timeout_s <= 0:
            raise ValueError("test timeout must be positive")
        self.test_source = test_source
        self.timeout_s = timeout_s

    def grade(self, task: Task, edits: Sequence[FileEdit]) -> Grade:
        files = dict(task.files)
        for edit in edits:
            validate_path(edit.path)
            if edit.path not in files or not edit.old or files[edit.path].count(edit.old) != 1:
                return Grade(False, "patch_rejected", "edit target must match exactly once")
            files[edit.path] = files[edit.path].replace(edit.old, edit.new, 1)
        with tempfile.TemporaryDirectory(prefix="ril-fixture-") as directory:
            root = Path(directory)
            for path, source in files.items():
                target = root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(source)
            (root / "_checks.py").write_text(self.test_source)
            try:
                result = subprocess.run(
                    [sys.executable, "-I", "-B", "_checks.py"],
                    cwd=root,
                    env={"PATH": os.defpath, "PYTHONDONTWRITEBYTECODE": "1"},
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_s,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                return Grade(False, "timeout", "fixture test exceeded the configured timeout")
        return Grade(
            result.returncode == 0,
            "passed" if result.returncode == 0 else "tests_failed",
            result.stdout + result.stderr,
        )
