"""Scan the added lines of a branch for shortcuts a reviewer should not have to find by eye.

Implements docs/REVIEW.md "Flags and trace-to-source". The scan reads ``git diff`` between the
merge base of ``base`` and ``head`` and the blobs at ``head``; it never reads the working tree, so
the result does not depend on what is checked out. A BLOCKING finding makes the command exit
non-zero; a WARNING is printed and does not.

The rules are deliberately line-based and conservative (see docs/REVIEW.md "What the scan does not
catch"): a rule that cannot be stated precisely enough to avoid firing on ordinary code is narrowed,
not switched off for a path.
"""

from __future__ import annotations

import argparse
import ast
import bisect
import fnmatch
import os
import re
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

BLOCKING = "BLOCKING"
WARNING = "WARNING"

MAX_FILE_BYTES = 5 * 1024 * 1024
LEAD_BRANCH_PREFIX = "b/"
FROZEN_DIR = "configs/frozen/"
SOURCE_MAX_BYTES = 30 * 1024 * 1024
SOURCE_SUFFIXES = {".csv", ".tsv", ".json", ".jsonl", ".md", ".txt", ".yaml", ".yml", ".log"}
RESULT_PATH_RE = re.compile(r"results/[A-Za-z0-9_.*/-]*(?:\{[^{}]*\}[A-Za-z0-9_.*/-]*)*")
Claim = tuple[str, int, float, int, str, list[str]]
LEDGER_RE = re.compile(r"^(RESULTS\.md|results/ledger[^/]*\.md)$")
REGISTRY_FILE = "docs/EXPERIMENTS.md"
SHARED_PREFIXES = ("ril/util/", "ril/config/")
SHARED_FILES = {"ril/evaluation/metrics.py"}
TEXT_SUFFIXES = {
    ".py", ".md", ".yaml", ".yml", ".sh", ".sbatch", ".toml", ".txt", ".tex", ".cfg", ".ini",
}  # fmt: skip

# Patterns are written so that their own source text does not match them (a character class around
# one letter), because this module is scanned by its own rules.
SKIP_RE = re.compile(
    r"pytest\.mark\.(?:skip|skipif|xfail)\b|pytest\.(?:skip|xfail)\(|unittest\.skip|@skip\w*\b"
)
DIRECTIVE_RE = re.compile(
    r"#\s*(?P<kind>(?:ruff:\s*)?no[q]a|type:\s*ignore|pragma:\s*no\s*cover)"
    r"(?P<codes>(?:\s*:\s*[A-Z]+[0-9]+(?:\s*,\s*[A-Z]+[0-9]+)*)|(?:\[[^\]]*\]))?"
    r"(?P<rest>.*)$"
)
BARE_EXCEPT_RE = re.compile(r"^\s*except\s*:")
BROAD_EXCEPT_RE = re.compile(
    r"^\s*except\s+\(?\s*(?:Exception|BaseException)\b[^:]*:\s*(?P<tail>.*)$"
)
SUPPRESS_RE = re.compile(r"\bsuppress\(\s*(?:Exception|BaseException)\b")
ASSERT_RE = re.compile(
    r"^\s*(?:assert\b|self\.assert\w*\(|(?:np|numpy)\.testing\.assert\w*\(|with\s+pytest\.raises\()"
)
TOL_RE = re.compile(
    r"approx|tol\b|atol|rtol|\babs\s*=|\brel\s*=|delta|places|isclose|epsilon|eps\b"
)
NUMBER_RE = re.compile(r"(?<![\w.])\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")
TOLERANCE_ARG_RE = re.compile(
    r"\b(?P<name>abs|rel|atol|rtol|delta|tol|eps|epsilon|places)\s*=\s*"
    r"(?P<num>\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)"
)
TOLERANCE_ASSIGN_RE = re.compile(
    r"^\s*\w*(?:tol|eps|epsilon|delta)\w*\s*(?::[^=]+)?=\s*(?P<num>\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)\s*$",
    re.IGNORECASE,
)
HOME_RE = re.compile(
    r"(?<![\w.])(?:/Users/(?P<mac>[A-Za-z0-9._-]+)|/home\d*/(?P<lin>[A-Za-z0-9._-]+)"
    r"|[A-Za-z]:\\Users\\(?P<win>[A-Za-z0-9._-]+))"
)
HOME_PLACEHOLDERS = {"user", "username", "you", "me", "name", "yourname", "someone", "USER"}
TOKEN_RES: dict[str, re.Pattern[str]] = {
    "github token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
    "github fine-grained token": re.compile(r"\bgithub_pat_[A-Za-z0-9_]{22,}"),
    "cloud access key id": re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    "model-hub token": re.compile(r"\bhf_[A-Za-z0-9]{30,}\b"),
    "api secret key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"),
    "chat token": re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"),
    "google api key": re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    "private key block": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
}
WEIGHT_SUFFIXES = {
    ".pt", ".pth", ".ckpt", ".safetensors", ".gguf", ".onnx", ".h5", ".bin", ".pb", ".npz",
}  # fmt: skip
ARCHIVE_SUFFIXES = {
    ".zip", ".tar", ".tgz", ".gz", ".bz2", ".xz", ".7z", ".rar", ".whl", ".jar", ".zst",
}  # fmt: skip
SECRET_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".ppk", ".kdbx", ".jks"}
SECRET_NAMES = {
    "id_rsa",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
    ".netrc",
    ".pgpass",
    "credentials.json",
}
MARKER_RE = re.compile(
    r"\b(?:TO[D]O|FIX[M]E|HA[C]K|X{3})\b|(?i:\bwork-?around\b|\btemporar(?:y|ily)\b|\bfor now\b)"
)
DEF_RE = re.compile(r"^(?:async\s+def|def|class)\s+(?P<name>[A-Za-z]\w*)")
TUNING_RE = re.compile(r"(?:^|[^a-z])(?:tuning|tune|sweep|search|dev)(?:[^a-z]|$)")
VERIFIED_RE = re.compile(r"verified", re.IGNORECASE)
HUNK_RE = re.compile(r"^@@ -(?P<old>\d+)(?:,(?P<oldn>\d+))? \+(?P<new>\d+)(?:,(?P<newn>\d+))? @@")
LEDGER_NUMBER_RE = re.compile(r"(?<![\w.])[+\-\u2212]?(?P<num>\d{1,3}(?:,\d{3})+|\d+\.\d+)(?![\w])")
SOURCE_NUMBER_RE = re.compile(
    r"(?<![\w.])\d{1,3}(?:,\d{3})+(?![\w])|(?<![\w.])\d+(?:\.\d+)?(?:[eE][-+]?\d+)?"
)


