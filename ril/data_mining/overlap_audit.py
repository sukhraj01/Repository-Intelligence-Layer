"""Content-overlap audit of the mined corpora against the held-out corpora (decision D105).

Implements ``docs/experiments/B.md`` E-OVERLAP-AUDIT (the precondition of O10 in
``docs/RQ2_PROTOCOL.md`` section 11, and the audit D65 left unbuilt). The mined population was
filtered by repository name, exact and current-name, so a fork, a vendored copy or a copied file
can still put a held-out function into a mined directory. A mined *positive* equal to a
held-out evaluation function leaks the answer; corpus overlap alone is shared boilerplate or
vendored code.

Matching key: the syntax-tree hash of a function as E-CONTAM-PROBE computes it
(``ril.training.contamination.ast_hash_and_size``: docstring, decorators, comments, layout and
quoting ignored; names and statements kept), with the same floor of 20 syntax-tree nodes as the
primary and 10 and 50 as the sensitivity cells. The line-hash coverage of
``ril.training.content_overlap`` is computed too, as a second reading.

Two levels, per directory:

(a) *positives*: a positive function of the directory whose hash matches a held-out function at or
    above the floor. The directory is **dropped from training** (the rule below).
(b) *corpus*: the share of the directory's distinct functions (distinct syntax-tree hashes at or
    above the floor, test-file functions excluded under the primary reading) whose hash matches a
    held-out function. At or above ``CORPUS_FLAG_SHARE`` the directory is **flagged, not dropped**.

The audit reads the de-duplicated store (``ril.data_mining.cas``): per repository the needed rows
are decompressed once and hashed once, whatever the number of directories that hold them, so it
scales to the full store without materialising directories. The store is never written.

Primary reading is ``non_test`` (D96): a test-file function is not in the corpus and a test
positive is not a positive. Positive matches are also counted over all positives (a sensitivity
cell). Kept compatible with Python 3.10 (the cluster's compute nodes).
"""

from __future__ import annotations

import array
import gzip
import hashlib
import json
import os
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from ril.data_mining import cas
from ril.data_mining.agreement import is_test_id
from ril.training.contamination import ProbeSet, ast_hash_and_size
from ril.training.content_overlap import (
    COVER_THRESHOLD,
    MIN_LINES,
    build_index,
    unit_coverage,
)

AUDIT_VERSION = "overlap-audit/v1"
"""Recorded with every run; part of its configuration hash."""

FLOOR = 20
"""Primary floor in syntax-tree nodes, the floor of E-CONTAM-PROBE."""
SENSITIVITY_FLOORS: tuple[int, ...] = (10, 20, 50)
CORPUS_FLAG_SHARE = 0.05
"""Corpus share (of distinct functions at the floor) at or above which a directory is flagged."""
SIZE_BUCKETS: tuple[tuple[str, int, int], ...] = (
    ("under 20", 0, 20),
    ("20 to 49", 20, 50),
    ("50 and up", 50, 10**9),
)
POSITIVES_READINGS = ("non_test", "all")
SAMPLE_SIZE = 20

Record = dict[str, Any]


def bucket_of(nodes: int) -> str:
    """Name of the size class of a function with ``nodes`` syntax-tree nodes."""
    for name, lo, hi in SIZE_BUCKETS:
        if lo <= nodes < hi:
            return name
    raise ValueError(nodes)


# --------------------------------------------------------------------------- held-out side


@dataclass
class HeldOutIndex:
    """Hashes of the held-out functions: syntax-tree hashes with repositories, and line hashes."""

    probe: ProbeSet = field(default_factory=ProbeSet)
    lines: set[int] = field(default_factory=set)
    repos_lines: set[str] = field(default_factory=set)
    sources: list[Record] = field(default_factory=list)

    def match(self, ast_hash: str | None) -> tuple[int, tuple[str, ...]]:
        """``(nodes, held-out repositories)`` of a hash; ``(0, ())`` when it is not held out."""
        if ast_hash is None:
            return 0, ()
        repos = self.probe.ast.get(ast_hash)
        if not repos:
            return 0, ()
        return self.probe.nodes.get(ast_hash, 0), tuple(sorted(repos))


