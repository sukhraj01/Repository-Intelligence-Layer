"""Labelled readings of the mined data: views over a run root, never a re-mining (decision D95).

Implements ``docs/experiments/B.md`` E-MINE-STORE (Q61, ``docs/POOL_CONSTRUCTION.md``). The mined
directories hold the unrestricted set. A *reading* selects from a directory's corpus and positives
without touching the run root:

``unrestricted``  every corpus row and every positive as mined (the earlier "all" reading).
``non_test``      no function of a test file (D9 path rule), no test positive, a directory with no
                  positive left is dropped (the reading of stage M3, DEV-030; keeps ``async def``).
``pool_aligned``  the rules of the code that produced the published pool, as far as they can be
                  applied to mined rows (``docs/POOL_CONSTRUCTION.md``): the corpus loses every
                  ``async def`` function and every function whose repository-relative path
                  contains ``test`` in any case (a substring, as the released code tests it); a
                  positive must still be in that corpus and own a *removed or rewritten* old-side
                  line (``removed_lines > 0`` in the directory's ``pr_meta.json``); positives that
                  only received inserted lines are not positives; a directory with no positive
                  left is dropped. Rows are not added, so the nested functions and vendored
                  directories the released code keeps are not reproduced (they are not mined).

``DEFAULT_READING`` is the primary reading of the mined set for RQ2, the reading of the M3 measurement (D96);
``pool_aligned`` is a sensitivity reading and the unrestricted reading stays available, each under its own label. Kept compatible with Python 3.10.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from typing import Any

from ril.data_mining.agreement import is_test_id, path_of

UNRESTRICTED = "unrestricted"
NON_TEST = "non_test"
POOL_ALIGNED = "pool_aligned"
READINGS: tuple[str, ...] = (UNRESTRICTED, NON_TEST, POOL_ALIGNED)
DEFAULT_READING = NON_TEST
"""The primary reading of the mined set for RQ2 (D96, DEV-031); it is not the library default of
:func:`apply`, which is unrestricted so that no caller changes meaning without naming a reading."""

_DEF_LINE = re.compile(r"^[ \t]*(async[ \t]+)?def[ \t]", re.MULTILINE)


def check_reading(reading: str) -> str:
    """``reading`` itself, or a ``ValueError`` naming the valid ones."""
    if reading not in READINGS:
        raise ValueError(f"unknown reading {reading!r}; use one of {READINGS}")
    return reading


def is_async_row(text: str) -> bool:
    """Whether a corpus row's text (``<id>\\n<source>``) defines an ``async def`` function.

    The source starts at the first decorator line, so the first line that begins with ``def`` or
    ``async def`` after the identifier line is the definition itself.
    """
    _, _, source = text.partition("\n")
    found = _DEF_LINE.search(source)
    return bool(found and found.group(1))


def has_test_substring(pool_id: str) -> bool:
    """Whether the file path of a pool id contains ``test`` in any case (the released rule)."""
    return "test" in path_of(pool_id).lower()


def _split(data: bytes) -> list[bytes]:
    return [line for line in data.splitlines(keepends=True) if line.strip()]


def apply(
    reading: str, corpus: bytes, qrels: bytes, meta: Mapping[str, Any]
) -> tuple[bytes, bytes] | None:
    """``(corpus, qrels)`` bytes of one directory under ``reading``, or ``None`` if it is dropped.

    ``meta`` is the directory's ``pr_meta.json``; only ``pool_aligned`` reads it.
    """
    check_reading(reading)
    if reading == UNRESTRICTED:
        return corpus, qrels
    lines = qrels.decode("utf-8").splitlines(keepends=True)
    header, body = lines[0], [x for x in lines[1:] if x.strip()]
    rows = _split(corpus)
    if reading == NON_TEST:
        kept_rows = [r for r in rows if not is_test_id(str(json.loads(r)["_id"]))]
        kept_qrels = [x for x in body if not is_test_id(x.split("\t")[1])]
    else:
        removed = _removed_lines(meta)
        kept_rows = []
        kept_ids: set[str] = set()
        for r in rows:
            doc = json.loads(r)
            pid = str(doc["_id"])
            if has_test_substring(pid) or is_async_row(str(doc["text"])):
                continue
            kept_rows.append(r)
            kept_ids.add(pid)
        kept_qrels = []
        for x in body:
            pid = x.split("\t")[1]
            if pid not in removed:
                raise ValueError(f"positive {pid!r} has no row in pr_meta.json positives")
            if pid in kept_ids and removed[pid] > 0:
                kept_qrels.append(x)
    if not kept_qrels:
        return None
    return b"".join(kept_rows), (header + "".join(kept_qrels)).encode("utf-8")


def _removed_lines(meta: Mapping[str, Any]) -> dict[str, int]:
    rows: Sequence[Mapping[str, Any]] = meta["positives"]
    return {str(p["pool_id"]): int(p["removed_lines"]) for p in rows if p["in_corpus"]}
