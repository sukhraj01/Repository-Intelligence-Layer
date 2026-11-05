"""A scripted three-condition pilot; real benchmark execution fails closed."""

from __future__ import annotations

import argparse
import itertools
import json
import math
import os
import time
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from functools import cache
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from ril.agent.contracts import ModelRequest, PatchGrader, RepairModel, RetrievalTool, Task, digest
from ril.agent.fixtures import make_fixtures
from ril.agent.grading import FixtureTestGrader
from ril.agent.scripted import ScriptedRepair
from ril.agent.tools import FileRetrieval
from ril.bench.latency_harness import LATENCY_COLUMNS, append_rows
from ril.evaluation.run import cpu_environment
from ril.evaluation.stats import (
    clustered_mean_ci,
    clustered_paired_diff_ci,
    exact_mcnemar_p,
    mde_mcnemar,
)
from ril.retrieval.bm25_index import BM25Params

VERSION = "scripted-agent-pilot/v1"
Record = dict[str, Any]


def live_gate(config: Mapping[str, Any], environ: Mapping[str, str] | None = None) -> None:
    """Require a fully specified reviewed execution path before any future live adapter call."""
    env = os.environ if environ is None else environ
    needed = [
        key
        for key in ("model_revision", "scaffold_revision", "harness_revision", "adapter")
        if not isinstance(config.get(key), str) or not config[key].strip()
    ]
    cap = config.get("spend_cap_usd")
    if (
        not isinstance(cap, (int, float))
        or isinstance(cap, bool)
        or not math.isfinite(cap)
        or cap <= 0
    ):
        needed.append("positive spend cap")
    credential_env = config.get("credential_env")
    if not isinstance(credential_env, str) or not env.get(credential_env):
        needed.append("credential environment")
    if needed:
        raise ValueError("live execution blocked: " + ", ".join(needed))
    raise ValueError(
        "live execution blocked: reviewed scaffold and benchmark adapter not installed"
    )


def run_instance(
    task: Task,
    *,
    retriever_id: str,
    tool: RetrievalTool,
    model: RepairModel,
    grader: PatchGrader,
    seed: int,
    temperature: float,
    top_k: int,
    execution_identity: Mapping[str, str] | None = None,
) -> Record:
    """The model sees issue plus tool output; tests and reference edits stay with the grader."""
    if type(seed) is not int or seed < 0 or not math.isfinite(temperature) or temperature < 0:
        raise ValueError("seed and temperature must be nonnegative and finite")
    if type(top_k) is not int or top_k <= 0:
        raise ValueError("top_k must be a positive integer")
    began = time.perf_counter()
    retrieval_began = time.perf_counter()
    context = tuple(tool.search(task.issue, top_k))
    retrieval_ms = (time.perf_counter() - retrieval_began) * 1000
    if len(context) > top_k or len({f.path for f in context}) != len(context):
        raise ValueError("retriever returned duplicate or over-limit files")
    for file in context:
        if task.files.get(file.path) != file.content:
            raise ValueError("retrieved file must match the task snapshot")
        if file.score is not None and not math.isfinite(file.score):
            raise ValueError("retrieval scores must be finite when supplied")
    request = ModelRequest(task.instance_id, task.issue, context, seed, temperature)
    response = model.propose(request)
    grade = grader.grade(task, response.edits)
    return {
        "instance_id": task.instance_id,
        "repo": task.repo,
        "role": task.role,
        "retriever_id": retriever_id,
        "seed": seed,
        "temperature": temperature,
        "execution_identity": dict(execution_identity or {}),
        "issue_sha256": digest(task.issue),
        "snapshot_sha256": digest(json.dumps(dict(task.files), sort_keys=True)),
        "request_sha256": digest(json.dumps(asdict(request), sort_keys=True)),
        "retrieved": [
            {"path": f.path, "sha256": digest(f.content), "score": f.score} for f in context
        ],
        "edits": [asdict(e) for e in response.edits],
        "patch_sha256": digest(json.dumps([asdict(e) for e in response.edits], sort_keys=True)),
        "resolved": grade.resolved,
        "grade_status": grade.status,
        "test_log": grade.test_log,
        "usage": {**asdict(response.usage), "kind": "synthetic_surrogate", "actual_usd": 0.0},
        "retrieval_ms": retrieval_ms,
        "wall_seconds": time.perf_counter() - began,
    }


@cache
def _fixture_mde(n: int, discordance: float) -> float | None:
    return mde_mcnemar(n, discordance)