def repo_of_store_name(filename: str) -> str:
    """``owner/name`` of a unit-text store file ``owner__name.sN.jsonl`` (case-folded)."""
    stem = filename.split(".s", 1)[0] if ".s" in filename else filename.rsplit(".", 1)[0]
    return stem.replace("__", "/").lower()


def merge_probe(into: ProbeSet, other: ProbeSet) -> None:
    """Add every hash of ``other`` (repositories case-folded) to ``into``."""
    for h, repos in other.ast.items():
        into.ast.setdefault(h, set()).update(r.lower() for r in repos)
        into.nodes[h] = other.nodes.get(h, into.nodes.get(h, 0))
    into.functions += other.functions


def add_unit_texts(index: HeldOutIndex, repo: str, texts: Iterable[str]) -> int:
    """Add the held-out function texts of one repository; returns the number hashed.

    A text that is not exactly one function definition (a class or module unit) has no
    syntax-tree hash and is skipped at that level; every text adds to the line index.
    """
    seen = 0
    texts = list(texts)
    for text in texts:
        h, n = ast_hash_and_size(text)
        if h is not None:
            index.probe.ast.setdefault(h, set()).add(repo)
            index.probe.nodes[h] = n
            index.probe.functions += 1
            seen += 1
    index.lines |= build_index(texts)
    index.repos_lines.add(repo)
    return seen


def read_text_store(path: str) -> Iterator[str]:
    """Unit texts of a ``texts_units/<repo>.sN.jsonl`` store (one ``{"h", "t"}`` per line)."""
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield str(json.loads(line)["t"])


def file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def build_held_out_index(probe_files: Sequence[str], text_stores: Sequence[str]) -> HeldOutIndex:
    """The held-out index from stored probe sets and unit-text stores (read-only).

    ``probe_files`` are ``ProbeSet`` JSON files (E-CONTAM-PROBE; syntax-tree level only is used).
    ``text_stores`` are unit-text store files; the repository is read from the file name.
    The union over snapshots is what is kept, as in the probe.
    """
    index = HeldOutIndex()
    for path in probe_files:
        with open(path, encoding="utf-8") as handle:
            probe = ProbeSet.from_json(handle.read())
        merge_probe(index.probe, probe)
        repos = {r for rs in probe.ast.values() for r in rs}
        index.sources.append(
            {
                "kind": "probe_set",
                "file": os.path.basename(path),
                "sha256": file_sha256(path),
                "ast_hashes": len(probe.ast),
                "repositories": len(repos),
            }
        )
    by_repo: dict[str, list[str]] = defaultdict(list)
    for path in sorted(text_stores):
        by_repo[repo_of_store_name(os.path.basename(path))].append(path)
    for repo in sorted(by_repo):
        hashed = texts = 0
        for path in by_repo[repo]:
            batch = list(read_text_store(path))
            texts += len(batch)
            hashed += add_unit_texts(index, repo, batch)
        index.sources.append(
            {
                "kind": "unit_texts",
                "repository": repo,
                "files": len(by_repo[repo]),
                "texts": texts,
                "function_texts_hashed": hashed,
            }
        )
    return index