@dataclass(frozen=True)
class Finding:
    severity: str
    rule: str
    path: str
    line: int
    message: str

    def render(self) -> str:
        return f"{self.severity} {self.path}:{self.line}: {self.rule}: {self.message}"


@dataclass
class Hunk:
    old_start: int
    new_start: int
    removed: list[tuple[int, str]] = field(default_factory=list)
    added: list[tuple[int, str]] = field(default_factory=list)


@dataclass
class FileDiff:
    path: str
    status: str = "M"  # A added, M modified, D deleted, R renamed
    binary: bool = False
    hunks: list[Hunk] = field(default_factory=list)

    @property
    def added(self) -> list[tuple[int, str]]:
        return [x for h in self.hunks for x in h.added]


class GitError(RuntimeError):
    pass


class Git:
    """Thin reader over a repository; every call names a revision, none touches the work tree."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def out(self, *args: str, check: bool = True) -> str:
        proc = subprocess.run(
            ["git", "-c", "core.quotepath=false", *args],
            cwd=self.root,
            capture_output=True,
            check=False,
        )
        if check and proc.returncode != 0:
            raise GitError(f"git {' '.join(args)}: {proc.stderr.decode(errors='replace').strip()}")
        return proc.stdout.decode("utf-8", errors="replace")

    def resolve(self, rev: str) -> str:
        return self.out("rev-parse", "--verify", f"{rev}^{{commit}}").strip()

    def merge_base(self, base: str, head: str) -> str:
        proc = self.out("merge-base", base, head, check=False).strip()
        return proc or self.resolve(base)

    def current_branch(self) -> str:
        return self.out("rev-parse", "--abbrev-ref", "HEAD", check=False).strip()

    def tree(self, rev: str, *prefixes: str) -> dict[str, int]:
        """Return ``{path: size}`` of the blobs under ``prefixes`` at ``rev``."""
        raw = self.out("ls-tree", "-r", "-l", "-z", "--full-tree", rev, "--", *prefixes)
        sizes: dict[str, int] = {}
        for entry in raw.split("\0"):
            if not entry or "\t" not in entry:
                continue
            meta, path = entry.split("\t", 1)
            parts = meta.split()
            if len(parts) == 4 and parts[1] == "blob" and parts[3].isdigit():
                sizes[path] = int(parts[3])
        return sizes

    def blobs(self, rev: str, paths: Sequence[str]) -> dict[str, bytes | None]:
        """Read many blobs with one process; a missing path maps to ``None``."""
        if not paths:
            return {}
        payload = "".join(f"{rev}:{p}\n" for p in paths).encode()
        proc = subprocess.run(
            ["git", "cat-file", "--batch"],
            cwd=self.root,
            input=payload,
            capture_output=True,
            check=False,
        )
        data, pos = proc.stdout, 0
        result: dict[str, bytes | None] = {}
        for path in paths:
            end = data.index(b"\n", pos)
            header = data[pos:end].decode(errors="replace").split()
            pos = end + 1
            if len(header) == 3 and header[1] == "blob":
                size = int(header[2])
                result[path] = data[pos : pos + size]
                pos += size + 1
            else:
                result[path] = None
        return result

    def text(self, rev: str, path: str) -> str | None:
        raw = self.blobs(rev, [path]).get(path)
        return None if raw is None else raw.decode("utf-8", errors="replace")


def parse_diff(text: str) -> list[FileDiff]:
    """Parse ``git diff -U0`` output into per-file added and removed lines with line numbers."""
    files: list[FileDiff] = []
    cur: FileDiff | None = None
    hunk: Hunk | None = None
    old_no = new_no = 0
    minus_path = ""
    for line in text.split("\n"):
        if line.startswith("diff --git "):
            body = line[len("diff --git ") :]
            idx = body.rfind(" b/")
            cur = FileDiff(path=body[idx + 3 :] if idx >= 0 else body)
            files.append(cur)
            hunk = None
            minus_path = ""
            continue
        if cur is None:
            continue
        if hunk is None:
            if line.startswith("new file mode"):
                cur.status = "A"
            elif line.startswith("deleted file mode"):
                cur.status = "D"
            elif line.startswith("rename to "):
                cur.status = "R"
                cur.path = line[len("rename to ") :]
            elif line.startswith("Binary files") or line.startswith("GIT binary patch"):
                cur.binary = True
            elif line.startswith("--- "):
                minus_path = line[4:].split("\t")[0]
            elif line.startswith("+++ "):
                target = line[4:].split("\t")[0]
                if target.startswith("b/"):
                    cur.path = target[2:]
                elif target == "/dev/null" and minus_path.startswith("a/"):
                    cur.path = minus_path[2:]
                continue
        m = HUNK_RE.match(line)
        if m:
            old_no, new_no = int(m.group("old")), int(m.group("new"))
            hunk = Hunk(old_start=old_no, new_start=new_no)
            cur.hunks.append(hunk)
            continue
        if hunk is None:
            continue
        if line.startswith("+"):
            hunk.added.append((new_no, line[1:]))
            new_no += 1
        elif line.startswith("-"):
            hunk.removed.append((old_no, line[1:]))
            old_no += 1
    return files


def is_test_path(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    return path.endswith(".py") and (
        path.startswith("tests/") or name.startswith("test_") or name == "conftest.py"
    )


def is_shared_path(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    return path.endswith(".py") and (
        path.startswith(SHARED_PREFIXES)
        or path in SHARED_FILES
        or (path.startswith("ril/") and name.startswith("stat"))
    )


def _has_reason(rest: str) -> bool:
    cleaned = re.sub(r"^[\s\-\u2013\u2014:#;,.]+", "", rest)
    return len(re.findall(r"[A-Za-z]", cleaned)) >= 4


@dataclass
class Scan:
    git: Git
    base: str
    head: str
    branch: str
    root_rev: str
    files: list[FileDiff]
    numbers: bool = True
    findings: list[Finding] = field(default_factory=list)
    _tests_tokens: set[str] | None = None

    def add(self, severity: str, rule: str, path: str, line: int, message: str) -> None:
        self.findings.append(Finding(severity, rule, path, line, message))

    # -- helpers ---------------------------------------------------------------------------------

    def test_identifiers(self) -> set[str]:
        if self._tests_tokens is None:
            paths = [p for p in self.git.tree(self.head, "tests") if p.endswith(".py")]
            tokens: set[str] = set()
            for raw in self.git.blobs(self.head, paths).values():
                if raw:
                    tokens.update(
                        re.findall(r"[A-Za-z_]\w*", raw.decode("utf-8", errors="replace"))
                    )
            self._tests_tokens = tokens
        return self._tests_tokens

    # -- rules over added lines ------------------------------------------------------------------

    def scan_added_lines(self) -> None:
        for fd in self.files:
            if fd.binary or fd.status == "D":
                continue
            py = fd.path.endswith(".py")
            added = dict(fd.added)
            scan_markers = (
                Path(fd.path).suffix in TEXT_SUFFIXES or fd.path.endswith("Makefile")
            ) and not (fd.path.startswith("results/") or fd.path == "RESULTS.md")
            for no, text in fd.added:
                if is_test_path(fd.path) and SKIP_RE.search(text):
                    self.add(
                        BLOCKING, "test-skip", fd.path, no, f"skip or xfail added: {text.strip()}"
                    )
                if py:
                    self._directive(fd.path, no, text)
                    self._broad_except(fd.path, no, text, added)
                self._secrets(fd.path, no, text)
                self._home_path(fd.path, no, text)
                if scan_markers and MARKER_RE.search(text):
                    self.add(WARNING, "unfinished-marker", fd.path, no, text.strip()[:100])

    def _directive(self, path: str, no: int, text: str) -> None:
        m = DIRECTIVE_RE.search(text)
        if m and not _has_reason(m.group("rest")):
            kind = " ".join(m.group("kind").split())
            self.add(
                BLOCKING,
                "suppression-without-reason",
                path,
                no,
                f"'{kind}' with no one-line reason after it",
            )

    def _broad_except(self, path: str, no: int, text: str, added: dict[int, str]) -> None:
        if BARE_EXCEPT_RE.match(text):
            self.add(BLOCKING, "bare-except", path, no, "bare except")
            return
        m = BROAD_EXCEPT_RE.match(text)
        if m:
            tail = m.group("tail").strip()
            follower = added.get(no + 1, "").strip()
            if tail in {"pass", "..."} or (not tail and follower in {"pass", "..."}):
                self.add(
                    BLOCKING, "swallowed-exception", path, no, "broad except that does nothing"
                )
        if SUPPRESS_RE.search(text):
            self.add(BLOCKING, "swallowed-exception", path, no, "suppress() of a broad exception")

    def _secrets(self, path: str, no: int, text: str) -> None:
        for label, pattern in TOKEN_RES.items():
            if pattern.search(text):
                self.add(BLOCKING, "secret", path, no, f"text shaped like a {label}")

    def _home_path(self, path: str, no: int, text: str) -> None:
        for m in HOME_RE.finditer(text):
            name = m.group("mac") or m.group("lin") or m.group("win") or ""
            if name in HOME_PLACEHOLDERS:
                continue
            self.add(BLOCKING, "home-path", path, no, f"absolute home-directory path: {m.group(0)}")
            return

    # -- file-level rules ------------------------------------------------------------------------

    def scan_files(self) -> None:
        touched = [fd for fd in self.files if fd.status != "D"]
        sizes = self._sizes([fd.path for fd in touched])
        for fd in self.files:
            if fd.path.startswith(FROZEN_DIR) and not self.branch.startswith(LEAD_BRANCH_PREFIX):
                self.add(
                    BLOCKING,
                    "frozen-config",
                    fd.path,
                    1,
                    f"configs/frozen/ changed on branch '{self.branch or '?'}' "
                    f"(only '{LEAD_BRANCH_PREFIX}' branches may)",
                )
            if (
                fd.status == "D"
                and fd.path.startswith(("results/", "tests/"))
                and not fd.path.endswith("/.gitkeep")
            ):
                self.add(WARNING, "deleted-file", fd.path, 1, "file deleted")
        for fd in touched:
            size = sizes.get(fd.path, 0)
            if size > MAX_FILE_BYTES:
                self.add(BLOCKING, "large-file", fd.path, 1, f"{size / 2**20:.1f} MB (limit 5 MB)")
            self._forbidden_name(fd.path)

    def _sizes(self, paths: list[str]) -> dict[str, int]:
        if not paths:
            return {}
        payload = "".join(f"{self.head}:{p}\n" for p in paths).encode()
        proc = subprocess.run(
            ["git", "cat-file", "--batch-check"],
            cwd=self.git.root,
            input=payload,
            capture_output=True,
            check=False,
        )
        sizes: dict[str, int] = {}
        for path, line in zip(paths, proc.stdout.decode().split("\n"), strict=False):
            parts = line.split()
            if len(parts) == 3 and parts[2].isdigit():
                sizes[path] = int(parts[2])
        return sizes

    def _forbidden_name(self, path: str) -> None:
        name = path.rsplit("/", 1)[-1]
        suffix = Path(name).suffix.lower()
        if suffix in WEIGHT_SUFFIXES:
            self.add(BLOCKING, "forbidden-file", path, 1, "model weights or binary array")
        elif suffix in ARCHIVE_SUFFIXES or name.endswith((".tar.gz", ".tar.bz2")):
            self.add(BLOCKING, "forbidden-file", path, 1, "archive")
        elif (name == ".env" or name.startswith(".env.")) and not name.endswith(
            (".example", ".sample", ".template")
        ):
            self.add(BLOCKING, "forbidden-file", path, 1, "environment file")
        elif suffix in SECRET_SUFFIXES or name in SECRET_NAMES or name.startswith("id_ed25519"):
            self.add(BLOCKING, "forbidden-file", path, 1, "key or credential file")

    # -- test weakening --------------------------------------------------------------------------

    def scan_test_weakening(self) -> None:
        for fd in self.files:
            if fd.status not in {"M", "R"} or not is_test_path(fd.path):
                continue
            removed = [(n, t) for h in fd.hunks for n, t in h.removed if ASSERT_RE.match(t)]
            added = [(n, t) for h in fd.hunks for n, t in h.added if ASSERT_RE.match(t)]
            if len(removed) > len(added):
                first = next(
                    h.new_start for h in fd.hunks if any(ASSERT_RE.match(t) for _, t in h.removed)
                )
                self.add(
                    BLOCKING,
                    "assert-removed",
                    fd.path,
                    first,
                    f"{len(removed)} assertion line(s) removed, {len(added)} added: "
                    f"{removed[0][1].strip()[:80]}",
                )
            for h in fd.hunks:
                self._paired_numbers(fd.path, h)

    @staticmethod
    def _checked(text: str) -> bool:
        return bool(ASSERT_RE.match(text) or (TOL_RE.search(text) and "=" in text))

    def _paired_numbers(self, path: str, h: Hunk) -> None:
        old = [t for _, t in h.removed if self._checked(t)]
        new = [(n, t) for n, t in h.added if self._checked(t)]
        if not old or len(old) != len(new):
            return
        for before, (no, after) in zip(old, new, strict=True):
            tol_a, rest_a = _split_numbers(before)
            tol_b, rest_b = _split_numbers(after)
            detail = f"{before.strip()} -> {after.strip()}"
            if len(tol_a) == len(tol_b) and any(
                (y < x) if inverse else (y > x)
                for (x, inverse), (y, _) in zip(tol_a, tol_b, strict=True)
            ):
                self.add(BLOCKING, "tolerance-widened", path, no, detail)
            elif rest_a != rest_b and (ASSERT_RE.match(before) or ASSERT_RE.match(after)):
                self.add(BLOCKING, "expected-number-changed", path, no, detail)

    # -- configs ---------------------------------------------------------------------------------

    def scan_configs(self) -> None:
        paths = [
            fd.path
            for fd in self.files
            if fd.status != "D"
            and fd.path.startswith("configs/")
            and fd.path.endswith((".yaml", ".yml"))
        ]
        texts = self.git.blobs(self.head, paths)
        status = {fd.path: fd.status for fd in self.files}
        for path in paths:
            raw = texts.get(path)
            if raw is None:
                continue
            text = raw.decode("utf-8", errors="replace")
            if status[path] == "A":
                self._config_markers(path, text)
            if path.startswith("configs/experiments/"):
                self._verified_in_tuning(path, text)

    def _config_markers(self, path: str, text: str) -> None:
        has_seed = re.search(r"^\s*(?:[\w.]*seed[\w]*)\s*:", text, re.MULTILINE) is not None
        has_marker = re.search(
            r"config_hash|^\s*hash\s*:|provisional\s*:|frozen\s*:", text, re.MULTILINE
        ) is not None or path.startswith(FROZEN_DIR)
        if not has_seed:
            self.add(WARNING, "config-no-seed", path, 1, "new config has no seed field")
        if not has_marker:
            self.add(
                WARNING,
                "config-no-marker",
                path,
                1,
                "new config has no hash field, 'provisional:' marker or frozen marker",
            )

    def _verified_in_tuning(self, path: str, text: str) -> None:
        purpose = ""
        try:
            doc = yaml.safe_load(text)
        except yaml.YAMLError:
            doc = None
        if isinstance(doc, dict) and isinstance(doc.get("purpose"), str):
            purpose = doc["purpose"]
        label = f"{path.rsplit('/', 1)[-1].lower()} {purpose.lower()}"
        if not TUNING_RE.search(label):
            return
        hits = _verified_uses(doc) if doc is not None else [0] * len(VERIFIED_RE.findall(text))
        if hits:
            line = next(
                (i for i, ln in enumerate(text.split("\n"), 1) if VERIFIED_RE.search(ln)), 1
            )
            self.add(
                BLOCKING,
                "verified-in-tuning-config",
                path,
                line,
                "the Verified split is named in a config whose name or purpose says tuning, "
                "sweep, search or dev (outside an entry with role: test)",
            )

    # -- ril/ ------------------------------------------------------------------------------------

    def scan_untested(self) -> None:
        for fd in self.files:
            if (
                fd.binary
                or fd.status == "D"
                or not fd.path.startswith("ril/")
                or not fd.path.endswith(".py")
            ):
                continue
            for no, text in fd.added:
                m = DEF_RE.match(text)
                if not m or m.group("name").startswith("_"):
                    continue
                if m.group("name") not in self.test_identifiers():
                    self.add(
                        WARNING,
                        "untested-definition",
                        fd.path,
                        no,
                        f"'{m.group('name')}' added with no test referencing it",
                    )

    def scan_shared_defaults(self) -> None:
        for fd in self.files:
            if fd.status != "M" or not is_shared_path(fd.path):
                continue
            old = self.git.text(self.base, fd.path)
            new = self.git.text(self.head, fd.path)
            if old is None or new is None:
                continue
            for name, line, before, after in changed_defaults(old, new):
                self.add(
                    WARNING,
                    "changed-default",
                    fd.path,
                    line,
                    f"default of '{name}' changed from {before} to {after} in a shared module",
                )

    def scan_registry(self) -> None:
        fd = next((f for f in self.files if f.path == REGISTRY_FILE and f.status != "D"), None)
        if fd is None:
            return
        text = self.git.text(self.head, REGISTRY_FILE)
        if text is None:
            return
        lines = text.split("\n")
        for no, row in fd.added:
            cells = _cells(row)
            if len(cells) != 7 or not cells[-1].lower().startswith("done"):
                continue
            m = re.match(r"[A-Z][A-Z0-9-]*", cells[0].strip())
            if not m:
                continue
            ident = m.group(0)
            if "results/" in row or _section_has_results(lines, ident):
                continue
            self.add(
                WARNING,
                "done-without-output",
                REGISTRY_FILE,
                no,
                f"{ident} is marked done but neither the row nor its section names a result path",
            )

    # -- trace to source -------------------------------------------------------------------------

    def scan_numbers(self) -> None:
        tree = self.git.tree(self.head, "results")
        cache: dict[str, _Index] = {}
        for path, no, value, precision, shown, sources in self._claims():
            linked = _expand_sources(sources, tree)
            if not linked:
                self.add(
                    BLOCKING,
                    "unsourced-number",
                    path,
                    no,
                    f"{shown}: no existing file under results/ is named by the row or its section",
                )
                continue
            fresh = [p for p in linked if p not in cache]
            for p, raw in self.git.blobs(self.head, fresh).items():
                cache[p] = _Index.of(raw)
            if not any(cache[p].supports(value, precision) for p in linked):
                self.add(
                    BLOCKING,
                    "unsourced-number",
                    path,
                    no,
                    f"{shown} is in none of the {len(linked)} file(s) the row or section names",
                )

    def _claims(self) -> list[Claim]:
        claims: list[Claim] = []
        for fd in self.files:
            if fd.binary or fd.status == "D":
                continue
            if LEDGER_RE.match(fd.path):
                claims.extend(self._ledger_claims(fd))
            elif fd.path == REGISTRY_FILE:
                claims.extend(self._result_line_claims(fd))
        return claims

    def _ledger_claims(self, fd: FileDiff) -> list[Claim]:
        text = self.git.text(self.head, fd.path)
        if text is None:
            return []
        lines = text.split("\n")
        doc = self.git.text(self.head, REGISTRY_FILE) or ""
        ledger_header = next(
            (_cells(ln) for ln in lines if ln.startswith("|") and "headline" in ln.lower()), None
        )
        out: list[Claim] = []
        for no, row in fd.added:
            if not row.startswith("|") or re.match(r"^\|[\s:|-]+$", row):
                continue
            cells = _cells(row)
            header = _header_of(lines, no)
            if header is None or not any("headline" in h.lower() for h in header):
                # rows appended below another table still belong to the ledger table
                header = ledger_header if len(cells) == len(ledger_header or []) else None
            if header is None:
                continue
            width = len(header)
            col = next((i for i, h in enumerate(header) if "headline" in h.lower()), None)
            if col is None or len(cells) < width or "headline" in cells[col - width].lower():
                continue
            sources = RESULT_PATH_RE.findall(row)
            if not sources:
                # a row that cites a registry section is read against the paths that section names
                m = re.search(r"docs/EXPERIMENTS\.md\s+([A-Z][A-Za-z0-9-]*)", row)
                if m:
                    sources = _section_paths(doc.split("\n"), m.group(1))
            out.extend((fd.path, no, *c, sources) for c in _numbers_in(cells[col - width]))
        return out

    def _result_line_claims(self, fd: FileDiff) -> list[Claim]:
        text = self.git.text(self.head, REGISTRY_FILE)
        if text is None:
            return []
        lines = text.split("\n")
        out: list[Claim] = []
        for no, line in fd.added:
            if line.startswith("**Result"):
                sources = _section_paths(lines, None, at=no)
                out.extend((fd.path, no, *c, sources) for c in _numbers_in(line))
        return out


class _Index:
    """Sorted numbers of one source file, plain and (for fractions) scaled to percent."""

    def __init__(self, plain: list[float], pct: list[float]) -> None:
        self.plain, self.pct = plain, pct

    @classmethod
    def of(cls, raw: bytes | None) -> _Index:
        values: list[float] = []
        if raw is not None and len(raw) <= SOURCE_MAX_BYTES:
            for tok in SOURCE_NUMBER_RE.findall(raw.decode("utf-8", errors="replace")):
                try:
                    values.append(abs(float(tok.replace(",", ""))))
                except ValueError:
                    continue
        plain = sorted(values)
        return cls(plain, sorted(v * 100 for v in plain if v <= 1.0))

    def supports(self, value: float, precision: int) -> bool:
        """Whether a number rounds to ``value`` as printed, directly or as a fraction."""
        half = 0.5 * 10**-precision + 1e-9
        for series in (self.plain, self.pct):
            i = bisect.bisect_left(series, value - half)
            if i < len(series) and series[i] - value <= half:
                return True
        return False


def _expand_sources(tokens: list[str], tree: dict[str, int]) -> list[str]:
    """Existing files under results/ that the cited paths, globs and directories denote."""
    found: list[str] = []
    for token in tokens:
        for pattern in _braces(token.rstrip(".,;:)")):
            for path in tree:
                if Path(path).suffix.lower() not in SOURCE_SUFFIXES:
                    continue
                if fnmatch.fnmatchcase(path, pattern) or path.startswith(pattern.rstrip("/") + "/"):
                    found.append(path)
    return sorted(set(found))


def _braces(pattern: str) -> list[str]:
    m = re.search(r"\{([^{}]*)\}", pattern)
    if not m:
        return [pattern]
    return [
        out
        for alt in m.group(1).split(",")
        for out in _braces(pattern[: m.start()] + alt + pattern[m.end() :])
    ]


def _section_paths(lines: list[str], ident: str | None, at: int | None = None) -> list[str]:
    """``results/`` paths in the registry section of ``ident`` or holding 1-based line ``at``."""
    if at is None and ident is None:
        return []
    if at is not None:
        start = next((i for i in range(at - 1, -1, -1) if lines[i].startswith("## ")), None)
    else:
        start = next(
            (
                i
                for i, ln in enumerate(lines)
                if ln.startswith("## ") and ident is not None and ident in ln
            ),
            None,
        )
    if start is None:
        return []
    paths: list[str] = []
    for ln in lines[start + 1 :]:
        if ln.startswith("## "):
            break
        paths.extend(RESULT_PATH_RE.findall(ln))
    return paths


def _verified_uses(node: Any) -> list[str]:
    """Return the strings naming Verified that are not inside a mapping with ``role: test``."""
    if isinstance(node, dict):
        if node.get("role") == "test":
            return []
        found: list[str] = []
        for key, value in node.items():
            if isinstance(key, str) and VERIFIED_RE.search(key):
                found.append(key)
            found.extend(_verified_uses(value))
        return found
    if isinstance(node, list):
        return [u for item in node for u in _verified_uses(item)]
    if isinstance(node, str) and VERIFIED_RE.search(node):
        return [node]
    return []


def changed_defaults(old_src: str, new_src: str) -> list[tuple[str, int, str, str]]:
    """Return ``(parameter, line in new, old default, new default)`` for each edited default."""

    def collect(src: str) -> dict[str, tuple[int, str]]:
        try:
            tree = ast.parse(src)
        except SyntaxError:
            return {}
        found: dict[str, tuple[int, str]] = {}

        def visit(node: ast.AST, prefix: str) -> None:
            for child in ast.iter_child_nodes(node):
                if isinstance(child, ast.ClassDef):
                    visit(child, f"{prefix}{child.name}.")
                elif isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
                    a = child.args
                    pos = [*a.posonlyargs, *a.args]
                    for arg, default in zip(
                        pos[len(pos) - len(a.defaults) :], a.defaults, strict=True
                    ):
                        found[f"{prefix}{child.name}({arg.arg})"] = (
                            child.lineno,
                            ast.unparse(default),
                        )
                    for arg, kw in zip(a.kwonlyargs, a.kw_defaults, strict=True):
                        if kw is not None:
                            found[f"{prefix}{child.name}({arg.arg})"] = (
                                child.lineno,
                                ast.unparse(kw),
                            )
                    visit(child, f"{prefix}{child.name}.")

        visit(tree, "")
        return found

    before, after = collect(old_src), collect(new_src)
    return [
        (name, after[name][0], before[name][1], after[name][1])
        for name in sorted(before.keys() & after.keys())
        if before[name][1] != after[name][1]
    ]


def _split_numbers(line: str) -> tuple[list[tuple[float, bool]], list[float]]:
    """Split a line's numbers into tolerances (flagged inverse for ``places``) and the rest."""
    tolerances: list[tuple[float, bool]] = []
    spans: list[tuple[int, int]] = []
    for m in TOLERANCE_ARG_RE.finditer(line):
        tolerances.append((float(m.group("num")), m.group("name") == "places"))
        spans.append(m.span("num"))
    assigned = TOLERANCE_ASSIGN_RE.match(line)
    if assigned:
        tolerances.append((float(assigned.group("num")), False))
        spans.append(assigned.span("num"))
    rest = [
        float(m.group(0))
        for m in NUMBER_RE.finditer(line)
        if not any(lo <= m.start() < hi for lo, hi in spans)
    ]
    return tolerances, rest