def summarize(rows: Sequence[Record], *, draws: int, seed: int) -> Record:
    """Strict identity pairing, clustered intervals, exact discordance and illustrative MDE."""
    grouped: dict[str, dict[str, Record]] = {}
    for row in rows:
        condition, identity = row["retriever_id"], row["instance_id"]
        group = grouped.setdefault(condition, {})
        if identity in group:
            raise ValueError("duplicate instance/condition pair")
        group[identity] = row
    if len(grouped) < 2:
        raise ValueError("at least two paired conditions required")
    identities = sorted(next(iter(grouped.values())))
    if not identities or any(set(group) != set(identities) for group in grouped.values()):
        raise ValueError("missing paired instance")
    reference = next(iter(grouped.values()))
    for group in grouped.values():
        for identity in identities:
            for key in (
                "repo",
                "role",
                "seed",
                "temperature",
                "issue_sha256",
                "snapshot_sha256",
                "execution_identity",
            ):
                if group[identity][key] != reference[identity][key]:
                    raise ValueError("paired task or fixed configuration differs")
    repos = [reference[i]["repo"] for i in identities]
    conditions: list[Record] = []
    comparisons: list[Record] = []
    discordance_rows: list[Record] = []
    for condition, group in sorted(grouped.items()):
        selected = [group[i] for i in identities]
        mean, low, high = clustered_mean_ci(
            [int(r["resolved"]) for r in selected], repos, draws=draws, seed=seed
        )
        conditions.append(
            {
                "retriever_id": condition,
                "n": len(selected),
                "resolved_count": sum(r["resolved"] for r in selected),
                "resolved_rate": mean,
                "resolved_low": low,
                "resolved_high": high,
                "input_tokens": sum(r["usage"]["input_tokens"] for r in selected),
                "output_tokens": sum(r["usage"]["output_tokens"] for r in selected),
                "synthetic_usd": sum(r["usage"]["synthetic_usd"] for r in selected),
                "actual_usd": 0.0,
                "wall_seconds": sum(r["wall_seconds"] for r in selected),
            }
        )
    for a, b in itertools.combinations(sorted(grouped), 2):
        first = [int(grouped[a][i]["resolved"]) for i in identities]
        second = [int(grouped[b][i]["resolved"]) for i in identities]
        only_a = sum(x and not y for x, y in zip(first, second, strict=True))
        only_b = sum(y and not x for x, y in zip(first, second, strict=True))
        discordance_rows.extend(
            {
                "instance_id": identity,
                "first": a,
                "second": b,
                "first_resolved": bool(x),
                "second_resolved": bool(y),
                "discordant": x != y,
            }
            for identity, x, y in zip(identities, first, second, strict=True)
        )
        d, dl, dh = clustered_mean_ci(
            [int(x != y) for x, y in zip(first, second, strict=True)],
            repos,
            draws=draws,
            seed=seed,
        )
        effect, low, high = clustered_paired_diff_ci(second, first, repos, draws=draws, seed=seed)
        comparisons.append(
            {
                "first": a,
                "second": b,
                "n": len(identities),
                "only_first": only_a,
                "only_second": only_b,
                "discordance": d,
                "discordance_low": dl,
                "discordance_high": dh,
                "effect_second_minus_first": effect,
                "effect_low": low,
                "effect_high": high,
                "exact_mcnemar_p": exact_mcnemar_p(only_a, only_b),
                "illustrative_fixture_mde": {str(n): _fixture_mde(n, d) for n in (302, 432)},
            }
        )
    return {
        "conditions": conditions,
        "comparisons": comparisons,
        "discordance_rows": discordance_rows,
    }


def source_manifest() -> Record:
    """Checksum executed first-party code as well as the git state, including dirty sources."""
    root = Path(__file__).resolve().parents[2]
    paths = sorted((root / "ril/agent").glob("*.py")) + [
        root / "ril/evaluation/stats.py",
        root / "ril/evaluation/run.py",
        root / "ril/retrieval/bm25_index.py",
    ]
    files = {str(p.relative_to(root)): digest(p.read_text()) for p in paths}
    return {"files": files, "sha256": digest(json.dumps(files, sort_keys=True))}


