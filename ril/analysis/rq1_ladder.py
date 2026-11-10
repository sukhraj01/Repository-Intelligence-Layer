"""Tables of the RQ1 ladder: rung values, paired differences, controls, latency, regression check.

Exploratory. Implements ``docs/experiments/B.md`` E-RQ1-LADDER. Reads the per-instance files of
``ril.evaluation.rq1_ladder`` (development set only) and the stored latency log. Values are
percentages (mean over queries of nDCG@10 at L2, Recall@100 at L3, each with the other metric
beside it, D71); differences are percentage points.

Intervals: the decision interval is the cluster-robust t interval over repositories with R - 1
degrees of freedom (D136; every query its own cluster below three repositories, ``MIN_CLUSTERS``),
and the percentile bootstrap that resamples whole repositories (D17) is reported beside it. Below
three repositories the bootstrap beside it is query-level. Differences between rungs are paired on
the query.

Latency is read from stored rows only (``results/latency/latency_log.csv``): per stage the row
that the latency configuration names (query-set id, host prefix, cache state), the latest of the
matching rows; a stage without a row is listed as not measured and never interpolated.

Kept compatible with Python 3.10.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
from typing import Any

import numpy as np

from ril.analysis.cluster_t import cluster_t
from ril.analysis.e3_tables import COLUMN, DRAWS, Boot, EvalTable, load_eval_dir
from ril.analysis.rq2_final import ALPHA, MIN_CLUSTERS
from ril.evaluation.e3_eval import read_eval
from ril.evaluation.rq1_ladder import all_keys

Record = dict[str, Any]
Arr = np.ndarray[Any, Any]

PRIMARY_READING = "units_all_nomod"
"""D18's reading for graph questions; ``units_all`` is reported beside it."""
READINGS_SHOWN = ("units_all_nomod", "units_all")
LEVEL_PRIMARY = {"L2": "ndcg10", "L3": "recall100"}
METRICS = ("ndcg10", "recall100")

LADDER: tuple[tuple[str, str, str], ...] = (
    ("R1", "dense alone", "r1|dense"),
    ("R2", "plus BM25 by RRF", "p|first"),
    ("R3", "plus same-file expansion", "p|sfscore|b"),
    ("R4", "plus typed graph expansion (non-contain edges)", "p|graph|e"),
    ("R5", "plus recency prior", "r|graph|e"),
)
"""Rung id, label and metric key. R3 is size-matched to the stored graph (edge set b), R4 is the
non-contain expansion; R4 is an alternative expansion of the same budget compared with R3 and its
controls, not stacked on R3 (the stacked test is the owner's item, Q30)."""

PATH: dict[str, tuple[str, ...]] = {
    "R1": ("R1",),
    "R2": ("R1", "R2"),
    "R3": ("R1", "R2", "R3"),
    "R4": ("R1", "R2", "R4"),
    "R5": ("R1", "R2", "R4", "R5"),
}
"""Stages a query passes through at each rung. R4 branches from R2: the typed expansion is an
alternative to the same-file expansion of R3, not stacked on it."""
PRED_PAIR: dict[str, str] = {
    "R2": "R2 minus R1",
    "R3": "R3 minus R2",
    "R4": "R4 minus R2",
    "R5": "R5 minus R4",
}
"""The paired difference that gives each rung's gain over its predecessor on ``PATH``."""

# (name, key, reference key, kind): kind says what the difference is read as
PAIRS: tuple[tuple[str, str, str, str], ...] = (
    ("R2 minus R1", "p|first", "r1|dense", "adjacent"),
    ("R3 minus R2", "p|sfscore|b", "p|first", "adjacent"),
    ("R4 minus R3", "p|graph|e", "p|sfscore|b", "adjacent"),
    ("R4 minus R2", "p|graph|e", "p|first", "adjacent"),
    ("R5 minus R4", "r|graph|e", "p|graph|e", "adjacent"),
    ("R4 minus same-file control", "p|graph|e", "p|sfscore|e", "graph_control"),
    ("R4 minus same-file chance", "p|graph|e", "p|sfrand|e", "graph_control"),
    ("R4 minus top-M control", "p|graph|e", "p|topm|e", "graph_control"),
    ("stored graph minus same-file control", "p|graph|b", "p|sfscore|b", "graph_control"),
    ("stored graph minus first stage", "p|graph|b", "p|first", "other"),
    ("same-file (b) minus first stage", "p|sfscore|b", "p|first", "other"),
    ("recency on RRF", "r|first", "p|first", "recency"),
    ("recency on typed graph", "r|graph|e", "p|graph|e", "recency"),
    ("recency on same-file", "r|sfscore|b", "p|sfscore|b", "recency"),
    ("RRF minus BM25", "p|first", "ref|bm25", "other"),
    ("score-level stored graph minus same-file control", "s|graph|b", "s|sfscore|b", "regression"),
)


