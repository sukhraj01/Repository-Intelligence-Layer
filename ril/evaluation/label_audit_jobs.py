"""Stages of the label-sheet build: draw, extract, sheets (run on the cluster where the store is).

Implements ``docs/LABEL_AUDIT.md`` and ``docs/RQ2_PROTOCOL.md`` section 7. Each stage is
deterministic from its inputs and the seed, and the extraction is resumable (one JSON line per
pair, appended after each pull request). ``scripts/label_audit_build.py`` is the thin wrapper.
Kept compatible with Python 3.10 (the cluster's compute nodes).
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping
from typing import Any

from ril.evaluation import label_audit as la

Record = dict[str, Any]


def read_jsonl(path: str) -> list[Record]:
    with open(path, encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def file_sha256(path: str) -> str:
    import hashlib

    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def draw_job(
    ranks_bm25: str,
    ranks_dense: str | None,
    *,
    seed: int,
    per_stratum: int = 200,
    overlap_total: int = 100,
) -> tuple[la.Draw, Record]:
    """The seeded draw from the BM25 rank rows, and the numbers that describe it."""
    dense = read_jsonl(ranks_dense) if ranks_dense else []
    population = la.candidates_from_ranks(read_jsonl(ranks_bm25), dense)
    d = la.draw(population, seed=seed, per_stratum=per_stratum, overlap_total=overlap_total)
    dense_dirs = {c.directory for c in population if c.dense_rank is not None}
    sampled_dense = {s: 0 for s in la.STRATA}
    for c in d.pairs:
        if c.dense_rank is not None:
            sampled_dense[c.stratum] += 1
    doc: Record = {
        "seed": seed,
        "k": la.K_FILTER,
        "ranks_bm25_sha256": file_sha256(ranks_bm25),
        "ranks_dense_sha256": file_sha256(ranks_dense) if ranks_dense else None,
        "population_pairs": len(population),
        "population_directories": len({c.directory for c in population}),
        "population_by_stratum": d.population,
        "sample_by_stratum": d.sample,
        "requested_per_stratum": per_stratum,
        "overlap": len(d.overlap),
        "own": {r: len(v) for r, v in d.own.items()},
        "sample_directories": len({c.directory for c in d.pairs}),
        "sample_repositories": len({c.directory.rsplit("-", 1)[0] for c in d.pairs}),
        "dense_ranks_exist_for_directories": len(dense_dirs),
        "dense_ranks_exist_for_population_pairs": sum(
            1 for c in population if c.dense_rank is not None
        ),
        "dense_ranks_exist_for_sampled_pairs": sampled_dense,
    }
    return d, doc


def extract_job(
    d: la.Draw,
    store_root: str,
    work: str,
    out_jsonl: str,
    *,
    client: Any,
    snapshots: Any,
    log: Callable[[str], None] = lambda _m: None,
) -> Record:
    """Fill ``out_jsonl`` with one record per sampled pair; pairs already in it are kept."""
    from ril.data_mining import cas
    from ril.data_mining.audit_pairs import extract_pr

    done: set[str] = set()
    if os.path.exists(out_jsonl):
        done = {str(r["pair_id"]) for r in read_jsonl(out_jsonl)}
    by_dir = la.group_by_directory(d.ids, d)
    todo = {k: [i for i in v if i not in done] for k, v in by_dir.items()}
    todo = {k: v for k, v in todo.items() if v}
    mat = cas.materialise(store_root, os.path.join(work, "mat"), sorted(todo))
    log(f"materialised {mat['materialised']} directories, {len(todo)} pull requests to extract")
    errors = 0
    for n, (directory, ids) in enumerate(sorted(todo.items()), 1):
        pool_ids = [d.ids[i].positive for i in ids]
        recs = extract_pr(
            os.path.join(work, "mat", "pr", directory),
            pool_ids,
            client=client,
            snapshots=snapshots,
            log=log,
        )
        with open(out_jsonl, "a", encoding="utf-8") as handle:
            for i, rec in zip(ids, recs, strict=True):
                rec["pair_id"] = i
                rec["directory"] = directory
                errors += bool(rec["error"])
                handle.write(json.dumps(rec, sort_keys=True, ensure_ascii=False) + "\n")
        log(f"[{n}/{len(todo)}] {directory}: {len(ids)} pair(s)")
    return {"pull_requests_extracted": len(todo), "pairs_with_error": errors, "materialise": mat}


def sheets_job(d: la.Draw, raw_jsonl: str, sheets_dir: str, key_dir: str) -> Record:
    """Write the three sheets and the key from the extracted records; return their hashes."""
    records: dict[str, Record] = {str(r["pair_id"]): r for r in read_jsonl(raw_jsonl)}
    for pid, c in d.ids.items():
        if pid in records and records[pid]["pool_id"] != c.positive:
            raise ValueError(f"{pid}: extracted record is for another positive")
    sheets = la.build_sheets(d, records)
    os.makedirs(sheets_dir, exist_ok=True)
    os.makedirs(key_dir, exist_ok=True)
    hashes: dict[str, str] = {}
    sizes: dict[str, int] = {}
    for name, data in sheets.items():
        with open(os.path.join(sheets_dir, name), "wb") as handle:
            handle.write(data)
        hashes[name] = la.sha256(data)
        sizes[name] = len(data)
    reproduced = {i: bool(r["hunk_reproduced"]) for i, r in records.items()}
    key = la.key_csv(d, reproduced)
    with open(os.path.join(key_dir, "key.csv"), "wb") as handle:
        handle.write(key)
    hashes["key.csv"] = la.sha256(key)
    return {
        "sha256": hashes,
        "bytes": sizes,
        "hunk_reproduced": sum(reproduced.values()),
        "pairs_with_error": sum(1 for r in records.values() if r["error"]),
        "function_text_missing": sum(
            1
            for r in records.values()
            if str(r["unit_text"]).startswith("(function text not found")
        ),
    }


def truncation_rules() -> Mapping[str, int]:
    """The truncation limits in force (recorded with the sample, to check the instructions)."""
    return {
        "issue_body_chars": la.ISSUE_BODY_CHARS,
        "function_text_chars": la.FUNCTION_TEXT_CHARS,
        "diff_hunk_chars": la.HUNK_CHARS,
        "other_functions_max": la.OTHER_FUNCTIONS_MAX,
        "pull_request_title_chars": la.PR_TITLE_CHARS,
    }
