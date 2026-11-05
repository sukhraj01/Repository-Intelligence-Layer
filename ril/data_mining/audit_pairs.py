"""Text of the sampled pairs of the label sheet: issue, pull request title, function, diff hunks.

Implements ``docs/LABEL_AUDIT.md`` (the sheet of the noise audit, ``docs/RQ2_PROTOCOL.md`` O11).
The mined directories keep the issue text, the corpus (the function text at the base commit) and
the positives, but not the diff or the pull request title. Both are fetched again for the sampled
pull requests only, with the miner's own steps: the compare response of the same base and head,
the base-commit snapshot parsed by the project parser, and ``map_change``. The positive's
removed and inserted line counts are compared with the stored ones (``hunk_reproduced``), so a
hunk shown on the sheet is known to be the change that made the function a positive.

Nothing here decides who is a positive or what is shown; truncation lives in
``ril/evaluation/label_audit.py``. Kept compatible with Python 3.10 (the cluster's compute nodes).
"""

from __future__ import annotations

import gzip
import json
import os
import shutil
import tempfile
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from ril.data_mining.diff import (
    HUNK_RE,
    Comparison,
    FileChange,
    merge_pages,
    parse_comparison,
    parse_patch,
)
from ril.data_mining.files import CORPUS_GZ
from ril.data_mining.github_api import ApiClient, ApiError
from ril.data_mining.mapping import map_change, owner_of_insertion
from ril.data_mining.miner import COMPARE_MAX_PAGES, COMPARE_PAGE
from ril.data_mining.snapshot import SnapshotError, SnapshotProvider
from ril.parsing.code_unit import CodeUnit
from ril.parsing.repository_parser import parse_repository

Record = dict[str, Any]


def split_hunks(patch: str) -> list[tuple[int, str]]:
    """``(old start line, text)`` of each hunk of a file patch; text includes its ``@@`` header."""
    hunks: list[tuple[int, list[str]]] = []
    for line in patch.split("\n"):
        m = HUNK_RE.match(line)
        if m:
            hunks.append((int(m.group(1)), [line]))
        elif hunks:
            hunks[-1][1].append(line)
    return [(start, "\n".join(lines).rstrip("\n")) for start, lines in hunks]


def hunks_touching(patch: str, unit: CodeUnit, units: Sequence[CodeUnit]) -> list[str]:
    """Hunks of ``patch`` that remove or rewrite a line of ``unit`` or insert lines it owns.

    Uses the miner's rule (``map_change``): a removed old line belongs to the innermost
    definition holding it, an insertion to ``owner_of_insertion``. A hunk's context lines do not
    count, so a neighbouring edit three lines away is not attached to the function.
    """
    out: list[str] = []
    for _, text in split_hunks(patch):
        part = parse_patch(text)
        removed_in = any(unit.start_line <= n <= unit.end_line for n in part.removed)
        inserted_in = any(
            (owner := owner_of_insertion(units, ins)) is not None and owner.id == unit.id
            for ins in part.insertions
        )
        if removed_in or inserted_in:
            out.append(text)
    return out


def fetch_compare(client: ApiClient, repo: str, base: str, head: str) -> Record:
    """The merged compare response (all pages) of ``base...head``, raw."""
    owner, _, name = repo.partition("/")
    path = f"/repos/{owner}/{name}/compare/{base}...{head}"
    pages: list[Mapping[str, Any]] = []
    for page in range(1, COMPARE_MAX_PAGES + 1):
        doc = client.get_json(path, {"per_page": COMPARE_PAGE, "page": page})
        pages.append(doc)
        if len(doc.get("files") or []) < COMPARE_PAGE:
            break
    return merge_pages(pages)


def corpus_text(corpus_gz: str, pool_id: str) -> str | None:
    """Source of one function from a materialised corpus (the row text without its id line)."""
    needle = json.dumps(pool_id, ensure_ascii=False)
    with gzip.open(corpus_gz, "rt", encoding="utf-8") as handle:
        for line in handle:
            if needle in line:
                row = json.loads(line)
                if row.get("_id") == pool_id:
                    _, _, source = str(row["text"]).partition("\n")
                    return source
    return None


def _by_file(units: Sequence[CodeUnit]) -> dict[str, list[CodeUnit]]:
    out: dict[str, list[CodeUnit]] = {}
    for u in units:
        out.setdefault(u.file, []).append(u)
    return out


def other_functions(meta: Mapping[str, Any], pool_id: str) -> list[str]:
    """``path::qualified_name`` of the other non-test positives of the pull request, sorted."""
    return sorted(
        f"{p['path']}::{p['qualified_name']}"
        for p in meta["positives"]
        if p["in_corpus"] and not p["is_test"] and p["pool_id"] != pool_id
    )


