"""Tables of the first parse-and-graph build, from the run logs (reads ``results/`` only).

Implements the reporting side of ``specs/parse_one_repo.md``: per-status edge counts, call-site
rule counts, the storage and expansion-latency measurements (ADR-011) and the extrapolation to the
largest repository. Every table row carries the machine it was measured on; numbers from
different machines are never merged.
"""

from __future__ import annotations

import csv
import json
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any


def read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def write_csv(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def status_rows(stats: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Edge counts per (machine, repository, family, status). ``stats`` is keyed ``host/repo``."""
    rows: list[dict[str, Any]] = []
    for key in sorted(stats):
        host, repo = key.split("/")
        s = stats[key]
        for family, counts in s["edges_by_type_and_status"].items():
            for status in ("resolved", "ambiguous", "unresolved", "external"):
                rows.append(
                    {
                        "machine": host,
                        "repo": repo,
                        "commit": s["commit"][:12],
                        "family": family,
                        "status": status,
                        "count": counts.get(status, 0),
                        "config_hash": s.get("config_hash", "")[:12],
                    }
                )
    return rows


def rule_rows(stats: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Invoke and import counts per derivation rule and status."""
    rows: list[dict[str, Any]] = []
    for key in sorted(stats):
        host, repo = key.split("/")
        for family, field in (("invoke", "invoke_by_rule"), ("import", "import_by_rule")):
            for rule, counts in stats[key][field].items():
                for status, n in counts.items():
                    rows.append(
                        {
                            "machine": host,
                            "repo": repo,
                            "family": family,
                            "rule": rule,
                            "status": status,
                            "count": n,
                        }
                    )
    return rows


def latency_lookup(
    rows: Sequence[dict[str, str]], host: str
) -> dict[tuple[str, str, str, str], tuple[str, str, str]]:
    """(label, backend, stage, cache_state) -> (p50, p95, p99), newest graph row of ``host``."""
    out: dict[tuple[str, str, str, str], tuple[str, str, str]] = {}
    for r in rows:
        parts = r["query_set_id"].split("-")
        if r["host"] != host or len(parts) != 4 or parts[0] != "graph":
            continue
        out[(parts[1], parts[2], r["stage"], r["cache_state"])] = (
            r["p50_ms"],
            r["p95_ms"],
            r["p99_ms"],
        )
    return out


def storage_rows(
    summaries: dict[str, dict[str, Any]], latency: Sequence[dict[str, str]], hosts: dict[str, str]
) -> list[dict[str, Any]]:
    """One row per (machine, repository, backend). ``hosts`` maps a machine tag to the host name
    recorded in the latency log."""
    rows: list[dict[str, Any]] = []
    for tag in sorted(summaries):
        lat = latency_lookup(latency, hosts[tag])
        for label, info in sorted(summaries[tag]["repos"].items()):
            for backend, b in sorted(info["backends"].items()):
                row: dict[str, Any] = {
                    "machine": tag,
                    "repo": label,
                    "backend": backend,
                    "write_s": b["write_s"],
                    "size_kb": round(b["size_bytes"] / 1024, 1),
                    "import_s": b.get("import_s", ""),
                    "load_s": b["load_s"],
                    "peak_rss_before_load_mb": b["rss_before_load_mb"],
                    "peak_rss_after_load_mb": b["peak_rss_after_load_mb"],
                    "peak_rss_after_queries_mb": b["peak_rss_after_queries_mb"],
                    "mean_units_reached_1hop": b["result_size_mean"]["1"],
                    "mean_units_reached_2hop": b["result_size_mean"]["2"],
                }
                for stage, short in (("graph_expand_1hop", "1hop"), ("graph_expand_2hop", "2hop")):
                    for state in ("warm", "cold"):
                        p = lat.get((label, backend, stage, state), ("", "", ""))
                        for name, value in zip(("p50_ms", "p95_ms", "p99_ms"), p, strict=True):
                            row[f"{short}_{state}_{name}"] = value
                rows.append(row)
    return rows


def _two_point(f_x: float, f_y: float, r_x: float, r_y: float, x: float) -> float:
    """Value at ``x`` of the line through (r_x, r_y) and (f_x, f_y)."""
    slope = (f_y - r_y) / (f_x - r_x)
    return r_y + slope * (x - r_x)


def extrapolation_rows(
    summary: dict[str, Any],
    source_lines: dict[str, int],
    machine: str,
    pre_run: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    """Predict the largest repository's build from the two small ones; compare with the measurement.

    Two-point linear fits of each quantity against source lines (and against units) through flask
    and requests, evaluated at django. Reported next to the measured value; the prediction error
    is the point of the table. ``pre_run`` holds the values written down before the first django run
    (source-lines basis), which used earlier runs of the two small repositories.
    """
    b = {k: summary["repos"][k]["build"] for k in ("flask", "requests", "django")}
    rows: list[dict[str, Any]] = []
    quantities: dict[str, Callable[[dict[str, Any]], float]] = {
        "parse_s": lambda x: x["seconds"]["parse"],
        "graph_build_s": lambda x: x["seconds"]["graph_build"],
        "history_s": lambda x: x["seconds"]["history"],
        "peak_rss_mb": lambda x: x["peak_rss_mb"],
        "artifact_mb": lambda x: x["artifact_bytes"] / 1e6,
        "edges": lambda x: x["edges"],
    }
    for name, get in quantities.items():
        measured = get(b["django"])
        for basis, key in (("source lines", None), ("units", "units")):
            if key is None:
                fx, rx, dx = (
                    source_lines["flask"],
                    source_lines["requests"],
                    source_lines["django"],
                )
            else:
                fx, rx, dx = (b["flask"][key], b["requests"][key], b["django"][key])
            predicted = _two_point(fx, get(b["flask"]), rx, get(b["requests"]), dx)
            rows.append(
                {
                    "machine": machine,
                    "quantity": name,
                    "fit_basis": basis,
                    "predicted_before_the_run": (pre_run or {}).get(name, "")
                    if key is None
                    else "",
                    "predicted_from_the_two_small_repos": round(predicted, 2),
                    "measured_django": round(measured, 2),
                    "measured_over_predicted": round(measured / predicted, 2) if predicted else "",
                }
            )
    return rows


def recovery_rows(
    stats: dict[str, dict[str, Any]],
    recovery: dict[str, Any],
    jedi: dict[str, Any],
    inspection: dict[str, Any],
) -> list[dict[str, Any]]:
    """One row per reported quantity of the four recovery definitions (none is chosen)."""
    rows: list[dict[str, Any]] = []

    def add(defn: str, scope: str, quantity: str, n: Any, value: Any, source: str) -> None:
        rows.append(
            {
                "definition": defn,
                "scope": scope,
                "quantity": quantity,
                "n": n,
                "value": value,
                "source": source,
            }
        )

    for key in sorted(stats):
        host, repo = key.split("/")
        inv = stats[key]["edges_by_type_and_status"]["invoke"]
        total = sum(inv.values())
        non_ext = total - inv["external"]
        src = f"p_stats_{repo}_{host}"
        add(
            "a",
            f"{repo} ({host})",
            "resolved / all call sites",
            total,
            round(inv["resolved"] / total, 4),
            src,
        )
        add(
            "a",
            f"{repo} ({host})",
            "resolved / non-external",
            non_ext,
            round(inv["resolved"] / non_ext, 4),
            src,
        )
        add(
            "a",
            f"{repo} ({host})",
            "(resolved + ambiguous) / non-external",
            non_ext,
            round((inv["resolved"] + inv["ambiguous"]) / non_ext, 4),
            src,
        )
    src_b = "p_flask_recovery"
    for v in recovery["recall_in_repo_callees"]:
        add(
            "b",
            f"flask: {v['view']}",
            "recall, resolved",
            v["n_pairs"],
            v["recall_resolved"],
            src_b,
        )
        add(
            "b",
            f"flask: {v['view']}",
            "recall, resolved or ambiguous",
            v["n_pairs"],
            v["recall_resolved_or_ambiguous"],
            src_b,
        )
    inc = recovery["recall_including_builtin_and_external_callees"]
    add(
        "b",
        "flask: all callees (in-repo, builtin, external)",
        "recall (name match for non-repo callees)",
        inc["n_pairs"],
        inc["recall"],
        src_b,
    )
    in_repo, c = inc["in_repo"], inc["builtin_c"]
    add(
        "b",
        "flask: in-repo + builtin callees",
        "recall (name match for builtin)",
        in_repo["n"] + c["n"],
        round(
            (in_repo["recovered_resolved"] + c["matched_by_terminal_name"])
            / (in_repo["n"] + c["n"]),
            4,
        ),
        src_b,
    )
    prec = recovery["precision_among_edges_whose_caller_executed"]
    add(
        "b",
        "flask",
        "precision among resolved edges whose caller executed",
        prec["caller_executed"],
        prec["precision"],
        src_b,
    )
    cov = recovery["suite_function_coverage_non_test_units"]["function_or_method"]
    add(
        "b",
        "flask suite",
        "function and method coverage (non-test units entered)",
        cov["units"],
        cov["share"],
        src_b,
    )
    for status in ("resolved", "ambiguous", "external", "unresolved"):
        j = jedi[status]
        add(
            "c",
            f"flask+requests, own status {status}",
            "Jedi agreement rate over answered",
            j["jedi_answered"],
            j["agreement_rate_over_answered"],
            "p_jedi_agreement",
        )
    add(
        "c",
        "flask+requests, all",
        "agreement rate",
        jedi["all"]["n"],
        jedi["all"]["agreement_rate"],
        "p_jedi_agreement",
    )
    for status, v in inspection["precision_by_status"].items():
        add(
            "d",
            f"flask+requests, recorded {status}",
            "claim holds (correct / decided)",
            v["n"],
            v["precision"],
            "p_edge_inspection",
        )
    for name, v in inspection["weighted_estimates"].items():
        add(
            "d", "flask+requests, population-weighted", name, "", v["estimate"], "p_edge_inspection"
        )
    return rows
