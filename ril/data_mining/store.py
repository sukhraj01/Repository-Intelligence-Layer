"""Output, resumable state and provenance of a mining run (design D66).

Implements ``docs/experiments/B.md`` E-MINE-PILOT. Layout under the run root::

    pr/<owner>__<name>-<PR>/{corpus.jsonl.gz, queries.jsonl, qrels/test.tsv, pr_meta.json}
    listing/<owner>__<name>.json    merged pull requests and closing issues of one repository
    state.jsonl                     one row per finished pull request (append-only)
    run.json                        first-creation record (date, config hash), never rewritten
    provenance.json                 source, endpoints, token description, counts per stage

The first three files of a ``pr/`` directory are what ``ril.training.pool_reader`` reads (the
pool's layout, BEIR style); the corpus is stored compressed (``files.py``) and ``pack`` writes it
into the archive as the plain member. A directory is written under a temporary name and renamed,
so a crash leaves either no directory or a complete one; the state row follows the rename, and a
directory without a row is adopted on resume. Every file is written with sorted keys and fixed
separators, so a rerun from the same state produces the same bytes.

Kept compatible with Python 3.10 (the cluster's compute nodes).
"""

from __future__ import annotations

import json
import os
import shutil
from collections.abc import Iterable, Mapping
from dataclasses import asdict
from typing import Any

from ril.data_mining.files import CORPUS_GZ, gzip_bytes
from ril.data_mining.links import LinkedIssue, PullRequest
from ril.data_mining.miner import STATUS_MINED, MinedInstance, Outcome

QRELS_HEADER = "query-id\tcorpus-id\tscore"
SOURCE = "GitHub GraphQL and REST API (api.github.com), git objects from github.com"
ENDPOINTS = (
    "POST /graphql (repository.pullRequests, closingIssuesReferences)",
    "GET /repos/{owner}/{repo}/compare/{base}...{head}",
    "git fetch --depth 1 <commit> from github.com (Python files of the base commit)",
)
TOKEN_SCOPE = "read-only access to public repositories; the token value is never recorded"


