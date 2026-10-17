"""Same data, code and seed give identical pilot M records (draws are seeded per chunk)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tests.integration.test_pilot_m import _run, origin  # noqa: F401  (fixture re-export)


def _without_timing(path: Path) -> dict[str, Any]:
    doc: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    for inst in doc["instances"]:
        inst.pop("build_seconds")  # wall-clock time is the one field allowed to vary
    return doc


def test_records_are_identical_across_fresh_runs(
    tmp_path: Path,
    origin: tuple[Path, str],  # noqa: F811
) -> None:
    _run(tmp_path, origin, out="first")
    (tmp_path / "work").rename(tmp_path / "work_first")  # second run: new clones, no cache
    _run(tmp_path, origin, out="second")
    assert _without_timing(tmp_path / "first" / "records.json") == _without_timing(
        tmp_path / "second" / "records.json"
    )
