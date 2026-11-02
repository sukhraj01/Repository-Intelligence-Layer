"""Entry ids of the experiment logs, and the checks that keep them unique and citable.

The experiment log is split by workstream so that three people never append to one file:
``docs/EXPERIMENTS.md`` (the lead: rules, index, own entries), ``docs/experiments/A.md``,
``docs/experiments/B.md`` and ``docs/experiments/C.md``. An entry id is the first cell of a registry row or the leading id(s) of a
``##`` heading. Ids must be unique across the four files, every citation of the form
a citation (the log file, then the id) must name the file that defines the id, and the index in
``docs/EXPERIMENTS.md`` must agree with the definitions.

Implements docs/REVIEW.md "Merging" (logs are append-only per workstream).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

LOG_FILES: tuple[str, ...] = (
    "docs/EXPERIMENTS.md",
    "docs/experiments/A.md",
    "docs/experiments/B.md",
    "docs/experiments/C.md",
)
INDEX_FILE = "docs/EXPERIMENTS.md"
# branch-name letter -> the one log that workstream may edit
OWNED_LOG: dict[str, str] = {"a": "docs/experiments/A.md", "c": "docs/experiments/C.md"}

_ID = r"(?:E-[A-Z0-9]+(?:-[A-Z0-9]+)*|A\d+[a-z]?(?:-[A-Z0-9]+)*|C\d+[a-z]?(?:-[A-Z0-9]+)*)"
_ID_RE = re.compile(rf"^{_ID}$")
_HEAD_LEAD = re.compile(
    rf"^##\s+(?P<ids>{_ID}(?:\s*\([^)]*\))?(?:(?:\s*,\s*|\s+and\s+){_ID}(?:\s*\([^)]*\))?)*)"
)
_HEAD_ID = re.compile(_ID)
_FILE = r"(?:docs/EXPERIMENTS\.md|docs/experiments/[ABC]\.md)"
_CITE = re.compile(
    rf"(?P<file>{_FILE})[`\s,:;(]*(?:(?:section|sections|entry|entries)\s+)?(?P<id>{_ID})(?![\w-])"
)


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    token: str
    message: str

    def render(self) -> str:
        return f"{self.path}:{self.line}: {self.token}: {self.message}"


def _cells(row: str) -> list[str]:
    return [c.strip() for c in row.strip().strip("|").split("|")]


def defined_ids(text: str) -> list[tuple[int, str]]:
    """``(line, id)`` of every registry row and heading definition in one log file."""
    out: list[tuple[int, str]] = []
    in_registry = False
    for no, line in enumerate(text.splitlines(), start=1):
        if line.startswith("## "):
            in_registry = line.strip() == "## Registry"
        if in_registry and line.startswith("|"):
            first = _cells(line)[0]
            base = re.sub(r"\s*\(.*$", "", first)
            if _ID_RE.match(base):
                out.append((no, base))
                out.extend((no, a) for a in re.findall(rf"\(was ({_ID})\)", first))
        m = _HEAD_LEAD.match(line)
        if m:
            out.extend((no, i) for i in _HEAD_ID.findall(re.sub(r"\([^)]*\)", "", m.group("ids"))))
    return out


def index_rows(text: str) -> list[tuple[int, str, str]]:
    """``(line, id, file)`` of the rows of the index table in the lead's log."""
    out: list[tuple[int, str, str]] = []
    in_index = False
    for no, line in enumerate(text.splitlines(), start=1):
        if line.startswith("## "):
            in_index = line.strip() == "## Index of entries"
        if in_index and line.startswith("|"):
            cells = _cells(line)
            if len(cells) >= 3 and _ID_RE.match(re.sub(r"\s*\(.*$", "", cells[0])):
                out.append((no, re.sub(r"\s*\(.*$", "", cells[0]), cells[2].strip("`")))
    return out


def check_registry(logs: Mapping[str, str], citing: Mapping[str, str]) -> list[Finding]:
    """Duplicate ids, index disagreements and citations that resolve to nothing.

    ``logs`` maps each log path to its text; ``citing`` maps any other document or source path to
    its text (the logs themselves are scanned for citations too).
    """
    findings: list[Finding] = []
    where: dict[str, str] = {}
    reported: set[str] = set()
    for path in LOG_FILES:
        if path not in logs:
            continue
        seen_here: set[str] = set()
        for no, ident in defined_ids(logs[path]):
            if ident in where and where[ident] != path:
                findings.append(
                    Finding(path, no, ident, f"entry id also defined in {where[ident]}")
                )
            elif (
                ident in seen_here
                and ident not in reported
                and not _table_and_heading(logs[path], ident)
            ):
                reported.add(ident)
                findings.append(Finding(path, no, ident, "entry id defined twice in this file"))
            where.setdefault(ident, path)
            seen_here.add(ident)
    if INDEX_FILE in logs:
        for no, ident, file in index_rows(logs[INDEX_FILE]):
            if ident not in where:
                findings.append(Finding(INDEX_FILE, no, ident, "index row for an undefined entry"))
            elif where[ident] != file:
                findings.append(
                    Finding(
                        INDEX_FILE, no, ident, f"index names {file}, entry is in {where[ident]}"
                    )
                )
    for path, text in [*logs.items(), *citing.items()]:
        for no, line in enumerate(text.splitlines(), start=1):
            for m in _CITE.finditer(line):
                ident, file = m.group("id"), m.group("file")
                if ident not in where:
                    findings.append(Finding(path, no, ident, "cited entry is defined in no log"))
                elif where[ident] != file:
                    findings.append(
                        Finding(path, no, ident, f"cited in {file}, entry is in {where[ident]}")
                    )
    return findings


def _table_and_heading(text: str, ident: str) -> bool:
    """True when the two definitions in one file are one registry row plus one heading."""
    rows = 0
    heads = 0
    in_registry = False
    for line in text.splitlines():
        if line.startswith("## "):
            in_registry = line.strip() == "## Registry"
        if in_registry and line.startswith("|"):
            first = re.sub(r"\s*\(.*$", "", _cells(line)[0])
            rows += first == ident
        m = _HEAD_LEAD.match(line)
        if m and ident in _HEAD_ID.findall(re.sub(r"\([^)]*\)", "", m.group("ids"))):
            heads += 1
    return rows <= 1 and heads <= 1


def owned_log(branch: str) -> str | None:
    """The one log a workstream branch (``a/...``, ``c/...``) may edit, or None."""
    head = branch.split("/", 1)[0]
    return OWNED_LOG.get(head) if "/" in branch else None
