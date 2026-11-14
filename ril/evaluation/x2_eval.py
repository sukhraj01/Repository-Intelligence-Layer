"""Evaluation of dense retrieval, BM25+dense fusion and the graph on top (X2), on the E3 cache.

Exploratory. Implements the evaluation half of ``docs/EXPERIMENTS.md`` E-DENSE-FUSION. Inputs per
instance: the pilot-E3 cache (BM25 scores, typed edge pairs, file of each unit, gold unit indices
under the four readings) and one dense score file per encoder variant (``<encoder>__t<cut>``,
written by ``ril.evaluation.x2_dense.score_units``). Output: one file per instance in the layout of
``ril.evaluation.e3_eval`` (keys, a ``(keys, 4)`` metric matrix per level), so the bootstrap and
table code of the pilots reads it unchanged.

Two stages, both configured in YAML, both refusing to sweep on test instances:

* ``first`` (item 2): ``bm25``; ``dense|<v>``; ``rrf|<v>|k<k>`` (reciprocal rank fusion of the BM25
  and dense rankings, ``sum 1 / (k + rank)``); ``score|<v>|a<alpha>`` (score-level fusion
  ``alpha * mm(bm25) + (1 - alpha) * mm(dense)``, ``mm`` = min-max over the snapshot).
* ``graph`` (item 3) on one first stage ``F`` (an RRF of BM25 and one dense variant at a stated k):
  seeds are the top-C units of ``F``; hop-decay expansion over an edge-family subset; three ways
  to use it: ``list`` (edited list: seeds, expansion, rest of ``F``), ``rrf3`` (the graph list is a
  third ranked list in the RRF with BM25 and dense, same k), ``score`` (score level:
  ``(1 - w) * (alpha * mm(bm25) + (1 - alpha) * mm(dense)) + w * g`` with ``g`` the hop-decay score,
  ``alpha`` stated, ``w`` swept on dev). Chance controls of the same size (``rand_whole``,
  ``rand_files``) for every ``list``/``rrf3`` cell; for ``score`` cells only when ``score_controls``
  is set (the random units take the expansion's graph scores), because they cost a full re-ranking
  per draw.

Kept compatible with Python 3.10.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from dataclasses import dataclass
from typing import Any

import numpy as np

from ril.evaluation.e3_eval import (
    CONTROLS,
    GraphGrid,
    _Level,
    _rng,
    read_eval,
    subset_table,
    write_eval,
)
from ril.evaluation.e3_prepare import READINGS, read_cache
from ril.retrieval.bm25_index import order_by_score
from ril.retrieval.graph_expansion import (
    FamilyGraph,
    bfs_distances,
    combine_uniform,
    random_same_files,
    random_whole,
    select_expansion,
)

X2_EVAL_VERSION = "x2-eval/v1"
Record = dict[str, Any]
Arr = np.ndarray[Any, Any]


@dataclass(frozen=True)
class FirstSpec:
    """First-stage grid (item 2)."""

    variants: tuple[str, ...]
    rrf_ks: tuple[int, ...]
    alphas: tuple[float, ...]
    rrf_k_of: dict[str, int] | None = None
    """Per-variant k (a confirmation states one k per encoder); overrides ``rrf_ks``."""
    alpha_of: dict[str, float] | None = None


@dataclass(frozen=True)
class GraphSpec:
    """Graph-on-top grid (item 3) on the first stage ``rrf(variant, k)``."""

    variant: str
    k: int
    alpha: float
    ways: tuple[str, ...]
    subsets: tuple[str, ...]
    seeds: tuple[int, ...]
    gammas: tuple[float, ...]
    hops: tuple[int, ...]
    weights: tuple[float, ...]
    cap: int = 50
    draws: int = 3
    score_controls: bool = False


@dataclass(frozen=True)
class X2Spec:
    roles: tuple[str, ...]
    confirm: bool
    first: FirstSpec | None
    graph: GraphSpec | None

    def validate(self) -> None:
        if "test" in self.roles and not self.confirm:
            raise ValueError("test instances may only be evaluated by a confirm specification")
        if not self.confirm:
            return
        f, g = self.first, self.graph
        if f is not None and (f.rrf_ks or f.alphas):
            raise ValueError("confirm: state one k and one alpha per variant (rrf_k_of, alpha_of)")
        if g is not None and not (
            len(g.ways) == len(g.seeds) == len(g.gammas) == len(g.hops) == len(g.weights) == 1
        ):
            raise ValueError("confirm: one way, C, gamma, hop count and weight")


def spec_from_config(cfg: Record) -> X2Spec:
    """Build and validate the specification from a parsed YAML configuration."""
    first = graph = None
    if "first" in cfg:
        fc = cfg["first"]
        first = FirstSpec(
            variants=tuple(fc["variants"]),
            rrf_ks=tuple(int(k) for k in fc.get("rrf_ks", ())),
            alphas=tuple(float(a) for a in fc.get("alphas", ())),
            rrf_k_of={str(k): int(v) for k, v in fc["rrf_k_of"].items()}
            if "rrf_k_of" in fc
            else None,
            alpha_of={str(k): float(v) for k, v in fc["alpha_of"].items()}
            if "alpha_of" in fc
            else None,
        )
    if "graph" in cfg:
        gc = cfg["graph"]
        table = subset_table()
        for s in gc["subsets"]:
            if s not in table:
                raise ValueError(f"unknown subset {s!r}")
        graph = GraphSpec(
            variant=str(gc["variant"]),
            k=int(gc["k"]),
            alpha=float(gc["alpha"]),
            ways=tuple(gc["ways"]),
            subsets=tuple(gc["subsets"]),
            seeds=tuple(int(c) for c in gc["seeds"]),
            gammas=tuple(float(x) for x in gc["gammas"]),
            hops=tuple(int(h) for h in gc["hops"]),
            weights=tuple(float(w) for w in gc.get("weights", (0.2,))),
            cap=int(gc.get("cap", 50)),
            draws=int(gc.get("draws", 3)),
            score_controls=bool(gc.get("score_controls", False)),
        )
    spec = X2Spec(tuple(cfg["roles"]), bool(cfg.get("confirm", False)), first, graph)
    spec.validate()
    return spec


def x2_eval_hash(cfg: Record, prepare_hash: str) -> str:
    """SHA-256 over the evaluation configuration and the cache's configuration hash."""
    payload = {"version": X2_EVAL_VERSION, "config": cfg, "prepare": prepare_hash}
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- helpers


