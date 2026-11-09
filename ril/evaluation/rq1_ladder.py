"""RQ1 ladder on the development cache: each signal added to the dense retriever (E-RQ1-LADDER).

Exploratory. Implements ``docs/experiments/B.md`` E-RQ1-LADDER. Inputs are those of
``ril.evaluation.s1_graph_role``: the E3 instance cache (BM25 scores, typed edge pairs, file and
age of every unit, gold unit indices under four readings) and one stored dense score file per
encoder variant. Nothing is encoded here and no test instance is read (a specification that
names the role ``test`` is refused).

Per (instance, level) the whole-snapshot score vectors of these rungs are scored, all on the same
queries, the same candidate set (every unit of the snapshot) and the same expansion budget:

* ``ref|bm25``, ``r1|dense``: the two signals alone (BM25 is a reference row, not a rung);
* ``p|first``: RRF of the BM25 and dense rankings (rung 2), the first stage of the ``p`` stage;
* ``r|first``: the same first stage plus the recency prior ``score / best + lam * exp(-age / tau)``;
* ``s|first``: the score-level fusion of E-GRAPH-ROLE (``alpha * mm(bm25) + (1 - alpha) *
  mm(dense)``), kept only as the regression control of the earlier entry.

On each of the three first stages (``p`` RRF, ``r`` RRF with recency, ``s`` score level) and for the
two edge sets ``b`` (the stored graph, contain included) and ``e`` (non-contain edges only) the
stated cell of E-GRAPH-ROLE is run (C seeds, gamma, hops, graph weight, cap) with four candidate
sources: ``graph`` (the typed expansion), ``sfscore`` (same-file expansion ordered by the
first-stage score), ``sfrand`` (same files, random order, mean of ``draws``) and ``topm`` (the
next best units with no file constraint). ``sfscore``, ``sfrand`` and ``topm`` are size-matched
to the graph expansion of the same edge set and take the same graph-score values in the same
order, so what differs is which units receive the boost.

Metric columns per reading of ``ril.evaluation.e3_prepare.READINGS``: nDCG@10 and Recall@100.

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
from ril.evaluation.s1_graph_role import (
    VARIANT_FAMILIES,
    _blend,
    _gvec,
    same_file_by_score,
)
from ril.evaluation.x2_eval import _Scorer, minmax, positions, rrf_scores
from ril.retrieval.bm25_index import order_by_score
from ril.retrieval.graph_expansion import (
    FamilyGraph,
    bfs_distances,
    combine_uniform,
    random_same_files,
    select_expansion,
)
from ril.retrieval.recency import blend, recency_prior

LADDER_VERSION = "rq1-ladder/v2"
Record = dict[str, Any]
Arr = np.ndarray[Any, Any]

STAGES = ("p", "r", "s")
"""First stages: ``p`` RRF, ``r`` RRF plus recency, ``s`` score-level fusion (control)."""
EDGE_SETS = ("b", "e")
"""``b`` stored graph (contain, import, invoke, inherit), ``e`` non-contain edges only."""
SOURCES = ("graph", "sfscore", "sfrand", "topm")


@dataclass(frozen=True)
class LadderSpec:
    """One stated cell on one dense variant."""

    variant: str
    k: int
    alpha: float
    seeds: int
    gamma: float
    hops: int
    weight: float
    cap: int
    draws: int
    lam: float
    tau_days: float


def spec_from_config(cfg: Record) -> tuple[LadderSpec, tuple[str, ...]]:
    """Validated specification and roles; the final test is never read here."""
    roles = tuple(cfg["roles"])
    if roles != ("dev",):
        raise ValueError("the ladder is a development-set measurement: roles must be ['dev']")
    g, r = cfg["graph"], cfg["recency"]
    return (
        LadderSpec(
            variant=str(g["variant"]),
            k=int(g["k"]),
            alpha=float(g["alpha"]),
            seeds=int(g["seeds"]),
            gamma=float(g["gamma"]),
            hops=int(g["hops"]),
            weight=float(g["weight"]),
            cap=int(g["cap"]),
            draws=int(g["draws"]),
            lam=float(r["lam"]),
            tau_days=float(r["tau_days"]),
        ),
        roles,
    )


def ladder_hash(cfg: Record, prepare_hash: str) -> str:
    """SHA-256 over the evaluation configuration and the cache's configuration hash."""
    payload = {"version": LADDER_VERSION, "config": cfg, "prepare": prepare_hash}
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def expansion_keys(stage: str) -> list[str]:
    """Metric keys of one stage's expansion runs, in the order ``expansion_level`` writes them."""
    return [f"{stage}|{src}|{v}" for v in EDGE_SETS for src in SOURCES]