def _vector(tab: EvalTable, idx: Arr, key: str, reading: str, metric: str) -> Arr:
    out: Arr = 100.0 * tab.metrics[idx, tab.index[key], COLUMN[(reading, metric)]]
    return out


def level_panel(tab: EvalTable, level: str, reading: str) -> tuple[Arr, list[str]]:
    """Rows of one level's queries with a gold unit under ``reading``, and their repositories."""
    first = tab.keys[0]
    col = COLUMN[(reading, "ndcg10")]
    ok = tab.mask(level=level) & np.isfinite(tab.metrics[:, tab.index[first], col])
    idx = np.nonzero(ok)[0]
    return idx, [str(tab.rows[i]["repo"]) for i in idx]


def _quantiles(boots: Arr) -> tuple[float, float]:
    lo, hi = np.quantile(boots, [ALPHA / 2, 1 - ALPHA / 2])
    return float(lo), float(hi)


def interval_fields(x: Arr, repos: list[str], boot: Boot) -> Record:
    """Mean, decision interval and the bootstrap beside it for the vector ``x``."""
    n_repos = len(set(repos))
    clustered = n_repos >= MIN_CLUSTERS
    ct = cluster_t(x, repos)
    lo, hi = ct.interval(ALPHA)
    w = boot.cluster if clustered else boot.micro
    blo, bhi = _quantiles(np.asarray(w @ x))
    return {
        "n": int(x.size),
        "repos": n_repos,
        "mean": float(x.mean()),
        "ci_kind": ct.kind,
        "df": ct.df,
        "se": ct.se,
        "t_lo": lo,
        "t_hi": hi,
        "boot_kind": "repository-clustered" if clustered else "query-level",
        "boot_lo": blo,
        "boot_hi": bhi,
    }


def verdict(lo: float, hi: float) -> str:
    """Reading of a paired difference from its decision interval."""
    if lo > 0:
        return "gain"
    if hi < 0:
        return "loss"
    return "not distinguishable"


def summary_rows(tab: EvalTable, label: str, seed: int = 0, draws: int = DRAWS) -> list[Record]:
    """Value of every key at every level, both readings, both metrics."""
    rows: list[Record] = []
    for level in ("L2", "L3"):
        for reading in READINGS_SHOWN:
            idx, repos = level_panel(tab, level, reading)
            if idx.size < 2:
                continue
            boot = Boot(repos, seed, draws)
            for key in tab.keys:
                for metric in METRICS:
                    x = _vector(tab, idx, key, reading, metric)
                    rows.append(
                        {
                            "label": label,
                            "level": level,
                            "reading": reading,
                            "metric": metric,
                            "primary": metric == LEVEL_PRIMARY[level]
                            and reading == PRIMARY_READING,
                            "key": key,
                            **interval_fields(x, repos, boot),
                        }
                    )
    return rows


def compare_rows(tab: EvalTable, label: str, seed: int = 0, draws: int = DRAWS) -> list[Record]:
    """Paired differences of ``PAIRS`` at every level, both readings, both metrics."""
    rows: list[Record] = []
    for level in ("L2", "L3"):
        for reading in READINGS_SHOWN:
            idx, repos = level_panel(tab, level, reading)
            if idx.size < 2:
                continue
            boot = Boot(repos, seed, draws)
            for name, key, ref, kind in PAIRS:
                for metric in METRICS:
                    d = _vector(tab, idx, key, reading, metric) - _vector(
                        tab, idx, ref, reading, metric
                    )
                    f = interval_fields(d, repos, boot)
                    rows.append(
                        {
                            "label": label,
                            "level": level,
                            "reading": reading,
                            "metric": metric,
                            "primary": metric == LEVEL_PRIMARY[level]
                            and reading == PRIMARY_READING,
                            "pair": name,
                            "kind": kind,
                            "key": key,
                            "ref": ref,
                            **f,
                            "verdict": verdict(f["t_lo"], f["t_hi"]),
                            "boot_agrees": (f["boot_lo"] > 0) == (f["t_lo"] > 0)
                            and (f["boot_hi"] < 0) == (f["t_hi"] < 0),
                        }
                    )
    return rows


