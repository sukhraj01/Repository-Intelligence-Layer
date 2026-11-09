"""Stacked expansion against the same-file control, and the test and configure edges on L3 (G1).

Exploratory. Implements ``docs/experiments/B.md`` E-A-OWNER-ITEMS items 1 and 2 (the flip
experiment stated at the end of ``docs/EXPERIMENTS.md`` E-GRAPH-ROLE, Q30, and E-GRAPH-L3). Inputs
are those of ``ril.evaluation.s1_graph_role``: the E3 cache (BM25 scores, typed edge pairs per
family, file of each unit, gold under four readings) and one dense score file per encoder variant.
The first stage, the cell (score-level blend, C 5, gamma 0.7, two hops, weight 0.5, cap 50) and the
rest are those of E-GRAPH-ROLE, nothing is tuned.

Two groups of candidate sources, every one at the same budget as its matched control:

* *plain* (as in S1): the expansion over an edge-family set ``v``, the same number of units taken
  as same-file by first-stage score (``sfscore``), as the next best first-stage units with no file
  constraint (``topm``) and as random units of the seeds' files (``sfrand``, 3 draws). The same
  hop-decay values are assigned in the same order, so only which units get the boost differs.
  Family sets: ``core`` (contain, import, invoke, inherit: the stored graph and the regression
  control against S1), ``coretc`` (core plus tests and configures), ``tc`` (tests and configures
  alone).
* *stacked*: the reference list is the same-file list of M units (M the size of the ``core``
  expansion, values those of ``core``); in the stacked list the last N of them are replaced by the
  N best neighbours of the seeds over a family set ``f`` (``nc``: import, invoke, inherit; ``nctc``:
  those plus tests and configures; ``tc``), hop-decay order, never a seed or a retained unit, and
  carry the values of the positions they take. Chance controls replace the same N positions by the
  next best first-stage units outside the list (``stacktopm``) or by random units outside it
  (``stackrand``, 3 draws). If fewer than N neighbours exist the list is filled with the next
  same-file units, so the size is always M.

A recency prior at the setting E-RECENCY selected on dev (lam 0.2, tau 30 days; fixed, not
re-tuned) is added to the same blended first stage, with the same ages shuffled over the units as
its chance control (version v2 of this module; v1 had no recency arm).

Kept compatible with Python 3.10.
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any

import numpy as np

from ril.evaluation.e3_eval import _rng, read_eval, write_eval
from ril.evaluation.e3_prepare import READINGS, read_cache
from ril.evaluation.s1_graph_role import (
    CORE,
    NONCONTAIN,
    S1Spec,
    _blend,
    _gvec,
    same_file_by_score,
    spec_from_config,
)
from ril.evaluation.x2_eval import _Scorer, minmax, positions, rrf_scores
from ril.retrieval.bm25_index import order_by_score
from ril.retrieval.graph_expansion import (
    FamilyGraph,
    bfs_distances,
    combine_uniform,
    random_same_files,
    random_whole,
    select_expansion,
)
from ril.retrieval.recency import blend as recency_blend
from ril.retrieval.recency import recency_prior

G1_VERSION = "g1-stacked/v2"
Record = dict[str, Any]
Arr = np.ndarray[Any, Any]

TC = ("tests", "configures")
PLAIN_VARIANTS: dict[str, tuple[str, ...]] = {
    "core": CORE,
    "coretc": CORE + TC,
    "tc": TC,
}
STACK_FAMILIES: dict[str, tuple[str, ...]] = {
    "nc": NONCONTAIN,
    "nctc": NONCONTAIN + TC,
    "tc": TC,
}
STACK_N = (10, 25)
RECENCY_LAM = 0.2
RECENCY_TAU = 30.0
"""The setting E-RECENCY selected on dev (E5 grid); fixed here, nothing is tuned again."""
KINDS_PLAIN = ("graph", "sfscore", "sfrand", "topm")
KINDS_STACK = ("stack", "stacktopm", "stackrand")


def g1_hash(cfg: Record, prepare_hash: str) -> str:
    """SHA-256 over the evaluation configuration and the cache's configuration hash."""
    payload = {"version": G1_VERSION, "config": cfg, "prepare": prepare_hash}
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def stacked_list(
    retained: list[int],
    neighbours: list[int],
    filler: list[int],
    m: int,
) -> list[int]:
    """The stacked list: retained same-file units, then neighbours, then filler up to ``m``."""
    out = list(retained) + list(neighbours)
    for u in filler:
        if len(out) >= m:
            break
        if u not in set(out):
            out.append(u)
    return out[:m]


