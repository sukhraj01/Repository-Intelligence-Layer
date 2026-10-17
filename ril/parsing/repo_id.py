"""Repository identity: the ``repo_id`` form of a CodeUnit.

Implements ``specs/code_unit.md`` decision D5: ``repo_id`` is ``owner/name``, case-folded. The
snapshot (commit) is not part of the identity; it lives in the container that holds a repository's
units and graph. A repository that was renamed or transferred keeps its recorded ``repo_id`` and
gets an entry in an alias table (see ``ril/training/rename_resolution.py``), never a second form.

Why case-folded: GitHub treats owner and name case-insensitively, and the repository-level
disjointness test compares names, so two spellings of one repository must collapse to one string.
"""

from __future__ import annotations

import re

_URL_RE = re.compile(
    r"^(?:https?://)?(?:www\.)?github\.com/([^/\s]+)/([^/\s]+?)(?:\.git)?/?$", re.I
)
_PART_RE = re.compile(r"^[^/\s@#]+$")


def normalize_repo_id(name: str) -> str:
    """Return the canonical ``owner/name`` (case-folded) for a repository spelling.

    Accepts ``owner/name``, ``owner__name`` (CORE-Bench and SWE-bench style) and a github.com URL.
    Raises ``ValueError`` for anything else: a bare truncated folder name such as ``scikit`` has
    no owner and is refused rather than guessed, and a snapshot suffix (``owner/name@commit``) is
    refused because the commit does not belong in the identity.
    """
    text = name.strip()
    m = _URL_RE.match(text)
    if m:
        owner, repo = m.group(1), m.group(2)
    elif "/" in text and text.count("/") == 1:
        owner, repo = text.split("/")
    elif "__" in text and "/" not in text:
        owner, repo = text.split("__", 1)
    else:
        raise ValueError(f"cannot read owner/name from {name!r}")
    if repo.endswith(".git") and len(repo) > 4:
        repo = repo[:-4]
    if not _PART_RE.match(owner) or not _PART_RE.match(repo) or repo == ".git":
        raise ValueError(f"cannot read owner/name from {name!r}")
    return f"{owner}/{repo}".casefold()


def is_normalized_repo_id(name: str) -> bool:
    """True if ``name`` is already in the canonical ``owner/name`` form (``/`` form only)."""
    if "/" not in name:
        return False
    try:
        return normalize_repo_id(name) == name
    except ValueError:
        return False