def save_index(index: HeldOutIndex, out_dir: str) -> Record:
    """Write ``ast.json.gz``, ``lines.bin`` (sorted uint64, little endian) and ``manifest.json``."""
    os.makedirs(out_dir, exist_ok=True)
    ast_path = os.path.join(out_dir, "ast.json.gz")
    with gzip.GzipFile(ast_path, "wb", compresslevel=6, mtime=0) as handle:
        handle.write(index.probe.to_json().encode("utf-8"))
    lines = array.array("Q", sorted(index.lines))
    if sys.byteorder == "big":  # pragma: no cover
        lines.byteswap()
    lines_path = os.path.join(out_dir, "lines.bin")
    with open(lines_path, "wb") as handle:
        handle.write(lines.tobytes())
    repos = Counter(r for rs in index.probe.ast.values() for r in rs)
    manifest: Record = {
        "version": AUDIT_VERSION,
        "ast_hashes": len(index.probe.ast),
        "ast_hashes_at_floor": sum(1 for n in index.probe.nodes.values() if n >= FLOOR),
        "line_hashes": len(lines),
        "repositories_ast": dict(sorted(repos.items())),
        "repositories_lines": sorted(index.repos_lines),
        "ast_sha256": file_sha256(ast_path),
        "lines_sha256": file_sha256(lines_path),
        "sources": index.sources,
    }
    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=1, sort_keys=True)
    return manifest


def load_index(in_dir: str) -> HeldOutIndex:
    """The index written by :func:`save_index`."""
    index = HeldOutIndex()
    with gzip.open(os.path.join(in_dir, "ast.json.gz"), "rt", encoding="utf-8") as handle:
        index.probe = ProbeSet.from_json(handle.read())
    lines = array.array("Q")
    with open(os.path.join(in_dir, "lines.bin"), "rb") as handle:
        lines.frombytes(handle.read())
    if sys.byteorder == "big":  # pragma: no cover
        lines.byteswap()
    index.lines = set(lines)
    with open(os.path.join(in_dir, "manifest.json"), encoding="utf-8") as handle:
        manifest = json.load(handle)
    index.repos_lines = set(manifest["repositories_lines"])
    index.sources = list(manifest["sources"])
    return index


# --------------------------------------------------------------------------- mined side


@dataclass(frozen=True)
class RowInfo:
    """What one stored row contributes: id, test-file flag, hash and size, line coverage."""

    row_id: str
    is_test: bool
    ast_hash: str | None
    nodes: int
    line_scored: bool
    line_covered: bool


def row_info(line: bytes, lines_index: set[int]) -> RowInfo:
    """Hashes and coverage of one corpus row (``{"_id", "text": "<id>\\n<source>"}``)."""
    doc = json.loads(line)
    row_id = str(doc["_id"])
    _, _, source = str(doc["text"]).partition("\n")
    h, n = ast_hash_and_size(source)
    count, hit = unit_coverage(source, lines_index)
    scored = count >= MIN_LINES
    return RowInfo(
        row_id=row_id,
        is_test=is_test_id(row_id),
        ast_hash=h,
        nodes=n,
        line_scored=scored,
        line_covered=scored and hit / count >= COVER_THRESHOLD,
    )


def read_positives(directory: str) -> list[str]:
    """Positive corpus ids of one directory (``qrels/test.tsv``, header skipped)."""
    out: list[str] = []
    with open(os.path.join(directory, "qrels", "test.tsv"), encoding="utf-8") as handle:
        for i, line in enumerate(handle):
            if i == 0 or not line.strip():
                continue
            out.append(line.rstrip("\n").split("\t")[1])
    return out


def _by_floor(floors: Sequence[int], values: Mapping[int, int]) -> dict[str, int]:
    return {str(f): values.get(f, 0) for f in floors}