def g1_level(
    ident: str,
    bm25: Arr,
    dense: Arr,
    golds: dict[str, Arr],
    file_of_unit: Arr,
    graph: FamilyGraph,
    sp: S1Spec,
    age_days: Arr,
) -> tuple[_Scorer, list[str], list[list[float]]]:
    """All keys of one (instance, level): scorer, aux keys and aux rows (sizes, hits, in-file)."""
    n = len(bm25)
    w = sp.weights[0]
    sc = _Scorer(golds)
    fused = rrf_scores([positions(bm25), positions(dense)], sp.k)
    base = sp.alpha * minmax(bm25) + (1 - sp.alpha) * minmax(dense)
    sc.add("a_none", base)
    order = order_by_score(fused)
    pos = np.empty(n, dtype=np.int64)
    pos[order] = np.arange(n)
    top = float(fused[order[0]]) if n else 1.0
    seeds = [int(u) for u in order[: sp.seeds]]
    snorm = [float(fused[u]) / top for u in seeds]
    seed_set = set(seeds)
    seed_files = {int(file_of_unit[x]) for x in seeds}
    file_of_pos = file_of_unit[order].astype(np.int64)
    gold_sets = [{int(x) for x in golds[r]} for r in READINGS]
    aux_keys: list[str] = []
    aux_rows: list[list[float]] = []

    def note(key: str, members: list[int]) -> None:
        infile = [u for u in members if int(file_of_unit[u]) in seed_files]
        aux_keys.append(f"E|{key}")
        aux_rows.append([float(len(members)), *[float(len(set(members) & g)) for g in gold_sets]])
        aux_keys.append(f"E|{key}_infile")
        aux_rows.append([float(len(infile)), *[float(len(set(infile) & g)) for g in gold_sets]])

    def expansion(
        fams: tuple[str, ...], skip: list[int], cap: int
    ) -> tuple[list[int], list[float]]:
        dmaps = [bfs_distances(graph, fams, s, sp.hops) for s in seeds]
        g = combine_uniform(dmaps, snorm, sp.gamma, sp.hops)
        exp_u = select_expansion(g, [*seeds, *skip], pos, n, cap)
        return exp_u, [g[u] for u in exp_u]

    # ---- plain expansions against their size-matched controls (S1 form)
    ref_units: list[int] = []
    ref_vals: list[float] = []
    for vname, fams in PLAIN_VARIANTS.items():
        exp_u, vals = expansion(fams, [], sp.cap)
        m = len(exp_u)
        if vname == "core":
            ref_units, ref_vals = exp_u, vals
        c_u = same_file_by_score(file_of_unit, order, seeds, m)
        topm_u = [int(u) for u in order if int(u) not in seed_set][:m]
        sets = {"graph": exp_u, "sfscore": c_u, "topm": topm_u}
        for kind, members in sets.items():
            sc.add(f"{kind}|{vname}", _blend(base, _gvec(n, members, vals, seeds, snorm), w))
            note(f"{kind}|{vname}", members)
        acc: list[list[float]] = []
        for draw in range(sp.draws):
            # "b" is the name S1 gave the core family set: same draws, so the control can match
            rng = _rng(
                ident, "b" if vname == "core" else vname, sp.seeds, sp.hops, w, "rand_files", draw
            )
            rp = random_same_files(rng, file_of_pos, [int(pos[s]) for s in seeds], m)
            ru = [int(order[p]) for p in rp]
            acc.append(sc.metrics(_blend(base, _gvec(n, ru, vals, seeds, snorm), w)))
        sc.keys.append(f"sfrand|{vname}")
        sc.rows.append([float(x) for x in np.mean(acc, axis=0)])

    # ---- recency prior at the E5 dev setting on the same blended first stage, and its chance
    # control: the same ages shuffled over the units of the instance (3 draws)
    prior = recency_prior(age_days.astype(np.float64), RECENCY_TAU)
    sc.add("recency", recency_blend(base, prior, RECENCY_LAM))
    acc = []
    for draw in range(sp.draws):
        perm = _rng(ident, "recency_shuffle", RECENCY_LAM, RECENCY_TAU, draw).permutation(n)
        acc.append(sc.metrics(recency_blend(base, prior[perm], RECENCY_LAM)))
    sc.keys.append("recencyshuf")
    sc.rows.append([float(x) for x in np.mean(acc, axis=0)])

    # ---- stacked lists at the budget M of the core expansion
    m_ref = len(ref_units)
    long_sf = same_file_by_score(file_of_unit, order, seeds, m_ref + max(STACK_N))
    ref_list = long_sf[:m_ref]
    sc.add("ref|samefile", _blend(base, _gvec(n, ref_list, ref_vals, seeds, snorm), w))
    for nrep in STACK_N:
        k = min(nrep, m_ref)
        retained = ref_list[: m_ref - k]
        filler = long_sf[m_ref - k :]
        taken = [*retained]
        for fname, fams in STACK_FAMILIES.items():
            neigh, _ = expansion(fams, taken, k)
            lst = stacked_list(retained, neigh, filler, m_ref)
            sc.add(f"stack{nrep}|{fname}", _blend(base, _gvec(n, lst, ref_vals, seeds, snorm), w))
            note(f"stack{nrep}|{fname}", lst[len(retained) :])
            # chance controls with the same number of replacements as this stacked list made
            made = max(0, len(lst) - len(retained))
            avoid = seed_set | set(retained)
            topm_r = [int(u) for u in order if int(u) not in avoid][:made]
            lst_t = stacked_list(retained, topm_r, filler, m_ref)
            sc.add(
                f"stacktopm{nrep}|{fname}",
                _blend(base, _gvec(n, lst_t, ref_vals, seeds, snorm), w),
            )
            acc = []
            for draw in range(sp.draws):
                rng = _rng(ident, fname, nrep, w, "stack_rand", draw)
                rr = random_whole(rng, n, made, [*seeds, *retained])
                lst_r = stacked_list(retained, rr, filler, m_ref)
                acc.append(sc.metrics(_blend(base, _gvec(n, lst_r, ref_vals, seeds, snorm), w)))
            sc.keys.append(f"stackrand{nrep}|{fname}")
            sc.rows.append([float(x) for x in np.mean(acc, axis=0)])
    return sc, aux_keys, aux_rows


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
        sc, aux_keys, aux_rows = g1_level(
            f"{meta['instance']}|{level}",
            arrays[f"scores_{level}"].astype(np.float64),
            d,
            golds,
            arrays["file_of_unit"],
            graph,
            sp,
            arrays["age_days"],
        )
        if keys_ref is None:
            keys_ref, aux_ref = sc.keys, aux_keys
        elif keys_ref != sc.keys or aux_ref != aux_keys:
            raise RuntimeError("key order differs between levels of one instance")
        out[f"metrics_{level}"] = np.asarray(sc.rows, dtype=np.float64)
        out[f"aux_{level}"] = np.asarray(aux_rows, dtype=np.float64).reshape(-1, 1 + len(READINGS))
        info["levels"][level] = {f"gold_{r}": int(len(golds[r])) for r in READINGS}
        info["levels"][level]["gold_units"] = int(len(golds["units"]))
    out["keys"] = np.asarray(keys_ref or [], dtype=str)
    out["aux_keys"] = np.asarray(aux_ref or [], dtype=str)
    return info, out


