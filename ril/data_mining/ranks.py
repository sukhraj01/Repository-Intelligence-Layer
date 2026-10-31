"""Post-mining rank audit using the unchanged pool-rank implementation."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

from ril.data_mining.github import atomic_json, digest
from ril.evaluation.runtime import require_runtime
from ril.evaluation.stats import clustered_mean_ci
from ril.training import pool_ranks
from ril.training.pool_reader import read_cache

ENCODER = {
    "name": "coderankembed",
    "revision": "3c4b60807d71f79b43f3c4363786d9493691f8b1",
    "max_tokens": 1024,
    "dtype": "float16",
    "text_form": "code",
}


def dense_audit_scores(out: Path) -> Path:
    """Use the pinned teacher and real CUDA gate on an admitted GPU runtime and real pilot."""
    try:
        require_runtime(cpu_only=False, require_gpu=True)
    except RuntimeError as exc:
        raise ValueError(str(exc)) from exc
    provenance = json.loads((out / "provenance.json").read_text())
    if provenance["source_kind"] != "live_github":
        raise ValueError("dense audit waits for a real pilot")
    from ril.training.train_jobs import teacher_score_fn

    identity = {"run_identity": provenance["run_identity"], "encoder": ENCODER}
    path = out / "dense" / "identity.json"
    if path.exists() and json.loads(path.read_text()) != identity:
        raise ValueError("dense resume identity mismatch")
    atomic_json(path, identity)
    score_fn, gate = teacher_score_fn("coderankembed", cut=1024, device="cuda", batch_size=32)
    instances = {}
    for ex in read_cache(str(out / "pool.jsonl.gz")):
        checkpoint = path.parent / f"{digest(ex.instance_id)}.json"
        texts = list(ex.positive_texts + ex.candidate_texts)
        expected = {
            "ids": list(ex.ids),
            "query_sha256": digest(ex.query),
            "texts_sha256": digest(texts),
        }
        if checkpoint.exists():
            row = json.loads(checkpoint.read_text())
            if any(row.get(k) != v for k, v in expected.items()):
                raise ValueError("dense checkpoint identity mismatch")
        else:
            row = {**expected, "scores": [float(v) for v in score_fn(ex, texts)]}
            atomic_json(checkpoint, row)
        instances[ex.instance_id] = row
    output = out / "dense_scores.json"
    atomic_json(output, {**identity, "instances": instances, "cuda_gate": gate})
    return output


def rank_audit(out: Path, *, dense_scores: Path | None = None) -> dict[str, Any]:
    """Measure BM25 and optionally identity-validated dense scores; never rewrite labels."""
    provenance = json.loads((out / "provenance.json").read_text())
    examples = read_cache(str(out / "pool.jsonl.gz"))
    supplied = json.loads(dense_scores.read_text()) if dense_scores else None
    if supplied is not None and supplied["run_identity"] != provenance["run_identity"]:
        raise ValueError("dense scores belong to another mining run")
    if supplied is not None and supplied.get("encoder") != ENCODER:
        raise ValueError("pinned CodeRankEmbed metadata required")
    groups = [e.repo for e in examples]
    rank_rows: list[dict[str, Any]] = []
    comparison = []
    teachers = ["bm25"] + (["coderankembed"] if supplied is not None else [])
    for teacher in teachers:
        indicators = []
        for ex in examples:
            ids = list(ex.ids)
            texts = list(ex.positive_texts + ex.candidate_texts)
            if teacher == "bm25":
                scores = pool_ranks.bm25_scores(texts, ex.query)
            else:
                assert supplied is not None
                row = supplied["instances"][ex.instance_id]
                if (
                    row["ids"] != ids
                    or row["query_sha256"] != digest(ex.query)
                    or row["texts_sha256"] != digest(texts)
                ):
                    raise ValueError("dense score query/candidate identity mismatch")
                scores = row["scores"]
                if not all(math.isfinite(float(v)) for v in scores):
                    raise ValueError("dense scores must be finite")
            ranks = pool_ranks.positive_ranks(ids, scores, ex.positive_ids)
            indicators.append(float(all(r["rank"] > 10 for r in ranks)))
            rank_rows.extend(
                {"instance_id": ex.instance_id, "repo": ex.repo, "teacher": teacher, **r}
                for r in ranks
            )
        point, low, high = (
            clustered_mean_ci(indicators, groups, draws=2000, seed=0)
            if indicators
            else (None, None, None)
        )
        comparison.append(
            {
                "dataset": "raw pilot",
                "teacher": teacher,
                "text_form": "code",
                "evidence": provenance["source_kind"],
                "n": len(examples),
                "share": point,
                "low": low,
                "high": high,
                "interval": "repository-clustered bootstrap; 2000 draws; seed 0",
            }
        )
    if supplied is None:
        comparison.append(
            {
                "dataset": "raw pilot",
                "teacher": "coderankembed",
                "text_form": "code",
                "evidence": "blocked: pinned dense scores absent",
                "n": 0,
                "share": None,
                "low": None,
                "high": None,
                "interval": "unavailable",
            }
        )
    # Archived project measurements, not new observations or interchangeable teachers.
    for dataset, teacher, form, n, share, low, high, interval in [
        (
            "published pool",
            "coderankembed",
            "code",
            160,
            0.153,
            0.088,
            0.222,
            "stratified bootstrap; weighted pool estimate",
        ),
        (
            "published pool",
            "bm25",
            "code",
            160,
            0.232,
            0.164,
            0.310,
            "stratified bootstrap; weighted pool estimate",
        ),
        (
            "never-filtered Verified",
            "swerankembed-small",
            "pool",
            457,
            0.193,
            0.157,
            0.232,
            "exact binomial",
        ),
        (
            "never-filtered Verified",
            "coderankembed",
            "code",
            457,
            0.357,
            0.313,
            0.403,
            "exact binomial",
        ),
    ]:
        comparison.append(
            {
                "dataset": dataset,
                "teacher": teacher,
                "text_form": form,
                "evidence": "archived E-POOL-RANKS; not rerun",
                "n": n,
                "share": share,
                "low": low,
                "high": high,
                "interval": interval,
            }
        )
    atomic_json(out / "ranks.json", rank_rows)
    atomic_json(out / "rank_comparison.json", comparison)
    with (out / "rank_comparison.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(comparison[0]))
        writer.writeheader()
        writer.writerows(comparison)
    report = {
        "source_kind": provenance["source_kind"],
        "config_hash": provenance["config_hash"],
        "run_identity": provenance["run_identity"],
        "n": len(examples),
        "seed": 0,
        "comparability": (
            "Synthetic cells validate mechanics only; "
            "corpus, teacher, text form and weighting differ."
        ),
        "dense_metadata": supplied.get("encoder") if supplied is not None else None,
        "comparison": comparison,
    }
    atomic_json(out / "rank_audit.json", report)
    return report
