"""Merged pull requests and the issues they close (design D61, D62).

Implements ``docs/experiments/B.md`` E-MINE-PILOT. The link between an issue and a pull request is
the platform's own ``closingIssuesReferences`` of the merged pull request (authoritative). A regex
over the pull request body ("fixes #n") is *not* used to select anything: :func:`regex_issue_refs`
only counts the extra recall it would have given. One issue may be closed by several pull requests
and one pull request may close several issues; the unit is the (issue, pull request) pair.

Kept compatible with Python 3.10 (the cluster's compute nodes).
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

PAGE_SIZE = 50
ISSUES_PER_PR = 10

PR_PAGE_QUERY = """
query($owner: String!, $name: String!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    nameWithOwner
    isArchived
    isFork
    pullRequests(states: MERGED, first: __PAGE__, after: $cursor,
                 orderBy: {field: CREATED_AT, direction: ASC}) {
      totalCount
      pageInfo { hasNextPage endCursor }
      nodes {
        number
        title
        body
        createdAt
        mergedAt
        baseRefOid
        headRefOid
        changedFiles
        additions
        deletions
        closingIssuesReferences(first: __ISSUES__) {
          totalCount
          nodes {
            number
            title
            body
            createdAt
            lastEditedAt
            repository { nameWithOwner }
          }
        }
      }
    }
  }
  rateLimit { cost remaining resetAt }
}
""".replace("__PAGE__", str(PAGE_SIZE)).replace("__ISSUES__", str(ISSUES_PER_PR))

_CLOSING_RE = re.compile(
    r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\b:?\s+"
    r"(?:(?P<repo>[\w.-]+/[\w.-]+))?#(?P<num>\d+)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class LinkedIssue:
    """An issue named by ``closingIssuesReferences``."""

    number: int
    repo: str
    title: str
    body: str
    created_at: str
    last_edited_at: str

    def query_text(self) -> str:
        """The training query: the issue title, a blank line, the issue body (D62)."""
        return f"{self.title}\n\n{self.body}" if self.body else self.title


@dataclass(frozen=True)
class PullRequest:
    """A merged pull request with its closing-issue links."""

    repo: str
    number: int
    title: str
    created_at: str
    merged_at: str
    base_oid: str
    head_oid: str
    changed_files: int
    issues: tuple[LinkedIssue, ...]
    closing_total: int
    """``totalCount`` of the closing references (may exceed ``len(issues)`` when cut)."""
    regex_refs: tuple[int, ...]
    """Issue numbers a body regex would name, sorted; counted for recall, never used."""

    @property
    def key(self) -> str:
        """Stable identifier ``owner/name#number``."""
        return f"{self.repo}#{self.number}"


def regex_issue_refs(body: str, repo: str) -> tuple[int, ...]:
    """Issue numbers in ``body`` that a "fixes #n" style regex names in the same repository."""
    out: set[int] = set()
    for m in _CLOSING_RE.finditer(body or ""):
        named = m.group("repo")
        if named is None or named.lower() == repo.lower():
            out.add(int(m.group("num")))
    return tuple(sorted(out))


def _issue(node: Mapping[str, Any]) -> LinkedIssue:
    repo = node.get("repository") or {}
    return LinkedIssue(
        number=int(node["number"]),
        repo=str(repo.get("nameWithOwner") or "").lower(),
        title=str(node.get("title") or ""),
        body=str(node.get("body") or ""),
        created_at=str(node.get("createdAt") or ""),
        last_edited_at=str(node.get("lastEditedAt") or ""),
    )


def parse_pr_page(
    data: Mapping[str, Any], repo: str
) -> tuple[list[PullRequest], str | None, Mapping[str, Any]]:
    """``(pull requests, next cursor, repository info)`` of one GraphQL page.

    Null issue nodes (a deleted or inaccessible issue) are dropped from ``issues`` and show up as
    ``closing_total`` larger than ``len(issues)``.
    """
    info = data.get("repository")
    if not info:
        raise ValueError(f"{repo}: no repository in the response")
    page = info["pullRequests"]
    prs: list[PullRequest] = []
    for node in page.get("nodes") or []:
        if node is None:
            continue
        refs = node.get("closingIssuesReferences") or {}
        issues = tuple(_issue(n) for n in (refs.get("nodes") or []) if n)
        prs.append(
            PullRequest(
                repo=repo.lower(),
                number=int(node["number"]),
                title=str(node.get("title") or ""),
                created_at=str(node.get("createdAt") or ""),
                merged_at=str(node.get("mergedAt") or ""),
                base_oid=str(node.get("baseRefOid") or ""),
                head_oid=str(node.get("headRefOid") or ""),
                changed_files=int(node.get("changedFiles") or 0),
                issues=tuple(sorted(issues, key=lambda i: (i.repo, i.number))),
                closing_total=int(refs.get("totalCount") or 0),
                regex_refs=regex_issue_refs(str(node.get("body") or ""), repo),
            )
        )
    cursor = None
    pi = page.get("pageInfo") or {}
    if pi.get("hasNextPage"):
        cursor = str(pi["endCursor"])
    return prs, cursor, info


def issue_edited_after(issue: LinkedIssue, pr_created_at: str) -> bool:
    """Whether the issue was edited after the pull request was created (D62).

    ISO-8601 UTC strings of equal form compare correctly as text. An issue never edited is
    ``False``; the historical text is not reconstructed in the pilot.
    """
    return bool(issue.last_edited_at) and issue.last_edited_at > pr_created_at


def multiplicity(prs: Sequence[PullRequest]) -> dict[str, int]:
    """Counts of the (issue, PR) pairs over ``prs``: pairs, many-issue PRs, many-PR issues."""
    pairs = [(i.repo, i.number, p.number) for p in prs for i in p.issues]
    per_issue: dict[tuple[str, int], int] = {}
    for repo, num, _ in pairs:
        per_issue[(repo, num)] = per_issue.get((repo, num), 0) + 1
    return {
        "pairs": len(pairs),
        "prs_with_issue": sum(1 for p in prs if p.issues),
        "prs_with_several_issues": sum(1 for p in prs if len(p.issues) > 1),
        "issues": len(per_issue),
        "issues_with_several_prs": sum(1 for n in per_issue.values() if n > 1),
    }
