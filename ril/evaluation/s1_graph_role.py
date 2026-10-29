"""Is the graph a retrieval signal beyond same-file expansion? (S1, Q49), on the E3/X2 cache.

Exploratory. Implements ``docs/EXPERIMENTS.md`` E-GRAPH-ROLE. Inputs are those of
``ril.evaluation.x2_eval``: the pilot-E3 cache (BM25 scores, typed edge pairs, file of each unit,
gold unit indices under four readings) and one dense score file per encoder variant. The stated
cell of X2 (score-level form, C 5, gamma 0.7, two hops, graph weight, cap 50) is run on one fused
first stage, with six candidate sources at the same budget (``cap``):

* ``a``  no expansion (the first-stage score and, beside it, the first-stage RRF);
* ``b``  graph expansion as stored: the D19 families ``contain``, ``import``, ``invoke``,
  ``inherit`` (the stored graph already drops ambiguous call sites, D26);
* ``c``  same-file expansion ordered by the first-stage score: the units of the seeds' files,
  best first-stage score first, as many as the graph variant it is matched to produced;
* ``d``  the same units drawn at random from the seeds' files (what earlier waves used as chance);
* ``e``  graph expansion over non-contain edges only (``import``, ``invoke``, ``inherit``);
* ``f``  contain edges only;
* ``topm`` (control added after the first run, see the configuration note): no file constraint,
  the next best first-stage units, as many as the matched graph variant, so that the part of
  ``c`` that is a top-up from the ranking can be told from the part that is same-file.

``c`` and ``d`` are size-matched to each of ``b``, ``e``, ``f`` and take the *same* graph-score
values in the same order as that variant, so what differs between a graph variant and its
same-file counterparts is which units receive the boost, nothing else. The gold readings and the
metrics are those of X2.

The reachability part answers: of the L3 gold units that the first stage leaves outside its top
100, how many can the graph reach from the first stage's best units in one or two hops over one
edge family, and how many of those lie in a file that contains none of the sources (so that a
same-file expansion could not reach them)?

Kept compatible with Python 3.10.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from typing import Any

import numpy as np

from ril.evaluation.e3_eval import _rng, read_eval, write_eval
from ril.evaluation.e3_prepare import READINGS, read_cache
from ril.evaluation.x2_eval import _Scorer, minmax, positions, rrf_scores
from ril.retrieval.bm25_index import order_by_score
from ril.retrieval.graph_expansion import (
    FamilyGraph,
    bfs_distances,
    combine_uniform,
    random_same_files,
    select_expansion,
)

S1_VERSION = "s1-graph-role/v1"
Record = dict[str, Any]
Arr = np.ndarray[Any, Any]

CORE = ("contain", "import", "invoke", "inherit")
NONCONTAIN = ("import", "invoke", "inherit")
VARIANT_FAMILIES: dict[str, tuple[str, ...]] = {
    "b": CORE,
    "e": NONCONTAIN,
    "f": ("contain",),
}
KINDS = ("graph", "sfscore", "sfrand")
"""Candidate sources of a graph variant: its expansion and the two size-matched same-file ones."""
REACH_FAMILIES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("contain", ("contain",)),
    ("import", ("import",)),
    ("invoke", ("invoke",)),
    ("inherit", ("inherit",)),
    ("noncontain", NONCONTAIN),
    ("core", CORE),
)
REACH_HOPS = (1, 2)
FIRST_STAGE_TOP = 100


@dataclass(frozen=True)
class S1Spec:
    """One stated cell on one first stage."""

    variant: str
    k: int
    alpha: float
    seeds: int
    gamma: float
    hops: int
    weights: tuple[float, ...]
    cap: int
    draws: int
    reach_top: tuple[int, ...]


def spec_from_config(cfg: Record) -> tuple[S1Spec, tuple[str, ...]]:
    """Validated specification and roles; test instances need a confirm specification."""
    roles = tuple(cfg["roles"])
    if "test" in roles and not cfg.get("confirm", False):
        raise ValueError("test instances may only be evaluated by a confirm specification")
    g = cfg["graph"]
    if len(g["seeds"]) != 1 or len(g["gammas"]) != 1 or len(g["hops"]) != 1:
        raise ValueError("one C, one gamma and one hop count")
    weights = tuple(float(w) for w in g["weights"])
    if "test" in roles and len(weights) != 1:
        raise ValueError("confirm: one weight")
    return (
        S1Spec(
            variant=str(g["variant"]),
            k=int(g["k"]),
            alpha=float(g["alpha"]),
            seeds=int(g["seeds"][0]),
            gamma=float(g["gammas"][0]),
            hops=int(g["hops"][0]),
            weights=weights,
            cap=int(g.get("cap", 50)),
            draws=int(g.get("draws", 3)),
            reach_top=tuple(int(t) for t in g.get("reach_top", (5, 100))),
        ),
        roles,
    )


def s1_hash(cfg: Record, prepare_hash: str) -> str:
    """SHA-256 over the evaluation configuration and the cache's configuration hash."""
    payload = {"version": S1_VERSION, "config": cfg, "prepare": prepare_hash}
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- candidate sources


