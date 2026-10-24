"""Tables of the pool-rank measurement (E-POOL-RANKS): rank distributions, top-K shares, agreement.

Exploratory. Reads the stratified sample (``ril.training.pool_rank_jobs.sample_job``) and the rank
rows of every teacher, and writes:

* the distribution of positive ranks per teacher (``rank`` = among non-positive functions, the
  construction of the published SweRank scripts; ``rank_all`` beside it);
* per teacher and K in ``K_CUTS``: the share of positives outside the top K and the share of
  directories with no positive in the top K, as sample values and as pool estimates (stratified:
  each stratum's sample ratio weighted by the stratum's pool positives or directories), with
  stratified bootstrap intervals (instances resampled within strata);
* the estimated pool count of positives inside the top K and of directories keeping at least one,
  set beside the SweRank+ Table 1 Python row (49,973 instances, 24,285 PRs; ``paper_reported``);
* agreement between teachers per positive (Spearman correlation of ranks, top-K membership
  agreement and Cohen's kappa), with intervals;
* shares per repository and per held-out flag;
* the full-pool cost estimate from the measured throughput and the measured dedup ratio.

Values are fractions in [0, 1] in the JSON and percentages in the CSV tables.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
from collections.abc import Callable, Mapping, Sequence
from typing import Any

import numpy as np
import yaml

from ril.training import pool_ranks as pr

Record = dict[str, Any]
Arr = np.ndarray[Any, Any]

PAPER_INSTANCES = 49973
PAPER_PRS = 24285
PAPER_POSITIVE_ROWS = 307996
"""SweRank+ Table 1 Python row (``paper_reported``) and the measured qrels total of the pool."""
HIST_EDGES: tuple[int, ...] = (1, 5, 10, 20, 40, 100, 1000)


def config_hash(cfg: Mapping[str, Any]) -> str:
    """SHA-256 of the canonical JSON of the experiment configuration plus the code version."""
    payload = {"version": pr.POOL_RANKS_VERSION, "config": cfg}
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------------------------
# per-instance arrays


class RankSet:
    """Ranks of one teacher over the sampled instances, aligned with the sample order."""

    def __init__(
        self, teacher: str, instances: Sequence[pr.PoolInstance], rows: Sequence[Mapping[str, Any]]
    ) -> None:
        self.teacher = teacher
        by = {str(r["dir"]): r for r in rows if r.get("teacher") == teacher}
        self.instances = [i for i in instances if i.dir in by]
        self.ranks: list[list[int]] = []
        self.ranks_all: list[list[int]] = []
        self.positive_ids: list[list[str]] = []
        self.functions: list[int] = []
        for inst in self.instances:
            r = by[inst.dir]
            self.ranks.append([int(x["rank"]) for x in r["ranks"]])
            self.ranks_all.append([int(x["rank_all"]) for x in r["ranks"]])
            self.positive_ids.append([str(x["positive"]) for x in r["ranks"]])
            self.functions.append(int(r["functions"]))

    @property
    def dirs(self) -> list[str]:
        """Directories covered."""
        return [i.dir for i in self.instances]

    def flat(self, kind: str = "rank") -> Arr:
        """All positive ranks in one array."""
        src = self.ranks if kind == "rank" else self.ranks_all
        return np.asarray([x for xs in src for x in xs], dtype=np.int64)

    def inside(self, k: int) -> tuple[Arr, Arr, Arr]:
        """Per instance: positives in the top k, positives, whether any positive is in the top k."""
        n_in = np.asarray([sum(1 for x in xs if x <= k) for xs in self.ranks], dtype=np.float64)
        n_pos = np.asarray([len(xs) for xs in self.ranks], dtype=np.float64)
        return n_in, n_pos, (n_in > 0).astype(np.float64)


def describe_ranks(ranks: Arr) -> Record:
    """Quantiles, mean and a coarse histogram of ranks."""
    if ranks.size == 0:
        return {"n": 0}
    q = np.percentile(ranks, [5, 25, 50, 75, 95])
    hist: Record = {}
    lo = 0
    for e in HIST_EDGES:
        hist[f"{lo + 1}-{e}"] = int(((ranks > lo) & (ranks <= e)).sum())
        lo = e
    hist[f">{lo}"] = int((ranks > lo).sum())
    return {
        "n": int(ranks.size),
        "mean": float(ranks.mean()),
        "p5": float(q[0]),
        "p25": float(q[1]),
        "p50": float(q[2]),
        "p75": float(q[3]),
        "p95": float(q[4]),
        "max": int(ranks.max()),
        "histogram": hist,
    }


# --------------------------------------------------------------------------------------------
# stratified estimators with a bootstrap


def stratified_estimates(
    strata: Sequence[str],
    n_in: Arr,
    n_pos: Arr,
    any_in: Arr,
    pool: Mapping[str, Mapping[str, int]],
) -> Record:
    """Pool estimates from one (re)sample: positives inside, share inside, directories keeping one.

    Ratio estimator per stratum (positives inside / positives in the stratum's sample) times the
    stratum's pool positives; directory share per stratum times its pool directories. A stratum
    absent from the sample is an error (the estimate would silently drop pool mass).
    """
    labels = np.asarray(strata)
    pos_in = 0.0
    dirs_keep = 0.0
    for s, tot in pool.items():
        m = labels == s
        if not m.any():
            raise ValueError(f"stratum {s} has no sampled instance")
        denom = n_pos[m].sum()
        ratio = n_in[m].sum() / denom if denom > 0 else 0.0
        pos_in += ratio * tot["positives"]
        dirs_keep += any_in[m].mean() * tot["dirs"]
    pos_total = sum(t["positives"] for t in pool.values())
    dirs_total = sum(t["dirs"] for t in pool.values())
    return {
        "positives_inside": pos_in,
        "share_positives_inside": pos_in / pos_total,
        "dirs_keeping": dirs_keep,
        "share_dirs_none": 1.0 - dirs_keep / dirs_total,
    }


def stratified_bootstrap(
    strata: Sequence[str],
    stat: Callable[[Arr], Record],
    draws: int,
    seed: int,
) -> dict[str, tuple[float, float]]:
    """95% percentile intervals of every key of ``stat`` under resampling within strata.

    ``stat`` receives an index array (positions into the sample) and returns a flat record.
    """
    rng = np.random.default_rng(seed)
    labels = np.asarray(strata)
    groups = [np.flatnonzero(labels == s) for s in sorted(set(strata))]
    acc: dict[str, list[float]] = {}
    for _ in range(draws):
        idx = np.concatenate([g[rng.integers(0, g.size, g.size)] for g in groups])
        for k, v in stat(idx).items():
            acc.setdefault(k, []).append(float(v))
    return {
        k: (float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))) for k, v in acc.items()
    }


def spearman(a: Arr, b: Arr) -> float:
    """Spearman correlation (average ranks for ties); nan for fewer than three pairs."""
    if a.size < 3:
        return float("nan")
    ra = _average_ranks(a)
    rb = _average_ranks(b)
    if ra.std() == 0 or rb.std() == 0:
        return float("nan")
    return float(np.corrcoef(ra, rb)[0, 1])


def _average_ranks(x: Arr) -> Arr:
    order = np.argsort(x, kind="mergesort")
    ranks = np.empty(x.size, dtype=np.float64)
    xs = x[order]
    i = 0
    while i < x.size:
        j = i
        while j + 1 < x.size and xs[j + 1] == xs[i]:
            j += 1
        ranks[order[i : j + 1]] = (i + j) / 2.0 + 1.0
        i = j + 1
    return ranks


def kappa(a: Arr, b: Arr) -> float:
    """Cohen's kappa of two boolean arrays; nan when chance agreement is 1."""
    a = a.astype(bool)
    b = b.astype(bool)
    po = float((a == b).mean())
    pa, pb = float(a.mean()), float(b.mean())
    pe = pa * pb + (1 - pa) * (1 - pb)
    return float("nan") if pe >= 1.0 else (po - pe) / (1.0 - pe)


# --------------------------------------------------------------------------------------------
# tables


def _pct(x: float) -> float:
    return round(100.0 * float(x), 2)


def topk_rows(
    rs: RankSet, pool: Mapping[str, Mapping[str, int]], ks: Sequence[int], draws: int, seed: int
) -> list[Record]:
    """Per K: sample and pool-estimated shares, counts beside the paper's row, with intervals."""
    strata = [i.stratum for i in rs.instances]
    out: list[Record] = []
    for k in ks:
        n_in, n_pos, any_in = rs.inside(k)

        def stat(idx: Arr, n_in: Arr = n_in, n_pos: Arr = n_pos, any_in: Arr = any_in) -> Record:
            est = stratified_estimates(
                [strata[i] for i in idx], n_in[idx], n_pos[idx], any_in[idx], pool
            )
            est["sample_share_positives_outside"] = 1.0 - n_in[idx].sum() / n_pos[idx].sum()
            est["sample_share_dirs_none"] = 1.0 - any_in[idx].mean()
            return est

        point = stat(np.arange(len(strata)))
        ci = stratified_bootstrap(strata, stat, draws, seed + k)
        out.append(
            {
                "teacher": rs.teacher,
                "k": k,
                "instances": len(strata),
                "positives": int(n_pos.sum()),
                "sample_pct_positives_outside": _pct(point["sample_share_positives_outside"]),
                "sample_pct_positives_outside_ci": _ci(ci["sample_share_positives_outside"]),
                "sample_pct_dirs_none": _pct(point["sample_share_dirs_none"]),
                "sample_pct_dirs_none_ci": _ci(ci["sample_share_dirs_none"]),
                "pool_pct_positives_outside": _pct(1.0 - point["share_positives_inside"]),
                "pool_pct_positives_outside_ci": _ci(
                    (1.0 - ci["share_positives_inside"][1], 1.0 - ci["share_positives_inside"][0])
                ),
                "pool_pct_dirs_none": _pct(point["share_dirs_none"]),
                "pool_pct_dirs_none_ci": _ci(ci["share_dirs_none"]),
                "pool_positives_inside": round(point["positives_inside"]),
                "pool_positives_inside_ci": [round(x) for x in ci["positives_inside"]],
                "pool_dirs_keeping": round(point["dirs_keeping"]),
                "pool_dirs_keeping_ci": [round(x) for x in ci["dirs_keeping"]],
                "paper_instances": PAPER_INSTANCES,
                "paper_prs": PAPER_PRS,
            }
        )
    return out


def _ci(pair: tuple[float, float]) -> list[float]:
    return [_pct(pair[0]), _pct(pair[1])]


def group_rows(rs: RankSet, ks: Sequence[int]) -> list[Record]:
    """Sample shares by held-out flag and by size stratum (positive- and directory-level)."""
    out: list[Record] = []
    keys: dict[str, Callable[[pr.PoolInstance], str]] = {
        "held_out": lambda i: "held_out" if i.held_out else "kept",
        "size_bin": lambda i: f"s{i.size_bin}",
        "stratum": lambda i: i.stratum,
    }
    for gname, fn in keys.items():
        labels = [fn(i) for i in rs.instances]
        for g in sorted(set(labels)):
            m = np.asarray([lab == g for lab in labels])
            row: Record = {
                "teacher": rs.teacher,
                "grouping": gname,
                "group": g,
                "instances": int(m.sum()),
            }
            for k in ks:
                n_in, n_pos, any_in = rs.inside(k)
                row[f"pct_positives_outside_top{k}"] = _pct(1 - n_in[m].sum() / n_pos[m].sum())
                row[f"pct_dirs_none_top{k}"] = _pct(1 - any_in[m].mean())
            ranks = np.asarray([x for xs, mm in zip(rs.ranks, m, strict=True) if mm for x in xs])
            row["positives"] = int(ranks.size)
            row["median_rank"] = float(np.median(ranks))
            out.append(row)
    return out


def repository_rows(rs: RankSet, k: int) -> list[Record]:
    """Per sampled repository: directories, positives, share of positives inside the top k."""
    by: dict[str, list[int]] = {}
    held: dict[str, bool] = {}
    dirs: dict[str, int] = {}
    for inst, xs in zip(rs.instances, rs.ranks, strict=True):
        by.setdefault(inst.repo, []).extend(xs)
        held[inst.repo] = inst.held_out
        dirs[inst.repo] = dirs.get(inst.repo, 0) + 1
    return [
        {
            "teacher": rs.teacher,
            "repo": repo,
            "held_out": int(held[repo]),
            "dirs": dirs[repo],
            "positives": len(xs),
            f"pct_inside_top{k}": _pct(sum(1 for x in xs if x <= k) / len(xs)),
        }
        for repo, xs in sorted(by.items())
    ]


def repository_summary(rows: Sequence[Mapping[str, Any]], k: int) -> Record:
    """How the top-k survival spreads over repositories (share with none / all inside)."""
    col = f"pct_inside_top{k}"
    vals = np.asarray([float(r[col]) for r in rows])
    return {
        "repositories": int(vals.size),
        "pct_repos_none_inside": _pct(float((vals == 0).mean())),
        "pct_repos_all_inside": _pct(float((vals == 100).mean())),
        "median_pct_inside": float(np.median(vals)),
    }


def _rank_map(rs: RankSet) -> dict[tuple[str, str], int]:
    """``{(directory, positive): rank}`` of one teacher."""
    out: dict[tuple[str, str], int] = {}
    for d, ps, xs in zip(rs.dirs, rs.positive_ids, rs.ranks, strict=True):
        for p, x in zip(ps, xs, strict=True):
            out[(d, p)] = x
    return out


def agreement_rows(
    a: RankSet, b: RankSet, ks: Sequence[int], draws: int, seed: int
) -> list[Record]:
    """Per positive agreement of two teachers: Spearman of ranks and top-K membership."""
    ra = _rank_map(a)
    rb = _rank_map(b)
    keys = sorted(set(ra) & set(rb))
    xa = np.asarray([ra[k] for k in keys], dtype=np.float64)
    xb = np.asarray([rb[k] for k in keys], dtype=np.float64)
    inst = [k[0] for k in keys]
    uniq = sorted(set(inst))
    pos_of: dict[str, list[int]] = {}
    for j, d in enumerate(inst):
        pos_of.setdefault(d, []).append(j)
    rng = np.random.default_rng(seed)
    boots: list[float] = []
    for _ in range(draws):  # clustered by instance: positives of one issue move together
        pick = rng.integers(0, len(uniq), len(uniq))
        idx = np.concatenate([pos_of[uniq[i]] for i in pick])
        boots.append(spearman(xa[idx], xb[idx]))
    rho = spearman(xa, xb)
    out: list[Record] = [
        {
            "pair": f"{a.teacher}~{b.teacher}",
            "measure": "spearman_rank",
            "k": "",
            "positives": len(keys),
            "value": round(rho, 3),
            "ci": [
                round(float(np.nanpercentile(boots, 2.5)), 3),
                round(float(np.nanpercentile(boots, 97.5)), 3),
            ],
        }
    ]
    for k in ks:
        ia, ib = xa <= k, xb <= k
        out.append(
            {
                "pair": f"{a.teacher}~{b.teacher}",
                "measure": "topk_membership",
                "k": k,
                "positives": len(keys),
                "both_inside": int((ia & ib).sum()),
                "only_first": int((ia & ~ib).sum()),
                "only_second": int((~ia & ib).sum()),
                "neither": int((~ia & ~ib).sum()),
                "value": round(kappa(ia, ib), 3),
            }
        )
    return out


def cost_estimate(
    sample_doc: Mapping[str, Any],
    dense_rows: Sequence[Mapping[str, Any]],
    dedup_rows: Sequence[Mapping[str, Any]],
    pool_meta_functions_per_byte: float,
) -> Record:
    """GPU-hours for the whole pool per teacher, from measured encode throughput and dedup.

    Pool functions are estimated from the pool's total corpus bytes times the measured functions
    per corpus byte of the sample; dedup is the per-bin distinct/all ratio weighted by each bin's
    share of texts in the dedup sample (a ratio estimate; bins without data fall back to 1).
    """
    pool_bytes = sum(int(t["corpus_bytes"]) for t in sample_doc["pool_strata"].values())
    pool_functions = pool_bytes * pool_meta_functions_per_byte
    per_teacher: Record = {}
    for t in sorted({str(r["teacher"]) for r in dense_rows}):
        rows = [r for r in dense_rows if r["teacher"] == t]
        enc = sum(int(r["encoded"]) for r in rows)
        sec = sum(float(r["encode_seconds"]) for r in rows)
        rate = enc / sec if sec > 0 else float("nan")
        per_teacher[t] = {
            "encoded": enc,
            "encode_seconds": round(sec, 1),
            "texts_per_second": round(rate, 1),
        }
    texts = sum(int(r["texts"]) for r in dedup_rows)
    distinct = sum(int(r["distinct"]) for r in dedup_rows)
    ratio = distinct / texts if texts else 1.0
    out: Record = {
        "pool_corpus_bytes": pool_bytes,
        "functions_per_byte": pool_meta_functions_per_byte,
        "pool_functions_est": round(pool_functions),
        "dedup_texts": texts,
        "dedup_distinct": distinct,
        "dedup_ratio": round(ratio, 4),
        "dedup_repos": len(dedup_rows),
        "teachers": per_teacher,
    }
    for v in per_teacher.values():
        rate = float(v["texts_per_second"])
        if rate > 0:
            v["gpu_hours_no_dedup"] = round(pr.gpu_hours_estimate(pool_functions, rate), 2)
            v["gpu_hours_dedup"] = round(pr.gpu_hours_estimate(pool_functions, rate, ratio), 2)
    return out


def write_csv(path: str, rows: Sequence[Mapping[str, Any]]) -> None:
    """CSV with the union of keys (first-seen order); list cells joined by ``;``."""
    cols: list[str] = []
    for r in rows:
        for k in r:
            if k not in cols:
                cols.append(k)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        w = csv.DictWriter(handle, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow(
                {k: ";".join(map(str, v)) if isinstance(v, list) else v for k, v in r.items()}
            )


def write_tables(
    sample_path: str,
    rank_paths: Sequence[str],
    config_path: str,
    out_dir: str,
    dedup_path: str | None = None,
    dense_logs: Sequence[str] = (),
    pool_sample_path: str | None = None,
) -> Record:
    """Write every table of the measurement and return the summary record (the run log body)."""
    with open(config_path, encoding="utf-8") as handle:
        cfg = yaml.safe_load(handle)
    with open(sample_path, encoding="utf-8") as handle:
        sample = json.load(handle)
    instances = [pr.instance_from_record(r) for r in sample["sample"]]
    rows = [r for p in rank_paths for r in pr.read_jsonl(p)]
    teachers = list(cfg["teachers"])
    ks = tuple(int(k) for k in cfg["k_cuts"])
    draws = int(cfg["bootstrap_draws"])
    seed = int(cfg["seed"])
    pool = sample["pool_strata"]
    sets = {t: RankSet(t, instances, rows) for t in teachers}
    summary: Record = {
        "experiment_id": cfg["experiment_id"],
        "config_hash": config_hash(cfg),
        "seed": seed,
        "sample_instances": len(instances),
        "pool_instances": sample["pool_instances"],
        "pool_positives": sample["pool_positives"],
        "covered": {t: len(s.instances) for t, s in sets.items()},
        "distribution": {},
        "topk": [],
        "groups": [],
        "agreement": [],
        "repositories": {},
    }
    prefix = os.path.join(out_dir, str(cfg["table_prefix"]))
    dist_rows: list[Record] = []
    repo_rows: list[Record] = []
    for t, s in sets.items():
        for kind in ("rank", "rank_all"):
            d = describe_ranks(s.flat(kind))
            summary["distribution"][f"{t}:{kind}"] = d
            flat = {k: v for k, v in d.items() if k != "histogram"}
            flat.update({f"h_{k}": v for k, v in d.get("histogram", {}).items()})
            dist_rows.append({"teacher": t, "rank_kind": kind, **flat})
        summary["topk"] += topk_rows(s, pool, ks, draws, seed)
        summary["groups"] += group_rows(s, ks)
        rr = repository_rows(s, max(ks))
        repo_rows += rr
        summary["repositories"][t] = repository_summary(rr, max(ks))
    for i, a in enumerate(teachers):
        for b in teachers[i + 1 :]:
            summary["agreement"] += agreement_rows(sets[a], sets[b], ks, draws, seed)
    feats = pr.feature_rows({i.dir: i for i in instances}, rows, teachers)
    write_csv(f"{prefix}_rank_distribution.csv", dist_rows)
    write_csv(f"{prefix}_topk.csv", summary["topk"])
    write_csv(f"{prefix}_groups.csv", summary["groups"])
    write_csv(f"{prefix}_agreement.csv", summary["agreement"])
    write_csv(f"{prefix}_repositories.csv", repo_rows)
    write_csv(
        f"{prefix}_features.csv",
        [{c: r.get(c, "") for c in pr.feature_columns(teachers)} for r in feats],
    )
    dense_rows = [r for r in rows if r.get("teacher") in teachers and "encoded" in r]
    # functions per corpus byte from the pool check's simple random sample when given (the
    # stratified sample over-weights large snapshots), else from the rank rows
    src = pr.read_jsonl(pool_sample_path) if pool_sample_path else dense_rows
    fpb = sum(int(r["functions"]) for r in src) / max(1, sum(int(r["corpus_bytes"]) for r in src))
    dedup_rows = pr.read_jsonl(dedup_path) if dedup_path else []
    summary["cost"] = cost_estimate(sample, dense_rows, dedup_rows, fpb)
    summary["dense_logs"] = [json.load(open(p, encoding="utf-8")) for p in dense_logs]
    summary["feature_rows"] = len(feats)
    return summary
