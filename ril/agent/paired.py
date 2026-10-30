"""Locked, durable fixture pairs with conservative synthetic budget reservations."""

from __future__ import annotations

import argparse
import csv
import fcntl
import io
import json
import math
import os
import tempfile
from collections import Counter
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from ril.agent.contracts import ModelRequest, ModelResponse, RepairModel, digest
from ril.agent.fixtures import Fixture, make_fixtures
from ril.agent.grading import FixtureTestGrader
from ril.agent.pilot import live_gate, run_instance, source_manifest, summarize
from ril.agent.scripted import ScriptedRepair
from ril.agent.tools import FileRetrieval
from ril.bench.latency_harness import LATENCY_COLUMNS
from ril.evaluation.run import cpu_environment
from ril.retrieval.bm25_index import BM25Params

VERSION = "paired-fixture/v1"
Record = dict[str, Any]


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def atomic_write(path: Path, text: str) -> None:
    """Replace one complete file and synchronize it and its directory before returning."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".checkpoint-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        Path(name).unlink(missing_ok=True)


def save_checkpoint(path: Path, payload: Record) -> None:
    atomic_write(path, canonical({"sha256": digest(canonical(payload)), "payload": payload}) + "\n")


def load_checkpoint(path: Path) -> Record:
    try:
        envelope = json.loads(path.read_text())
        payload = envelope["payload"]
        if set(envelope) != {"sha256", "payload"} or not isinstance(payload, dict):
            raise ValueError("invalid checkpoint envelope")
        if envelope["sha256"] != digest(canonical(payload)):
            raise ValueError("checkpoint checksum differs")
    except (ValueError, KeyError, TypeError) as exc:
        raise ValueError("corrupt checkpoint; do not replay dispatches") from exc
    return payload


def finite(value: Any, *, positive: bool = False) -> bool:
    return (
        type(value) in (int, float)
        and math.isfinite(value)
        and (value > 0 if positive else value >= 0)
    )


def validate_config(cfg: Record) -> None:
    if cfg.get("mode") != "fixture":
        live_gate(cfg)
    required = {
        "experiment_id",
        "mode",
        "provisional",
        "seed",
        "temperature",
        "instances",
        "retrievers",
        "bootstrap_draws",
        "synthetic_pricing",
        "synthetic_cap_usd",
        "max_output_tokens",
        "output",
    }
    if set(cfg) != required:
        raise ValueError("missing or unknown paired configuration keys")
    if cfg["provisional"] != ["ADR-007", "ADR-008"]:
        raise ValueError("scaffold/model decisions remain provisional")
    if (
        type(cfg["seed"]) is not int
        or cfg["seed"] < 0
        or type(cfg["temperature"]) not in (int, float)
        or cfg["temperature"] != 0
    ):
        raise ValueError("fixture seed must be nonnegative integer and temperature zero")
    for field in ("bootstrap_draws", "max_output_tokens"):
        if type(cfg[field]) is not int or cfg[field] < 1:
            raise ValueError(field + " must be a positive integer")
    make_fixtures(cfg["instances"])
    if not isinstance(cfg["experiment_id"], str) or not cfg["experiment_id"]:
        raise ValueError("experiment identity required")
    if not isinstance(cfg["output"], str) or not cfg["output"]:
        raise ValueError("output directory required")
    if not finite(cfg["synthetic_cap_usd"], positive=True):
        raise ValueError("positive finite synthetic cap required")
    pricing = cfg["synthetic_pricing"]
    if (
        not isinstance(pricing, dict)
        or set(pricing) != {"input_per_million", "output_per_million"}
        or not all(finite(v, positive=True) for v in pricing.values())
    ):
        raise ValueError("positive finite synthetic rates required")
    retrievers = cfg["retrievers"]
    if not isinstance(retrievers, list) or len(retrievers) < 2:
        raise ValueError("at least two retrievers required")
    ids = []
    for ret in retrievers:
        if not isinstance(ret, dict) or set(ret) != {"id", "kind", "top_k", "k1", "b"}:
            raise ValueError("retriever requires id/kind/top_k/k1/b")
        if (
            not isinstance(ret["id"], str)
            or not ret["id"]
            or ret["kind"] not in ("none", "bm25", "oracle")
        ):
            raise ValueError("fixture retrieval id/kind invalid")
        if (
            type(ret["top_k"]) is not int
            or ret["top_k"] <= 0
            or not finite(ret["k1"], positive=True)
            or not finite(ret["b"])
            or ret["b"] > 1
        ):
            raise ValueError("invalid finite retrieval parameters")
        BM25Params(ret["k1"], ret["b"])
        ids.append(ret["id"])
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate retriever identity")


def fixture_identity(fixture: Fixture) -> Record:
    return {
        "task": asdict(fixture.task),
        "gold_files": list(fixture.gold_files),
        "test_sha256": digest(fixture.test_source),
        "reference_sha256": digest(canonical(fixture.reference_edits)),
        "grader": "trusted-unittest-v1:timeout=5",
    }


def quote(fixture: Fixture, cfg: Record) -> Record:
    # Every possible retrieved file fits this input bound; the output bound is checked at dispatch.
    text = fixture.task.issue + "".join(p + s for p, s in fixture.task.files.items())
    input_max = (len(text.encode()) + 3) // 4
    output_max = cfg["max_output_tokens"]
    pricing = cfg["synthetic_pricing"]
    amount = (
        input_max * pricing["input_per_million"] + output_max * pricing["output_per_million"]
    ) / 1_000_000
    if not finite(amount, positive=True):
        raise ValueError("quote must be finite and positive")
    return {"input_max": input_max, "output_max": output_max, "synthetic_usd_max": amount}


class QuoteViolation(ValueError):
    def __init__(self, response: ModelResponse):
        super().__init__(
            "quoted maximum exceeded; observed synthetic usage retained; dispatch blocked"
        )
        self.usage = asdict(response.usage)


class QuotedModel:
    def __init__(self, model: RepairModel, maximum: Record):
        self.model, self.maximum = model, maximum
        self.calls = 0

    def propose(self, request: ModelRequest) -> ModelResponse:
        self.calls += 1
        response = self.model.propose(request)
        usage = response.usage
        if (
            usage.input_tokens > self.maximum["input_max"]
            or usage.output_tokens > self.maximum["output_max"]
            or usage.synthetic_usd > self.maximum["synthetic_usd_max"]
        ):
            raise QuoteViolation(response)
        return response


def diagnose(row: Record, gold: Sequence[str]) -> Record:
    """Each gold file gets independent hits; edit use is an observable attempted-file proxy."""
    retrieved = {item["path"] for item in row["retrieved"]}
    attempted = {item["path"] for item in row["edits"]}
    flags = [
        {"path": path, "retrieved": path in retrieved, "attempted_edit": path in attempted}
        for path in gold
    ]
    failure = None
    if not row["resolved"]:
        if not any(f["retrieved"] for f in flags):
            failure = "not_retrieved"
        elif not any(f["attempted_edit"] and f["retrieved"] for f in flags):
            failure = "retrieved_not_used"
        else:
            failure = "used_wrong"
    return {
        "gold_file_hits": flags,
        "use_proxy": "attempted_edit_file",
        "gold_files_missing": sum(not flag["retrieved"] for flag in flags),
        "failure_diagnostic": failure,
    }


def key_for(instance_id: str, retriever_id: str) -> str:
    return canonical([instance_id, retriever_id])


def validate_state(state: Record, identity: Record, requested: Record) -> None:
    if set(state) != {"identity", "pairs", "environment"} or state["identity"] != identity:
        raise ValueError("resume identity mismatch: config/source/model/scaffold/tasks/grader/gold")
    if not isinstance(state["pairs"], dict) or set(state["pairs"]) != set(requested):
        raise ValueError("checkpoint requested pairs missing or unexpected")
    for key, expected in requested.items():
        entry = state["pairs"][key]
        if entry.get("quote") != expected["quote"] or entry.get("status") not in (
            "pending",
            "reserved",
            "complete",
            "blocked",
        ):
            raise ValueError("corrupt pair state or quote")
        if entry["status"] == "complete":
            row = entry.get("row")
            fixture = expected["fixture"]
            if not isinstance(row, dict) or type(row.get("resolved")) is not bool:
                raise ValueError("complete pair lacks a boolean independent grade")
            for field, value in expected["row_identity"].items():
                if row.get(field) != value:
                    raise ValueError("stored row identity differs: " + field)
            if row.get("gold_files") != list(fixture.gold_files) or any(
                row.get(k) != v for k, v in diagnose(row, fixture.gold_files).items()
            ):
                raise ValueError("stored diagnostic or gold identity differs")
            if row.get("row_sha256") != digest(
                canonical({k: v for k, v in row.items() if k != "row_sha256"})
            ):
                raise ValueError("stored row checksum differs")
            usage = row["usage"]
            if (
                usage.get("actual_usd") != 0
                or not finite(usage.get("synthetic_usd"))
                or usage["synthetic_usd"] > entry["quote"]["synthetic_usd_max"]
            ):
                raise ValueError("stored usage exceeds reservation")


def build_report(state: Record, cfg: Record) -> Record:
    pairs = state["pairs"]
    rows = [entry["row"] for entry in pairs.values() if entry["status"] == "complete"]
    counts = Counter(entry["status"] for entry in pairs.values())
    complete_instances = sum(
        all(
            pairs[key_for(f"fixture-{i:03d}", r["id"])]["status"] == "complete"
            for r in cfg["retrievers"]
        )
        for i in range(cfg["instances"])
    )
    missing = [
        {
            "pair": json.loads(key),
            "status": entry["status"],
            "reason": entry.get(
                "reason",
                "not_dispatched" if entry["status"] == "pending" else "dispatch_outcome_unknown",
            ),
        }
        for key, entry in pairs.items()
        if entry["status"] != "complete"
    ]
    complete = not missing
    summary = summarize(rows, draws=cfg["bootstrap_draws"], seed=cfg["seed"]) if complete else None
    diagnostics = []
    for ret in cfg["retrievers"]:
        selected = [r for r in rows if r["retriever_id"] == ret["id"]]
        failures = Counter(r["failure_diagnostic"] for r in selected if not r["resolved"])
        diagnostics.append(
            {
                "retriever_id": ret["id"],
                "requested": cfg["instances"],
                "completed": len(selected),
                "missing": cfg["instances"] - len(selected),
                "resolved": sum(r["resolved"] for r in selected),
                **{
                    name: failures[name]
                    for name in ("not_retrieved", "retrieved_not_used", "used_wrong")
                },
            }
        )
    reserved = sum(
        e["quote"]["synthetic_usd_max"] for e in pairs.values() if e["status"] != "pending"
    )
    observed = sum(r["usage"]["synthetic_usd"] for r in rows) + sum(
        e.get("observed_usage", {}).get("synthetic_usd", 0) for e in pairs.values()
    )
    return {
        "version": VERSION,
        "environment": state["environment"],
        "evidence_class": "measured_synthetic_plumbing_only",
        "real_instances": 0,
        "scientific_cost_discordance_mde": None,
        "published_scaffold_replication": False,
        "identity": state["identity"],
        "requested_pairs": len(pairs),
        "completed_pairs": len(rows),
        "requested_instances": cfg["instances"],
        "complete_paired_instances": complete_instances,
        "missing_pairs": missing,
        "state_counts": dict(counts),
        "statistics_status": "complete" if complete else "blocked_incomplete_pairs",
        "summary": summary,
        "diagnostics": diagnostics,
        "rows": rows,
        "budget": {
            "kind": "synthetic_test_only",
            "cap_usd": cfg["synthetic_cap_usd"],
            "reserved_usd": reserved,
            "observed_usd": observed,
            "observed_cap_exceeded": observed > cfg["synthetic_cap_usd"],
            "unknown_dispatches": sum(
                e["status"] in ("reserved", "blocked") and "observed_usage" not in e
                for e in pairs.values()
            ),
            "dispatch_halted": any(
                e.get("reason") == "quoted_maximum_exceeded" for e in pairs.values()
            ),
            "actual_usd": 0.0,
        },
    }


def csv_text(rows: Sequence[Record]) -> str:
    if not rows:
        return ""
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def publish(output: Path, report: Record) -> None:
    artifacts = {
        "results.json": canonical(report) + "\n",
        "diagnostics.csv": csv_text(report["diagnostics"]),
    }
    latency = []
    for ret in report["identity"]["config"]["retrievers"]:
        samples = [r["retrieval_ms"] for r in report["rows"] if r["retriever_id"] == ret["id"]]
        if samples:
            p50, p95, p99 = np.quantile(samples, [0.5, 0.95, 0.99])
            row = {
                **report["environment"],
                "query_set_id": "c4-synthetic-v1:" + ret["id"],
                "n_queries": len(samples),
                "warmup_n": 0,
                "cache_state": "cold",
                "stage": "fixture_retrieval_" + ret["kind"],
                "p50_ms": float(p50),
                "p95_ms": float(p95),
                "p99_ms": float(p99),
                "n": len(samples),
            }
            latency.append({column: row[column] for column in LATENCY_COLUMNS})
    artifacts["latency_log.csv"] = csv_text(latency)
    summary = report["summary"]
    if summary is not None:
        artifacts["paired.csv"] = csv_text(summary["discordance_rows"])
        artifacts["mcnemar.csv"] = csv_text(summary["comparisons"])
        artifacts["conditions.csv"] = csv_text(summary["conditions"])
    # Reports are derived caches. Never replace a differing recorded artifact on a later invocation.
    for name, text in artifacts.items():
        path = output / name
        if path.exists() and path.read_text() != text:
            raise ValueError("recorded report differs; use a new report path after recovery")
        if not path.exists():
            atomic_write(path, text)


def run_config(path: str, *, report_dir: str | None = None) -> Record:
    cfg = yaml.safe_load(Path(path).read_text())
    if not isinstance(cfg, dict):
        raise ValueError("configuration must be a mapping")
    validate_config(cfg)
    fixtures = make_fixtures(cfg["instances"])
    sources = source_manifest()
    wrapper = Path(__file__).resolve().parents[2] / "scripts/c_paired_runner.py"
    sources["entrypoint_sha256"] = digest(wrapper.read_text())
    chash = digest(canonical({"version": VERSION, "config": cfg}))
    execution = {
        "scaffold": VERSION,
        "model": "scripted-fixture-v1",
        "config_hash": chash,
        "source_sha256": digest(canonical(sources)),
    }
    identity = {
        "execution": execution,
        "config": cfg,
        "sources": sources,
        "fixture_sha256": digest(canonical([fixture_identity(f) for f in fixtures])),
    }
    requested = {}
    for fixture in fixtures:
        for ret in cfg["retrievers"]:
            requested[key_for(fixture.task.instance_id, ret["id"])] = {
                "fixture": fixture,
                "retriever": ret,
                "quote": quote(fixture, cfg),
                "row_identity": {
                    "instance_id": fixture.task.instance_id,
                    "retriever_id": ret["id"],
                    "repo": fixture.task.repo,
                    "role": "fixture",
                    "seed": cfg["seed"],
                    "temperature": cfg["temperature"],
                    "issue_sha256": digest(fixture.task.issue),
                    "snapshot_sha256": digest(json.dumps(dict(fixture.task.files), sort_keys=True)),
                    "execution_identity": execution,
                },
            }
    output = Path(cfg["output"])
    output.mkdir(parents=True, exist_ok=True)
    new_calls = 0
    reused = 0
    with (output / ".runner.lock").open("a+") as lock:
        # Hold the process lock through dispatch, grading, checkpoint and report publication.
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        checkpoint = output / "checkpoint.json"
        if checkpoint.exists():
            state = load_checkpoint(checkpoint)
            validate_state(state, identity, requested)
        else:
            state = {
                "identity": identity,
                "environment": cpu_environment(chash),
                "pairs": {
                    key: {"status": "pending", "quote": spec["quote"]}
                    for key, spec in requested.items()
                },
            }
            if any(output.iterdir()) and set(p.name for p in output.iterdir()) != {".runner.lock"}:
                raise ValueError("checkpoint missing in nonempty run directory; replay blocked")
            save_checkpoint(checkpoint, state)
            atomic_write(output / "hardware.json", canonical(state["environment"]) + "\n")
            atomic_write(output / "config.yaml", Path(path).read_text())
        model = ScriptedRepair(**cfg["synthetic_pricing"])
        for key, spec in requested.items():
            entry = state["pairs"][key]
            if entry["status"] == "complete":
                reused += 1
                continue
            if entry["status"] in ("reserved", "blocked"):
                continue
            if any(e.get("reason") == "quoted_maximum_exceeded" for e in state["pairs"].values()):
                entry["reason"] = "dispatch_halted_after_quote_violation"
                save_checkpoint(checkpoint, state)
                continue
            reserved = sum(
                e["quote"]["synthetic_usd_max"]
                for e in state["pairs"].values()
                if e["status"] != "pending"
            )
            if reserved + entry["quote"]["synthetic_usd_max"] > cfg["synthetic_cap_usd"]:
                entry["reason"] = "synthetic_budget_exhausted"
                save_checkpoint(checkpoint, state)
                continue
            entry["status"] = "reserved"
            entry.pop("reason", None)
            save_checkpoint(checkpoint, state)  # Must durably precede every dispatch.
            fixture, ret = spec["fixture"], spec["retriever"]
            quoted_model = QuotedModel(model, entry["quote"])
            try:
                tool = FileRetrieval(
                    fixture.task.files,
                    ret["kind"],
                    gold_files=fixture.gold_files if ret["kind"] == "oracle" else (),
                    params=BM25Params(ret["k1"], ret["b"]),
                )
                row = run_instance(
                    fixture.task,
                    retriever_id=ret["id"],
                    tool=tool,
                    model=quoted_model,
                    grader=FixtureTestGrader(fixture.test_source),
                    seed=cfg["seed"],
                    temperature=cfg["temperature"],
                    top_k=ret["top_k"],
                    execution_identity=execution,
                )
                if type(row["resolved"]) is not bool:
                    raise ValueError("independent grader must return a boolean resolved flag")
                row["gold_files"] = list(fixture.gold_files)
                row.update(diagnose(row, fixture.gold_files))
                row["row_sha256"] = digest(canonical(row))
                entry.update(status="complete", row=row)
            except Exception as exc:
                entry.update(
                    status="blocked", reason="dispatch_or_grade_failed:" + type(exc).__name__
                )
                if isinstance(exc, QuoteViolation):
                    entry["reason"] = "quoted_maximum_exceeded"
                    entry["observed_usage"] = exc.usage
                    for other in state["pairs"].values():
                        if other["status"] == "pending":
                            other["reason"] = "dispatch_halted_after_quote_violation"
                save_checkpoint(checkpoint, state)
                break
            finally:
                new_calls += quoted_model.calls
            save_checkpoint(checkpoint, state)
        validate_state(state, identity, requested)
        report = build_report(state, cfg)
        publish(Path(report_dir) if report_dir else output, report)
    return {
        "report": report,
        "invocation": {"new_model_calls": new_calls, "reused_pairs": reused, "actual_usd": 0.0},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument(
        "--report-dir", help="new immutable report path after interrupted execution"
    )
    parser.add_argument(
        "--audit-output", help="new invocation audit file; existing files are refused"
    )
    args = parser.parse_args()
    if args.audit_output and Path(args.audit_output).exists():
        parser.error("audit output already exists; use a new path")
    result = run_config(args.config, report_dir=args.report_dir)
    audit = {
        **result["invocation"],
        "config_hash": result["report"]["identity"]["execution"]["config_hash"],
        "statistics_status": result["report"]["statistics_status"],
        "completed_pairs": result["report"]["completed_pairs"],
    }
    if args.audit_output:
        atomic_write(Path(args.audit_output), canonical(audit) + "\n")
    print(canonical(audit))  # noqa: T201
    if audit["statistics_status"] != "complete":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