def _cells(row: str) -> list[str]:
    inner = row.strip()
    if inner.startswith("|"):
        inner = inner[1:]
    if inner.endswith("|"):
        inner = inner[:-1]
    return [c.strip() for c in re.split(r"(?<!\\)\|", inner)]


def _header_of(lines: list[str], no: int) -> list[str] | None:
    """Header cells of the table that holds 1-based line ``no``."""
    i = no - 2
    while i >= 1 and lines[i].startswith("|"):
        if re.match(r"^\|[\s:|-]+$", lines[i]):
            return _cells(lines[i - 1])
        i -= 1
    return None


def _section_has_results(lines: list[str], ident: str) -> bool:
    start = next(
        (
            i
            for i, ln in enumerate(lines)
            if ln.startswith("## ") and ident is not None and ident in ln
        ),
        None,
    )
    if start is None:
        return False
    for ln in lines[start + 1 :]:
        if ln.startswith("## "):
            break
        if "results/" in ln:
            return True
    return False


def _numbers_in(text: str) -> list[tuple[float, int, str]]:
    """Headline numbers of a cell or line: comma-grouped integers and numbers with decimals."""
    found: list[tuple[float, int, str]] = []
    stripped = re.sub(r"`[^`]*`", " ", text)
    for m in LEDGER_NUMBER_RE.finditer(stripped):
        raw = m.group("num")
        precision = len(raw.split(".")[1]) if "." in raw else 0
        found.append((abs(float(raw.replace(",", ""))), precision, raw))
    return found


