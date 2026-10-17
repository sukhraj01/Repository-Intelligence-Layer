"""Unit tests for ril.evaluation.dynamic_trace."""

import importlib
import sys
from pathlib import Path

from ril.evaluation.dynamic_trace import Tracer


def test_tracer_records_in_root_pairs_and_builtin_callees(tmp_path: Path) -> None:
    (tmp_path / "tmod.py").write_text(
        "def leaf():\n    return len([1])\n\n"
        "def mid():\n    return leaf()\n\n"
        "def top():\n    return mid()\n",
        encoding="utf-8",
    )
    sys.path.insert(0, str(tmp_path))
    try:
        mod = importlib.import_module("tmod")
        tracer = Tracer(str(tmp_path))
        tracer.start()
        try:
            mod.top()
        finally:
            tracer.stop()
    finally:
        sys.path.remove(str(tmp_path))
        sys.modules.pop("tmod", None)
    pairs = {(a[2], b[2]) for a, b in tracer.pairs_py}
    assert ("mid", "leaf") in pairs and ("top", "mid") in pairs
    # the caller of ``top`` is this test (outside the root), so that pair is not kept
    assert not any(b[2] == "top" for _, b in tracer.pairs_py)
    assert any(name == "len" for _, _, name in tracer.pairs_c)
    assert ("tmod.py", 1, "leaf") in tracer.entered