def minmax(x: Arr) -> Arr:
    """Scores scaled to [0, 1] over the snapshot (a constant vector becomes zeros)."""
    x = np.asarray(x, dtype=np.float64)
    lo, hi = float(x.min()), float(x.max())
    if hi <= lo:
        return np.zeros_like(x)
    out: Arr = (x - lo) / (hi - lo)
    return out


def positions(scores: Arr) -> Arr:
    """0-based position of every unit in the ranking by score (ties by lower index)."""
    order = order_by_score(scores)
    pos = np.empty(len(scores), dtype=np.int64)
    pos[order] = np.arange(len(scores))
    return pos


def rrf_scores(pos_lists: list[Arr], k: int) -> Arr:
    """Reciprocal rank fusion of whole rankings given as positions."""
    out = np.zeros(len(pos_lists[0]), dtype=np.float64)
    for p in pos_lists:
        out += 1.0 / (k + p.astype(np.float64) + 1.0)
    return out


def gold_ranks(scores: Arr, gold: Arr) -> list[int]:
    """1-based rank of each gold unit by score, ties by lower index."""
    out: list[int] = []
    idx = np.arange(len(scores))
    for g in gold:
        sg = scores[int(g)]
        out.append(1 + int((scores > sg).sum()) + int(((scores == sg) & (idx < g)).sum()))
    return out


class _Scorer:
    """Metrics of whole score vectors under the four gold readings."""

    def __init__(self, golds: dict[str, Arr]) -> None:
        self.golds = golds
        self.keys: list[str] = []
        self.rows: list[list[float]] = []

    def metrics(self, scores: Arr) -> list[float]:
        from ril.evaluation.metrics import ndcg_at_k, recall_at_k

        out: list[float] = []
        for r in READINGS:
            g = self.golds[r]
            if len(g) == 0:
                out += [math.nan, math.nan]
                continue
            ranks = gold_ranks(scores, g)
            out += [ndcg_at_k(ranks, 10, len(g)), recall_at_k(ranks, 100, len(g))]
        return out

    def add(self, key: str, scores: Arr) -> None:
        self.keys.append(key)
        self.rows.append(self.metrics(scores))


# --------------------------------------------------------------------------- one level


