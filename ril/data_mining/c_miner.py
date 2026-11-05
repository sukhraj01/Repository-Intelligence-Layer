"""Resumable raw PR pilot: base snapshots, complete diffs and all edited functions."""

from __future__ import annotations

import hashlib
import io
import json
import os
import platform
import re
import resource
import subprocess
import tarfile
import tempfile
import time
from collections import Counter
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any, Protocol

from ril.data_mining.github import Client, atomic_json, digest, linked_issues, search_path
from ril.parsing.repository_parser import parse_repository
from ril.training.content_overlap import audit_pool
from ril.training.held_out import canonical_repo, is_held_out, load_held_out_lists, rule_counts
from ril.training.pool_reader import PoolExample, read_cache, write_cache

Record = dict[str, Any]
VERSION = "raw-pr-miner/v1"
_SHA = re.compile(r"^[a-fA-F0-9]{40}$")
_REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+\d+(?:,\d+)? @@")


def historical_base(
    client: Client, repo: str, number: int, detail: Record
) -> tuple[str | None, Record]:
    """Use a standard merge's immutable parents, quarantining unsupported histories.

    The first parent fixes the target immediately before merge. Comparing it to the
    recorded head finds the last shared target update even after upstream sync merges.
    Single-parent squash/rebase and merge queues need separate validation before admission.
    """
    head, merged = detail["head"]["sha"], detail.get("merge_commit_sha", "")
    if not all(_SHA.fullmatch(x) for x in (head, merged)):
        return None, {"base_selection": "quarantined_missing_merge_identity"}
    commit = client.request(f"/repos/{repo}/git/commits/{merged}")["data"]
    parents = commit.get("parents", [])
    metadata: Record = {"merge_commit": merged, "base_selection": "standard_merge_parents"}
    if len(parents) != 2 or parents[1]["sha"] != head:
        return None, {**metadata, "base_selection": "quarantined_unsupported_merge_history"}
    target = parents[0]["sha"]
    if not _SHA.fullmatch(target):
        raise ValueError("immutable target parent required")
    compare = client.request(f"/repos/{repo}/compare/{target}...{head}")["data"]
    base = str(compare["merge_base_commit"]["sha"])
    metadata["target_before_merge"] = target
    if not _SHA.fullmatch(base) or base == head:
        return None, {**metadata, "base_selection": "quarantined_unverifiable_merge_base"}
    return base, metadata


def safe_path(value: str) -> str:
    """Reject archive/diff paths that escape a scratch snapshot."""
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError("unsafe snapshot path")
    return str(path)


def changed_lines(diff: str) -> dict[str, set[int]]:
    """Old-file removed lines and insertion anchors from a complete unified diff.

    An insertion touches its two adjoining old lines (0 is omitted). Added files have no
    base-commit target. Renames use the old path; deletions keep all removed old lines.
    Quoted Git paths are decoded as JSON-compatible quoted strings.
    """
    result: dict[str, set[int]] = {}
    path: str | None = None
    old_line = 0
    in_hunk = False
    insertion = False
    for line in diff.splitlines():
        if line.startswith("diff --git "):
            path, in_hunk = None, False
        elif line.startswith("--- ") and not in_hunk:
            raw = line[4:]
            raw = json.loads(raw) if raw.startswith('"') else raw
            path = None if raw == "/dev/null" else safe_path(raw.removeprefix("a/"))
        elif match := _HUNK.match(line):
            insertion = match[2] == "0"
            old_line = int(match[1]) + (1 if insertion else 0)
            in_hunk = True
        elif in_hunk and path is not None:
            touched = result.setdefault(path, set())
            if line.startswith("-"):
                touched.add(old_line)
                old_line += 1
            elif line.startswith("+") and insertion:
                touched.update(x for x in (old_line - 1, old_line) if x > 0)
            elif line.startswith(" "):
                old_line += 1
    return result


class Snapshots(Protocol):
    def materialize(self, repo: str, base: str, head: str, root: Path) -> str:
        """Populate root at base and return the complete base-to-head diff."""
        ...