def same_file_by_score(file_of_unit: Arr, order: Arr, seeds: list[int], m: int) -> list[int]:
    """``m`` units of the seeds' files (seeds excluded), best first-stage score first.

    ``order`` lists all units best first. When the files hold fewer than ``m`` other units the
    list is topped up with the next best units of the whole ranking, so the size always matches
    (the same convention as ``random_same_files``).
    """
    if m <= 0:
        return []
    seed_set = set(seeds)
    files = {int(file_of_unit[s]) for s in seeds}
    chosen: list[int] = []
    for u in order:
        iu = int(u)
        if iu in seed_set:
            continue
        if int(file_of_unit[iu]) in files:
            chosen.append(iu)
            if len(chosen) == m:
                return chosen
    taken = set(chosen)
    for u in order:
        iu = int(u)
        if iu in seed_set or iu in taken:
            continue
        chosen.append(iu)
        if len(chosen) == m:
            break
    return chosen


def _blend(base: Arr, gvec: Arr, w: float) -> Arr:
    out: Arr = (1 - w) * base + w * gvec
    return out


def _gvec(n: int, units: list[int], vals: list[float], seeds: list[int], snorm: list[float]) -> Arr:
    g = np.zeros(n)
    for u, v in zip(units, vals, strict=False):
        g[u] = v
    for s, sn in zip(seeds, snorm, strict=True):
        g[s] = sn  # seeds keep their own (hop 0) score
    return g


def multi_source_reach(
    graph: FamilyGraph, families: tuple[str, ...], sources: list[int], hops: int
) -> dict[int, int]:
    """Hop distance (1..hops) of every node reached from any source over ``families``.

    Sources themselves are not in the result.
    """
    dist: dict[int, int] = {s: 0 for s in sources}
    frontier = list(sources)
    tables = [graph.adj[f] for f in families if f in graph.adj]
    for d in range(1, hops + 1):
        nxt: list[int] = []
        for node in frontier:
            for table in tables:
                for nb in table.get(node, ()):
                    if nb not in dist:
                        dist[nb] = d
                        nxt.append(nb)
        frontier = nxt
        if not frontier:
            break
    for s in sources:
        del dist[s]
    return dist


# --------------------------------------------------------------------------- one level


def reach_keys(tops: tuple[int, ...]) -> list[str]:
    """Row names of the reachability matrix: ``top|family|hop`` plus one same-file row per top."""
    keys: list[str] = []
    for t in tops:
        keys.append(f"top{t}|samefile|0")
        for fam, _ in REACH_FAMILIES:
            for h in REACH_HOPS:
                keys.append(f"top{t}|{fam}|{h}")
    return keys


