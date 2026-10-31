"""Docstring-to-function retrieval with BM25 variants: an exploratory local pilot for session A1.

The benchmark's development repositories are on the cluster; this pilot asks the same kind of
question on local checkouts, with a task that needs no labels: the first line of a function's
docstring is the query, the function is the one relevant unit, and every docstring is removed
from every unit's indexed text first (otherwise the query would be found verbatim). It measures
whether identifier splitting and field weights move natural-language-to-code retrieval at all
before the development-set runs; it chooses nothing (``docs/EXPERIMENTS.md``, section A1-PILOT).

Variants, all over the same units in the same order (ties: lower index first):

* ``ref``           reference tokenisation (``ril.retrieval.bm25_index.tokenize``), the index of E1
* ``split``         identifiers split, whole identifier kept
* ``split_noorig``  identifiers split, whole identifier dropped
* ``split_fields``  ``split`` with the name field counted twice (one setting stated before the run)

Metrics per query from the rank of its function: reciprocal rank (0 beyond rank 100), Recall@10
and nDCG@10 with one relevant unit. Intervals: paired percentile bootstrap over queries, and a
repository-clustered bootstrap (repositories resampled, then queries within each).

Kept compatible with Python 3.10.
"""

from __future__ import annotations

import ast
import hashlib
import json
import math
import textwrap
import time
from collections.abc import Callable
from typing import Any

import numpy as np

from ril.bench.latency_harness import percentile
from ril.evaluation.metrics import mean_ci, paired_diff_ci
from ril.parsing.code_unit import CodeUnit
from ril.parsing.repository_parser import parse_repository
from ril.retrieval.bm25_index import BM25Index, field_tokens, tokenize, tokenize_code

VARIANTS: tuple[str, ...] = ("ref", "split", "split_noorig", "split_fields")
NAME_WEIGHT = 2  # split_fields: stated before the run, not swept
MAX_QUERIES = 1000
MIN_QUERY_TOKENS = 3
RR_CUTOFF = 100


def config_hash() -> str:
    """SHA-256 prefix of the pilot's fixed settings (recorded with every run)."""
    payload = {
        "variants": VARIANTS,
        "name_weight": NAME_WEIGHT,
        "max_queries": MAX_QUERIES,
        "min_query_tokens": MIN_QUERY_TOKENS,
        "rr_cutoff": RR_CUTOFF,
        "k1": 1.5,
        "b": 0.75,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:12]


def strip_docstrings(source: str) -> tuple[str, bool]:
    """``source`` without the docstring of the module and of every definition in it.

    Returns (text, parsed): when the text does not parse on its own (a residual module unit can
    be a fragment), it is returned unchanged with ``parsed`` false.
    """
    text = textwrap.dedent(source)
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError, RecursionError):
        return source, False
    drop: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            body = node.body
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                first = body[0]
                drop.update(range(first.lineno, (first.end_lineno or first.lineno) + 1))
    lines = text.split("\n")
    return "\n".join(line for i, line in enumerate(lines, start=1) if i not in drop), True


def _query_text(unit: CodeUnit) -> str:
    for line in (unit.docstring or "").split("\n"):
        if line.strip():
            return line.strip()
    return ""


def _documents(units: list[CodeUnit], variant: str, bodies: list[str]) -> list[list[str]]:
    if variant == "ref":
        return [tokenize(b) for b in bodies]
    if variant == "split":
        return [tokenize_code(b) for b in bodies]
    if variant == "split_noorig":
        return [tokenize_code(b, keep_original=False) for b in bodies]
    weights = {"name": NAME_WEIGHT, "signature": 1, "path": 1, "body": 1}
    return [
        field_tokens(
            {"name": u.name, "signature": u.signature, "path": u.file, "body": b},
            weights,
            tokenize_code,
        )
        for u, b in zip(units, bodies, strict=True)
    ]


def _query_tokenizer(variant: str) -> Callable[[str], list[str]]:
    if variant == "ref":
        return tokenize
    if variant == "split_noorig":
        return lambda t: tokenize_code(t, keep_original=False)
    return tokenize_code


def _rank(scores: np.ndarray, gold: int) -> int:
    s = scores[gold]
    return int(np.count_nonzero(scores > s) + np.count_nonzero(scores[:gold] == s) + 1)


def _per_query(rank: int) -> tuple[float, float, float]:
    rr = 1.0 / rank if rank <= RR_CUTOFF else 0.0
    r10 = 1.0 if rank <= 10 else 0.0
    ndcg = 1.0 / math.log2(rank + 1) if rank <= 10 else 0.0
    return rr, r10, ndcg