def size_rows(tab: EvalTable, label: str) -> list[Record]:
    """Mean expansion size and gold hits (primary reading) of every source, per level."""
    rows: list[Record] = []
    col = 1 + 3  # aux columns: size, then hits under the four readings; units_all_nomod is the last
    for level in ("L2", "L3"):
        idx = np.nonzero(tab.mask(level=level))[0]
        for j, key in enumerate(tab.aux_keys):
            rows.append(
                {
                    "label": label,
                    "level": level,
                    "key": key,
                    "queries": int(idx.size),
                    "size_mean": float(tab.aux[idx, j, 0].mean()),
                    "hits_mean": float(tab.aux[idx, j, col].mean()),
                }
            )
    return rows


def query_rows(tab: EvalTable, label: str) -> list[Record]:
    """One row per (query, level, key): both shown readings and metrics, in percent."""
    out: list[Record] = []
    for i, r in enumerate(tab.rows):
        for key in tab.keys:
            rec: Record = {
                "label": label,
                "instance": r["instance"],
                "level": r["level"],
                "repo": r["repo"],
                "key": key,
            }
            for reading in READINGS_SHOWN:
                for metric in METRICS:
                    v = 100.0 * float(tab.metrics[i, tab.index[key], COLUMN[(reading, metric)]])
                    rec[f"{reading}_{metric}"] = "" if math.isnan(v) else round(v, 6)
            out.append(rec)
    return out


def check_keys(tab: EvalTable) -> None:
    """The evaluation files must carry exactly the keys the ladder reads."""
    if tab.keys != all_keys():
        raise ValueError("key layout differs from rq1_ladder.all_keys()")


# --------------------------------------------------------------------------- regression control


def regression_rows(
    tab: EvalTable, label: str, stored: list[Record], s1_stored: list[Record], tol: float = 0.05
) -> list[Record]:
    """Dev values of the earlier entries recomputed by this job against the stored ones.

    ``stored`` are rows of ``results/tables/x2_first_dev.csv`` (BM25, dense, RRF), ``s1_stored``
    those of an E-GRAPH-ROLE compare file (score-level first stage and the stored graph). A row
    reproduces when the absolute difference is at most ``tol`` points.
    """
    dense_name, rrf_name = stored_names(label)
    # (this job's key, stored table, stored name, stored reference name, description)
    checks = [
        ("ref|bm25", "x2", "bm25", "bm25", "BM25 alone"),
        ("r1|dense", "x2", dense_name, "bm25", "dense alone"),
        ("p|first", "x2", rrf_name, "bm25", "RRF of BM25 and dense"),
        ("s|first", "s1", "a_none", "a_none", "score-level first stage (a_none)"),
        ("s|graph|b", "s1", "graph|b", "a_none", "stored graph, score level"),
        ("s|sfscore|b", "s1", "sfscore|b", "a_none", "same-file by score, score level"),
    ]
    out: list[Record] = []
    for level in ("L2", "L3"):
        idx, _ = level_panel(tab, level, PRIMARY_READING)
        metric = LEVEL_PRIMARY[level]
        for key, which, name, against, what in checks:
            rows = stored if which == "x2" else s1_stored
            want = [
                r
                for r in rows
                if r["group"] == "dev"
                and r["level"] == level
                and r["reading"] == PRIMARY_READING
                and r["metric"] == metric
                and r["against"] == against
                and r["name"] == name
            ]
            if not want:
                continue
            ref = float(want[0]["value"])
            got = float(_vector(tab, idx, key, PRIMARY_READING, metric).mean())
            out.append(
                {
                    "label": label,
                    "level": level,
                    "metric": metric,
                    "key": key,
                    "what": what,
                    "stored_name": want[0]["name"],
                    "stored_queries": want[0]["queries"],
                    "queries": int(idx.size),
                    "stored": ref,
                    "recomputed": round(got, 4),
                    "abs_diff": round(abs(got - ref), 4),
                    "reproduces": abs(got - ref) <= tol,
                }
            )
    return out


