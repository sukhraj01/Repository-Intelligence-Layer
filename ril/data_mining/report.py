"""Markdown tables of a finished run root (stage M2), and its measured unit costs (stage M4).

Implements ``docs/experiments/B.md`` E-MINE-PILOT questions 2, 3 and 5. Reads only the files of
the run root (``summary.json``, the API event logs, ``sessions.jsonl``, the directory sizes), so
every figure in the report can be reproduced with the quoted command.

Kept compatible with Python 3.10 (the cluster's compute nodes).
"""

from __future__ import annotations

import glob
import json
import os
from collections import Counter
from collections.abc import Mapping
from typing import Any

from ril.data_mining.pack import list_dirs


def api_totals(root: str) -> dict[str, Any]:
    """Calls by endpoint, sleeps and slept seconds, from every ``api_events*.jsonl`` of the run."""
    calls: Counter[str] = Counter()
    sleeps: Counter[str] = Counter()
    slept = 0.0
    for path in sorted(glob.glob(os.path.join(root, "api_events*.jsonl"))):
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if ev.get("event") == "call":
                    calls[str(ev.get("endpoint"))] += 1
                elif ev.get("event") == "sleep":
                    sleeps[str(ev.get("why"))] += 1
                    slept += float(ev.get("seconds") or 0)
    return {
        "calls_by_endpoint": dict(sorted(calls.items())),
        "calls": sum(calls.values()),
        "sleeps_by_reason": dict(sorted(sleeps.items())),
        "slept_seconds": round(slept, 1),
    }


def session_seconds(root: str) -> dict[str, float]:
    """Summed listing and mining seconds of the sessions that logged them."""
    totals = {"listing": 0.0, "mining": 0.0}
    path = os.path.join(root, "sessions.jsonl")
    if not os.path.exists(path):
        return totals
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                secs = json.loads(line).get("seconds") or {}
                totals["listing"] += float(secs.get("listing") or 0)
                totals["mining"] += float(secs.get("mining") or 0)
    return totals


def disk_use(root: str) -> dict[str, float]:
    """Bytes and files of the mined directories and of the listings of a run root."""

    def tree(path: str) -> tuple[int, int]:
        size = files = 0
        for base, _dirs, names in os.walk(path):
            for n in names:
                size += os.path.getsize(os.path.join(base, n))
                files += 1
        return size, files

    pr_bytes, pr_files = tree(os.path.join(root, "pr"))
    ls_bytes, ls_files = tree(os.path.join(root, "listing"))
    dirs = len(list_dirs(root))
    return {
        "mined_dirs": dirs,
        "pr_bytes": pr_bytes,
        "pr_files": pr_files,
        "bytes_per_mined_pr": pr_bytes / dirs if dirs else 0.0,
        "files_per_mined_pr": pr_files / dirs if dirs else 0.0,
        "listing_bytes": ls_bytes,
        "listing_files": ls_files,
    }


def _row(cells: list[Any]) -> str:
    return "| " + " | ".join(str(c) for c in cells) + " |"


def _pct(x: float) -> str:
    return f"{100 * x:.1f}%"


