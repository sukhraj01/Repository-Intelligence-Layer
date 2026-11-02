"""One merged pull request to one training instance (designs D61 to D64).

Implements ``docs/experiments/B.md`` E-MINE-PILOT. Steps: compare the pull request's base and head
(merge-base of the two, so the merge style does not matter), unpack the Python files of that base
commit, parse them with the project parser, map the old-side changes to units, and emit the
instance in the layout ``ril.training.pool_reader`` reads. A pull request that cannot be fetched or
parsed completely is *quarantined with its reason*, never dropped and never repaired.

Nothing retriever-dependent is computed here: the output holds the issue text, the corpus, the
positives and what a later filter would need (kind, test flag, hunk lines touched, unit size).

Kept compatible with Python 3.10 (the cluster's compute nodes).
"""

from __future__ import annotations

import re
import shutil
import tempfile
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from ril.data_mining.config import MiningConfig
from ril.data_mining.diff import (
    Comparison,
    PatchError,
    merge_pages,
    parse_comparison,
)
from ril.data_mining.github_api import ApiClient, ApiError, NotFound
from ril.data_mining.links import LinkedIssue, PullRequest, issue_edited_after
from ril.data_mining.mapping import FileMapping, UnitHit, map_change
from ril.data_mining.snapshot import SnapshotError, SnapshotProvider
from ril.parsing.code_unit import CodeUnit
from ril.parsing.repository_parser import ParsedRepository, parse_repository
from ril.parsing.unit_id import id_to_pool

COMPARE_PAGE = 100
COMPARE_MAX_PAGES = 3
"""The endpoint lists at most 300 files: three pages of 100."""

STATUS_MINED = "mined"
STATUS_NO_PYTHON = "no_python_change"
STATUS_NO_POSITIVE = "no_positive"
STATUS_QUARANTINED = "quarantined"


@dataclass(frozen=True)
class PositiveRow:
    """One positive with what a later filter would need (D63)."""

    unit_id: str
    pool_id: str
    path: str
    unit_kind: str
    name: str
    qualified_name: str
    is_test: bool
    removed_lines: int
    inserted_lines: int
    hunk_lines_touched: int
    unit_loc: int
    unit_lines: int
    in_corpus: bool
    whole_file_deleted: bool

    def to_dict(self) -> dict[str, Any]:
        """JSON form."""
        return dict(self.__dict__)


@dataclass
class MinedInstance:
    """A pull request in the layout of the pool: query, corpus, qrels, plus the side record."""

    repo: str
    pr: int
    dir_name: str
    query: str
    base_commit: str
    corpus: list[tuple[str, str]]
    qrels: list[str]
    meta: dict[str, Any]


@dataclass
class Outcome:
    """Result of mining one pull request."""

    key: str
    status: str
    reason: str = ""
    instance: MinedInstance | None = None
    counters: dict[str, int] = field(default_factory=dict)

    def row(self) -> dict[str, Any]:
        """The state-log row (no text)."""
        return {
            "key": self.key,
            "status": self.status,
            "reason": self.reason,
            "counters": dict(sorted(self.counters.items())),
        }


def dir_name(repo: str, pr: int) -> str:
    """Directory name in the pool's form: ``owner__name-<PR>`` (repository lower-cased)."""
    owner, _, name = repo.partition("/")
    return f"{owner}__{name}-{pr}"


# --------------------------------------------------------------------------- parse failures

_SYNTAX_CAUSES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("python2-print", re.compile(r"Missing parentheses in call to 'print'", re.I)),
    ("python2-exec", re.compile(r"Missing parentheses in call to 'exec'", re.I)),
    ("python2-except", re.compile(r"multiple exception types must be parenthesized", re.I)),
    ("python2-octal", re.compile(r"leading zeros in decimal integer literals", re.I)),
    ("python2-long-literal", re.compile(r"invalid decimal literal", re.I)),
    ("mixed-tabs-spaces", re.compile(r"inconsistent use of tabs and spaces", re.I)),
)


