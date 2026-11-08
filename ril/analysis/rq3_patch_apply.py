"""Apply rates of the pilot's stored edit blocks at the base commits. Implements D110
(``docs/experiments/B.md`` E-RQ3-PATCHAPPLY).

Inputs are the pilot's call log and hashed replies, its prepared prompts, and the base-commit text
of every file a usable reply names (``snapshots``: ``{(instance, path): text or None}``). Nothing
is graded and no model is called. A unit's outcome is the converter's outcome for its final reply
under each reading; a block's class is its own outcome when it is the only block.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ril.agent.contracts import FileEdit
from ril.agent.providers.patch_convert import (
    READINGS,
    Reading,
    blocks_overlap_in_base,
    convert_edits,
    reader_of,
)
from ril.agent.providers.patch_format import parse_edits
from ril.analysis.rq3_pilot_analysis import _squash, excerpts_of, wilson

Row = dict[str, Any]
Snapshots = Mapping[tuple[str, str], str | None]


@dataclass(frozen=True)
class Unit:
    instance_id: str
    arm: str
    run_index: int
    reply: str
    prompt: str
    usable: bool


def load_units(log_dir: Path, prepared_dir: Path) -> list[Unit]:
    """One unit per (instance, arm, run): the final reply, its usability, the prompt it answered."""
    prompts: dict[tuple[str, str], str] = {}
    for line in (prepared_dir / "items.jsonl").read_text("utf-8").splitlines():
        if line:
            it = json.loads(line)
            prompts[(it["instance_id"], it["arm"])] = (
                prepared_dir / "prompts" / f"{it['prompt_sha256']}.txt"
            ).read_text("utf-8")
    units: list[Unit] = []
    for line in (log_dir / "calls.jsonl").read_text("utf-8").splitlines():
        if not line:
            continue
        r = json.loads(line)
        if not r["final"]:
            continue
        sha = r["response_sha256"]
        text = (log_dir / "responses" / f"{sha}.txt").read_text("utf-8") if sha else ""
        units.append(
            Unit(
                r["instance_id"],
                r["arm"],
                int(r["run_index"]),
                text,
                prompts[(r["instance_id"], r["arm"])],
                bool(r["patch_ok"]),
            )
        )
    units.sort(key=lambda u: (u.instance_id, u.arm, u.run_index))
    return units


def edits_of(unit: Unit) -> tuple[FileEdit, ...]:
    """Edit blocks of a usable unit (the parser unchanged, no path filter)."""
    edits, code = parse_edits(unit.reply, None)
    if code is not None:
        raise ValueError(f"{unit.instance_id}/{unit.arm}/{unit.run_index}: {code}")
    return edits


def needed_files(units: list[Unit]) -> dict[str, list[str]]:
    """Paths to read per instance: every file a usable unit's blocks name."""
    out: dict[str, set[str]] = {}
    for u in units:
        if u.usable:
            out.setdefault(u.instance_id, set()).update(e.path for e in edits_of(u))
    return {k: sorted(v) for k, v in sorted(out.items())}


def _reader(instance: str, snaps: Snapshots) -> Any:
    return reader_of({p: t for (i, p), t in snaps.items() if i == instance})


def block_class(edit: FileEdit, text: str | None, reading: Reading, whole: str) -> Row:
    """The block's own outcome plus where its SEARCH text is found."""
    res = convert_edits([edit], reader_of({edit.path: text}), reading)
    shown = excerpts_of(whole).get(edit.path, "")
    return {
        "outcome": res.outcome,
        "in_excerpts": edit.old in shown,
        "in_excerpts_squashed": _squash(edit.old) in _squash(shown),
        "in_file_exact": text is not None and edit.old in text,
    }


def unit_rows(units: list[Unit], snaps: Snapshots) -> tuple[list[Row], list[Row]]:
    """``(unit rows, block rows)`` for the usable units; one row per unit and per block."""
    urows: list[Row] = []
    brows: list[Row] = []
    for u in units:
        if not u.usable:
            continue
        edits = edits_of(u)
        read = _reader(u.instance_id, snaps)
        row: Row = {
            "instance_id": u.instance_id,
            "arm": u.arm,
            "run_index": u.run_index,
            "n_blocks": len(edits),
        }
        for reading in READINGS:
            res = convert_edits(edits, read, reading)
            row[reading] = res.outcome
            row[reading + "_block"] = res.failure.block if res.failure else -1
        row["overlap_in_base_exact"] = blocks_overlap_in_base(edits, read, "exact")
        urows.append(row)
        for k, e in enumerate(edits):
            b = {"instance_id": u.instance_id, "arm": u.arm, "run_index": u.run_index, "block": k}
            for reading in READINGS:
                c = block_class(e, snaps.get((u.instance_id, e.path)), reading, u.prompt)
                b[reading] = c["outcome"]
            b["in_excerpts"] = c["in_excerpts"]
            b["in_excerpts_squashed"] = c["in_excerpts_squashed"]
            b["in_file_exact"] = c["in_file_exact"]
            brows.append(b)
    return urows, brows


OUTCOMES = ("applied", "applied_empty", "file_missing", "no_match", "multiple_matches")