def audit_directory(
    name: str,
    repo: str,
    slots: Sequence[int],
    positives: Sequence[str],
    info: Mapping[int, RowInfo],
    index: HeldOutIndex,
    floors: Sequence[int] = SENSITIVITY_FLOORS,
) -> Record:
    """The audit record of one directory (no source text, only counts, ids and hashes)."""
    distinct = sorted(set(slots))
    by_id: dict[str, RowInfo] = {}
    for s in distinct:
        by_id.setdefault(info[s].row_id, info[s])
    # corpus level, primary reading: test-file functions are not part of the corpus
    hashes: dict[str, int] = {}
    scored = covered = 0
    for s in distinct:
        r = info[s]
        if r.is_test:
            continue
        if r.ast_hash is not None:
            hashes[r.ast_hash] = r.nodes
        scored += r.line_scored
        covered += r.line_covered
    distinct_ge: Counter[int] = Counter()
    matched_ge: Counter[int] = Counter()
    matched_by_size: Counter[str] = Counter()
    held_repos: Counter[str] = Counter()
    for h, n in hashes.items():
        _, m_repos = index.match(h)
        for f in floors:
            if n >= f:
                distinct_ge[f] += 1
                if m_repos:
                    matched_ge[f] += 1
        if m_repos:
            matched_by_size[bucket_of(n)] += 1
            for held in m_repos:
                held_repos[held] += 1
    # positives
    pos_matches: list[Record] = []
    missing = 0
    non_test = 0
    for pid in positives:
        row = by_id.get(pid)
        is_test = is_test_id(pid)
        non_test += not is_test
        if row is None:
            missing += 1
            continue
        _, m_repos = index.match(row.ast_hash)
        if m_repos:
            pos_matches.append(
                {
                    "id": pid,
                    "is_test": is_test,
                    "nodes": row.nodes,
                    "heldout_repos": list(m_repos),
                }
            )
    return {
        "directory": name,
        "repo": repo,
        "rows": len(distinct),
        "functions_hashed": len(hashes),
        "distinct_ge": _by_floor(floors, distinct_ge),
        "matched_ge": _by_floor(floors, matched_ge),
        "matched_by_size": {b: matched_by_size.get(b, 0) for b, _, _ in SIZE_BUCKETS},
        "heldout_repos": dict(sorted(held_repos.items())),
        "line_scored": scored,
        "line_covered": covered,
        "positives": len(positives),
        "positives_non_test": non_test,
        "positives_without_row": missing,
        "positive_matches": pos_matches,
    }


def audit_store(
    store_root: str,
    index: HeldOutIndex,
    floors: Sequence[int] = SENSITIVITY_FLOORS,
    names: Sequence[str] | None = None,
) -> Iterator[Record]:
    """Audit records of every directory of a de-duplicated store, repository by repository.

    Reads ``pr/<dir>`` small files and manifests and the ``cas`` rows; writes nothing. A row is
    parsed and hashed once per repository however many directories hold it.
    """
    wanted = list(names) if names is not None else cas.instance_names(store_root)
    by_repo: dict[str, list[str]] = defaultdict(list)
    for name in wanted:
        by_repo[cas._repo_of(os.path.join(store_root, "pr", name))].append(name)
    for repo in sorted(by_repo):
        dirs = sorted(by_repo[repo])
        manifests = {n: cas.read_manifest(os.path.join(store_root, "pr", n)) for n in dirs}
        needed = sorted({s for m in manifests.values() for s in m})
        block = cas.RepoRows(store_root, repo).load()
        if needed and needed[-1] >= len(block):
            raise cas.StoreError(f"{repo}: slot {needed[-1]} beyond the {len(block)} stored rows")
        info = {s: row_info(block.line(s), index.lines) for s in needed}
        del block
        for n in dirs:
            positives = read_positives(os.path.join(store_root, "pr", n))
            yield audit_directory(n, repo, list(manifests[n]), positives, info, index, floors)


# --------------------------------------------------------------------------- the rule


@dataclass(frozen=True)
class Rule:
    """The rule applied to the mined set, fixed before the full set is audited (D105)."""

    floor: int = FLOOR
    corpus_share: float = CORPUS_FLAG_SHARE
    positives: str = "non_test"
    drop_flagged: bool = False
    """Sensitivity cell: also drop the directories flagged by (b)."""

    def __post_init__(self) -> None:
        if self.positives not in POSITIVES_READINGS:
            raise ValueError(f"positives must be one of {POSITIVES_READINGS}")


def positive_hits(rec: Mapping[str, Any], rule: Rule) -> list[Record]:
    """Positive matches of a record that count under ``rule`` (floor and positives reading)."""
    return [
        m
        for m in rec["positive_matches"]
        if m["nodes"] >= rule.floor and (rule.positives == "all" or not m["is_test"])
    ]


