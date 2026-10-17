"""Shared fixtures: a small synthetic repository written to a temp directory."""

from __future__ import annotations

from pathlib import Path

import pytest

MINI_REPO_FILES: dict[str, str] = {
    "pkg/__init__.py": "from .core import Engine, helper\n\n__all__ = ['Engine', 'helper']\n",
    "pkg/util.py": (
        '"""Utilities."""\n\ndef fmt(x):\n    return str(x)\n\ndef other():\n    return 1\n'
    ),
    "pkg/core.py": (
        "import os\n"
        "from . import util\n"
        "from .util import fmt\n\n"
        "VALUE = 3\n\n"
        "class Base:\n"
        "    def run(self):\n        return 1\n\n"
        "    def hook(self):\n        return 2\n\n"
        "class Helper:\n"
        "    def go(self):\n        return util.other()\n\n"
        "class Engine(Base):\n"
        "    def __init__(self):\n        self.helper = Helper()\n\n"
        "    @property\n    def size(self):\n        return 1\n\n"
        "    def run(self):\n"
        "        super().run()\n"
        "        self.hook()\n"
        "        fmt(VALUE)\n"
        "        os.getcwd()\n"
        "        return self.helper.go()\n\n"
        "    def dyn(self, name):\n        return getattr(self, name)()\n\n"
        "    def make(self, factory):\n        return factory()\n\n"
        "def helper():\n"
        "    def inner():\n        return 1\n"
        "    return inner()\n\n"
        "try:\n    import fastjson as json\n"
        "except ImportError:\n    import json\n\n"
        "if VALUE:\n    def twice():\n        return 1\n"
        "else:\n    def twice():\n        return 2\n\n"
        "def uses():\n    return twice()\n"
    ),
    "pkg/broken.py": "def oops(:\n",
    "tests/test_core.py": (
        "from pkg.core import Engine, helper\n\n"
        "def test_run():\n    assert Engine().run() == 1\n\n"
        "def test_helper():\n    assert helper() == 1\n"
    ),
    "setup.cfg": "[options.entry_points]\nconsole_scripts =\n    tool = pkg.core:helper\n",
    "pkg/__pycache__/skipme.py": "x = 1\n",
    "pkg/vendor/lib.py": "def vendored():\n    return 1\n",
    "pkg/gen_pb2.py": "x = 1\n",
}


@pytest.fixture
def mini_repo(tmp_path: Path) -> Path:
    """Write the synthetic repository under a temp directory and return its root."""
    for rel, text in MINI_REPO_FILES.items():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return tmp_path