def render(summary: Mapping[str, Any]) -> str:
    """The M2 tables as markdown: yield, positives, parse failures, links, selection."""
    y = summary["yield"]
    out = ["### Yield", "", _row(["stage", "count"]), _row(["---", "---"])]
    for key in (
        "repositories_listed",
        "merged_prs",
        "prs_with_closing_issue",
        "pairs",
        "prs_mined_attempted",
        "prs_mined",
        "positives_total",
        "added_function_defs_total",
    ):
        out.append(_row([key, y.get(key, "")]))
    out += [
        "",
        "Status of attempted pull requests: " + json.dumps(y.get("status", {}), sort_keys=True),
    ]
    if y.get("quarantine_reasons"):
        out.append("Quarantine reasons: " + json.dumps(y["quarantine_reasons"], sort_keys=True))
    out += ["", "### Mined pull requests (one row per property)", ""]
    out += [_row(["property", "n", "median", "mean", "p90", "max"]), _row(["---"] * 6)]
    mined = summary["mined"]
    for prop in ("positives_per_pr", "py_files_changed", "hunk_lines_touched", "corpus_units"):
        d = mined.get(prop, {})
        out.append(
            _row([prop, d.get("n"), d.get("median"), d.get("mean"), d.get("p90"), d.get("max")])
        )
    pf = summary["parse_failures"]
    out += [
        "",
        "### Parse failures",
        "",
        "Quarantined for an unparseable changed file: "
        f"{pf['quarantined_unparseable_changed_file']} of {pf['attempted']} attempted "
        f"({_pct(pf['share_of_attempted'])}); by cause: "
        + json.dumps(pf["by_cause_changed_file"], sort_keys=True)
        + ". Unparsed files of mined corpora, by cause: "
        + json.dumps(pf["unparsed_corpus_files_by_cause_in_mined"], sort_keys=True)
        + f". Mined pull requests with at least one unparsed corpus file: "
        f"{pf['mined_prs_with_unparsed_corpus_file']} of {pf['mined_prs']}.",
    ]
    tp = summary["test_positives"]
    out += [
        "",
        "### Test-file positives (the pool has none)",
        "",
        f"{tp['in_test_files']} of {tp['mined_positives']} corpus positives ({_pct(tp['share'])}) "
        f"are in test files; {tp['prs_with_test_positive']} of {tp['prs']} mined pull requests "
        f"have a test positive and {tp['prs_only_test_positives']} have only test positives.",
    ]
    lq = summary["links"]
    mult = lq["multiplicity"]
    out += [
        "",
        "### Links",
        "",
        f"Pairs {mult['pairs']}, issues {mult['issues']}, pull requests with an issue "
        f"{mult['prs_with_issue']}; issues with several pull requests "
        f"{mult['issues_with_several_prs']}; pull requests with several issues "
        f"{mult['prs_with_several_issues']}; pull requests whose body names an issue the closing "
        f"list lacks {lq['prs_with_regex_ref_not_in_closing_refs']}; closing list cut at the limit "
        f"{lq['prs_with_closing_refs_cut_at_limit']}; mined pairs with the issue edited after the "
        f"pull request was created {lq['issue_edited_after_pr_created']} of {lq['mined_pairs']} "
        f"({_pct(lq['issue_edited_share'])}).",
    ]
    sel = summary["selection"]
    s = sel["summary"]
    shares = sorted(r["kept_share"] for r in sel["per_repo"] if r["linked_prs"])
    median_share = shares[len(shares) // 2] if shares else None
    out += [
        "",
        "### Selection by the published pool",
        "",
        f"{s['kept_by_pool']} of {s['linked_prs']} linked pull requests of {s['repos']} "
        f"repositories are in the published pool ({_pct(s['kept_share'])}); pool pull requests "
        f"with no closing reference found: {s['published_not_linked']}. "
        "Median per-repository kept share: "
        f"{median_share}.",
        "",
        _row(
            [
                "property",
                "kept n",
                "dropped n",
                "kept median",
                "dropped median",
                "difference",
                "95% interval",
                "excludes 0",
            ]
        ),
        _row(["---"] * 8),
    ]
    for prop, d in sel["differences"].items():
        out.append(
            _row(
                [
                    prop,
                    d["kept_n"],
                    d["dropped_n"],
                    d.get("kept_median"),
                    d.get("dropped_median"),
                    d["difference"],
                    d["interval"],
                    d["excludes_zero"],
                ]
            )
        )
    return "\n".join(out) + "\n"


def scale_inputs(
    summary: Mapping[str, Any],
    costs: Mapping[str, Any],
    listing_seconds: float,
    shell_free_bytes: float | None = None,
) -> dict[str, float]:
    """Measured per-unit quantities for :func:`ril.data_mining.scale.extrapolate`.

    ``costs`` is the ``report.costs.json`` of a run root (API totals, session seconds, disk use);
    ``listing_seconds`` is the summed seconds of every listing job (shards included), the pages
    are the GraphQL calls in the event logs.
    """
    y = summary["yield"]
    api = costs["api"]["calls_by_endpoint"]
    attempted = float(y["prs_mined_attempted"])
    pages = float(api.get("graphql", 0))
    disk = costs["disk"]
    return {
        "merged_prs_per_repo": float(y["merged_prs"]) / float(y["repositories_listed"]),
        "pr_per_listing_page": 50.0,
        "graphql_cost_per_listing_page": 1.0,
        "listing_seconds_per_page": listing_seconds / pages,
        "rest_calls_per_attempted_pr": float(api.get("repos/compare", 0)) / attempted,
        "graphql_cost_per_attempted_pr": 0.0,
        "mining_seconds_per_attempted_pr": float(costs["seconds"]["mining"]) / attempted,
        "mined_share": float(y["prs_mined"]) / attempted,
        "bytes_per_mined_pr": float(disk["bytes_per_mined_pr"]),
        "files_per_mined_pr": float(disk["files_per_mined_pr"]),
    }