def corpus_share(rec: Mapping[str, Any], floor: int) -> float:
    """Matched distinct functions over distinct functions at ``floor`` (0.0 when none)."""
    key = str(floor)
    if key not in rec["distinct_ge"]:
        raise KeyError(f"floor {floor} was not audited; audited: {sorted(rec['distinct_ge'])}")
    total = rec["distinct_ge"][key]
    return rec["matched_ge"][key] / total if total else 0.0


def classify(rec: Mapping[str, Any], rule: Rule) -> str:
    """``drop`` (a), ``flag`` (b only) or ``keep`` for one directory."""
    if positive_hits(rec, rule):
        return "drop"
    if corpus_share(rec, rule.floor) >= rule.corpus_share:
        return "drop" if rule.drop_flagged else "flag"
    return "keep"


def remaining_positives(rec: Mapping[str, Any], reading: str) -> int:
    return int(rec["positives_non_test"] if reading == "non_test" else rec["positives"])


def apply_rule(records: Sequence[Mapping[str, Any]], rule: Rule) -> Record:
    """Counts of one rule over audited directories, at directory and repository level.

    ``pool_like`` is a directory with at least one positive under the primary reading (the
    1,286 of the integration pilot). Repositories are the case-folded ``owner/name`` of the
    directories.
    """
    dropped: list[str] = []
    flagged: list[str] = []
    for rec in records:
        c = classify(rec, rule)
        if c == "drop":
            dropped.append(rec["directory"])
        elif c == "flag":
            flagged.append(rec["directory"])
    dropset = set(dropped)
    pool_like = [r for r in records if r["positives_non_test"] > 0]
    kept_pool = [r for r in pool_like if r["directory"] not in dropset]
    repos_all = {r["repo"] for r in records}
    repos_dropped = {r["repo"] for r in records if r["directory"] in dropset}
    repos_left = {r["repo"] for r in records if r["directory"] not in dropset}
    drop_by_a = [r["directory"] for r in records if positive_hits(r, rule)]
    return {
        "rule": {
            "floor": rule.floor,
            "corpus_share": rule.corpus_share,
            "positives": rule.positives,
            "drop_flagged": rule.drop_flagged,
        },
        "directories": len(records),
        "dropped": len(dropped),
        "dropped_by_a": len(drop_by_a),
        "dropped_by_b_only": len(dropped) - len(drop_by_a),
        "flagged": len(flagged),
        "repositories": len(repos_all),
        "repositories_with_a_dropped_directory": len(repos_dropped),
        "repositories_with_every_directory_dropped": len(repos_all - repos_left),
        "pool_like_directories": len(pool_like),
        "pool_like_after": len(kept_pool),
        "pool_like_positives": sum(r["positives_non_test"] for r in pool_like),
        "pool_like_positives_after": sum(r["positives_non_test"] for r in kept_pool),
        "dropped_directories": sorted(dropped),
        "flagged_directories": sorted(flagged),
    }


def positive_match_summary(records: Sequence[Mapping[str, Any]], reading: str) -> Record:
    """Positive matches by size class (all sizes, as E-CONTAM-PROBE) and by held-out repository."""
    by_size: Counter[str] = Counter()
    by_repo: Counter[str] = Counter()
    dirs: set[str] = set()
    for rec in records:
        for m in rec["positive_matches"]:
            if reading == "non_test" and m["is_test"]:
                continue
            by_size[bucket_of(m["nodes"])] += 1
            dirs.add(rec["directory"])
            for r in m["heldout_repos"]:
                by_repo[r] += 1
    return {
        "reading": reading,
        "matches": sum(by_size.values()),
        "directories_with_a_match": len(dirs),
        "by_size": {b: by_size.get(b, 0) for b, _, _ in SIZE_BUCKETS},
        "by_heldout_repository": dict(by_repo.most_common()),
    }