def run_config(path: str) -> Record:
    cfg = yaml.safe_load(Path(path).read_text())
    if not isinstance(cfg, dict):
        raise ValueError("configuration must be a mapping")
    if cfg.get("mode") != "fixture":
        live_gate(cfg)
    allowed = {
        "experiment_id",
        "mode",
        "provisional",
        "seed",
        "temperature",
        "instances",
        "conditions",
        "retriever",
        "bootstrap_draws",
        "synthetic_pricing",
        "output",
        "log_path",
    }
    if set(cfg) != allowed:
        raise ValueError("missing or unknown pilot configuration keys")
    if cfg["provisional"] != ["ADR-007", "ADR-008"]:
        raise ValueError("scaffold and model decisions must remain provisional")
    if type(cfg["seed"]) is not int or cfg["seed"] < 0 or cfg["temperature"] != 0:
        raise ValueError("scripted fixture requires nonnegative integer seed and temperature zero")
    if cfg["conditions"] != ["none", "bm25", "oracle"]:
        raise ValueError("pilot requires all three conditions in registered order")
    if type(cfg["bootstrap_draws"]) is not int or cfg["bootstrap_draws"] < 1:
        raise ValueError("bootstrap draws must be positive")
    ret = cfg["retriever"]
    if set(ret) != {"top_k", "k1", "b"} or type(ret["top_k"]) is not int or ret["top_k"] < 1:
        raise ValueError("retriever needs positive top_k and BM25 parameters")
    pricing = cfg["synthetic_pricing"]
    if set(pricing) != {"input_per_million", "output_per_million"} or any(
        type(v) not in (float, int) or not math.isfinite(v) or v < 0 for v in pricing.values()
    ):
        raise ValueError("synthetic rates must be finite and nonnegative")
    fixtures = make_fixtures(cfg["instances"])
    chash = digest(json.dumps({"version": VERSION, "config": cfg}, sort_keys=True))
    env, rows = cpu_environment(chash), []
    sources = source_manifest()
    identity = {
        "scaffold": VERSION,
        "model": "scripted-fixture-v1",
        "source_sha256": sources["sha256"],
        "config_hash": chash,
    }
    began = time.perf_counter()
    model = ScriptedRepair(**pricing)
    for fixture in fixtures:
        grader = FixtureTestGrader(fixture.test_source)
        for condition in cfg["conditions"]:
            tool = FileRetrieval(
                fixture.task.files,
                condition,
                gold_files=fixture.gold_files if condition == "oracle" else (),
                params=BM25Params(ret["k1"], ret["b"]),
            )
            row = run_instance(
                fixture.task,
                retriever_id=condition,
                tool=tool,
                model=model,
                grader=grader,
                seed=cfg["seed"],
                temperature=cfg["temperature"],
                top_k=ret["top_k"],
                execution_identity=identity,
            )
            # Gold identities are joined only after the model call and independent grading.
            row["gold_files"] = list(fixture.gold_files)
            rows.append(row)
    result = {
        "version": VERSION,
        "experiment_id": cfg["experiment_id"],
        "config_hash": chash,
        "environment": env,
        "source_manifest": sources,
        "evidence_class": "measured_synthetic_plumbing_only",
        "real_instances": 0,
        "scientific_cost_discordance_mde": None,
        "usage_kind": "synthetic_surrogate_bytes_divided_by_four",
        "scaffold": "scripted-fixture-v1",
        "published_scaffold_replication": False,
        "seed": cfg["seed"],
        "bootstrap_draws": cfg["bootstrap_draws"],
        "provisional": cfg["provisional"],
        "wall_seconds": time.perf_counter() - began,
        "rows": rows,
        **summarize(rows, draws=cfg["bootstrap_draws"], seed=cfg["seed"]),
    }
    output = Path(cfg["output"])
    output.mkdir(parents=True, exist_ok=True)
    (output / "config.yaml").write_text(Path(path).read_text())
    for filename, value in (("results.json", result), ("hardware.json", env)):
        (output / filename).write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")
    log = Path(cfg["log_path"])
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    timing = []
    for condition in cfg["conditions"]:
        samples = [r["retrieval_ms"] for r in rows if r["retriever_id"] == condition]
        p50, p95, p99 = np.quantile(samples, [0.5, 0.95, 0.99])
        timing.append(
            {
                **env,
                "query_set_id": "c3-synthetic-v1:" + condition,
                "n_queries": len(samples),
                "warmup_n": 0,
                "cache_state": "cold",
                "stage": "fixture_retrieval_" + condition,
                "p50_ms": float(p50),
                "p95_ms": float(p95),
                "p99_ms": float(p99),
                "n": len(samples),
            }
        )
    append_rows(output / "latency_log.csv", LATENCY_COLUMNS, timing)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    result = run_config(args.config)
    print(json.dumps({"config_hash": result["config_hash"], "real_instances": 0}))  # noqa: T201  # CLI emits machine-readable summary JSON.


if __name__ == "__main__":
    main()
