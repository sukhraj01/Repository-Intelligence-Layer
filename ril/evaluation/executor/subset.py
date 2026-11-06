"""The executable subset: which instances qualify, with the reason for every exclusion.

Implements D106 (``docs/RQ3_PILOT.md``). The rule is fixed before any retriever's patch is
evaluated: the environment builds from the specification without ``apt-get``; the gold patch
applied to the base commit makes every FAIL_TO_PASS test pass and every PASS_TO_PASS test still
pass; two repeated runs agree.
"""

from __future__ import annotations

import csv
import io
import json
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from ril.evaluation.executor.spec import InstanceSpec

SUBSET_VERSION = "executable-instances/v1"
RULE = (
    "environment builds from the specification with uv and no apt-get; the gold patch applied to "
    "the base commit makes every FAIL_TO_PASS test pass and every PASS_TO_PASS test pass; two "
    "repeated runs agree (same status for every named test)"
)


def read_rows(paths: Iterable[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for p in paths:
        for line in p.read_text().splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return rows


def classify(runs: Sequence[Mapping[str, Any]], expected_runs: int = 2) -> tuple[bool, str, str]:
    """(executable, reason, detail) from one instance's run rows."""
    by_run = {int(r["run"]): r for r in runs}
    if len(by_run) < expected_runs:
        return False, "incomplete", f"{len(by_run)} of {expected_runs} runs recorded"
    rs = [by_run[i] for i in sorted(by_run)][:expected_runs]
    for r in rs:
        if not r["built"]:
            stage = r["failure_stage"] or "unknown"
            return False, f"not_built:{stage}", r.get("failure_detail", "")
    for r in rs:
        if not r["patch_applied"]:
            return False, "gold_patch_not_applied", r.get("failure_detail", "")
    for r in rs:
        if not r["tests_ran"]:
            return (
                False,
                f"tests_not_run:{r['failure_stage'] or 'unknown'}",
                r.get("failure_detail", ""),
            )
    f2p_ok = [r["f2p"][0] == r["f2p"][1] and r["f2p"][1] > 0 for r in rs]
    p2p_ok = [r["p2p"][0] == r["p2p"][1] for r in rs]
    digests = {r["outcome_digest"] for r in rs}
    if len(digests) > 1 or len(set(f2p_ok)) > 1 or len(set(p2p_ok)) > 1:
        return False, "runs_disagree", f"digests {sorted(digests)}"
    if not f2p_ok[0]:
        r = rs[0]
        return False, "gold_f2p_failed", f"{r['f2p'][0]} of {r['f2p'][1]} pass"
    if not p2p_ok[0]:
        r = rs[0]
        return False, "gold_p2p_failed", f"{r['p2p'][0]} of {r['p2p'][1]} pass"
    return True, "executable", ""


def _built_in_all(runs: Sequence[Mapping[str, Any]], expected_runs: int) -> bool:
    return len(runs) >= expected_runs and all(r["built"] for r in runs[:expected_runs])


def build_subset(
    specs: Sequence[InstanceSpec],
    rows: Sequence[Mapping[str, Any]],
    *,
    run_id: str,
    config_hash: str,
    commit: str,
    spec_digest: str,
    expected_runs: int = 2,
) -> dict[str, Any]:
    """The subset document: members with cost, every exclusion with its reason, counts."""
    by_instance: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for r in rows:
        by_instance[r["instance_id"]].append(r)
    members: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    built = 0
    for s in specs:
        runs = sorted(by_instance.get(s.instance_id, []), key=lambda r: int(r["run"]))
        ok, reason, detail = classify(runs, expected_runs)
        built += 1 if _built_in_all(runs, expected_runs) else 0
        head = {
            "instance_id": s.instance_id,
            "repo": s.repo,
            "version": s.version,
            "difficulty": s.difficulty,
        }
        if ok:
            secs = [r["seconds"]["total"] for r in runs[:expected_runs]]
            members.append(
                {
                    **head,
                    "seconds_per_run": [round(x, 1) for x in secs],
                    "peak_rss_mb": max(r["peak_rss_mb"] for r in runs[:expected_runs]),
                    "departures": sorted({d for r in runs for d in r["departures"]}),
                }
            )
        else:
            excluded.append({**head, "reason": reason, "detail": detail[-200:]})
    reasons = Counter(e["reason"] for e in excluded)
    return {
        "version": SUBSET_VERSION,
        "rule": RULE,
        "run_id": run_id,
        "config_hash": config_hash,
        "commit": commit,
        "spec_digest": spec_digest,
        "counts": {
            "instances": len(specs),
            "built_in_both_runs": built,
            "executable": len(members),
            "excluded_by_reason": dict(sorted(reasons.items())),
        },
        "executable": members,
        "excluded": excluded,
    }


def repo_table(doc: Mapping[str, Any], specs: Sequence[InstanceSpec]) -> list[dict[str, Any]]:
    """Per repository: instances, built in both runs, executable."""
    total = Counter(s.repo for s in specs)
    execu = Counter(m["repo"] for m in doc["executable"])
    not_built = Counter(
        e["repo"] for e in doc["excluded"] if e["reason"].startswith(("not_built", "incomplete"))
    )
    out = []
    for repo in sorted(total):
        built = total[repo] - not_built[repo]
        out.append(
            {
                "repo": repo,
                "instances": total[repo],
                "built": built,
                "executable": execu[repo],
            }
        )
    return out


def table_csv(rows: Sequence[Mapping[str, Any]]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(rows[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()