class GitSnapshots:
    """Fetch immutable commits into isolated bare caches, with no credentialed Git URL."""

    def __init__(self, root: Path):
        self.root = root

    def materialize(self, repo: str, base: str, head: str, root: Path) -> str:
        if not _REPO.fullmatch(repo) or not all(_SHA.fullmatch(x) for x in (base, head)):
            raise ValueError("invalid repository or immutable commit")
        cache = self.root / repo.replace("/", "__")
        cache.parent.mkdir(parents=True, exist_ok=True)
        if not cache.exists():
            subprocess.run(["git", "init", "--bare", "--quiet", str(cache)], check=True)

        def git(*args: str) -> bytes:
            return subprocess.run(
                ["git", "--git-dir", str(cache), *args],
                check=True,
                capture_output=True,
            ).stdout

        for commit in (base, head):
            exists = (
                subprocess.run(
                    ["git", "--git-dir", str(cache), "cat-file", "-e", f"{commit}^{{commit}}"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                ).returncode
                == 0
            )
            if not exists:
                git(
                    "fetch",
                    "--quiet",
                    "--no-tags",
                    "--depth=1",
                    f"https://github.com/{repo}.git",
                    commit,
                )
        archive = git("archive", "--format=tar", base)
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            for member in tar:
                # Parse Python only, never execute source or traverse symlinks.
                if not member.isfile() or not member.name.endswith(".py"):
                    continue
                path = root / safe_path(member.name)
                path.parent.mkdir(parents=True, exist_ok=True)
                handle = tar.extractfile(member)
                if handle is None:
                    raise ValueError("archive regular file has no content")
                path.write_bytes(handle.read())
        return git(
            "-c",
            "core.quotePath=false",
            "diff",
            "--no-ext-diff",
            "--no-textconv",
            "--find-renames",
            "--unified=0",
            base,
            head,
            "--",
        ).decode("utf-8")


class RecordedSnapshots:
    """Synthetic base sources and complete diff bytes keyed by immutable identity."""

    def __init__(self, document: Record):
        self.rows = document["snapshots"]

    def materialize(self, repo: str, base: str, head: str, root: Path) -> str:
        row = self.rows[digest([repo, base, head])]
        for name, text in row["files"].items():
            path = root / safe_path(name)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        return str(row["diff"])


def extract_example(
    repo: str,
    number: int,
    issues: list[Record],
    root: Path,
    diff: str,
) -> tuple[PoolExample | None, Record]:
    """Call the shared parser and preserve every overlapping function or method.

    Classes and residual module units remain outside this function-level pool. Partial
    parses are quarantined in their entirety: unknown functions never become negatives.
    This is a mechanical completeness check, independent of every retriever.
    """
    parsed = parse_repository(str(root), repo)
    metadata: Record = {"parse_errors": parsed.unparseable, "skipped_files": parsed.skipped_files}
    if parsed.unparseable or parsed.skipped_files:
        metadata["outcome"] = "parse_incomplete"
        return None, metadata
    touched = changed_lines(diff)
    functions = [u for u in parsed.units if u.unit_type in ("function", "method")]
    # Preserve collision ordinals; the reader and rank tools accept arbitrary unique strings.
    pool_id = {
        u.id: (
            f"{u.file}/{u.qualified_name.replace('.', '/')}"
            + u.id[len(u.file) + 2 + len(u.qualified_name) :]
        )
        for u in functions
    }
    positives = [
        u
        for u in functions
        if any(u.start_line <= line <= u.end_line for line in touched.get(u.file, set()))
    ]
    metadata["functions"] = len(functions)
    metadata["positives"] = [
        {
            "id": pool_id[u.id],
            "codeunit_id": u.id,
            "file": u.file,
            "start_line": u.start_line,
            "end_line": u.end_line,
            "touched_old_lines": sorted(touched[u.file] & set(range(u.start_line, u.end_line + 1))),
            "source_sha256": digest(u.source),
        }
        for u in positives
    ]
    metadata["diff_sha256"] = digest(diff)
    if not positives:
        metadata["outcome"] = "no_overlapping_function"
        return None, metadata
    pos_ids = {u.id for u in positives}
    candidates = [u for u in functions if u.id not in pos_ids]
    instance = f"train/python/{repo.replace('/', '__')}-{number}"
    query = "\n\n".join(f"{issue['title']}\n\n{issue.get('body') or ''}" for issue in issues)
    metadata["outcome"] = "kept"
    return PoolExample(
        instance,
        repo,
        number,
        query,
        tuple(pool_id[u.id] for u in positives),
        tuple(u.source for u in positives),
        tuple(pool_id[u.id] for u in candidates),
        tuple(u.source for u in candidates),
    ), metadata


def source_checkout(repository_root: Path) -> Record:
    """Describe Git or a verified archive, never label an archive as a clean checkout."""
    try:
        top = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=repository_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        if Path(top).resolve() != repository_root.resolve():
            raise ValueError("source archive is nested beneath an unrelated checkout")
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repository_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=repository_root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        )
        return {
            "git_hash": commit,
            "git_dirty": dirty,
            "source_control": "git",
            "git_status": "dirty" if dirty else "clean",
        }
    except (OSError, subprocess.SubprocessError, ValueError):
        commit = os.environ.get("RIL_COMMIT", "")
        if not _SHA.fullmatch(commit):
            raise ValueError(
                "source archive requires the verified package's full RIL_COMMIT"
            ) from None
        return {
            "git_hash": commit.lower(),
            "git_dirty": True,
            "source_control": "archive_without_git",
            "git_status": "unavailable",
        }


