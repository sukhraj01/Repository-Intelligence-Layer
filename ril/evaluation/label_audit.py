"""Label sheet for the pull-request noise audit: draw, truncation rules, sheets and key.

Implements ``docs/RQ2_PROTOCOL.md`` section 7 (the noise audit) and O11/D78, and the instructions
in ``docs/LABEL_AUDIT.md``. A *pair* is one (issue, edited function) positive of a mined pull
request, the unit of the positive-level K-rank filter. Readers judge whether the edited function
answers the issue; the sheet carries no rank, stratum or filter decision, which live in a separate
key file the readers never see. The scorer is ``ril/evaluation/label_audit_score.py``.

Everything here is pure and deterministic: the same inputs and seed give the same bytes. Kept
compatible with Python 3.10 (the cluster's compute nodes).
"""

from __future__ import annotations

import csv
import hashlib
import io
import random
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

K_FILTER = 20
"""K of the positive-level K-rank filter whose findability the audit measures (O3)."""
STRATUM_KEPT = "bm25_kept"
STRATUM_DROPPED = "bm25_dropped"
STRATA: tuple[str, ...] = (STRATUM_KEPT, STRATUM_DROPPED)

# Verdicts, as typed by the readers (lower case; matched after strip and lower-casing).
RELEVANT = "relevant"
NOT_RELEVANT = "not relevant"
CANNOT_TELL = "cannot tell"
VERDICTS: tuple[str, ...] = (RELEVANT, NOT_RELEVANT, CANNOT_TELL)
YES = "yes"
NO = "no"
MISSING_ANSWERS: tuple[str, ...] = (YES, NO, CANNOT_TELL)

# Truncation rules, stated in docs/LABEL_AUDIT.md; changing one changes the instructions.
ISSUE_BODY_CHARS = 3000
FUNCTION_TEXT_CHARS = 4000
HUNK_CHARS = 4000
OTHER_FUNCTIONS_MAX = 30
PR_TITLE_CHARS = 300

SHEET_COLUMNS: tuple[str, ...] = (
    "pair_id",
    "repository",
    "issue_title",
    "issue_body",
    "pull_request_title",
    "function_path",
    "function_name",
    "function_kind",
    "function_text_before",
    "diff_hunk",
    "other_edited_functions",
    "verdict",
    "reason",
    "issue_function_not_edited",
    "reader_id",
)
"""The sheet's columns. The last four are filled by the reader (``reader_id`` is pre-filled)."""
READER_COLUMNS: tuple[str, ...] = ("verdict", "reason", "issue_function_not_edited", "reader_id")

KEY_COLUMNS: tuple[str, ...] = (
    "pair_id",
    "stratum",
    "rank_bm25",
    "rank_all_bm25",
    "rank_dense",
    "dense_kept_k20",
    "directory",
    "positive",
    "assignment",
    "in_overlap",
    "stratum_population",
    "stratum_sample",
    "hunk_reproduced",
)


@dataclass(frozen=True)
class Candidate:
    """One positive of the population with its BM25 rank (and the dense rank where it exists)."""

    directory: str
    positive: str
    rank: int
    rank_all: int
    dense_rank: int | None = None

    @property
    def stratum(self) -> str:
        return STRATUM_KEPT if self.rank <= K_FILTER else STRATUM_DROPPED


def pair_id(seed: int, directory: str, positive: str) -> str:
    """Opaque pair id: a hash prefix that says nothing about stratum, repository or order."""
    raw = f"label-audit/{seed}/{directory}/{positive}".encode()
    return hashlib.sha256(raw).hexdigest()[:10]


def candidates_from_ranks(
    bm25_rows: Iterable[Mapping[str, Any]], dense_rows: Iterable[Mapping[str, Any]] = ()
) -> list[Candidate]:
    """Population candidates from the rank rows (``rank-bm25`` / dense files), in sorted order.

    ``rank`` is the rank among the corpus the filter uses (``rank_all`` is the rank before test
    files are removed from the list). The dense rank is attached where a directory has one.
    """
    dense: dict[tuple[str, str], int] = {}
    for row in dense_rows:
        for r in row["ranks"]:
            dense[(str(row["dir"]), str(r["positive"]))] = int(r["rank"])
    out: list[Candidate] = []
    for row in bm25_rows:
        for r in row["ranks"]:
            key = (str(row["dir"]), str(r["positive"]))
            out.append(
                Candidate(key[0], key[1], int(r["rank"]), int(r["rank_all"]), dense.get(key))
            )
    out.sort(key=lambda c: (c.directory, c.positive))
    return out


