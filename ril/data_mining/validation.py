"""Stage M1 jobs: agreement with the published pool and the hand-check file.

Implements ``docs/experiments/B.md`` E-MINE-PILOT question 1. :func:`agreement_job` reads the mined
run root and, for every mined directory that the published pool also holds, the pool's directory
by range request; :func:`handcheck_file` prints, for a seeded sample of mined pull requests, the
issue title, the changed hunks of the Python files and the mined positives, for a human to read.
Nothing here judges correctness.

Kept compatible with Python 3.10 (the cluster's compute nodes).
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from ril.data_mining import agreement
from ril.data_mining.diff import merge_pages
from ril.data_mining.github_api import ApiClient
from ril.data_mining.miner import COMPARE_MAX_PAGES, COMPARE_PAGE
from ril.data_mining.pack import list_dirs
from ril.data_mining.store import MiningStore, dumps
from ril.training import pool_ranks as pr

Fetch = Callable[[str, int, int], bytes]
MAX_PATCH_LINES = 60
"""Lines of one file's patch printed in the hand-check file (the rest is marked as cut)."""


def _mined_meta(store: MiningStore, name: str) -> dict[str, Any]:
    with open(os.path.join(store.pr_path(name), "pr_meta.json"), encoding="utf-8") as handle:
        meta: dict[str, Any] = json.load(handle)
    return meta


def _mined_corpus_ids(store: MiningStore, name: str) -> frozenset[str]:
    ids = set()
    with open(os.path.join(store.pr_path(name), "corpus.jsonl"), encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                ids.add(str(json.loads(line)["_id"]))
    return frozenset(ids)


def agreement_job(
    root: str,
    url: str,
    members: Mapping[str, Mapping[str, Mapping[str, Any]]],
    *,
    fetch: Fetch = pr.http_fetch,
) -> dict[str, Any]:
    """Rows and the table for every mined directory that is also a published-pool directory."""
    store = MiningStore(root)
    names = list_dirs(root)
    both = [n for n in names if n in members]
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for name in both:
        try:
            pool = pr.fetch_instance(url, members[name], name, fetch)
        except (OSError, ValueError) as exc:
            errors.append({"dir": name, "error": f"{type(exc).__name__}: {str(exc)[:120]}"})
            continue
        rows.append(
            agreement.compare_pr(
                _mined_meta(store, name),
                _mined_corpus_ids(store, name),
                frozenset(pool.positives),
                frozenset(pool.ids),
            )
        )
    metas = [_mined_meta(store, n) for n in names]
    return {
        "mined_directories": len(names),
        "also_in_pool": len(both),
        "pool_fetch_errors": errors,
        "mined_positives_in_test_files": agreement.mined_test_share(metas),
        "table": agreement.summarize(rows),
        "rows": rows,
    }


def handcheck_sample(root: str, n: int, seed: int) -> list[str]:
    """``n`` mined directories with at least one corpus positive, in the seeded order."""
    store = MiningStore(root)
    have = [
        d
        for d in list_dirs(root)
        if any(p["in_corpus"] for p in _mined_meta(store, d)["positives"])
    ]
    return sorted(have, key=lambda d: pr.seeded_key(seed, d))[:n]


def fetch_patches(client: ApiClient, repo: str, base: str, head: str) -> dict[str, str]:
    """``{path: raw patch}`` of the Python files of ``base...head`` (all pages)."""
    owner, _, name = repo.partition("/")
    path = f"/repos/{owner}/{name}/compare/{base}...{head}"
    pages = []
    for page in range(1, COMPARE_MAX_PAGES + 1):
        doc = client.get_json(path, {"per_page": COMPARE_PAGE, "page": page})
        pages.append(doc)
        if len(doc.get("files") or []) < COMPARE_PAGE:
            break
    files = merge_pages(pages).get("files") or []
    return {
        str(f["filename"]): str(f.get("patch") or "")
        for f in files
        if str(f["filename"]).endswith(".py")
    }


def render_entry(
    meta: Mapping[str, Any], title: str, patches: Mapping[str, str], index: int
) -> str:
    """One hand-check block: issue title, changed hunks, mined positives (as stored)."""
    out = [f"## {index}. {meta['repo']}#{meta['pr']}", "", f"Issue title: {title}", ""]
    out.append(f"Merge base used: `{meta['base_commit']}`; head: `{meta['head_commit']}`")
    out.append("")
    out.append("### Changed hunks (Python files)")
    for path, patch in sorted(patches.items()):
        lines = patch.splitlines()
        out += ["", f"`{path}`", "", "```diff", *lines[:MAX_PATCH_LINES]]
        if len(lines) > MAX_PATCH_LINES:
            out.append(f"... ({len(lines) - MAX_PATCH_LINES} more lines cut)")
        out.append("```")
    out += ["", "### Mined positives", ""]
    for p in meta["positives"]:
        place = "corpus" if p["in_corpus"] else "side table"
        flag = " (test file)" if p["is_test"] else ""
        out.append(
            f"- `{p['pool_id']}`: {p['unit_kind']}, {place}{flag}, "
            f"-{p['removed_lines']}/+{p['inserted_lines']} lines, unit {p['unit_lines']} lines"
        )
    out.append(f"- added functions (not positives): {meta['counters']['added_function_defs']}")
    out.append("")
    return "\n".join(out)


def handcheck_file(root: str, client: ApiClient, n: int, seed: int) -> tuple[str, list[str]]:
    """The hand-check markdown for ``n`` seeded mined pull requests and the directories used."""
    store = MiningStore(root)
    chosen = handcheck_sample(root, n, seed)
    parts = [
        f"# Hand-check: {len(chosen)} mined pull requests (seed {seed})",
        "",
        "For a human to read. It lists what the miner stored beside the changed hunks fetched "
        "again from the compare endpoint; it does not claim that the positives are right.",
        "",
    ]
    for i, name in enumerate(chosen, start=1):
        meta = _mined_meta(store, name)
        with open(os.path.join(store.pr_path(name), "queries.jsonl"), encoding="utf-8") as handle:
            query = json.loads(handle.readline())
        title = str(query["text"]).split("\n", 1)[0]
        patches = fetch_patches(
            client, str(meta["repo"]), str(meta["base_commit"]), str(meta["head_commit"])
        )
        parts.append(render_entry(meta, title, patches, i))
    return "\n".join(parts) + "\n", chosen


def write_json(path: str, doc: Mapping[str, Any]) -> None:
    """Deterministic JSON file (sorted keys)."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        handle.write(dumps(doc) + "\n")
    os.replace(tmp, path)


def pool_members_for(listing_path: str) -> tuple[str, dict[str, dict[str, Mapping[str, Any]]]]:
    """``(url, {directory: members})`` from the pool listing."""
    from ril.training.pool_reader import load_listing

    url, groups = load_listing(listing_path)
    return url, groups


__all__: Sequence[str] = (
    "agreement_job",
    "handcheck_file",
    "handcheck_sample",
    "pool_members_for",
    "render_entry",
    "write_json",
)
