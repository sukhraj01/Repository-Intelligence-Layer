"""Write the result tables of the first parse-and-graph build from the run logs.

Usage: p_tables.py  (reads results/logs and results/latency, writes results/tables/p_*.csv)
A thin wrapper around ``ril.analysis.graph_tables``.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ril.analysis.graph_tables import (  # noqa: E402
    extrapolation_rows,
    read_json,
    recovery_rows,
    rule_rows,
    status_rows,
    storage_rows,
    write_csv,
)
from ril.config.paths import results_dir  # noqa: E402

DATE = "2026-10-17"
SOURCE_LINES = {"flask": 17478, "requests": 10152, "django": 447663}  # git ls-files '*.py'


def main() -> int:
    logs = results_dir() / "logs"
    tables = results_dir() / "tables"
    stats = {}
    for host, repos in (
        ("local", ("flask", "requests", "django")),
        ("ada", ("flask", "requests", "django")),
    ):
        for repo in repos:
            path = logs / f"p_stats_{repo}_{host}_{DATE}.json"
            if path.exists():
                stats[f"{host}/{repo}"] = read_json(path)
    write_csv(tables / "p_graph_status_counts.csv", status_rows(stats))
    write_csv(tables / "p_graph_rule_counts.csv", rule_rows(stats))

    co_rows = []
    for key in sorted(stats):
        host, repo = key.split("/")
        cc = stats[key].get("co_change", {})
        for n, count in cc.get("pairs_with_support_at_least", {}).items():
            co_rows.append(
                {
                    "machine": host,
                    "repo": repo,
                    "min_commits_N": n,
                    "file_pairs": count,
                    "pairs_any_support": cc["pairs_any_support"],
                    "commits_used": cc["commits_used"],
                    "commits_skipped_over_cap": cc["commits_skipped_too_large"],
                    "cap_files_per_commit": cc["max_files_per_commit"],
                }
            )
    write_csv(tables / "p_co_change_counts.csv", co_rows)

    summaries = {}
    hosts = {}
    for tag in ("local", "ada"):
        path = logs / f"p_graph_measure_{tag}_{DATE}.json"
        if path.exists():
            summaries[tag] = read_json(path)
            hosts[tag] = summaries[tag]["host"]
    with (results_dir() / "latency" / "latency_log.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        latency = list(csv.DictReader(handle))
    write_csv(tables / "p_storage_measurements.csv", storage_rows(summaries, latency, hosts))

    pre = read_json(logs / f"p_django_prediction_{DATE}.json")["projection"]
    pre_run = {
        "parse_s": pre["parse_s_per_line"],
        "graph_build_s": pre["graph_build_s_per_line"],
        "history_s": pre["history_s_per_line"],
        "peak_rss_mb": pre["peak_rss_mb_per_line"],
        "artifact_mb": pre["artifact_mb_per_line"],
        "edges": pre["edges_per_line"],
    }
    extra = []
    for tag, summary in sorted(summaries.items()):
        extra.extend(
            extrapolation_rows(summary, SOURCE_LINES, tag, pre_run if tag == "local" else None)
        )
    write_csv(tables / "p_extrapolation.csv", extra)

    write_csv(
        tables / "p_recovery_summary.csv",
        recovery_rows(
            {k: v for k, v in stats.items() if k.startswith(("local/", "ada/"))},
            read_json(logs / f"p_flask_recovery_{DATE}.json"),
            read_json(logs / f"p_jedi_agreement_{DATE}.json"),
            read_json(logs / f"p_edge_inspection_summary_{DATE}.json"),
        ),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
