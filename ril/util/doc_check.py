"""Check that the written documents point at things that exist.

Every relative link and every backticked repository path in the tracked documents must resolve to a
file or directory of the tracked tree, and every ADR, deviation and open-question number cited must
exist. A path that only exists on one machine (untracked) counts as dangling: a reader of a fresh
clone cannot follow it. Paths under the directories that are rebuilt on the cluster and never
tracked are exempt (``REBUILT_PREFIXES``).

Implements the documentation hygiene rule of ``docs/README.md``.
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

CHECKED_GLOBS: tuple[str, ...] = (
    "README.md",
    "PROJECT_STATE.md",
    "RESULTS.md",
    "docs/*.md",
    "docs/status/*.md",
    "decisions/*.md",
    "specs/*.md",
)

# Directories rebuilt by jobs on the cluster and never tracked (see data/README.md).
REBUILT_PREFIXES: tuple[str, ...] = (
    "data/raw",
    "data/processed",
    "data/index",
    "data/checkpoints",
    "data/review",
    "data/src_cache",
    ".venv",
)

# File names that appear as examples from the analysed repositories or as generated artifacts, not
# as tracked files of this one.
EXAMPLE_NAMES: frozenset[str] = frozenset(
    {"setup.py", "x.py", "test_x.py", "compat.py", "meta.json"}
)

PATH_SUFFIXES: tuple[str, ...] = (
    ".py",
    ".md",
    ".yaml",
    ".yml",
    ".csv",
    ".json",
    ".sbatch",
    ".sh",
    ".toml",
    ".tex",
    ".txt",
    ".sha256",
)
TOP_DIRS: tuple[str, ...] = (
    "ril",
    "docs",
    "decisions",
    "specs",
    "scripts",
    "tests",
    "configs",
    "results",
    "data",
    "knowledge",
    "reports",
)

_LINK = re.compile(r"\]\(([^)\s]+)\)")
_TICK = re.compile(r"`([^`\n]+)`")
_ADR = re.compile(r"\bADR-(\d{3})\b")
_DEV = re.compile(r"\bDEV-(\d{3})\b")
_Q = re.compile(r"(?<![\w-])Q(\d{1,3})\b")
_Q_RANGE = re.compile(r"(?<![\w-])Q(\d{1,3})\s*[-\u2013]\s*Q(\d{1,3})\b")
_ADR_RANGE = re.compile(r"ADR-(\d{3})\s*(?:\.\.\.?|…|to|-)\s*(?:ADR-)?(\d{3})")
_PLACEHOLDER = re.compile(r"[<>*{}$|\\\[\]()=,;\"'~]|\.\.\.|…|\bNN\b|\bNNN\b|[0-9]NN")


@dataclass(frozen=True)
class Finding:
    """One dangling reference: the file, the line, what was cited and why it fails."""

    file: str
    line: int
    target: str
    reason: str

    def render(self) -> str:
        return f"{self.file}:{self.line}: {self.target} ({self.reason})"


def tracked_files(root: Path) -> set[str]:
    """Paths of the tracked tree, relative to ``root``; falls back to a walk outside git.

    Files not yet added but not ignored count, so the check can run before a commit.
    """
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "ls-files", "--cached", "--others", "--exclude-standard"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        names = {line for line in out.splitlines() if line}
        if names:
            return names
    except (OSError, subprocess.CalledProcessError):
        pass
    return {
        p.relative_to(root).as_posix()
        for p in root.rglob("*")
        if p.is_file() and ".git" not in p.relative_to(root).parts
    }


def with_directories(files: Iterable[str]) -> set[str]:
    """The file set plus every directory that contains a file."""
    known = set(files)
    for name in list(known):
        parent = Path(name).parent
        while parent.as_posix() != ".":
            known.add(parent.as_posix())
            parent = parent.parent
    return known


def checked_documents(files: Iterable[str]) -> list[str]:
    """The tracked documents covered by ``CHECKED_GLOBS``, sorted."""
    names = sorted(files)
    out = [n for n in names if any(Path(n).match(g) and _depth_ok(n, g) for g in CHECKED_GLOBS)]
    return out


def _depth_ok(name: str, pattern: str) -> bool:
    return name.count("/") == pattern.count("/")


def looks_like_repo_path(token: str) -> bool:
    """True for a backticked token that names a repository path and not code or a placeholder."""
    if " " in token or _PLACEHOLDER.search(token) or token.startswith(("http", "-", "/")):
        return False
    first = token.split("/", 1)[0]
    if "/" in token:
        return first in TOP_DIRS or "." in first
    return token.endswith(PATH_SUFFIXES) and not token.startswith(".")


def _exempt(path: str) -> bool:
    return any(path == p or path.startswith(p + "/") for p in REBUILT_PREFIXES)


def _normalise(path: str) -> str:
    parts: list[str] = []
    for piece in path.split("/"):
        if piece in ("", "."):
            continue
        if piece == "..":
            if parts:
                parts.pop()
            continue
        parts.append(piece)
    return "/".join(parts)


def _adr_numbers(files: Iterable[str]) -> set[int]:
    out: set[int] = set()
    for name in files:
        m = re.fullmatch(r"decisions/ADR-(\d{3})-.+\.md", name)
        if m:
            out.add(int(m.group(1)))
    return out


def deviation_numbers(text: str) -> set[int]:
    """Numbers of the deviations that have a heading in ``docs/DEVIATIONS.md``."""
    return {int(n) for n in re.findall(r"^## DEV-(\d{3}) ", text, flags=re.M)}


def highest_question(text: str) -> int:
    """Highest open-question number named in the state file."""
    nums = [int(n) for n in _Q.findall(text)]
    return max(nums) if nums else 0


def question_gaps(text: str) -> list[int]:
    """Numbers missing between 1 and the highest open-question number named in the state file.

    A range written ``Qa-Qb`` names every number between its ends. The check is on contiguity up to
    the highest number found, not on a fixed upper bound, so a new question needs no edit
    here.
    """
    named = {int(n) for n in _Q.findall(text)}
    for lo, hi in _Q_RANGE.findall(text):
        named.update(range(int(lo), int(hi) + 1))
    top = max(named, default=0)
    return [n for n in range(1, top + 1) if n not in named]


def check_document(
    name: str,
    text: str,
    known: set[str],
    adrs: set[int],
    devs: set[int],
    max_question: int,
) -> list[Finding]:
    """Dangling links, paths and numbered references of one document.

    A bare file name (no slash) resolves when any tracked file carries that name; a ``::symbol``
    suffix is dropped before the lookup.
    """
    findings: list[Finding] = []
    basenames = {Path(k).name for k in known}
    folder = Path(name).parent.as_posix()
    in_fence = False
    for no, line in enumerate(text.splitlines(), start=1):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        for target in _LINK.findall(line):
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            bare = target.split("#", 1)[0]
            path = _normalise(f"{folder}/{bare}" if folder != "." else bare)
            if path and path not in known and not _exempt(path):
                findings.append(Finding(name, no, target, "link does not resolve"))
        for token in _TICK.findall(line):
            if not looks_like_repo_path(token):
                continue
            token = token.split("::", 1)[0]
            path = _normalise(token)
            if "/" not in token and (token in basenames or token in EXAMPLE_NAMES):
                continue
            beside = _normalise(f"{folder}/{token}") if folder != "." else path
            if path in known or beside in known or _exempt(path):
                continue
            findings.append(Finding(name, no, token, "path not in the tracked tree"))
        scrubbed = _ADR_RANGE.sub(lambda m: f"ADR-{m.group(1)} ADR-{m.group(2)}", line)
        for n in _ADR.findall(scrubbed):
            if int(n) not in adrs and name != "decisions/_TEMPLATE.md":
                findings.append(Finding(name, no, f"ADR-{n}", "no such decision record"))
        for n in _DEV.findall(line):
            if int(n) not in devs:
                findings.append(Finding(name, no, f"DEV-{n}", "no such deviation"))
        for n in _Q.findall(line):
            if not 1 <= int(n) <= max_question:
                findings.append(Finding(name, no, f"Q{n}", "no such open question"))
    return findings


def check_tree(root: Path, files: set[str] | None = None) -> list[Finding]:
    """Run the check over every document of ``CHECKED_GLOBS`` in the tree at ``root``."""
    tracked = tracked_files(root) if files is None else files
    known = with_directories(tracked)
    adrs = _adr_numbers(tracked)
    dev_path = root / "docs/DEVIATIONS.md"
    devs = deviation_numbers(dev_path.read_text(encoding="utf-8")) if dev_path.exists() else set()
    state = root / "PROJECT_STATE.md"
    max_q = highest_question(state.read_text(encoding="utf-8")) if state.exists() else 0
    findings: list[Finding] = []
    if state.exists():
        gaps = question_gaps(state.read_text(encoding="utf-8"))
        findings.extend(
            Finding("PROJECT_STATE.md", 1, f"Q{n}", "open-question number skipped") for n in gaps
        )
    for name in checked_documents(tracked):
        text = (root / name).read_text(encoding="utf-8")
        findings.extend(check_document(name, text, known, adrs, devs, max_q))
    return findings