def dumps(obj: Any) -> str:
    """Canonical JSON: sorted keys, compact separators, no ASCII escaping."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _write_atomic(path: str, data: bytes) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def instance_files(inst: MinedInstance) -> dict[str, bytes]:
    """The four files of one instance directory, as bytes."""
    corpus = "".join(
        dumps({"_id": pid, "title": "", "text": text, "metadata": {}}) + "\n"
        for pid, text in inst.corpus
    )
    query = (
        dumps(
            {
                "_id": inst.dir_name,
                "text": inst.query,
                "metadata": {"repo": inst.repo, "base_commit": inst.base_commit},
            }
        )
        + "\n"
    )
    qrels = QRELS_HEADER + "\n" + "".join(f"{inst.dir_name}\t{pid}\t1\n" for pid in inst.qrels)
    return {
        CORPUS_GZ: gzip_bytes(corpus.encode("utf-8")),
        "queries.jsonl": query.encode("utf-8"),
        "qrels/test.tsv": qrels.encode("utf-8"),
        "pr_meta.json": (dumps(inst.meta) + "\n").encode("utf-8"),
    }


def _pr_to_dict(pr: PullRequest) -> dict[str, Any]:
    return asdict(pr)


def _pr_from_dict(raw: Mapping[str, Any]) -> PullRequest:
    issues = tuple(LinkedIssue(**i) for i in raw["issues"])
    return PullRequest(
        repo=raw["repo"],
        number=raw["number"],
        title=raw["title"],
        created_at=raw["created_at"],
        merged_at=raw["merged_at"],
        base_oid=raw["base_oid"],
        head_oid=raw["head_oid"],
        changed_files=raw["changed_files"],
        issues=issues,
        closing_total=raw["closing_total"],
        regex_refs=tuple(raw["regex_refs"]),
    )


class MiningStore:
    """Files of one run root."""

    def __init__(self, root: str) -> None:
        self.root = root

    # ---- paths

    def pr_path(self, dir_name: str) -> str:
        return os.path.join(self.root, "pr", dir_name)

    def listing_path(self, repo: str) -> str:
        return os.path.join(self.root, "listing", repo.replace("/", "__") + ".json")

    @property
    def state_path(self) -> str:
        return os.path.join(self.root, "state.jsonl")

    @property
    def run_path(self) -> str:
        return os.path.join(self.root, "run.json")

    @property
    def budget_path(self) -> str:
        return os.path.join(self.root, "budget.json")

    # ---- instances

    def has_instance(self, dir_name: str) -> bool:
        """Whether a complete instance directory exists (its metadata file is written last)."""
        return os.path.exists(os.path.join(self.pr_path(dir_name), "pr_meta.json"))

    def write_instance(self, inst: MinedInstance) -> None:
        """Write the directory under a temporary name, then rename it into place."""
        final = self.pr_path(inst.dir_name)
        tmp = final + ".tmp"
        shutil.rmtree(tmp, ignore_errors=True)
        files = instance_files(inst)
        order = [CORPUS_GZ, "queries.jsonl", "qrels/test.tsv", "pr_meta.json"]
        for name in order:
            _write_atomic(os.path.join(tmp, *name.split("/")), files[name])
        if os.path.isdir(final):
            shutil.rmtree(final)
        os.replace(tmp, final)

    def clean_partial(self) -> int:
        """Remove ``*.tmp`` instance directories left by a crash; return how many."""
        base = os.path.join(self.root, "pr")
        if not os.path.isdir(base):
            return 0
        n = 0
        for name in sorted(os.listdir(base)):
            if name.endswith(".tmp"):
                shutil.rmtree(os.path.join(base, name), ignore_errors=True)
                n += 1
        return n

    # ---- state

    def load_state(self) -> dict[str, dict[str, Any]]:
        """``{pull request key: row}`` from the state log (the last row of a key wins)."""
        rows: dict[str, dict[str, Any]] = {}
        if not os.path.exists(self.state_path):
            return rows
        with open(self.state_path, encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue  # a torn last line from a crash: that PR is redone
                rows[str(row["key"])] = row
        return rows

    def record(self, outcome: Outcome) -> None:
        """Append one state row (after the instance directory, if any, is in place)."""
        os.makedirs(self.root, exist_ok=True)
        with open(self.state_path, "a", encoding="utf-8") as handle:
            handle.write(dumps(outcome.row()) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def adopt_unrecorded(self, state: Mapping[str, Any]) -> list[Outcome]:
        """Outcomes for complete instance directories that have no state row (crash recovery)."""
        out: list[Outcome] = []
        base = os.path.join(self.root, "pr")
        if not os.path.isdir(base):
            return out
        for name in sorted(os.listdir(base)):
            if name.endswith(".tmp") or not self.has_instance(name):
                continue
            with open(os.path.join(base, name, "pr_meta.json"), encoding="utf-8") as handle:
                meta = json.load(handle)
            key = f"{meta['repo']}#{meta['pr']}"
            if key in state:
                continue
            out.append(
                Outcome(key, STATUS_MINED, "adopted", None, dict(meta.get("counters") or {}))
            )
        return out

    # ---- listings and run record

    def save_listing(self, repo: str, prs: Iterable[PullRequest], info: Mapping[str, Any]) -> None:
        """Store the merged pull requests of one repository (sorted by number)."""
        rows = [_pr_to_dict(p) for p in sorted(prs, key=lambda p: p.number)]
        doc = {
            "repo": repo,
            "current_name": str(info.get("nameWithOwner") or repo).lower(),
            "is_archived": bool(info.get("isArchived")),
            "is_fork": bool(info.get("isFork")),
            "prs": rows,
        }
        _write_atomic(self.listing_path(repo), (dumps(doc) + "\n").encode("utf-8"))

    def save_tombstone(self, repo: str, reason: str) -> None:
        """Record that a repository is gone (404): a rerun must not ask again."""
        doc = {"repo": repo, "current_name": repo.lower(), "missing": reason, "prs": []}
        _write_atomic(self.listing_path(repo), (dumps(doc) + "\n").encode("utf-8"))

    def has_listing(self, repo: str) -> bool:
        return os.path.exists(self.listing_path(repo))

    @property
    def sessions_path(self) -> str:
        return os.path.join(self.root, "sessions.jsonl")

    def log_session(self, row: Mapping[str, Any]) -> None:
        """Append what one session did (listing calls, outcomes); not part of the run's outputs."""
        os.makedirs(self.root, exist_ok=True)
        with open(self.sessions_path, "a", encoding="utf-8") as handle:
            handle.write(dumps(row) + "\n")

    def load_listing(self, repo: str) -> tuple[dict[str, Any], list[PullRequest]]:
        """``(header, pull requests)`` of a stored listing."""
        with open(self.listing_path(repo), encoding="utf-8") as handle:
            doc = json.load(handle)
        prs = [_pr_from_dict(r) for r in doc["prs"]]
        header = {k: v for k, v in doc.items() if k != "prs"}
        return header, prs

    def ensure_run(self, config_hash: str, created: str) -> dict[str, Any]:
        """Read ``run.json`` or create it (first creation only: the date never changes)."""
        if os.path.exists(self.run_path):
            with open(self.run_path, encoding="utf-8") as handle:
                doc: dict[str, Any] = json.load(handle)
            if doc.get("config_hash") != config_hash:
                raise ValueError(
                    "run root was created with a different config hash; use a new root "
                    f"({doc.get('config_hash')} != {config_hash})"
                )
            return doc
        doc = {"created": created, "config_hash": config_hash}
        _write_atomic(self.run_path, (dumps(doc) + "\n").encode("utf-8"))
        return doc

    def load_budget(self) -> dict[str, Any]:
        """Cumulative API budget over all sessions of the run root."""
        if not os.path.exists(self.budget_path):
            return {}
        with open(self.budget_path, encoding="utf-8") as handle:
            doc: dict[str, Any] = json.load(handle)
        return doc

    def add_budget(self, session: Mapping[str, Any]) -> dict[str, Any]:
        """Add one session's counters (numbers only) to the cumulative budget and store it."""
        total = self.load_budget()
        by_ep: dict[str, int] = dict(total.get("by_endpoint") or {})
        for k, v in (session.get("by_endpoint") or {}).items():
            by_ep[k] = by_ep.get(k, 0) + int(v)
        for k, v in session.items():
            if k == "by_endpoint":
                continue
            total[k] = (
                round(total.get(k, 0) + v, 3)
                if isinstance(v, float)
                else (total.get(k, 0) + int(v))
            )
        total["by_endpoint"] = dict(sorted(by_ep.items()))
        _write_atomic(self.budget_path, (dumps(total) + "\n").encode("utf-8"))
        return total