def all_keys() -> list[str]:
    """Row names of the metric matrix of one (instance, level)."""
    keys = ["ref|bm25", "r1|dense"]
    for stage in STAGES:
        keys.append(f"{stage}|first")
        keys += expansion_keys(stage)
    return keys


def expansion_level(
    ident: str,
    stage: str,
    base: Arr,
    seed_scores: Arr,
    golds: dict[str, Arr],
    file_of_unit: Arr,
    graph: FamilyGraph,
    sp: LadderSpec,
    sc: _Scorer,
) -> tuple[list[str], list[list[float]]]:
    """Score the four sources of both edge sets on the first-stage score ``base``.

    ``seed_scores`` rank the units (seeds are its top ``sp.seeds``, the same-file and top-M sources
    follow its order and the seed scores are normalised by its best value); the blended score is
    ``(1 - w) * base + w * g``. They are the same vector except for the score-level control,
    which seeds from the RRF ranking as E-GRAPH-ROLE does. Returns the aux keys and rows: per
    source the expansion size and its gold hits under each reading.
    """
    n = len(base)
    order = order_by_score(seed_scores)
    pos = np.empty(n, dtype=np.int64)
    pos[order] = np.arange(n)
    top = float(seed_scores[order[0]]) if n else 1.0
    seeds = [int(u) for u in order[: sp.seeds]]
    snorm = [float(seed_scores[u]) / top for u in seeds]
    file_of_pos = file_of_unit[order].astype(np.int64)
    seed_pos = [int(pos[s]) for s in seeds]
    seed_set = set(seeds)
    gold_sets = [{int(x) for x in golds[r]} for r in READINGS]
    aux_keys: list[str] = []
    aux_rows: list[list[float]] = []
    w = sp.weight
    for vname in EDGE_SETS:
        fams = VARIANT_FAMILIES[vname]
        dmaps = [bfs_distances(graph, fams, s, sp.hops) for s in seeds]
        g = combine_uniform(dmaps, snorm, sp.gamma, sp.hops)
        exp_u = select_expansion(g, seeds, pos, n, sp.cap)
        vals = [g[u] for u in exp_u]
        m = len(exp_u)
        c_u = same_file_by_score(file_of_unit, order, seeds, m)
        topm_u = [int(u) for u in order if int(u) not in seed_set][:m]
        sets = {"graph": exp_u, "sfscore": c_u, "topm": topm_u}
        for src in ("graph", "sfscore"):
            sc.add(
                f"{stage}|{src}|{vname}", _blend(base, _gvec(n, sets[src], vals, seeds, snorm), w)
            )
        # sfrand sits between sfscore and topm in the key order of ``expansion_keys``
        acc: list[list[float]] = []
        hits: list[list[float]] = []
        for draw in range(sp.draws):
            rng = _rng(ident, stage, vname, sp.seeds, sp.hops, w, "rand_files", draw)
            rp = random_same_files(rng, file_of_pos, seed_pos, m)
            ru = [int(order[p]) for p in rp]
            acc.append(sc.metrics(_blend(base, _gvec(n, ru, vals, seeds, snorm), w)))
            hits.append([float(len(set(ru) & gs)) for gs in gold_sets])
        sc.keys.append(f"{stage}|sfrand|{vname}")
        sc.rows.append([float(x) for x in np.mean(acc, axis=0)])
        sc.add(f"{stage}|topm|{vname}", _blend(base, _gvec(n, topm_u, vals, seeds, snorm), w))
        aux_keys.append(f"E|{stage}|{vname}|sfrand")
        aux_rows.append([float(m), *[float(x) for x in np.mean(hits, axis=0)]])
        for src in ("graph", "sfscore", "topm"):
            members = sets[src]
            aux_keys.append(f"E|{stage}|{vname}|{src}")
            aux_rows.append(
                [float(len(members)), *[float(len(set(members) & gs)) for gs in gold_sets]]
            )
    return aux_keys, aux_rows