def first_stage(sc: _Scorer, bm25: Arr, dense: dict[str, Arr], fs: FirstSpec) -> None:
    """Keys of item 2 for one (instance, level)."""
    sc.add("bm25", bm25)
    pb = positions(bm25)
    nb = minmax(bm25)
    for v in fs.variants:
        d = dense[v]
        sc.add(f"dense|{v}", d)
        pd = positions(d)
        ks = (fs.rrf_k_of[v],) if fs.rrf_k_of and v in fs.rrf_k_of else fs.rrf_ks
        for k in ks:
            sc.add(f"rrf|{v}|k{k}", rrf_scores([pb, pd], k))
        nd = minmax(d)
        alphas = (fs.alpha_of[v],) if fs.alpha_of and v in fs.alpha_of else fs.alphas
        for a in alphas:
            sc.add(f"score|{v}|a{a}", a * nb + (1 - a) * nd)


def graph_stage(
    ident: str,
    sc: _Scorer,
    bm25: Arr,
    dense: Arr,
    golds: dict[str, Arr],
    file_of_unit: Arr,
    age_days: Arr,
    graph: FamilyGraph,
    gs: GraphSpec,
) -> tuple[list[str], list[list[float]]]:
    """Keys of item 3 for one (instance, level); returns the ``list``/``rrf3`` keys and rows."""
    table = subset_table()
    pb, pd = positions(bm25), positions(dense)
    fused = rrf_scores([pb, pd], gs.k)
    sc.add("first", fused)
    base_score = gs.alpha * minmax(bm25) + (1 - gs.alpha) * minmax(dense)
    sc.add("first_score", base_score)
    keys: list[str] = []
    rows: list[list[float]] = []
    list_ways = tuple(w for w in gs.ways if w in ("list", "rrf3"))
    if list_ways:
        lvl = _Level(ident, fused, golds, file_of_unit, age_days, graph, fused=True)
        variants = tuple("list" if w == "list" else "rrf" for w in list_ways)
        grid = GraphGrid(
            variants=variants,
            subsets=gs.subsets,
            seeds=gs.seeds,
            gammas=gs.gammas,
            hops=gs.hops,
            cap=gs.cap,
            controls=CONTROLS,
            draws=gs.draws,
            rrf_k=gs.k,
        )
        lvl.run_graph(grid, table)
        for k, r in zip(lvl.keys, lvl.rows, strict=True):
            keys.append(k.replace("rrf|", "rrf3|", 1) if k.startswith("rrf|") else k)
            rows.append(r)
    if "score" in gs.ways:
        order = order_by_score(fused)
        pos = np.empty(len(fused), dtype=np.int64)
        pos[order] = np.arange(len(fused))
        top = float(fused[order[0]]) if len(fused) else 1.0
        n = len(fused)
        max_c = max(gs.seeds)
        seeds_all = [int(u) for u in order[:max_c]]
        snorm_all = [float(fused[u]) / top for u in seeds_all]
        file_of_pos = file_of_unit[order].astype(np.int64)
        for subset in gs.subsets:
            fams = table[subset]
            dist_cache: dict[int, dict[int, int]] = {}
            for c in gs.seeds:
                seeds = seeds_all[:c]
                for s in seeds:
                    if s not in dist_cache:
                        dist_cache[s] = bfs_distances(graph, fams, s, max(gs.hops))
                for h in gs.hops:
                    for gamma in gs.gammas:
                        g = combine_uniform(
                            [dist_cache[s] for s in seeds], snorm_all[: len(seeds)], gamma, h
                        )
                        exp_u = select_expansion(g, seeds, pos, n, gs.cap)
                        gvec = np.zeros(n)
                        for u in exp_u:
                            gvec[u] = g[u]
                        for s, sn in zip(seeds, snorm_all, strict=False):
                            gvec[s] = sn  # seeds keep their own (hop 0) graph score
                        for w in gs.weights:
                            key = f"score|{subset}|C{c}|g{gamma}|h{h}|w{w}"
                            sc.add(key, (1 - w) * base_score + w * gvec)
                            if not gs.score_controls:
                                continue
                            seed_pos = [int(pos[s]) for s in seeds]
                            vals = [g[u] for u in exp_u]
                            for ctrl in CONTROLS:
                                acc = []
                                for draw in range(gs.draws):
                                    rng = _rng(ident, subset, c, h, gamma, w, ctrl, draw)
                                    m = len(exp_u)
                                    rp = (
                                        random_whole(rng, n, m, seed_pos)
                                        if ctrl == "rand_whole"
                                        else random_same_files(rng, file_of_pos, seed_pos, m)
                                    )
                                    cvec = np.zeros(n)
                                    for p, val in zip(rp, vals, strict=False):
                                        cvec[int(order[p])] = val
                                    for s, sn in zip(seeds, snorm_all, strict=False):
                                        cvec[s] = sn
                                    acc.append(sc.metrics((1 - w) * base_score + w * cvec))
                                sc.keys.append(f"score|{ctrl}|{subset}|C{c}|g{gamma}|h{h}|w{w}")
                                sc.rows.append([float(x) for x in np.mean(acc, axis=0)])
    return keys, rows