def stage_counts(
    listings: Mapping[str, list[PullRequest]], state: Mapping[str, Mapping[str, Any]]
) -> dict[str, Any]:
    """Per-stage yield from the stored listings and the state log (every count has a source)."""
    prs = [p for lst in listings.values() for p in lst]
    linked = [p for p in prs if p.issues]
    status: dict[str, int] = {}
    reasons: dict[str, int] = {}
    for row in state.values():
        status[row["status"]] = status.get(row["status"], 0) + 1
        if row["status"] == "quarantined":
            reasons[row["reason"]] = reasons.get(row["reason"], 0) + 1
    return {
        "repositories_listed": len(listings),
        "merged_prs": len(prs),
        "prs_with_closing_issue": len(linked),
        "pairs": sum(len(p.issues) for p in linked),
        "prs_mined_attempted": len(state),
        "status": dict(sorted(status.items())),
        "quarantine_reasons": dict(sorted(reasons.items())),
    }


def write_provenance(
    store: MiningStore,
    *,
    config: Mapping[str, Any],
    config_hash: str,
    created: str,
    authenticated: bool,
    counts: Mapping[str, Any],
    budget: Mapping[str, Any],
    population: Mapping[str, Any],
    code_commit: str,
) -> None:
    """Write ``provenance.json`` (source, endpoints, token description, counts per stage)."""
    doc = {
        "source": SOURCE,
        "endpoints": list(ENDPOINTS),
        "created": created,
        "token": {"authenticated": authenticated, "scope": TOKEN_SCOPE},
        "config": dict(config),
        "config_hash": config_hash,
        "code_commit": code_commit,
        "population": dict(population),
        "counts": dict(counts),
        "api_budget": dict(budget),
    }
    _write_atomic(os.path.join(store.root, "provenance.json"), (dumps(doc) + "\n").encode("utf-8"))