def outcome_table(urows: list[Row], units: list[Unit]) -> list[Row]:
    """Per arm and in total: units, usable, and the outcome counts under each reading."""
    out: list[Row] = []
    arms = sorted({u.arm for u in units}) + ["all"]
    for arm in arms:
        sel = [u for u in units if arm in ("all", u.arm)]
        rows = [r for r in urows if arm in ("all", r["arm"])]
        for reading in READINGS:
            c = Counter(r[reading] for r in rows)
            applying = c["applied"] + c["applied_empty"]
            lo, hi = wilson(applying, len(sel))[1:]
            out.append(
                {
                    "arm": arm,
                    "reading": reading,
                    "units": len(sel),
                    "usable": len(rows),
                    **{k: c[k] for k in OUTCOMES},
                    "usable_and_applying": applying,
                    "share_of_units": round(applying / len(sel), 4),
                    "share_low": round(lo, 4),
                    "share_high": round(hi, 4),
                }
            )
    return out


def rescue_table(urows: list[Row]) -> list[Row]:
    """Of the units that fail under exact, how many the tolerant reading applies; and how many
    applying units a base-text-only rule (no block may overlap another) would have failed."""
    out: list[Row] = []
    for arm in sorted({r["arm"] for r in urows}) + ["all"]:
        rows = [r for r in urows if arm in ("all", r["arm"])]
        failing = [r for r in rows if r["exact"] not in ("applied", "applied_empty")]
        rescued = [r for r in failing if r["tolerant"] in ("applied", "applied_empty")]
        lost = [
            r
            for r in rows
            if r["exact"] in ("applied", "applied_empty")
            and r["tolerant"] not in ("applied", "applied_empty")
        ]
        out.append(
            {
                "arm": arm,
                "usable": len(rows),
                "exact_failing": len(failing),
                "rescued_by_tolerant": len(rescued),
                "share_rescued": round(len(rescued) / len(failing), 4) if failing else "",
                "exact_applying_but_tolerant_failing": len(lost),
                "exact_applying_with_overlap_in_base_text": sum(
                    1
                    for r in rows
                    if r["exact"] in ("applied", "applied_empty") and r["overlap_in_base_exact"]
                ),
            }
        )
    return out


def block_table(brows: list[Row]) -> list[Row]:
    """Where blocks' SEARCH texts are found, for all blocks and for the exact-failing ones.

    ``in_excerpts``: exact substring of the named file's excerpts in the prompt; ``in_file``: exact
    substring of the named file at the base commit; ``tolerant_only``: the block applies under the
    tolerant reading but not the exact one.
    """
    out: list[Row] = []
    for arm in sorted({r["arm"] for r in brows}) + ["all"]:
        rows = [r for r in brows if arm in ("all", r["arm"])]
        cells: Counter[tuple[str, str, str]] = Counter()
        for r in rows:
            cls = r["exact"]
            if cls not in ("applied", "applied_empty"):
                if cls == "no_match" and r["tolerant"] in ("applied", "applied_empty"):
                    cls = "no_match:tolerant_only"
                elif cls == "no_match":
                    cls = "no_match:nowhere_in_file"
            where = "in_excerpts" if r["in_excerpts"] else "not_in_excerpts"
            file = "in_file" if r["in_file_exact"] else "not_in_file"
            cells[(cls, where, file)] += 1
        for (cls, where, file), n in sorted(cells.items()):
            out.append(
                {
                    "arm": arm,
                    "block_exact_outcome": cls,
                    "excerpts": where,
                    "file": file,
                    "blocks": n,
                }
            )
    return out


# ---------------------------------------------------------------------------- snapshots


def base_commit_of(cache_file: Path) -> str:
    """Base commit recorded in an instance cache file (``e3_prepare.write_cache``)."""
    import numpy as np

    with np.load(cache_file, allow_pickle=False) as data:
        return str(json.loads(str(data["meta"]))["base_commit"])


def mirror_of(instance_id: str, mirror_dir: Path) -> Path:
    """The bare repository of an instance: the longest ``<owner>__<repo>.git`` whose stem, followed
    by ``-``, starts the id (an ``instance_`` prefix of the newer benchmark ids is ignored)."""
    bare = instance_id.removeprefix("instance_")
    stems = [p.name[:-4] for p in mirror_dir.glob("*.git") if bare.startswith(p.name[:-4] + "-")]
    if not stems:
        raise FileNotFoundError(f"no mirror in {mirror_dir} for {instance_id}")
    return mirror_dir / (max(stems, key=len) + ".git")


def write_snapshots(
    needed: Mapping[str, list[str]], cache_dir: Path, mirror_dir: Path, out: Path
) -> dict[str, int]:
    """Base-commit text of every needed file, one JSON row each (``text`` null if absent).

    Mirrors are bare repositories named ``<owner>__<repo>.git`` (see ``mirror_of``).
    """
    from ril.agent.providers.patch_convert import git_reader

    counts = {"files": 0, "absent": 0, "undecodable": 0}
    with out.open("w", encoding="utf-8") as fh:
        for iid, paths in needed.items():
            commit = base_commit_of(cache_dir / f"{iid}.npz")
            read = git_reader(str(mirror_of(iid, mirror_dir)), commit)
            for path in paths:
                note = ""
                try:
                    text = read(path)
                except UnicodeDecodeError:
                    text, note = None, "undecodable"
                counts["files"] += 1
                counts["absent"] += text is None and not note
                counts["undecodable"] += bool(note)
                row = {"instance_id": iid, "path": path, "base_commit": commit, "text": text}
                fh.write(json.dumps({**row, "note": note}) + "\n")
    return counts


def read_snapshots(path: Path) -> dict[tuple[str, str], str | None]:
    out: dict[tuple[str, str], str | None] = {}
    for line in path.read_text("utf-8").splitlines():
        if line:
            r = json.loads(line)
            out[(r["instance_id"], r["path"])] = r["text"]
    return out