def classify_parse_failure(reason: str) -> str:
    """Language-version cause of an unparseable file (a heuristic on the error text).

    The parser records ``"<ErrorType>: <message>"``. Messages naming Python 2 constructs map to
    ``python2-*`` (``python2-long-literal`` also catches other malformed number literals, so it
    is an upper bound); mixed tabs and spaces, which Python 2 allowed, is its own label; other
    syntax errors stay ``syntax-other`` (this includes syntax newer than the interpreter running
    the parser, which the message text does not identify); non-syntax failures keep their error
    type. The split is a reading of message text, reported with its remainder.
    """
    kind, _, message = reason.partition(": ")
    if kind not in ("SyntaxError", "IndentationError", "TabError"):
        return kind or "unknown"
    for label, pattern in _SYNTAX_CAUSES:
        if pattern.search(message):
            return label
    return "syntax-other"


# --------------------------------------------------------------------------- compare


def fetch_comparison(client: ApiClient, pr: PullRequest) -> Comparison:
    """The compare response of ``base...head`` for one pull request, all pages."""
    owner, _, name = pr.repo.partition("/")
    path = f"/repos/{owner}/{name}/compare/{pr.base_oid}...{pr.head_oid}"
    pages: list[Mapping[str, Any]] = []
    for page in range(1, COMPARE_MAX_PAGES + 1):
        doc = client.get_json(path, {"per_page": COMPARE_PAGE, "page": page})
        pages.append(doc)
        if len(doc.get("files") or []) < COMPARE_PAGE:
            break
    return parse_comparison(merge_pages(pages))


# --------------------------------------------------------------------------- mining


def _quarantine(pr: PullRequest, reason: str, **counters: int) -> Outcome:
    return Outcome(pr.key, STATUS_QUARANTINED, reason, None, dict(counters))


def primary_issue(pr: PullRequest) -> LinkedIssue:
    """The issue whose text is the query: same repository first, then the lowest number."""
    return sorted(pr.issues, key=lambda i: (i.repo != pr.repo, i.number))[0]


def _positive_row(hit: UnitHit, in_corpus: bool) -> PositiveRow:
    u = hit.unit
    return PositiveRow(
        unit_id=u.id,
        pool_id=id_to_pool(u.id),
        path=u.file,
        unit_kind=u.unit_type,
        name=u.name,
        qualified_name=u.qualified_name,
        is_test=u.is_test,
        removed_lines=hit.removed_lines,
        inserted_lines=hit.inserted_lines,
        hunk_lines_touched=hit.hunk_lines_touched,
        unit_loc=u.loc,
        unit_lines=u.end_line - u.start_line + 1,
        in_corpus=in_corpus,
        whole_file_deleted=hit.whole_file_deleted,
    )


def build_corpus(
    units: Sequence[CodeUnit], kinds: Sequence[str]
) -> tuple[list[tuple[str, str]], dict[str, CodeUnit], int]:
    """``(corpus rows, pool id -> unit, collisions)``; a repeated pool id keeps the first unit."""
    rows: list[tuple[str, str]] = []
    first: dict[str, CodeUnit] = {}
    collisions = 0
    for u in units:
        if u.unit_type not in kinds:
            continue
        pid = id_to_pool(u.id)
        if pid in first:
            collisions += 1
            continue
        first[pid] = u
        rows.append((pid, f"{pid}\n{u.source}"))
    return rows, first, collisions


def _units_by_file(parsed: ParsedRepository) -> dict[str, list[CodeUnit]]:
    out: dict[str, list[CodeUnit]] = {}
    for u in parsed.units:
        out.setdefault(u.file, []).append(u)
    return out