def mine(
    config: Record,
    out: Path,
    client: Client,
    snapshots: Snapshots,
    held_out_doc: Record,
    *,
    source_kind: str,
    source_identity: str = "unspecified",
    overlap_index: set[int] | None = None,
    overlap_identity: str | None = None,
) -> Record:
    """Pilot only, resumable per request and PR, rejecting changed run identities."""
    if not 1 <= int(config["repositories"]) <= 200 or not 1 <= int(config["pull_requests"]) <= 2000:
        raise ValueError("pilot limits are 200 repositories and 2000 PRs; full scale needs review")
    repository_root = Path(__file__).resolve().parents[2]
    checkout = source_checkout(repository_root)
    source_paths = [
        *Path(__file__).parent.glob("*.py"),
        repository_root / "scripts/c_mine_prs.py",
        repository_root / "ril/evaluation/runtime.py",
        repository_root / "ril/parsing/repository_parser.py",
        repository_root / "ril/training/pool_reader.py",
        repository_root / "ril/training/pool_ranks.py",
    ]
    implementation_sources = {
        str(p.relative_to(repository_root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(source_paths)
    }
    identity = {
        "version": VERSION,
        "config": config,
        "held_out_sha256": digest(held_out_doc),
        "source_kind": source_kind,
        "source_identity": source_identity,
        "overlap_identity": overlap_identity,
        "implementation_sources": implementation_sources,
    }
    identity_path = out / "identity.json"
    if identity_path.exists() and json.loads(identity_path.read_text()) != identity:
        raise ValueError("resume identity/configuration mismatch; choose a new output directory")
    atomic_json(identity_path, identity)
    started = time.monotonic()
    lists = load_held_out_lists(held_out_doc)
    repos: list[str] = []
    for row in client.pages(search_path(config["repository_query"]), "items"):
        repo = canonical_repo(row["full_name"])
        if repo not in repos:
            repos.append(repo)
        if len(repos) == int(config["repositories"]):
            break
    aliases = dict(lists.aliases)
    resolved = []
    unresolved = []
    repository_metadata = {}
    forks: dict[str, tuple[str, ...]] = {}
    # Resolve both sides. Otherwise a held-out rename could evade candidate-only resolution.
    for repo in sorted(set(repos) | set(lists.blocked())):
        try:
            data = client.request(f"/repos/{repo}")["data"]
        except RuntimeError as exc:
            if str(exc) != "GitHub HTTP 404":
                raise
            unresolved.append(repo)
            continue
        current = canonical_repo(data["full_name"])
        aliases[repo] = current
        if repo in repos:
            repository_metadata[repo] = {
                k: data.get(k)
                for k in (
                    "full_name",
                    "language",
                    "stargazers_count",
                    "license",
                    "pushed_at",
                    "archived",
                    "fork",
                )
            }
        resolved.append(repo)
        forks[repo] = tuple(
            canonical_repo(data[k]["full_name"]) for k in ("parent", "source") if k in data
        )
    blocked = set(lists.blocked()) | {aliases.get(r, r) for r in lists.blocked()}
    rule_rows = [asdict(r) for r in rule_counts(dict.fromkeys(repos, 1), lists, aliases, forks)]
    kept_repos = [r for r in repos if not is_held_out(r, blocked, aliases)]
    counters: Counter[str] = Counter()
    examples: list[PoolExample] = []
    metadata_rows: list[Record] = []
    by_repo: dict[str, list[str]] = {}
    seen_prs: set[tuple[str, int]] = set()
    for repo in kept_repos:
        if counters["merged_prs"] >= config["pull_requests"]:
            break
        for row in client.pages(
            f"/repos/{repo}/pulls?state=closed&sort=updated&direction=desc&per_page=100"
        ):
            if not row.get("merged_at"):
                counters["unmerged_prs"] += 1
                continue
            number = int(row["number"])
            if (repo, number) in seen_prs:
                continue
            seen_prs.add((repo, number))
            counters["merged_prs"] += 1
            checkpoint = out / "instances" / f"{digest([repo, number])}.json"
            if checkpoint.exists():
                record = json.loads(checkpoint.read_text())
                cache = out / "instances" / record["cache"] if record.get("cache") else None
                example = read_cache(str(cache))[0] if cache else None
            else:
                issues = linked_issues(client, repo, number)
                record = {
                    "repo": repo,
                    "pr": number,
                    "issues": issues,
                    "linked_issue_count": len(issues),
                    "source_kind": source_kind,
                }
                example = None
                if not issues:
                    record["outcome"] = "no_linked_issue"
                else:
                    detail = client.request(f"/repos/{repo}/pulls/{number}")["data"]
                    head = detail["head"]["sha"]
                    base, selection = historical_base(client, repo, number, detail)
                    record.update(
                        selection,
                        head_commit=head,
                        merged_at=detail["merged_at"],
                        pr_url=detail["html_url"],
                    )
                    if base is None:
                        record["outcome"] = "history_unverifiable"
                    else:
                        record["base_commit"] = base
                        with tempfile.TemporaryDirectory(prefix="ril-miner-") as scratch:
                            diff = snapshots.materialize(repo, base, head, Path(scratch))
                            example, extracted = extract_example(
                                repo, number, issues, Path(scratch), diff
                            )
                        record.update(extracted)
                if example is not None:
                    record["cache"] = checkpoint.stem + ".jsonl.gz"
                    write_cache(str(checkpoint.parent / record["cache"]), [example])
                atomic_json(checkpoint, record)
            metadata_rows.append(record)
            counters[record["outcome"]] += 1
            counters["linked_issues"] += record["linked_issue_count"]
            counters["linked_prs"] += bool(record["linked_issue_count"])
            if example is not None:
                examples.append(example)
                counters["positives"] += len(example.positive_ids)
                by_repo.setdefault(repo, []).extend(
                    example.positive_texts + example.candidate_texts
                )
            if counters["merged_prs"] >= config["pull_requests"]:
                break
    write_cache(str(out / "pool.jsonl.gz"), examples)
    atomic_json(out / "metadata.json", metadata_rows)
    overlap: Record = {
        "status": "blocked: held-out content index absent",
        "applied_as_filter": False,
    }
    if overlap_index is not None:
        overlap = {
            "status": "computed",
            "index_identity": overlap_identity,
            "applied_as_filter": False,
            "rows": [asdict(r) | {"share": r.share} for r in audit_pool(by_repo, overlap_index)],
        }
    previous = (
        json.loads((out / "provenance.json").read_text())
        if (out / "provenance.json").exists()
        else {}
    )
    provenance = {
        "source": "https://api.github.com",
        "source_kind": source_kind,
        "date": datetime.now(UTC).isoformat(),
        "config_hash": digest(config),
        "run_identity": digest(identity),
        "version": VERSION,
        **checkout,
        "implementation_sources": implementation_sources,
        "hardware": {
            "platform": platform.system(),
            "processor": platform.machine(),
            "python": platform.python_version(),
            "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        },
        "repository_metadata": repository_metadata,
        "counts": dict(counters),
        "repositories_selected": len(repos),
        "repositories_after_held_out": len(kept_repos),
        "held_out_rule_counts": rule_rows,
        "rename_resolution": {
            "requested": len(set(repos) | set(lists.blocked())),
            "resolved": len(resolved),
            "unresolved": unresolved,
            "complete": not unresolved,
        },
        "content_overlap": overlap,
        "api": client.counts,
        "elapsed_seconds_cumulative": previous.get("elapsed_seconds_cumulative", 0)
        + time.monotonic()
        - started,
        "parse_failure_denominator": counters["linked_prs"],
        "parse_failure_share": counters["parse_incomplete"] / counters["linked_prs"]
        if counters["linked_prs"]
        else None,
        "positives_per_kept_pr": counters["positives"] / len(examples) if examples else None,
        "pool_sha256": hashlib.sha256((out / "pool.jsonl.gz").read_bytes()).hexdigest(),
        "positive_policy": "every overlapping base-commit function/method; no retriever filter",
        "full_scale_authorized": False,
        "supported_history": "two-parent merge; second parent equals recorded PR head",
    }
    atomic_json(out / "provenance.json", provenance)
    return provenance