def reach_level(
    graph: FamilyGraph,
    order: Arr,
    file_of_unit: Arr,
    golds: dict[str, Arr],
    tops: tuple[int, ...],
) -> Arr:
    """Counts per (reading, row): columns ``den, samefile, reach, reach_not_samefile``.

    ``den`` is the number of gold units outside the first-stage top 100; ``samefile`` those of
    them in a file of one of the sources; for a graph row ``reach`` is the number within the hop
    limit over the family and ``reach_not_samefile`` the number of those not in a source file.
    Rows are ``reach_keys`` for each reading in ``READINGS`` order.
    """
    n = graph.n_units
    pos = np.empty(n, dtype=np.int64)
    pos[order] = np.arange(n)
    rows: list[list[float]] = []
    for r in READINGS:
        gold = [int(g) for g in golds[r]]
        out = [g for g in gold if pos[g] >= FIRST_STAGE_TOP]
        for t in tops:
            sources = [int(u) for u in order[:t]]
            files = {int(file_of_unit[s]) for s in sources}
            same = {g for g in out if int(file_of_unit[g]) in files}
            rows.append([float(len(out)), float(len(same)), float(len(same)), 0.0])
            for _, fams in REACH_FAMILIES:
                dist = multi_source_reach(graph, fams, sources, max(REACH_HOPS))
                for h in REACH_HOPS:
                    hit = {g for g in out if dist.get(g, 99) <= h}
                    rows.append(
                        [
                            float(len(out)),
                            float(len(same)),
                            float(len(hit)),
                            float(len(hit - same)),
                        ]
                    )
    return np.asarray(rows, dtype=np.float64)


def s1_level(
    ident: str,
    bm25: Arr,
    dense: Arr,
    golds: dict[str, Arr],
    file_of_unit: Arr,
    graph: FamilyGraph,
    sp: S1Spec,
    with_reach: bool,
) -> tuple[_Scorer, list[str], list[list[float]], Arr | None]:
    """All keys of one (instance, level): scorer, aux keys, aux rows, reachability counts."""
    n = len(bm25)
    sc = _Scorer(golds)
    fused = rrf_scores([positions(bm25), positions(dense)], sp.k)
    base = sp.alpha * minmax(bm25) + (1 - sp.alpha) * minmax(dense)
    sc.add("a_none", base)
    sc.add("a_rrf", fused)
    order = order_by_score(fused)
    pos = np.empty(n, dtype=np.int64)
    pos[order] = np.arange(n)
    top = float(fused[order[0]]) if n else 1.0
    seeds = [int(u) for u in order[: sp.seeds]]
    snorm = [float(fused[u]) / top for u in seeds]
    file_of_pos = file_of_unit[order].astype(np.int64)
    aux_keys: list[str] = []
    aux_rows: list[list[float]] = []
    for vname, fams in VARIANT_FAMILIES.items():
        dmaps = [bfs_distances(graph, fams, s, sp.hops) for s in seeds]
        g = combine_uniform(dmaps, snorm, sp.gamma, sp.hops)
        exp_u = select_expansion(g, seeds, pos, n, sp.cap)
        vals = [g[u] for u in exp_u]
        m = len(exp_u)
        c_u = same_file_by_score(file_of_unit, order, seeds, m)
        seed_pos = [int(pos[s]) for s in seeds]
        seed_set = set(seeds)
        topm_u = [int(u) for u in order if int(u) not in seed_set][:m]
        files = {int(file_of_unit[x]) for x in seeds}
        sets = {"graph": exp_u, "sfscore": c_u, "topm": topm_u}
        for w in sp.weights:
            sc.add(f"graph|{vname}|w{w}", _blend(base, _gvec(n, exp_u, vals, seeds, snorm), w))
            sc.add(f"sfscore|{vname}|w{w}", _blend(base, _gvec(n, c_u, vals, seeds, snorm), w))
            sc.add(f"topm|{vname}|w{w}", _blend(base, _gvec(n, topm_u, vals, seeds, snorm), w))
            acc: list[list[float]] = []
            hits: list[list[float]] = []
            for draw in range(sp.draws):
                rng = _rng(ident, vname, sp.seeds, sp.hops, w, "rand_files", draw)
                rp = random_same_files(rng, file_of_pos, seed_pos, m)
                ru = [int(order[p]) for p in rp]
                acc.append(sc.metrics(_blend(base, _gvec(n, ru, vals, seeds, snorm), w)))
                hits.append([float(len(set(ru) & {int(x) for x in golds[r]})) for r in READINGS])
            sc.keys.append(f"sfrand|{vname}|w{w}")
            sc.rows.append([float(x) for x in np.mean(acc, axis=0)])
            if w == sp.weights[0]:  # sizes and hits do not depend on the weight
                aux_keys += [f"E|{vname}|sfrand"]
                aux_rows.append([float(m), *[float(x) for x in np.mean(hits, axis=0)]])
        for kind in ("graph", "sfscore", "topm"):
            members = sets[kind]
            gold_sets = [{int(x) for x in golds[r]} for r in READINGS]
            aux_keys.append(f"E|{vname}|{kind}")
            aux_rows.append(
                [float(len(members)), *[float(len(set(members) & g)) for g in gold_sets]]
            )
            infile = [u for u in members if int(file_of_unit[u]) in files]
            aux_keys.append(f"E|{vname}|{kind}_infile")
            aux_rows.append([float(len(infile)), *[float(len(set(infile) & g)) for g in gold_sets]])
    reach = reach_level(graph, order, file_of_unit, golds, sp.reach_top) if with_reach else None
    return sc, aux_keys, aux_rows, reach