def mine_pr(
    pr: PullRequest,
    *,
    client: ApiClient,
    snapshots: SnapshotProvider,
    config: MiningConfig,
) -> Outcome:
    """Mine one pull request that closes at least one issue; see the module docstring."""
    if not pr.issues:
        raise ValueError(f"{pr.key}: no linked issue; select before mining")
    if not pr.base_oid or not pr.head_oid:
        return _quarantine(pr, "missing_commit_id")
    try:
        comparison = fetch_comparison(client, pr)
    except NotFound:
        return _quarantine(pr, "compare_not_found")
    except (ApiError, PatchError, ValueError, KeyError) as exc:
        return _quarantine(pr, f"compare_failed:{type(exc).__name__}")
    py_files = comparison.python_files()
    counters: dict[str, int] = {
        "files_listed": comparison.files_listed,
        "py_files_changed": len(py_files),
    }
    if comparison.truncated:
        return _quarantine(pr, "diff_truncated", **counters)
    if any(f.patch_missing for f in py_files):
        return _quarantine(pr, "patch_missing", **counters)
    if not py_files:
        return Outcome(pr.key, STATUS_NO_PYTHON, "", None, counters)

    work = tempfile.mkdtemp(prefix="ril_snap_")
    try:
        try:
            snapshots.materialize(pr.repo, comparison.merge_base, work)
        except SnapshotError:
            return _quarantine(pr, "snapshot_unavailable", **counters)
        parsed = parse_repository(work, pr.repo)
    finally:
        shutil.rmtree(work, ignore_errors=True)

    unparseable = {path: reason for path, reason in parsed.unparseable}
    skipped = {path: reason for path, reason in parsed.skipped_files}
    by_file = _units_by_file(parsed)
    causes = Counter(classify_parse_failure(r) for r in unparseable.values())
    counters["corpus_unparsed_files"] = len(unparseable)
    counters["corpus_skipped_files"] = len(skipped)

    mappings: list[FileMapping] = []
    status_counts: Counter[str] = Counter()
    for change in py_files:
        status_counts[change.status] += 1
        if change.status == "added":
            mappings.append(map_change((), change))
            continue
        old = change.old_path
        if old in unparseable:
            cause = classify_parse_failure(unparseable[old])
            return _quarantine(pr, f"changed_file_unparseable:{cause}", **counters)
        if old in skipped:
            counters["changed_files_skipped"] = counters.get("changed_files_skipped", 0) + 1
            continue
        if old not in by_file:
            return _quarantine(pr, "old_file_missing_at_base", **counters)
        mappings.append(map_change(by_file[old], change))

    corpus, first, collisions = build_corpus(parsed.units, config.corpus_kinds)
    positives: list[PositiveRow] = []
    seen: set[str] = set()
    for fm in mappings:
        for hit in fm.hits:
            pid = id_to_pool(hit.unit.id)
            if pid in seen:
                continue
            seen.add(pid)
            in_corpus = hit.unit.unit_type in config.corpus_kinds and first.get(pid) is not None
            positives.append(_positive_row(hit, in_corpus))
    qrels = sorted({p.pool_id for p in positives if p.in_corpus})
    added_defs = sum(len(fm.added_defs) for fm in mappings)
    removed_defs = sum(len(fm.removed_defs) for fm in mappings)
    counters.update(
        corpus_units=len(corpus),
        pool_id_collisions=collisions,
        positives=len(qrels),
        positives_side_only=sum(1 for p in positives if not p.in_corpus),
        added_function_defs=added_defs,
        removed_function_defs=removed_defs,
    )
    if not qrels:
        return Outcome(pr.key, STATUS_NO_POSITIVE, "", None, counters)

    issue = primary_issue(pr)
    pairs = [
        {
            "issue_repo": i.repo,
            "issue": i.number,
            "primary": i is issue,
            "edited_after_pr_created": issue_edited_after(i, pr.created_at),
        }
        for i in pr.issues
    ]
    meta: dict[str, Any] = {
        "repo": pr.repo,
        "pr": pr.number,
        "base_commit": comparison.merge_base,
        "base_ref_oid": pr.base_oid,
        "head_commit": pr.head_oid,
        "pr_created_at": pr.created_at,
        "pairs": pairs,
        "closing_total": pr.closing_total,
        "regex_refs": list(pr.regex_refs),
        "regex_only_refs": sorted(
            set(pr.regex_refs) - {i.number for i in pr.issues if i.repo == pr.repo}
        ),
        "file_status": dict(sorted(status_counts.items())),
        "counters": dict(sorted(counters.items())),
        "parse_failure_causes": dict(sorted(causes.items())),
        "positives": [p.to_dict() for p in sorted(positives, key=lambda p: p.pool_id)],
    }
    inst = MinedInstance(
        repo=pr.repo,
        pr=pr.number,
        dir_name=dir_name(pr.repo, pr.number),
        query=issue.query_text(),
        base_commit=comparison.merge_base,
        corpus=corpus,
        qrels=qrels,
        meta=meta,
    )
    return Outcome(pr.key, STATUS_MINED, "", inst, counters)
