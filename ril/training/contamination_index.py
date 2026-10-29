"""Probe set from repository snapshots: the function and method units at given commits.

Implements the benchmark side of ``docs/EXPERIMENTS.md`` (E-CONTAM-PROBE). Files are read from the
git object store by blob id, so a file that is identical in many snapshots is parsed once per
repository. Files and functions are those of the CodeUnit definition: the discovery skip rules of
``ril.parsing.repository_parser`` and its ``parse_file`` (function and method units; nested
definitions fold into their parent). No source text is kept, only hashes.

Needs Python 3.10 (the parser does).
"""

from __future__ import annotations

import ast
import subprocess
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field

from ril.parsing.repository_parser import (
    SKIP_DIR_NAMES,
    VENDORED_DIR_NAMES,
    ParseOptions,
    _is_generated,
    parse_file,
)
from ril.training.contamination import ProbeSet, function_hashes

_HEAD_BYTES = 400


def path_is_probed(path: str, head: bytes) -> bool:
    """Whether a repo-relative ``.py`` path passes the CodeUnit discovery rules."""
    if not path.endswith(".py") or "::" in path or "\\" in path:
        return False
    parts = path.split("/")
    for d in parts[:-1]:
        if d in SKIP_DIR_NAMES or d.endswith(".egg-info") or d in VENDORED_DIR_NAMES:
            return False
    return not _is_generated(head, parts[-1])


def list_blobs(git_dir: str, commit: str) -> list[tuple[str, str]]:
    """(path, blob id) of every regular ``.py`` file of a commit (symlinks, submodules skipped)."""
    out = subprocess.run(
        ["git", "--git-dir", git_dir, "ls-tree", "-r", "-z", commit],
        check=True,
        capture_output=True,
    ).stdout
    blobs: list[tuple[str, str]] = []
    for rec in out.split(b"\0"):
        if not rec:
            continue
        meta, _, path = rec.partition(b"\t")
        mode, kind, sha = meta.decode().split()
        name = path.decode("utf-8", "surrogateescape")
        if kind == "blob" and mode in ("100644", "100755") and name.endswith(".py"):
            blobs.append((name, sha))
    return blobs


def read_blobs(git_dir: str, shas: Sequence[str]) -> dict[str, bytes]:
    """Contents of blobs by id through one ``git cat-file --batch`` process."""
    if not shas:
        return {}
    proc = subprocess.run(
        ["git", "--git-dir", git_dir, "cat-file", "--batch"],
        input=("\n".join(shas) + "\n").encode(),
        check=True,
        capture_output=True,
    )
    data, pos, result = proc.stdout, 0, {}
    for sha in shas:
        nl = data.index(b"\n", pos)
        header = data[pos:nl].decode().split()
        if len(header) != 3 or header[1] != "blob":
            raise ValueError(f"cat-file: unexpected answer for {sha}: {header}")
        size = int(header[2])
        result[sha] = data[nl + 1 : nl + 1 + size]
        pos = nl + 1 + size + 1
    return result


def function_sources(path: str, raw: bytes, repo: str) -> list[str] | None:
    """Sources of the function and method units of one file; ``None`` if it does not parse."""
    try:
        text = raw.decode("utf-8")
        tree = ast.parse(raw, filename=path)
    except (SyntaxError, ValueError, UnicodeError, RecursionError, MemoryError):
        return None
    units, _ = parse_file(
        repo_id=repo,
        path=path,
        text=text,
        tree=tree,
        module_name="m",
        is_package=False,
        last_modified="",
        options=ParseOptions(),
    )
    return [u.source for u in units if u.unit_type in ("function", "method")]


@dataclass
class IndexStats:
    """Counts of an index build."""

    snapshots: int = 0
    blobs_seen: int = 0
    blobs_parsed: int = 0
    blobs_unparseable: int = 0
    blobs_skipped_by_rule: int = 0
    functions: int = 0
    per_repo: dict[str, dict[str, int]] = field(default_factory=dict)


def add_snapshot(
    probe: ProbeSet,
    stats: IndexStats,
    repo: str,
    git_dir: str,
    commit: str,
    done_blobs: set[str],
) -> None:
    """Add the functions of one commit; ``done_blobs`` (per repository) is updated."""
    stats.snapshots += 1
    rs = stats.per_repo.setdefault(repo, {"snapshots": 0, "blobs_parsed": 0, "functions": 0})
    rs["snapshots"] += 1
    fresh: list[tuple[str, str]] = []
    for path, sha in list_blobs(git_dir, commit):
        stats.blobs_seen += 1
        if sha not in done_blobs:
            fresh.append((path, sha))
    contents = read_blobs(git_dir, [sha for _, sha in fresh])
    for path, sha in fresh:
        done_blobs.add(sha)
        raw = contents[sha]
        if not path_is_probed(path, raw[:_HEAD_BYTES]):
            stats.blobs_skipped_by_rule += 1
            continue
        srcs = function_sources(path, raw, repo)
        if srcs is None:
            stats.blobs_unparseable += 1
            continue
        stats.blobs_parsed += 1
        rs["blobs_parsed"] += 1
        for src in srcs:
            probe.add(repo, function_hashes(src))
            stats.functions += 1
            rs["functions"] += 1


def build_probe(
    git_dirs: Mapping[str, str], commits: Mapping[str, Iterable[str]]
) -> tuple[ProbeSet, IndexStats]:
    """Probe set over every listed commit of every repository (``repo`` -> git dir, commits)."""
    probe, stats = ProbeSet(), IndexStats()
    for repo in sorted(commits):
        done: set[str] = set()
        for commit in sorted(set(commits[repo])):
            add_snapshot(probe, stats, repo, git_dirs[repo], commit, done)
    return probe, stats


def instance_hashes(
    git_dirs: Mapping[str, str],
    instances: Mapping[str, tuple[str, str]],
    min_nodes: int = 0,
) -> dict[str, dict[str, int]]:
    """Syntax-tree hashes (with node counts) of the functions at each instance's own base commit.

    Implements ``docs/EXPERIMENTS.md`` E-CONTAM-SCAN: the restriction of a corpus hit to a
    function that exists at the instance's own base commit needs one hash set per instance, not
    the union over snapshots that :func:`build_probe` keeps. ``instances`` maps an instance id to
    ``(repo, base commit)``; hashes under ``min_nodes`` are dropped. A blob is parsed once per
    repository. No source text is kept.
    """
    per_blob: dict[str, dict[str, dict[str, int]]] = {}
    out: dict[str, dict[str, int]] = {}
    for iid in sorted(instances):
        repo, commit = instances[iid]
        cache = per_blob.setdefault(repo, {})
        fresh = [(p, s) for p, s in list_blobs(git_dirs[repo], commit) if s not in cache]
        contents = read_blobs(git_dirs[repo], [s for _, s in fresh])
        for path, sha in fresh:
            raw = contents[sha]
            found: dict[str, int] = {}
            if path_is_probed(path, raw[:_HEAD_BYTES]):
                for src in function_sources(path, raw, repo) or []:
                    fh = function_hashes(src)
                    if fh.ast is not None:
                        found[fh.ast] = fh.nodes
            cache[sha] = found
        hashes: dict[str, int] = {}
        for _, sha in list_blobs(git_dirs[repo], commit):
            hashes.update(cache[sha])
        out[iid] = {h: n for h, n in hashes.items() if n >= min_nodes}
    return out