def stored_names(label: str) -> tuple[str, str]:
    """Names of the dense-alone and RRF rows of ``x2_first_dev.csv`` behind a label."""
    return {
        "cre": ("dense|coderankembed__t1024", "rrf|coderankembed__t1024|k100"),
        "qwen3": ("dense|qwen3-embedding-0.6b__t512", "rrf|qwen3-embedding-0.6b__t512|k20"),
    }[label]


# --------------------------------------------------------------------------- latency


def read_csv_rows(path: str) -> list[Record]:
    with open(path, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def pick_latency(log: list[Record], sel: Record) -> Record | None:
    """The latest stored row matching stage, query-set id, host prefix and cache state."""
    hit = [
        r
        for r in log
        if r["stage"] == sel["stage"]
        and r["query_set_id"] == sel["query_set_id"]
        and r["host"].startswith(str(sel["host"]))
        and r["cache_state"] == sel.get("cache_state", "warm")
    ]
    if not hit:
        return None
    hit.sort(key=lambda r: r["timestamp_utc"])
    r = hit[-1]
    return {
        "stage": r["stage"],
        "query_set_id": r["query_set_id"],
        "host": r["host"],
        "gpu": r["gpu_name"],
        "cpu": r["cpu_model"],
        "cache_state": r["cache_state"],
        "commit": r["commit"],
        "config_hash": r["config_hash"],
        "timestamp_utc": r["timestamp_utc"],
        "p50_ms": float(r["p50_ms"]),
        "p95_ms": float(r["p95_ms"]),
        "p99_ms": float(r["p99_ms"]),
        "n": int(r["n"]),
        "rows_matched": len(hit),
    }


def latency_rows(log: list[Record], cfg: Record) -> list[Record]:
    """One row per (scale, rung, stage) of the latency configuration; ``measured`` marks a row."""
    out: list[Record] = []
    for scale, spec in cfg["scales"].items():
        for rung, stages in spec["rungs"].items():
            for sel in stages:
                row = pick_latency(log, sel)
                base: Record = {
                    "scale": scale,
                    "index_units": spec["index_units"],
                    "rung": rung,
                    "stage": sel["stage"],
                    "role": sel.get("role", ""),
                    "measured": row is not None,
                }
                if row is None:
                    out.append({**base, "query_set_id": sel["query_set_id"], "host": sel["host"]})
                else:
                    out.append({**base, **row})
    return out


def rung_costs(lat: list[Record], scale: str) -> dict[str, Record]:
    """Added p50 of each rung at one scale: sum over its measured stages, and what is missing."""
    costs: dict[str, Record] = {}
    for rung in (r[0] for r in LADDER):
        rows = [r for r in lat if r["scale"] == scale and r["rung"] == rung]
        measured = [r for r in rows if r["measured"]]
        missing = [r["stage"] for r in rows if not r["measured"]]
        hosts = sorted({str(r["host"]) for r in measured})
        costs[rung] = {
            "added_p50_ms": sum(float(r["p50_ms"]) for r in measured) if measured else None,
            "stages_measured": [r["stage"] for r in measured],
            "stages_not_measured": missing,
            "hosts": hosts,
            "complete": bool(rows) and not missing,
        }
    return costs


def cumulative_costs(costs: dict[str, Record]) -> dict[str, Record]:
    """Sum of the added p50 of the stages on each rung's path, with what is missing."""
    out: dict[str, Record] = {}
    for rung, path in PATH.items():
        parts = [costs[r] for r in path]
        measured = [p["added_p50_ms"] for p in parts if p["added_p50_ms"] is not None]
        out[rung] = {
            "p50_ms": float(sum(measured)) if measured else None,
            "complete": all(p["complete"] for p in parts),
            "not_measured": [s for p in parts for s in p["stages_not_measured"]],
            "hosts": sorted({h for p in parts for h in p["hosts"]}),
        }
    return out


def gain_per_ms(gain: float, added_ms: float | None) -> float | None:
    """Points gained per added millisecond; None when the added time is unknown or not positive."""
    if added_ms is None or added_ms <= 0:
        return None
    return gain / added_ms


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run_file_hashes(eval_dir: str) -> dict[str, str]:
    """SHA-256 of every evaluation file (the recomputability the rulings asked for)."""
    names = sorted(n for n in os.listdir(eval_dir) if n.endswith(".npz"))
    return {n: sha256_file(os.path.join(eval_dir, n)) for n in names}


def build(eval_dir: str, label: str, seed: int = 0, draws: int = DRAWS) -> dict[str, list[Record]]:
    """Every table of one dense variant from its evaluation directory."""
    tab = load_eval_dir(eval_dir)
    check_keys(tab)
    return {
        "summary": summary_rows(tab, label, seed, draws),
        "compare": compare_rows(tab, label, seed, draws),
        "sizes": size_rows(tab, label),
        "query_rows": query_rows(tab, label),
    }


def dump_json(path: str, doc: Record) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, sort_keys=True)
        fh.write("\n")