def ladder_level(
    ident: str,
    bm25: Arr,
    dense: Arr,
    golds: dict[str, Arr],
    file_of_unit: Arr,
    age_days: Arr,
    graph: FamilyGraph,
    sp: LadderSpec,
) -> tuple[_Scorer, list[str], list[list[float]]]:
    """All keys of one (instance, level)."""
    sc = _Scorer(golds)
    sc.add("ref|bm25", bm25)
    sc.add("r1|dense", dense)
    fused = rrf_scores([positions(bm25), positions(dense)], sp.k)
    top = float(fused.max()) if len(fused) else 1.0
    plain = fused / top if top > 0 else fused
    prior = recency_prior(age_days, sp.tau_days)
    rec = blend(fused, prior, sp.lam)
    score_level = sp.alpha * minmax(bm25) + (1 - sp.alpha) * minmax(dense)
    aux_keys: list[str] = []
    aux_rows: list[list[float]] = []
    for stage, base, seed_scores in (
        ("p", plain, fused),
        ("r", rec, rec),
        ("s", score_level, fused),
    ):
        sc.add(f"{stage}|first", base)
        ak, ar = expansion_level(
            ident, stage, base, seed_scores, golds, file_of_unit, graph, sp, sc
        )
        aux_keys += ak
        aux_rows += ar
    return sc, aux_keys, aux_rows


def evaluate_instance(
    arrays: dict[str, Arr], meta: Record, sp: LadderSpec, dense: dict[str, Arr]
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
        sc, aux_keys, aux_rows = ladder_level(
            f"{meta['instance']}|{level}",
            arrays[f"scores_{level}"].astype(np.float64),
            d,
            golds,
            arrays["file_of_unit"],
            arrays["age_days"].astype(np.float64),
            graph,
            sp,
        )
        if sc.keys != all_keys():
            raise RuntimeError("key order of the level differs from all_keys()")
        if keys_ref is None:
            keys_ref, aux_ref = sc.keys, aux_keys
        elif aux_ref != aux_keys:
            raise RuntimeError("aux key order differs between levels of one instance")
        out[f"metrics_{level}"] = np.asarray(sc.rows, dtype=np.float64)
        out[f"aux_{level}"] = np.asarray(aux_rows, dtype=np.float64).reshape(-1, 1 + len(READINGS))
        info["levels"][level] = {f"gold_{r}": int(len(golds[r])) for r in READINGS}
        info["levels"][level]["gold_units"] = int(len(golds["units"]))
    out["keys"] = np.asarray(keys_ref or [], dtype=str)
    out["aux_keys"] = np.asarray(aux_ref or [], dtype=str)
    return info, out


def run_ladder_eval(cfg: Record, cache_dir: str, dense_root: str, out_dir: str) -> dict[str, int]:
    """Evaluate every cached development instance; resumable (files carry the config hash)."""
    sp, roles = spec_from_config(cfg)
    counts = {"evaluated": 0, "skipped_role": 0, "reused": 0, "no_dense": 0}
    for name in sorted(os.listdir(cache_dir)):
        if not name.endswith(".npz"):
            continue
        arrays, meta = read_cache(os.path.join(cache_dir, name))
        if meta["role"] not in roles:
            counts["skipped_role"] += 1
            continue
        ehash = ladder_hash(cfg, str(meta["config_hash"]))
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
            cache_hash=str(meta["config_hash"]),
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


def inventory(cache_dir: str, dense_roots: dict[str, str]) -> Record:
    """What the development caches and stored dense scores hold: instances per repository and role.

    Counts cache files per (role, dataset, repository) with their levels, the configuration hashes
    found in the cache, and for each dense variant how many of the development instances have a
    stored score file with the units of the cache.
    """
    repos: dict[str, dict[str, int]] = {}
    hashes: dict[str, int] = {}
    dev: list[tuple[str, int]] = []
    for name in sorted(os.listdir(cache_dir)):
        if not name.endswith(".npz"):
            continue
        _, meta = read_cache(os.path.join(cache_dir, name))
        key = f"{meta['role']}|{meta['dataset']}|{meta['repo_id']}"
        slot = repos.setdefault(key, {"instances": 0, "L2": 0, "L3": 0, "units_max": 0})
        slot["instances"] += 1
        for lv in meta["levels"]:
            slot[str(lv)] += 1
        slot["units_max"] = max(slot["units_max"], int(meta["units"]))
        hashes[str(meta["config_hash"])] = hashes.get(str(meta["config_hash"]), 0) + 1
        if meta["role"] == "dev":
            dev.append((name, int(meta["units"])))
    dense: dict[str, dict[str, int]] = {}
    for variant, root in dense_roots.items():
        have = 0
        mismatched = 0
        for name, units in dev:
            p = os.path.join(root, variant, name)
            if not os.path.exists(p):
                continue
            have += 1
            with np.load(p, allow_pickle=False) as dz:
                lens = {len(dz[k]) for k in dz.files if k.startswith("dense_")}
            mismatched += int(lens != {units})
        dense[variant] = {
            "dev_instances": len(dev),
            "with_dense": have,
            "units_mismatch": mismatched,
        }
    return {"repositories": repos, "cache_config_hashes": hashes, "dense": dense}