def read_small(directory: str) -> tuple[str, Record]:
    """Stored query text and ``pr_meta`` of one mined directory."""
    with open(os.path.join(directory, "queries.jsonl"), encoding="utf-8") as handle:
        query = str(json.loads(handle.readline())["text"])
    with open(os.path.join(directory, "pr_meta.json"), encoding="utf-8") as handle:
        meta: Record = json.load(handle)
    return query, meta


def extract_pr(
    directory: str,
    pool_ids: Sequence[str],
    *,
    client: ApiClient,
    snapshots: SnapshotProvider,
    log: Callable[[str], None] = lambda _m: None,
) -> list[Record]:
    """Records for the sampled positives of one materialised mined directory.

    A failure of the network or the snapshot does not stop the draw: every requested pair still
    gets a record, with ``hunks`` saying why the diff is missing and ``hunk_reproduced`` false.
    """
    query, meta = read_small(directory)
    repo = str(meta["repo"])
    positives = {str(p["pool_id"]): p for p in meta["positives"]}
    corpus_gz = os.path.join(directory, CORPUS_GZ)
    base: Record = {"repo": repo, "pr": meta["pr"], "query": query}
    error = ""
    pr_title = ""
    comparison: Comparison | None = None
    raw_patches: dict[str, str] = {}
    units_by_file: dict[str, list[CodeUnit]] = {}
    try:
        owner, _, name = repo.partition("/")
        pr_title = str(
            client.get_json(f"/repos/{owner}/{name}/pulls/{meta['pr']}").get("title") or ""
        )
        doc = fetch_compare(client, repo, str(meta["base_ref_oid"]), str(meta["head_commit"]))
        comparison = parse_comparison(doc)
        raw_patches = {
            str(f["filename"]): str(f.get("patch") or "") for f in doc.get("files") or []
        }
        work = tempfile.mkdtemp(prefix="ril_audit_snap_")
        try:
            snapshots.materialize(repo, str(meta["base_commit"]), work)
            units_by_file = _by_file(parse_repository(work, repo).units)
        finally:
            shutil.rmtree(work, ignore_errors=True)
    except (ApiError, SnapshotError, ValueError, KeyError, OSError) as exc:
        error = f"{type(exc).__name__}: {str(exc)[:120]}"
        log(f"{directory}: {error}")
    out: list[Record] = []
    for pid in pool_ids:
        p = positives[pid]
        text = corpus_text(corpus_gz, pid)
        hunks = f"(diff not available: {error})" if error else ""
        reproduced = False
        if not error and comparison is not None:
            hunks, reproduced = _hunks_for(p, comparison, raw_patches, units_by_file)
        out.append(
            {
                **base,
                "pool_id": pid,
                "pr_title": pr_title,
                "path": p["path"],
                "qualified_name": p["qualified_name"],
                "unit_kind": p["unit_kind"],
                "unit_text": text
                if text is not None
                else "(function text not found in the corpus)",
                "hunks": hunks,
                "hunk_reproduced": reproduced,
                "other_functions": other_functions(meta, pid),
                "stored_removed_lines": p["removed_lines"],
                "stored_inserted_lines": p["inserted_lines"],
                "error": error,
            }
        )
    return out


def _hunks_for(
    p: Mapping[str, Any],
    comparison: Comparison,
    raw_patches: Mapping[str, str],
    units_by_file: Mapping[str, Sequence[CodeUnit]],
) -> tuple[str, bool]:
    """``(hunk text, reproduced)`` for one positive; reproduced = same unit and line counts."""
    units = units_by_file.get(str(p["path"]), ())
    unit = next((u for u in units if u.id == p["unit_id"]), None)
    change: FileChange | None = next(
        (c for c in comparison.python_files() if c.old_path == p["path"]), None
    )
    if unit is None or change is None:
        return "(the change to this function could not be matched to the diff)", False
    hit = next((h for h in map_change(units, change).hits if h.unit.id == unit.id), None)
    reproduced = (
        hit is not None
        and hit.removed_lines == p["removed_lines"]
        and hit.inserted_lines == p["inserted_lines"]
    )
    if change.status == "removed":
        return "(the whole file was deleted)", reproduced
    patch = raw_patches.get(change.path, "")
    hunks = hunks_touching(patch, unit, units)
    if not hunks:
        return "(no hunk of the diff touches this function)", False
    return "\n\n".join(hunks), reproduced