def write_latency(root: str) -> str:
    """Select the stored latency rows of ``rq1_ladder_latency.yaml`` into the ladder's table.

    Reads ``<root>/results/latency/latency_log.csv`` only; nothing is measured or interpolated, and
    a stage the configuration cannot match to a row is written as not measured. Returns the path.
    """
    import yaml

    from ril.analysis.x2_tables import write_csv

    cfg_path = os.path.join(root, "configs", "experiments", "rq1_ladder_latency.yaml")
    with open(cfg_path, encoding="utf-8") as fh:
        lat_cfg: Record = yaml.safe_load(fh)
    log_path = os.path.join(root, "results", "latency", "latency_log.csv")
    path = os.path.join(root, "results", "tables", "rq1_ladder_latency.csv")
    write_csv(path, latency_rows(read_csv_rows(log_path), lat_cfg))
    return path


def write_outputs(
    eval_dirs: dict[str, str],
    root: str,
    run_date: str,
    seed: int = 0,
    draws: int = DRAWS,
    env: Record | None = None,
) -> dict[str, list[str]]:
    """Write the tables, the regression check, the latency rows and the run-file hashes.

    ``eval_dirs`` maps a label (``cre``, ``qwen3``) to its evaluation directory. Tables go under
    ``<root>/results/tables``, the hash record under ``<root>/results/logs``; ``env`` is stored in
    the record (host, commit, job id) as given.
    """

    from ril.analysis.x2_tables import write_csv

    tables = os.path.join(root, "results", "tables")
    written: dict[str, list[str]] = {"tables": [], "logs": []}
    record: Record = {
        "version": "rq1-ladder-tables/v1",
        "date": run_date,
        "seed": seed,
        "draws": draws,
    }
    record["env"] = env or {}
    regression: list[Record] = []
    x2 = read_csv_rows(os.path.join(tables, "x2_first_dev.csv"))
    for label, eval_dir in eval_dirs.items():
        out = build(eval_dir, label, seed, draws)
        for part, rows in out.items():
            path = os.path.join(tables, f"rq1_ladder_{label}_{part}.csv")
            write_csv(path, rows)
            written["tables"].append(path)
        tab = load_eval_dir(eval_dir)
        s1 = read_csv_rows(os.path.join(tables, "s1", f"s1_graph_role_{label}_compare.csv"))
        regression += regression_rows(tab, label, x2, s1)
        infos = [read_eval(os.path.join(eval_dir, n))[0] for n in sorted(os.listdir(eval_dir))]
        record[label] = {
            "files": run_file_hashes(eval_dir),
            "eval_hashes": sorted({str(i["eval_hash"]) for i in infos}),
            "cache_hashes": sorted({str(i["cache_hash"]) for i in infos}),
        }
    path = os.path.join(tables, "rq1_ladder_regression.csv")
    write_csv(path, regression)
    written["tables"].append(path)
    cfg_path = os.path.join(root, "configs", "experiments", "rq1_ladder_latency.yaml")
    log_path = os.path.join(root, "results", "latency", "latency_log.csv")
    written["tables"].append(write_latency(root))
    record["latency"] = {
        "log_sha256": sha256_file(log_path),
        "config_sha256": sha256_file(cfg_path),
    }
    record["configs"] = {
        label: sha256_file(os.path.join(root, "configs", "experiments", f"rq1_ladder_{label}.yaml"))
        for label in eval_dirs
    }
    path = os.path.join(root, "results", "logs", f"rq1_ladder_run_files_{run_date}.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    dump_json(path, record)
    written["logs"].append(path)
    return written
