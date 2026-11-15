"""No-call replay of the floor arm's stored replies (E-RQ3-FLOOR addendum, D170). Descriptive only.

For each reply the edit blocks are matched against two texts, with no provider call: the issue text
the model was shown, and the base-commit file the block edits. A SEARCH text found in the base file
is consistent with recall of the repository, or with the issue quoting the code; this module does
not and cannot separate the two. Pure functions; the cluster wiring is in
``scripts/rq3_floor_replay.py``.
"""

from __future__ import annotations

import difflib
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any

from ril.agent.providers.patch_format import parse_edits

MIN_LINE_CHARS = 10
"""An edited line shorter than this (after stripping) is counted in the all-lines columns only."""

ReadFile = Callable[[str], str | None]


def issue_of_prompt(prompt: str) -> str:
    """The issue section of a prompt built by ``patch_format.build_prompt``."""
    start = prompt.index("## Issue\n\n") + len("## Issue\n\n")
    end = prompt.index("\n\n## Repository excerpts", start)
    return prompt[start:end]


def edited_lines(old: str, new: str) -> list[str]:
    """Stripped non-blank lines of ``new`` that are inserted or replaced relative to ``old``."""
    a, b = old.splitlines(), new.splitlines()
    out: list[str] = []
    for tag, _i1, _i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag in ("replace", "insert"):
            out += [x.strip() for x in b[j1:j2] if x.strip()]
    return out


def replay_reply(text: str, issue: str, read_file: ReadFile) -> dict[str, Any]:
    """Match the blocks of one reply against the issue and the base files; counts only."""
    edits, error = parse_edits(text, None)
    issue_ws = " ".join(issue.split())
    row: dict[str, Any] = {
        "parse_error": error or "",
        "n_blocks": len(edits),
        "blocks_search_in_issue": 0,
        "blocks_search_in_issue_ws": 0,
        "blocks_search_in_base": 0,
        "blocks_search_unique_in_base": 0,
        "blocks_file_unreadable": 0,
        "edited_lines": 0,
        "edited_lines_in_issue": 0,
        "edited_lines_long": 0,
        "edited_lines_long_in_issue": 0,
    }
    for e in edits:
        if e.old in issue:
            row["blocks_search_in_issue"] += 1
        if " ".join(e.old.split()) in issue_ws:
            row["blocks_search_in_issue_ws"] += 1
        try:
            base = read_file(e.path)
        except (UnicodeDecodeError, ValueError, OSError):
            base = None
        if base is None:
            row["blocks_file_unreadable"] += 1
        else:
            n = base.count(e.old)
            row["blocks_search_in_base"] += 1 if n >= 1 else 0
            row["blocks_search_unique_in_base"] += 1 if n == 1 else 0
        for line in edited_lines(e.old, e.new):
            long_ = len(line) >= MIN_LINE_CHARS
            hit = line in issue
            row["edited_lines"] += 1
            row["edited_lines_in_issue"] += int(hit)
            row["edited_lines_long"] += int(long_)
            row["edited_lines_long_in_issue"] += int(long_ and hit)
    n = row["n_blocks"]
    row["all_search_in_issue"] = bool(n) and row["blocks_search_in_issue"] == n
    row["all_search_in_issue_ws"] = bool(n) and row["blocks_search_in_issue_ws"] == n
    row["any_search_in_issue"] = row["blocks_search_in_issue"] > 0
    row["all_search_in_base"] = bool(n) and row["blocks_search_in_base"] == n
    row["any_search_in_base"] = row["blocks_search_in_base"] > 0
    return row


def classify(row: Mapping[str, Any]) -> str:
    """Resolved, or unresolved (applied but failed, apply failed, unusable)."""
    return "resolved" if row["resolved"] else "unresolved"


def summarise(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Counts by stage and by resolved/unresolved, and the same for each repository."""
    out: list[dict[str, Any]] = []
    groups: dict[tuple[str, str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for r in rows:
        for stage in (str(r["stage"]), "all"):
            for repo in (str(r["repo"]), "all"):
                groups[(stage, repo, classify(r))].append(r)
    for (stage, repo, cls), part in sorted(groups.items()):
        with_blocks = [r for r in part if r["n_blocks"]]
        el = sum(int(r["edited_lines"]) for r in with_blocks)
        out.append(
            {
                "stage": stage,
                "repo": repo,
                "class": cls,
                "replies": len(part),
                "with_blocks": len(with_blocks),
                "all_search_in_issue": sum(bool(r["all_search_in_issue"]) for r in with_blocks),
                "all_search_in_issue_ws": sum(
                    bool(r["all_search_in_issue_ws"]) for r in with_blocks
                ),
                "all_search_in_base": sum(bool(r["all_search_in_base"]) for r in with_blocks),
                "any_search_in_base": sum(bool(r["any_search_in_base"]) for r in with_blocks),
                "edited_lines": el,
                "edited_lines_in_issue": sum(int(r["edited_lines_in_issue"]) for r in with_blocks),
                "edited_lines_long": sum(int(r["edited_lines_long"]) for r in with_blocks),
                "edited_lines_long_in_issue": sum(
                    int(r["edited_lines_long_in_issue"]) for r in with_blocks
                ),
            }
        )
    return out


def resolved_by_repo(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Resolved fraction per repository and stage (exact reading, k = 1)."""
    acc: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0])
    for r in rows:
        for stage in (str(r["stage"]), "all"):
            for repo in (str(r["repo"]), "all"):
                a = acc[(stage, repo)]
                a[0] += int(bool(r["resolved"]))
                a[1] += 1
    return [
        {"stage": s, "repo": rp, "resolved": a[0], "instances": a[1], "fraction": a[0] / a[1]}
        for (s, rp), a in sorted(acc.items())
    ]
