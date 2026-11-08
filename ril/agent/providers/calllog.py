"""Per-call log and hash-addressed prompt and response files. Implements ``docs/RQ3_PILOT.md``.

One row per logical model call is appended to ``calls.jsonl`` after the call finishes (flushed and
synced), so a run that stops resumes from the rows alone. Prompts and responses are not in the rows:
they are files named by the SHA-256 of their bytes under ``prompts/`` and ``responses/``. A unit of
work is (instance, arm, run index); it is finished when a row with ``final`` set exists.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

Row = dict[str, Any]
Unit = tuple[str, str, int]


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass
class CallLog:
    root: Path

    def __post_init__(self) -> None:
        self.root = Path(self.root)
        (self.root / "prompts").mkdir(parents=True, exist_ok=True)
        (self.root / "responses").mkdir(parents=True, exist_ok=True)
        self.path = self.root / "calls.jsonl"

    def store(self, kind: str, text: str) -> str:
        """Write ``text`` under ``kind`` ('prompts' or 'responses') by hash; return the hash."""
        digest = sha256_text(text)
        target = self.root / kind / f"{digest}.txt"
        if not target.exists():
            tmp = target.with_suffix(".tmp")
            tmp.write_text(text, encoding="utf-8")
            os.replace(tmp, target)
        return digest

    def load(self, kind: str, digest: str) -> str:
        return (self.root / kind / f"{digest}.txt").read_text(encoding="utf-8")

    def append(self, row: Row) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def rows(self) -> Iterator[Row]:
        if not self.path.exists():
            return
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                yield json.loads(line)

    def by_unit(self) -> dict[Unit, list[Row]]:
        """Rows of every unit in attempt order."""
        out: dict[Unit, list[Row]] = {}
        for r in self.rows():
            out.setdefault((r["instance_id"], r["arm"], int(r["run_index"])), []).append(r)
        for rows in out.values():
            rows.sort(key=lambda r: int(r["attempt"]))
        return out