@dataclass(frozen=True)
class Draw:
    """The sample and how it is split between readers."""

    seed: int
    pairs: tuple[Candidate, ...]
    overlap: tuple[str, ...]
    """Pair ids read by both readers."""
    own: dict[str, tuple[str, ...]]
    """Reader name -> pair ids only that reader reads."""
    population: dict[str, int]
    sample: dict[str, int]
    ids: dict[str, Candidate]


def _rng(seed: int, label: str) -> random.Random:
    return random.Random(f"label-audit/{seed}/{label}")


def draw(
    population: Sequence[Candidate],
    *,
    seed: int,
    per_stratum: int = 200,
    overlap_total: int = 100,
    readers: Sequence[str] = ("reader_1", "reader_2"),
) -> Draw:
    """Seeded stratified draw, the overlap and the split of the rest between readers.

    ``per_stratum`` pairs are drawn uniformly without replacement from each stratum (all of a
    stratum if it holds fewer; the shortfall is visible in ``sample`` against ``per_stratum``).
    The overlap takes the same number from each stratum; the remaining pairs are shared out
    between the readers within each stratum, so every reader's own pairs have the same stratum mix.
    """
    if len(readers) != 2:
        raise ValueError("two readers")
    by: dict[str, list[Candidate]] = {s: [] for s in STRATA}
    for c in sorted(population, key=lambda c: (c.directory, c.positive)):
        by[c.stratum].append(c)
    chosen: dict[str, list[Candidate]] = {}
    for s in STRATA:
        pool = by[s]
        take = min(per_stratum, len(pool))
        chosen[s] = sorted(
            _rng(seed, f"draw/{s}").sample(pool, take), key=lambda c: (c.directory, c.positive)
        )
    ids: dict[str, Candidate] = {}
    for s in STRATA:
        for c in chosen[s]:
            pid = pair_id(seed, c.directory, c.positive)
            if pid in ids:
                raise ValueError(f"pair id collision {pid}")
            ids[pid] = c
    overlap: list[str] = []
    own: dict[str, list[str]] = {r: [] for r in readers}
    for s in STRATA:
        s_ids = [pair_id(seed, c.directory, c.positive) for c in chosen[s]]
        share = min(overlap_total // len(STRATA), len(s_ids))
        picked = _rng(seed, f"overlap/{s}").sample(s_ids, share)
        overlap.extend(picked)
        rest = [i for i in s_ids if i not in set(picked)]
        _rng(seed, f"split/{s}").shuffle(rest)
        half = (len(rest) + 1) // 2
        own[readers[0]].extend(rest[:half])
        own[readers[1]].extend(rest[half:])
    return Draw(
        seed=seed,
        pairs=tuple(ids[i] for i in sorted(ids)),
        overlap=tuple(sorted(overlap)),
        own={r: tuple(sorted(v)) for r, v in own.items()},
        population={s: len(by[s]) for s in STRATA},
        sample={s: len(chosen[s]) for s in STRATA},
        ids=ids,
    )


# --------------------------------------------------------------------------- text rules


def truncate(text: str, limit: int) -> str:
    """``text`` cut at ``limit`` characters, with a visible marker saying how many were omitted."""
    if len(text) <= limit:
        return text
    return f"{text[:limit]}\n[... truncated, {len(text) - limit} characters omitted]"


def other_functions_text(names: Sequence[str]) -> str:
    """One ``path::name`` per line, at most ``OTHER_FUNCTIONS_MAX``, then ``(+N more)``."""
    shown = list(names[:OTHER_FUNCTIONS_MAX])
    if len(names) > OTHER_FUNCTIONS_MAX:
        shown.append(f"(+{len(names) - OTHER_FUNCTIONS_MAX} more)")
    return "\n".join(shown)


_FORMULA_LEADERS = ("=", "+", "-", "@", "\t", "\r")


def spreadsheet_safe(text: str) -> str:
    """Prefix a space to text a spreadsheet would read as a formula (such as a diff line)."""
    return f" {text}" if text.startswith(_FORMULA_LEADERS) else text


def split_query(query: str) -> tuple[str, str]:
    """Issue title and body from the stored query (title, blank line, body; ``query_text``)."""
    title, _, body = query.partition("\n\n")
    return title, body


def sheet_row(record: Mapping[str, Any], pid: str, reader: str) -> dict[str, str]:
    """One sheet row from an extracted pair record, with the truncation rules applied."""
    title, body = split_query(str(record["query"]))
    row = {
        "pair_id": pid,
        "repository": str(record["repo"]),
        "issue_title": title,
        "issue_body": truncate(body, ISSUE_BODY_CHARS),
        "pull_request_title": str(record["pr_title"])[:PR_TITLE_CHARS],
        "function_path": str(record["path"]),
        "function_name": str(record["qualified_name"]),
        "function_kind": str(record["unit_kind"]),
        "function_text_before": truncate(str(record["unit_text"]), FUNCTION_TEXT_CHARS),
        "diff_hunk": truncate(str(record["hunks"]), HUNK_CHARS),
        "other_edited_functions": other_functions_text(list(record["other_functions"])),
        "verdict": "",
        "reason": "",
        "issue_function_not_edited": "",
        "reader_id": reader,
    }
    return {k: (spreadsheet_safe(v) if k not in READER_COLUMNS else v) for k, v in row.items()}


def shuffled(ids: Sequence[str], seed: int, label: str) -> list[str]:
    """``ids`` in an order fixed by ``seed`` and ``label`` (one independent shuffle per sheet)."""
    out = sorted(ids)
    _rng(seed, f"order/{label}").shuffle(out)
    return out


def sheet_csv(rows: Sequence[Mapping[str, str]]) -> bytes:
    """A sheet as UTF-8 CSV with a byte-order mark (spreadsheets then read the encoding right)."""
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=list(SHEET_COLUMNS), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({c: row[c] for c in SHEET_COLUMNS})
    return b"\xef\xbb\xbf" + buf.getvalue().encode("utf-8")


def key_csv(d: Draw, hunk_ok: Mapping[str, bool]) -> bytes:
    """The key file: stratum, ranks and assignment of every pair (readers never see it)."""
    assignment: dict[str, str] = {i: "overlap" for i in d.overlap}
    for r, v in d.own.items():
        for i in v:
            assignment[i] = r
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=list(KEY_COLUMNS), lineterminator="\n")
    writer.writeheader()
    for pid in sorted(d.ids):
        c = d.ids[pid]
        writer.writerow(
            {
                "pair_id": pid,
                "stratum": c.stratum,
                "rank_bm25": c.rank,
                "rank_all_bm25": c.rank_all,
                "rank_dense": "" if c.dense_rank is None else c.dense_rank,
                "dense_kept_k20": "" if c.dense_rank is None else int(c.dense_rank <= K_FILTER),
                "directory": c.directory,
                "positive": c.positive,
                "assignment": assignment[pid],
                "in_overlap": int(pid in set(d.overlap)),
                "stratum_population": d.population[c.stratum],
                "stratum_sample": d.sample[c.stratum],
                "hunk_reproduced": int(hunk_ok.get(pid, False)),
            }
        )
    return buf.getvalue().encode("utf-8")