def evaluate_instance(
    arrays: dict[str, Arr], meta: Record, sp: S1Spec, dense: dict[str, Arr]
) -> tuple[Record, dict[str, Arr]]:
    """Evaluate one cached instance; ``dense`` holds ``dense_<level>`` scores of the variant."""
    n = int(meta["units"])
    pairs = {
        k[6:]: [(int(a), int(b)) for a, b in v] for k, v in arrays.items() if k.startswith("pairs_")
    }
    graph = FamilyGraph.from_pairs(n, pairs)
    out: dict[str, Arr] = {}
    info: Record = {"levels": {}}
    keys_ref: list[str] | None = None
    aux_ref: list[str] | None = None
    for level in meta["levels"]:
        golds = {r: arrays[f"gold_{level}_{r}"] for r in READINGS}
        if not any(len(g) for g in golds.values()):
            continue
        d = dense[f"dense_{level}"].astype(np.float64)
        if len(d) != n:
            raise ValueError(f"{meta['instance']}: dense has {len(d)} units, cache {n}")
        sc, aux_keys, aux_rows, reach = s1_level(
            f"{meta['instance']}|{level}",
            arrays[f"scores_{level}"].astype(np.float64),
            d,
            golds,
            arrays["file_of_unit"],
            graph,
            sp,
            with_reach=(level == "L3"),
        )
        if keys_ref is None:
            keys_ref, aux_ref = sc.keys, aux_keys
        elif keys_ref != sc.keys or aux_ref != aux_keys:
            raise RuntimeError("key order differs between levels of one instance")
        out[f"metrics_{level}"] = np.asarray(sc.rows, dtype=np.float64)
        out[f"aux_{level}"] = np.asarray(aux_rows, dtype=np.float64).reshape(-1, 1 + len(READINGS))
        if reach is not None:
            out[f"reach_{level}"] = reach
        info["levels"][level] = {f"gold_{r}": int(len(golds[r])) for r in READINGS}
        info["levels"][level]["gold_units"] = int(len(golds["units"]))
    out["keys"] = np.asarray(keys_ref or [], dtype=str)
    out["aux_keys"] = np.asarray(aux_ref or [], dtype=str)
    out["reach_keys"] = np.asarray(reach_keys(sp.reach_top), dtype=str)
    return info, out


def run_s1_eval(cfg: Record, cache_dir: str, dense_root: str, out_dir: str) -> dict[str, int]:
    """Evaluate every cached instance of the specification's roles; resumable."""
    sp, roles = spec_from_config(cfg)
    counts = {"evaluated": 0, "skipped_role": 0, "reused": 0, "no_dense": 0}
    for name in sorted(os.listdir(cache_dir)):
        if not name.endswith(".npz"):
            continue
        arrays, meta = read_cache(os.path.join(cache_dir, name))
        if meta["role"] not in roles:
            counts["skipped_role"] += 1
            continue
        ehash = s1_hash(cfg, str(meta["config_hash"]))
        out = os.path.join(out_dir, name)
        if os.path.exists(out):
            old, _ = read_eval(out)
            if old.get("eval_hash") == ehash:
                counts["reused"] += 1
                continue
        p = os.path.join(dense_root, sp.variant, name)
        if not os.path.exists(p):
            counts["no_dense"] += 1
            continue
        with np.load(p, allow_pickle=False) as dz:
            dense = {k: dz[k] for k in dz.files if k.startswith("dense_")}
        info, res = evaluate_instance(arrays, meta, sp, dense)
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
