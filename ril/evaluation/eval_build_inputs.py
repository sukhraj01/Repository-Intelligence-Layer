"""Inputs of the evaluation-repository build (D100): e1-style configuration and base-commit table.

Implements the build half of ``docs/experiments/B.md`` E-EVAL-REPOS-BUILD. The selection itself
is fixed in ``configs/experiments/eval_repos_v1.json`` (``ril.analysis.eval_repo_selection``);
nothing here chooses or reorders. Folders come from the inventory's ``l2_queries_by_folder``;
a folder shared with other repositories is marked ``instances_of_repo`` so that only the
repository's own instances are built. Base commits come from the datasets' own metadata.
"""

from __future__ import annotations

import csv
import re
from collections.abc import Iterable, Mapping, Sequence
from copy import deepcopy
from typing import Any

Record = dict[str, Any]
ROLE = "test"
"""D100: the eight play the test role (no tuning, no replacement after a result)."""
PARQUET_OF_DATASET = {
    "SWE-bench-Live": (
        "live_full-00000-of-00002",
        "live_full-00001-of-00002",
        "live_test-00000-of-00001",
    ),
    "SWE-Bench-plus-plus": ("spp",),
}


def folders_of(inventory: str, repositories: Sequence[str]) -> list[tuple[str, str, str]]:
    """``(repository, dataset, folder)`` of every L2 folder holding one of the repositories."""
    with open(inventory, encoding="utf-8", newline="") as handle:
        rows = {r["repository"]: r for r in csv.DictReader(handle)}
    out: list[tuple[str, str, str]] = []
    for repo in repositories:
        for item in rows[repo]["l2_queries_by_folder"].split(";"):
            dataset, folder = item.rsplit("=", 1)[0].split("/", 1)
            out.append((repo, dataset, folder))
    return out


def build_config(template: Mapping[str, Any], folders: Iterable[tuple[str, str, str]]) -> Record:
    """The e1 configuration of the build: template parameters, one L2 spec per folder."""
    cfg = deepcopy(dict(template))
    cfg["experiment_id"] = "E-EVAL-REPOS-BUILD"
    cfg["status"] = "build only (no retrieval result is read)"
    cfg["note"] = (
        "Unit records and dense stores for the evaluation repositories of D100; BM25 parameters "
        "copied unchanged from the dev configuration. Role test: no tuning on these repositories."
    )
    cfg["folders"] = [
        {
            "role": ROLE,
            "dataset": dataset,
            "folder": folder,
            "repo": repo,
            "levels": ["L2"],
            "units": True,
            "instances_of_repo": True,
        }
        for repo, dataset, folder in folders
    ]
    return cfg


def instance_prefix(repo: str) -> str:
    return repo.replace("/", "__").lower() + "-"


def build_meta(
    folders: Iterable[tuple[str, str, str]],
    ids_all: Mapping[str, Any],
    tables: Mapping[str, Sequence[Mapping[str, Any]]],
) -> tuple[dict[str, Record], list[Record]]:
    """``(meta, missing)``: base commit and patch per instance (``tables``: dataset to rows)."""
    by_id = {dataset: {str(r["instance_id"]): r for r in rows} for dataset, rows in tables.items()}
    meta: dict[str, Record] = {}
    missing: list[Record] = []
    for repo, dataset, folder in folders:
        ids = ids_all[f"LEVEL-2/{dataset}/{folder}"]["qrels_query_ids"]
        for inst in sorted(i for i in ids if i.lower().startswith(instance_prefix(repo))):
            row = by_id.get(dataset, {}).get(inst)
            if row is None or not row.get("base_commit"):
                missing.append({"instance": inst, "reason": "no_metadata", "dataset": dataset})
                continue
            if not re.fullmatch(r"[0-9a-f]{40}", str(row["base_commit"])):
                missing.append({"instance": inst, "reason": "bad_base_commit", "dataset": dataset})
                continue
            meta[inst] = {
                "repo": repo,
                "base_commit": row["base_commit"],
                "patch": row.get("patch") or "",
                "dataset": dataset,
                "folder": folder,
            }
    return meta, missing
