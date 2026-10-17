"""Counts-only run log for pilot E1/E2 (config hashes, seed, hardware, item counts)."""

from __future__ import annotations

import json
import os
from collections import Counter
from collections.abc import Sequence
from typing import Any

Record = dict[str, Any]


def build_run_log(
    path: str,
    *,
    config_hash: str,
    full_config_hash: str,
    seed: int,
    draws: int,
    chunk_runs: Sequence[Record],
    unit_runs: Sequence[Record],
    full_rows: Sequence[Record],
    job_ids: str,
    code_commit: str,
    unit_failures_dir: str,
) -> None:
    """Write the log: what ran, where, with which configuration, and the item counts."""
    hardware = sorted({json.dumps(r.get("hardware", {}), sort_keys=True) for r in chunk_runs})
    failures: dict[str, Any] = {}
    fail_path = os.path.join(unit_failures_dir, "unit_failures.json")
    if os.path.exists(fail_path):
        with open(fail_path, encoding="utf-8") as handle:
            failures = json.load(handle).get("failures", {})
    doc: Record = {
        "experiment": "E-BM25-REPRO and E-LABEL-NOISE (exploratory pilots)",
        "config_hash": config_hash,
        "full_l2_config_hash": full_config_hash,
        "seed": seed,
        "bootstrap_draws": draws,
        "ada_job_ids": job_ids,
        "code_commit": code_commit,
        "hardware_chunk_stage": [json.loads(h) for h in hardware],
        "chunk_items": len(chunk_runs),
        "chunk_queries_by_role_level": dict(
            Counter({f"{r['role']}/{r['level']}": 0 for r in chunk_runs})
        ),
        "unit_instances": len(unit_runs),
        "unit_instances_by_role": dict(Counter(r["role"] for r in unit_runs)),
        "unit_failures": {k: v for k, v in failures.items() if v},
        "full_l2_queries": len(full_rows),
        "licence": "counts, ranks, ids, paths and line numbers only; no dataset or source text",
    }
    q_by: Counter[str] = Counter()
    for r in chunk_runs:
        q_by[f"{r['role']}/{r['level']}"] += r["queries"]
    doc["chunk_queries_by_role_level"] = dict(q_by)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(doc, handle, indent=1, sort_keys=True)
        handle.write("\n")