def corpus_match_summary(records: Sequence[Mapping[str, Any]]) -> Record:
    """Matched distinct functions of the corpora by size class and held-out repository."""
    by_size: Counter[str] = Counter()
    by_repo: Counter[str] = Counter()
    for rec in records:
        by_size.update(rec["matched_by_size"])
        by_repo.update(rec["heldout_repos"])
    return {
        "matched_functions": sum(by_size.values()),
        "by_size": {b: by_size.get(b, 0) for b, _, _ in SIZE_BUCKETS},
        "by_heldout_repository": dict(by_repo.most_common()),
    }


def line_reading(
    records: Sequence[Mapping[str, Any]], rule: Rule, share: float | None = None
) -> Record:
    """Directories whose line-hash coverage (``content_overlap``) reaches ``share``."""
    cut = rule.corpus_share if share is None else share
    high: list[str] = []
    both = 0
    for rec in records:
        s = rec["line_covered"] / rec["line_scored"] if rec["line_scored"] else 0.0
        if s >= cut:
            high.append(rec["directory"])
            both += corpus_share(rec, rule.floor) >= rule.corpus_share
    return {
        "share": cut,
        "directories_at_or_above": len(high),
        "of_which_also_flagged_by_ast": both,
    }


def sample_matches(
    records: Sequence[Mapping[str, Any]], rule: Rule, n: int = SAMPLE_SIZE, seed: int = 0
) -> list[Record]:
    """Up to ``n`` positive matches for a human to read, in a seeded order (no judgement).

    Order: ``sha256("<seed>:<directory>:<id>")``, so the draw is the same on every run. Only matches
    that count under ``rule`` are drawn.
    """
    pool: list[tuple[str, Record]] = []
    for rec in records:
        for m in positive_hits(rec, rule):
            key = hashlib.sha256(f"{seed}:{rec['directory']}:{m['id']}".encode()).hexdigest()
            pool.append(
                (
                    key,
                    {
                        "directory": rec["directory"],
                        "mined_repo": rec["repo"],
                        "positive_id": m["id"],
                        "nodes": m["nodes"],
                        "heldout_repos": ",".join(m["heldout_repos"]),
                    },
                )
            )
    pool.sort(key=lambda kv: kv[0])
    return [row for _, row in pool[:n]]


def config_hash(index_manifest: Mapping[str, Any], floors: Sequence[int], rule: Rule) -> str:
    """SHA-256 over the audit version, floors, the primary rule and the held-out index digests."""
    payload = {
        "version": AUDIT_VERSION,
        "floors": list(floors),
        "rule": [rule.floor, rule.corpus_share, rule.positives, rule.drop_flagged],
        "line": [MIN_LINES, COVER_THRESHOLD],
        "ast_sha256": index_manifest["ast_sha256"],
        "lines_sha256": index_manifest["lines_sha256"],
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def summarise(records: Sequence[Mapping[str, Any]], floors: Sequence[int], primary: Rule) -> Record:
    """Everything the entry reports, from the records alone (recomputable without the store)."""
    sens = {
        str(f): apply_rule(records, Rule(floor=f, corpus_share=primary.corpus_share))
        for f in floors
    }
    for v in sens.values():
        v.pop("dropped_directories")
        v.pop("flagged_directories")
    cells: Record = {}
    for label, rule in (
        ("primary", primary),
        ("positives_all", Rule(primary.floor, primary.corpus_share, "all")),
        ("drop_flagged", Rule(primary.floor, primary.corpus_share, primary.positives, True)),
    ):
        cell = apply_rule(records, rule)
        cell.pop("dropped_directories")
        cell.pop("flagged_directories")
        cells[label] = cell
    return {
        "version": AUDIT_VERSION,
        "directories": len(records),
        "floor_sensitivity": sens,
        "cells": cells,
        "positive_matches_non_test": positive_match_summary(records, "non_test"),
        "positive_matches_all": positive_match_summary(records, "all"),
        "corpus_matches": corpus_match_summary(records),
        "line_hash_reading": line_reading(records, primary),
        "positives_without_row": sum(r["positives_without_row"] for r in records),
    }