def scan(
    git: Git, base: str, head: str, branch: str | None = None, numbers: bool = True
) -> tuple[list[Finding], str, str]:
    """Run every rule; returns ``(findings, merge_base_sha, head_sha)``."""
    head_sha = git.resolve(head)
    merge_base = git.merge_base(base, head)
    diff = git.out(
        "diff", "-U0", "--no-color", "--no-ext-diff", "--find-renames", merge_base, head_sha
    )
    s = Scan(
        git=git,
        base=merge_base,
        head=head_sha,
        branch=branch if branch is not None else branch_name(git),
        root_rev=merge_base,
        files=parse_diff(diff),
        numbers=numbers,
    )
    s.scan_added_lines()
    s.scan_files()
    s.scan_test_weakening()
    s.scan_configs()
    s.scan_untested()
    s.scan_shared_defaults()
    s.scan_registry()
    if numbers:
        s.scan_numbers()
    ordered = sorted(
        set(s.findings), key=lambda f: (f.severity != BLOCKING, f.path, f.line, f.rule)
    )
    return ordered, merge_base, head_sha


def branch_name(git: Git) -> str:
    for var in ("GITHUB_HEAD_REF", "GITHUB_REF_NAME"):
        value = os.environ.get(var, "")
        if value:
            return value
    name = git.current_branch()
    return "" if name == "HEAD" else name


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Flag shortcuts in the added lines of a branch.")
    ap.add_argument("--base", default="main", help="base revision (default: main)")
    ap.add_argument("--head", default="HEAD", help="head revision (default: HEAD)")
    ap.add_argument("--branch", default=None, help="branch name used for ownership rules")
    ap.add_argument("--root", default=".", help="repository directory (default: current)")
    ap.add_argument(
        "--numbers",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="trace ledger and result-line numbers to files under results/ (default: on)",
    )
    args = ap.parse_args(argv)
    git = Git(Path(args.root).resolve())
    try:
        findings, merge_base, head_sha = scan(git, args.base, args.head, args.branch, args.numbers)
    except GitError as exc:
        sys.stderr.write(f"review_flags: {exc}\n")
        return 2
    out = sys.stdout
    for f in findings:
        out.write(f.render() + "\n")
    blocking = sum(f.severity == BLOCKING for f in findings)
    out.write(
        f"{blocking} blocking, {len(findings) - blocking} warning "
        f"(merge base {merge_base[:10]}, head {head_sha[:10]})\n"
    )
    return 1 if blocking else 0