def run_repository(root: str, repo_id: str, seed: int = 0) -> dict[str, Any]:
    """Parse, build the four indexes, score every sampled query; per-query rows and latencies."""
    parsed = parse_repository(root, repo_id)
    units = parsed.units
    bodies: list[str] = []
    unparsed = 0
    for u in units:
        text, ok = strip_docstrings(u.source)
        bodies.append(text)
        unparsed += 0 if ok or u.unit_type == "module" else 1
    candidates = [
        i
        for i, u in enumerate(units)
        if u.unit_type in ("function", "method")
        and not u.is_test
        and len(tokenize(_query_text(u))) >= MIN_QUERY_TOKENS
    ]
    rng = np.random.default_rng(seed)
    if len(candidates) > MAX_QUERIES:
        candidates = sorted(rng.choice(candidates, size=MAX_QUERIES, replace=False).tolist())
    out: dict[str, Any] = {
        "repo_id": repo_id,
        "n_units": len(units),
        "n_queries": len(candidates),
        "units_not_reparsed": unparsed,
        "variants": {},
    }
    for variant in VARIANTS:
        t0 = time.perf_counter()
        docs = _documents(units, variant, bodies)
        index = BM25Index(docs)
        build = time.perf_counter() - t0
        qtok = _query_tokenizer(variant)
        rows: list[tuple[float, float, float]] = []
        lat: list[float] = []
        for n, gold in enumerate(candidates):
            q = qtok(_query_text(units[gold]))
            t0 = time.perf_counter()
            scores = index.scores(q)
            index.top_k(q, RR_CUTOFF)
            if n >= 20:  # the first 20 queries warm the caches and are not timed
                lat.append((time.perf_counter() - t0) * 1000.0)
            rows.append(_per_query(_rank(scores, gold)))
        out["variants"][variant] = {
            "build_seconds": round(build, 4),
            "units_per_second": round(len(units) / build, 1) if build > 0 else None,
            "mean_doc_tokens": round(float(index.doc_len.mean()), 1) if len(units) else 0.0,
            "vocab": len(index.vocab),
            "query_ms": {f"p{p}": round(percentile(lat, p), 3) for p in (50, 95, 99)}
            if lat
            else {},
            "rows": rows,
        }
    return out


def clustered_diff_ci(
    per_repo: list[tuple[np.ndarray, np.ndarray]], draws: int = 2000, seed: int = 0
) -> tuple[float, float, float]:
    """Query-weighted mean of a - b with repositories resampled, then queries within each."""
    rng = np.random.default_rng(seed)
    diffs = [a - b for a, b in per_repo]
    point = float(np.concatenate(diffs).mean())
    means = np.empty(draws)
    for k in range(draws):
        picked = rng.integers(0, len(diffs), size=len(diffs))
        parts = [diffs[i][rng.integers(0, len(diffs[i]), size=len(diffs[i]))] for i in picked]
        means[k] = np.concatenate(parts).mean()
    lo, hi = np.quantile(means, [0.025, 0.975])
    return point, float(lo), float(hi)


def summarise(repos: list[dict[str, Any]]) -> dict[str, Any]:
    """Pooled means with intervals and paired differences against ``ref``."""
    metrics = ("rr", "recall10", "ndcg10")
    summary: dict[str, Any] = {}
    for variant in VARIANTS:
        entry: dict[str, Any] = {}
        for m_i, metric in enumerate(metrics):
            pooled = np.array(
                [row[m_i] for r in repos for row in r["variants"][variant]["rows"]], dtype=float
            )
            entry[metric] = [round(100 * x, 2) for x in mean_ci(pooled)]
            if variant != "ref":
                ref = np.array(
                    [row[m_i] for r in repos for row in r["variants"]["ref"]["rows"]], dtype=float
                )
                entry[f"{metric}_diff_query"] = [
                    round(100 * x, 2) for x in paired_diff_ci(pooled, ref)
                ]
                per_repo = [
                    (
                        np.array([row[m_i] for row in r["variants"][variant]["rows"]], dtype=float),
                        np.array([row[m_i] for row in r["variants"]["ref"]["rows"]], dtype=float),
                    )
                    for r in repos
                ]
                entry[f"{metric}_diff_clustered"] = [
                    round(100 * x, 2) for x in clustered_diff_ci(per_repo)
                ]
        summary[variant] = entry
    return summary