def build_sheets(
    d: Draw,
    records: Mapping[str, Mapping[str, Any]],
    readers: Sequence[str] = ("reader_1", "reader_2"),
) -> dict[str, bytes]:
    """The three sheets as bytes, keyed by file name.

    ``reader_overlap.csv`` holds the overlap alone; each reader's file holds the overlap plus that
    reader's own pairs, shuffled independently (so the two readers meet the shared pairs in
    different positions).
    """
    missing = sorted(set(d.ids) - set(records))
    if missing:
        raise ValueError(f"{len(missing)} pairs have no extracted record, first {missing[0]}")
    out: dict[str, bytes] = {}
    order = shuffled(d.overlap, d.seed, "overlap")
    out["reader_overlap.csv"] = sheet_csv([sheet_row(records[i], i, "") for i in order])
    for r in readers:
        ids = shuffled(list(d.overlap) + list(d.own[r]), d.seed, r)
        out[f"{r}.csv"] = sheet_csv([sheet_row(records[i], i, r) for i in ids])
    return out


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def group_by_directory(ids: Iterable[str], d: Draw) -> dict[str, list[str]]:
    """Sampled pair ids grouped by mined directory (extraction works one pull request at a time)."""
    out: dict[str, list[str]] = defaultdict(list)
    for i in sorted(ids):
        out[d.ids[i].directory].append(i)
    return dict(out)