def evaluate_instance(
    arrays: dict[str, Arr], meta: Record, spec: X2Spec, dense: dict[str, dict[str, Arr]]
) -> tuple[Record, dict[str, Arr]]:
    """Evaluate one cached instance; ``dense[variant][f"dense_{level}"]`` are its dense scores."""
    n = int(meta["units"])
    pairs = {
        k[6:]: [(int(a), int(b)) for a, b in v] for k, v in arrays.items() if k.startswith("pairs_")
    }
    graph = FamilyGraph.from_pairs(n, pairs)
    out: dict[str, Arr] = {}
    info: Record = {"levels": {}}
    keys_ref: list[str] | None = None
    for level in meta["levels"]:
        if f"gold_{level}_{READINGS[0]}" not in arrays:
            continue  # a member the folder does not label at this level has queries but no gold
        golds = {r: arrays[f"gold_{level}_{r}"] for r in READINGS}
        if not any(len(g) for g in golds.values()):
            continue
        bm25 = arrays[f"scores_{level}"].astype(np.float64)
        dl = {v: d[f"dense_{level}"].astype(np.float64) for v, d in dense.items()}
        for v, d in dl.items():
            if len(d) != n:
                raise ValueError(f"{meta['instance']}: dense {v} has {len(d)} units, cache {n}")
        sc = _Scorer(golds)
        extra_k: list[str] = []
        extra_r: list[list[float]] = []
        if spec.first is not None:
            first_stage(sc, bm25, dl, spec.first)
        if spec.graph is not None:
            gs = spec.graph
            extra_k, extra_r = graph_stage(
                f"{meta['instance']}|{level}",
                sc,
                bm25,
                dl[gs.variant],
                golds,
                arrays["file_of_unit"],
                arrays["age_days"],
                graph,
                gs,
            )
        keys = sc.keys + extra_k
        rows = sc.rows + extra_r
        if keys_ref is None:
            keys_ref = keys
        elif keys != keys_ref:
            raise RuntimeError("key order differs between levels of one instance")
        out[f"metrics_{level}"] = np.asarray(rows, dtype=np.float64)
        out[f"aux_{level}"] = np.zeros((0, 1 + len(READINGS)))
        info["levels"][level] = {f"gold_{r}": int(len(golds[r])) for r in READINGS}
        info["levels"][level]["gold_units"] = int(len(golds["units"]))
    out["keys"] = np.asarray(keys_ref or [], dtype=str)
    out["aux_keys"] = np.asarray([], dtype=str)
    return info, out


def run_x2_eval(cfg: Record, cache_dir: str, dense_root: str, out_dir: str) -> dict[str, int]:
    """Evaluate every cached instance of the specification's roles; resumable."""
    spec = spec_from_config(cfg)
    variants: set[str] = set()
    if spec.first is not None:
        variants |= set(spec.first.variants)
    if spec.graph is not None:
        variants.add(spec.graph.variant)
    counts = {"evaluated": 0, "skipped_role": 0, "reused": 0, "no_dense": 0}
    for name in sorted(os.listdir(cache_dir)):
        if not name.endswith(".npz"):
            continue
        arrays, meta = read_cache(os.path.join(cache_dir, name))
        if meta["role"] not in spec.roles:
            counts["skipped_role"] += 1
            continue
        ehash = x2_eval_hash(cfg, str(meta["config_hash"]))
        out = os.path.join(out_dir, name)
        if os.path.exists(out):
            old, _ = read_eval(out)
            if old.get("eval_hash") == ehash:
                counts["reused"] += 1
                continue
        dense: dict[str, dict[str, Arr]] = {}
        for v in sorted(variants):
            p = os.path.join(dense_root, v, name)
            if not os.path.exists(p):
                break
            with np.load(p, allow_pickle=False) as dz:
                dense[v] = {k: dz[k] for k in dz.files if k.startswith("dense_")}
        if len(dense) != len(variants):
            counts["no_dense"] += 1
            continue
        info, res = evaluate_instance(arrays, meta, spec, dense)
        info.update(
            eval_hash=ehash,
            instance=meta["instance"],
            role=meta["role"],
            dataset=meta["dataset"],
            folder=meta["folder"],
            repo_id=meta["repo_id"],
            units=meta["units"],
        )
        write_eval(out, info, res)
        counts["evaluated"] += 1
    return counts