def check_against_s1(out: dict[str, Arr], s1_file: str, levels: list[str], weight: float) -> float:
    """Largest absolute difference to the stored S1 rows of the same instance.

    The regression control of every job: ``graph|core`` and ``sfscore|core`` here are S1's
    ``graph|b|w`` and ``sfscore|b|w``, ``a_none`` is S1's ``a_none``.
    """
    _, old = read_eval(s1_file)
    okeys = [str(x) for x in old["keys"]]
    nkeys = [str(x) for x in out["keys"]]
    worst = 0.0
    for new_key, old_key in (
        ("a_none", "a_none"),
        ("graph|core", f"graph|b|w{weight}"),
        ("sfscore|core", f"sfscore|b|w{weight}"),
        ("topm|core", f"topm|b|w{weight}"),
        ("sfrand|core", f"sfrand|b|w{weight}"),
    ):
        for level in levels:
            a = out[f"metrics_{level}"][nkeys.index(new_key)]
            b = old[f"metrics_{level}"][okeys.index(old_key)]
            both = ~(np.isnan(a) & np.isnan(b))
            if both.any():
                worst = max(worst, float(np.max(np.abs(a[both] - b[both]))))
    return worst


def run_g1_eval(
    cfg: Record,
    cache_dir: str,
    dense_root: str,
    out_dir: str,
    s1_dir: str | None = None,
    roles_filter: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Evaluate every cached instance of the specification's roles; resumable."""
    sp, roles = spec_from_config(cfg)
    if roles_filter is not None:
        roles = tuple(r for r in roles if r in roles_filter)
    counts: dict[str, Any] = {
        "evaluated": 0,
        "skipped_role": 0,
        "reused": 0,
        "no_dense": 0,
        "regression_max_abs_diff": 0.0,
        "regression_checked": 0,
    }
    os.makedirs(out_dir, exist_ok=True)
    for name in sorted(os.listdir(cache_dir)):
        if not name.endswith(".npz"):
            continue
        arrays, meta = read_cache(os.path.join(cache_dir, name))
        if meta["role"] not in roles:
            counts["skipped_role"] += 1
            continue
        ehash = g1_hash(cfg, str(meta["config_hash"]))
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
        if s1_dir is not None and os.path.exists(os.path.join(s1_dir, name)):
            diff = check_against_s1(
                res, os.path.join(s1_dir, name), sorted(info["levels"]), sp.weights[0]
            )
            counts["regression_max_abs_diff"] = max(counts["regression_max_abs_diff"], diff)
            counts["regression_checked"] += 1
            if diff > 1e-9:
                raise RuntimeError(f"{name}: regression control differs from S1 by {diff}")
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
