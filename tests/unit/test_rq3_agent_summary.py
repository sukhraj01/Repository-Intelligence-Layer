"""Per-arm summary of graded runs (stored files only)."""

from __future__ import annotations

import json
from pathlib import Path

from ril.analysis.rq3_agent_summary import arm_summary, build, sha256_file


def _write(path: Path, rows: list[dict[str, object]]) -> str:
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return str(path)


def _files(tmp: Path) -> tuple[str, str]:
    res = [
        {
            "run": k,
            "resolved": k == 0 or i == 0,
            "outcome": "unusable" if i == 1 else "resolved",
            "cost_usd": 0.5,
        }
        for k in (0, 1)
        for i in range(2)
    ]
    calls = [
        {
            "run_index": k,
            "attempt": 0,
            "finish_reason": "MAX_TOKENS" if k == 0 else "STOP",
            "input_tokens": 100,
            "cached_tokens": 0 if k == 0 else 50,
        }
        for k in (0, 1)
        for _ in range(2)
    ]
    return _write(tmp / "r.jsonl", res), _write(tmp / "c.jsonl", calls)


def test_counts_truncation_cache_and_spread(tmp_path: Path) -> None:
    r, c = _files(tmp_path)
    s = arm_summary("a", r, c, [0, 1])
    assert s["rows"] == 4 and s["resolved"] == 3 and s["unusable"] == 2
    assert s["truncation_share"] == 0.5 and s["cache_share_all"] == 0.25
    assert s["cache_share_repeats_after_first"] == 0.5
    assert s["resolved_fraction_by_repeat"] == [1.0, 0.5]
    assert s["cost_usd"] == 2.0


def test_every_input_has_a_hash(tmp_path: Path) -> None:
    r, c = _files(tmp_path)
    out = build({"a": (r, c)}, [0, 1], {"plan": r})
    assert out["input_sha256"]["plan"] == sha256_file(r)
    assert set(out["input_sha256"]) == {"a:results", "a:calls", "plan"}
