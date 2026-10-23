"""Evaluation of graph expansion and a recency prior on the per-instance cache (pilots E3 to E5).

Implements the second half of ``docs/EXPERIMENTS.md`` E-GRAPH-SIGNAL, E-GRAPH-WEIGHTS and
E-RECENCY (all exploratory). For every cached instance and level it ranks the units by BM25,
takes the top-C as seeds, expands over an edge-family subset with hop decay, forms the scored
list in two ways (``list``: edited list; ``rrf``: a ranked graph list fused by reciprocal rank
fusion; see ``ril.retrieval.graph_expansion``) and records nDCG@10 and Recall@100 under both gold
readings (Q39: ``units`` and ``units_all``). Chance controls of the same expansion size follow:
``rand_whole`` draws units from the whole snapshot, ``rand_files`` from the files of the seeds.

The tuning discipline is enforced here: a specification that touches ``test`` instances must be
a ``confirm`` specification, i.e. one setting only (one C, one gamma, one hop count, one weight
set, one recency setting), stated in the configuration before the run.

Output per instance: one ``.npz`` with the key list, a ``(keys, 4)`` metric matrix per level
(nDCG@10 and Recall@100 for each gold reading) and a small auxiliary matrix (expansion size and
gold hits). No text.

Kept compatible with Python 3.10.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from ril.evaluation.e3_prepare import READINGS, read_cache
from ril.evaluation.metrics import ndcg_at_k, recall_at_k
from ril.retrieval.bm25_index import order_by_score
from ril.retrieval.graph_expansion import (
    RRF_K,
    FamilyGraph,
    bfs_distances,
    combine_uniform,
    expand_weighted,
    list_variant_ranks,
    random_same_files,
    random_whole,
    rrf_base,
    rrf_graph_list,
    rrf_ranks,
    select_expansion,
)
from ril.retrieval.recency import blend, recency_prior

EVAL_VERSION = "e3-eval/v1"
FAMILIES: tuple[str, ...] = (
    "contain",
    "import",
    "invoke",
    "inherit",
    "tests",
    "configures",
    "co_change",
)
EXPLORATORY_FAMILIES: tuple[str, ...] = ("tests", "configures", "co_change")
VARIANTS: tuple[str, ...] = ("list", "rrf")
CONTROLS: tuple[str, ...] = ("rand_whole", "rand_files")
Record = dict[str, Any]


def subset_table() -> dict[str, tuple[str, ...]]:
    """Edge-family subsets: each family alone, with the containment tree, leave-one-out, core, all.

    ``inherit`` includes ``override``; ``co_change`` has support 3; ``tests``, ``configures`` and
    ``co_change`` are exploratory families.
    """
    table: dict[str, tuple[str, ...]] = {f: (f,) for f in FAMILIES}
    for f in ("import", "invoke", "co_change"):
        table[f"{f}+contain"] = (f, "contain")
    for f in FAMILIES:
        table[f"all-minus-{f}"] = tuple(x for x in FAMILIES if x != f)
    table["core"] = ("contain", "import", "invoke", "inherit")
    table["all"] = FAMILIES
    return table


@dataclass(frozen=True)
class GraphGrid:
    """Grid of the graph-expansion runs (E3)."""

    variants: tuple[str, ...] = VARIANTS
    subsets: tuple[str, ...] = ()
    seeds: tuple[int, ...] = (1, 3, 5)
    gammas: tuple[float, ...] = (0.3, 0.5, 0.7)
    hops: tuple[int, ...] = (1, 2)
    cap: int = 50
    controls: tuple[str, ...] = CONTROLS
    draws: int = 3
    rrf_k: int = RRF_K


@dataclass(frozen=True)
class WeightGrid:
    """Edge-family weight sets (E4): one weight per family, multiplied along the path."""

    sets: dict[str, dict[str, float]] = field(default_factory=dict)
    subsets: tuple[str, ...] = ("all", "core")
    seeds: tuple[int, ...] = (3, 5)
    hops: tuple[int, ...] = (1, 2)


@dataclass(frozen=True)
class RecencyGrid:
    """Recency-prior settings (E5): weight and time constant in days."""

    lam: tuple[float, ...] = ()
    tau_days: tuple[float, ...] = ()


@dataclass(frozen=True)
class EvalSpec:
    """What one evaluation run computes, and on which roles."""

    roles: tuple[str, ...]
    seed: int = 0
    confirm: bool = False
    graph: GraphGrid | None = None
    weights: WeightGrid | None = None
    recency: RecencyGrid | None = None
    fusion: GraphGrid | None = None

    def validate(self) -> None:
        """Refuse a specification that would sweep on the test instances."""
        if "test" in self.roles and not self.confirm:
            raise ValueError("test instances may only be evaluated by a confirm specification")
        if not self.confirm:
            return
        g, w, r, fz = self.graph, self.weights, self.recency, self.fusion
        if fz is not None and not (len(fz.seeds) == len(fz.gammas) == len(fz.hops) == 1):
            raise ValueError("confirm: one C, one gamma and one hop count (fusion)")
        if g is not None and not (len(g.seeds) == len(g.gammas) == len(g.hops) == 1):
            raise ValueError("confirm: one C, one gamma and one hop count")
        if w is not None and not (len(w.sets) == 1 and len(w.seeds) == len(w.hops) == 1):
            raise ValueError("confirm: one weight set, one C and one hop count")
        if r is not None and not (len(r.lam) == len(r.tau_days) == 1):
            raise ValueError("confirm: one recency setting")


def spec_from_config(cfg: Record) -> EvalSpec:
    """Build the specification from a parsed YAML configuration."""
    table = subset_table()
    graph = weights = recency = fusion = None

    def grid_of(gc: Record) -> GraphGrid:
        subsets = tuple(gc.get("subsets", table))
        for sub in subsets:
            if sub not in table:
                raise ValueError(f"unknown subset {sub!r}")
        return GraphGrid(
            variants=tuple(gc.get("variants", VARIANTS)),
            subsets=subsets,
            seeds=tuple(int(c) for c in gc["seeds"]),
            gammas=tuple(float(x) for x in gc["gammas"]),
            hops=tuple(int(h) for h in gc["hops"]),
            cap=int(gc.get("cap", 50)),
            controls=tuple(gc.get("controls", CONTROLS)),
            draws=int(gc.get("draws", 3)),
            rrf_k=int(gc.get("rrf_k", RRF_K)),
        )

    if "graph" in cfg:
        graph = grid_of(cfg["graph"])
    if "fusion" in cfg:
        fusion = grid_of(cfg["fusion"])
    if "weights" in cfg:
        wc = cfg["weights"]
        weights = WeightGrid(
            sets={n: {f: float(v) for f, v in d.items()} for n, d in wc["sets"].items()},
            subsets=tuple(wc.get("subsets", ("all", "core"))),
            seeds=tuple(int(c) for c in wc.get("seeds", (3, 5))),
            hops=tuple(int(h) for h in wc.get("hops", (1, 2))),
        )
    if "recency" in cfg:
        rc = cfg["recency"]
        recency = RecencyGrid(
            lam=tuple(float(x) for x in rc["lam"]), tau_days=tuple(float(x) for x in rc["tau_days"])
        )
    spec = EvalSpec(
        roles=tuple(cfg["roles"]),
        seed=int(cfg.get("seed", 0)),
        confirm=bool(cfg.get("confirm", False)),
        graph=graph,
        weights=weights,
        recency=recency,
        fusion=fusion,
    )
    spec.validate()
    return spec


def eval_hash(cfg: Record, prepare_config_hash: str) -> str:
    """SHA-256 over the evaluation configuration and the cache's configuration hash."""
    payload = {"version": EVAL_VERSION, "config": cfg, "prepare": prepare_config_hash}
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- keys


def graph_key(variant: str, subset: str, c: int, gamma: float, hops: int) -> str:
    """Key of a hand-set-decay run."""
    return f"{variant}|{subset}|C{c}|g{gamma}|h{hops}"


def control_key(variant: str, control: str, subset: str, c: int, hops: int, wname: str = "") -> str:
    """Key of a chance control (its size follows the real expansion)."""
    tail = f"|w:{wname}" if wname else ""
    return f"{variant}|{control}|{subset}|C{c}{tail}|h{hops}"


def weight_key(variant: str, subset: str, c: int, wname: str, hops: int) -> str:
    """Key of a weighted-edge run."""
    return f"{variant}|{subset}|C{c}|w:{wname}|h{hops}"


def recency_key(lam: float, tau: float) -> str:
    """Key of a recency-prior run."""
    return f"rec|lam{lam}|tau{tau}"


def expansion_key(subset: str, c: int, setting: str, hops: int) -> str:
    """Key of the auxiliary size and hits (``setting``: ``g<gamma>`` or ``w:<name>``)."""
    return f"E|{subset}|C{c}|{setting}|h{hops}"


# --------------------------------------------------------------------------- one level


def _rng(*parts: object) -> np.random.Generator:
    digest = hashlib.sha256("\x1f".join(str(p) for p in parts).encode("utf-8")).digest()
    return np.random.default_rng(int.from_bytes(digest[:8], "big"))


class _Level:
    """Evaluation of all keys for one (instance, level)."""

    def __init__(
        self,
        ident: str,
        scores: np.ndarray[Any, Any],
        golds: dict[str, np.ndarray[Any, Any]],
        file_of_unit: np.ndarray[Any, Any],
        age_days: np.ndarray[Any, Any],
        graph: FamilyGraph,
        *,
        fused: bool = False,
        vpre: str = "",
    ) -> None:
        self.fused = fused
        self.vpre = vpre
        self.ident = ident
        self.scores = scores
        self.n = len(scores)
        self.order = order_by_score(scores)
        self.pos = np.empty(self.n, dtype=np.int64)
        self.pos[self.order] = np.arange(self.n)
        self.file_of_pos = file_of_unit[self.order].astype(np.int64)
        self.age_days = age_days
        self.graph = graph
        self.gold_pos = {r: [int(self.pos[g]) for g in golds[r]] for r in READINGS}
        self.union = sorted({p for r in READINGS for p in self.gold_pos[r]})
        self.keys: list[str] = []
        self.rows: list[list[float]] = []
        self.aux_keys: list[str] = []
        self.aux_rows: list[list[float]] = []
        self._rrf_base: dict[int, Any] = {}

    def metrics(self, rank_of: dict[int, int]) -> list[float]:
        out: list[float] = []
        for r in READINGS:
            ranks = [rank_of[p] for p in self.gold_pos[r]]
            n_rel = len(ranks)
            if n_rel == 0:  # no gold under this reading: the query is not scored
                out += [math.nan, math.nan]
            else:
                out += [ndcg_at_k(ranks, 10, n_rel), recall_at_k(ranks, 100, n_rel)]
        return out

    def add(self, key: str, rank_of: dict[int, int]) -> None:
        self.keys.append(key)
        self.rows.append(self.metrics(rank_of))

    def baseline_ranks(self) -> dict[int, int]:
        return {p: p + 1 for p in self.union}

    def ranks_list(self, seed_pos: list[int], exp_pos: list[int]) -> dict[int, int]:
        return dict(zip(self.union, list_variant_ranks(self.union, seed_pos, exp_pos), strict=True))

    def ranks_rrf(self, glist: list[int], k: int) -> dict[int, int]:
        if k not in self._rrf_base:
            # a fused retrieval list brings its own scores (sorted, so index = position)
            self._rrf_base[k] = self.scores[self.order] if self.fused else rrf_base(self.n, k)
        return dict(
            zip(self.union, rrf_ranks(self.n, self.union, glist, k, self._rrf_base[k]), strict=True)
        )

    def hits(self, exp_pos: list[int]) -> list[float]:
        s = set(exp_pos)
        return [float(len(s)), *[float(len(s & set(self.gold_pos[r]))) for r in READINGS]]

    # ---- graph
    def run_graph(self, grid: GraphGrid, table: dict[str, tuple[str, ...]]) -> None:
        max_c = max(grid.seeds)
        seeds_all = [int(u) for u in self.order[:max_c] if self.scores[u] > 0]
        top = float(self.scores[self.order[0]]) if self.n else 0.0
        snorm_all = [float(self.scores[u]) / top for u in seeds_all]
        for subset in grid.subsets:
            families = table[subset]
            dist_cache: dict[int, dict[int, int]] = {}
            for c in grid.seeds:
                seeds = seeds_all[:c]
                for h in grid.hops:
                    exp_sets: dict[float, tuple[list[int], list[float]]] = {}
                    for gamma in grid.gammas:
                        exp_u: list[int] = []
                        exp_g: list[float] = []
                        if seeds:
                            for s in seeds:
                                if s not in dist_cache:
                                    dist_cache[s] = bfs_distances(
                                        self.graph, families, s, max(grid.hops)
                                    )
                            g = combine_uniform(
                                [dist_cache[s] for s in seeds], snorm_all[: len(seeds)], gamma, h
                            )
                            exp_u = select_expansion(g, seeds, self.pos, self.n, grid.cap)
                            exp_g = [g[u] for u in exp_u]
                        exp_sets[gamma] = (exp_u, exp_g)
                        self._emit(
                            grid.variants,
                            subset,
                            c,
                            f"g{gamma}",
                            h,
                            seeds,
                            snorm_all,
                            exp_u,
                            exp_g,
                            grid.rrf_k,
                        )
                    m = len(exp_sets[grid.gammas[0]][0])
                    self._controls(grid, subset, c, h, "", seeds_all[:c], m)

    def run_weights(
        self, wg: WeightGrid, grid: GraphGrid, table: dict[str, tuple[str, ...]]
    ) -> None:
        max_c = max(wg.seeds)
        seeds_all = [int(u) for u in self.order[:max_c] if self.scores[u] > 0]
        top = float(self.scores[self.order[0]]) if self.n else 0.0
        snorm_all = [float(self.scores[u]) / top for u in seeds_all]
        for name, weights in sorted(wg.sets.items()):
            for subset in wg.subsets:
                fam_w = {f: weights.get(f, 0.0) for f in table[subset]}
                for c in wg.seeds:
                    seeds = seeds_all[:c]
                    for h in wg.hops:
                        exp_u: list[int] = []
                        exp_g: list[float] = []
                        if seeds:
                            g = expand_weighted(
                                self.graph, fam_w, seeds, snorm_all[: len(seeds)], h
                            )
                            exp_u = select_expansion(g, seeds, self.pos, self.n, grid.cap)
                            exp_g = [g[u] for u in exp_u]
                        self._emit(
                            grid.variants,
                            subset,
                            c,
                            f"w:{name}",
                            h,
                            seeds,
                            snorm_all,
                            exp_u,
                            exp_g,
                            grid.rrf_k,
                        )
                        self._controls(grid, subset, c, h, name, seeds_all[:c], len(exp_u))

    def _emit(
        self,
        variants: tuple[str, ...],
        subset: str,
        c: int,
        setting: str,
        h: int,
        seeds: list[int],
        snorm_all: list[float],
        exp_u: list[int],
        exp_g: list[float],
        rrf_k: int,
    ) -> None:
        seed_pos = [int(self.pos[s]) for s in seeds]
        exp_pos = [int(self.pos[u]) for u in exp_u]
        for variant in variants:
            if variant == "list":
                ranks = self.ranks_list(seed_pos, exp_pos)
            else:
                glist = rrf_graph_list(seed_pos, snorm_all[: len(seeds)], exp_pos, exp_g)
                ranks = self.ranks_rrf(glist, rrf_k)
            vname = self.vpre + variant
            key = (
                graph_key(vname, subset, c, float(setting[1:]), h)
                if setting.startswith("g")
                else weight_key(vname, subset, c, setting[2:], h)
            )
            self.add(key, ranks)
        akey = expansion_key(subset, c, setting, h)
        self.aux_keys.append(akey.replace("E|", "Efz|", 1) if self.vpre else akey)
        self.aux_rows.append(self.hits(exp_pos))

    def _controls(
        self, grid: GraphGrid, subset: str, c: int, h: int, wname: str, seeds: list[int], m: int
    ) -> None:
        seed_pos = [int(self.pos[s]) for s in seeds]
        for ctrl in grid.controls:
            acc: dict[str, list[list[float]]] = {v: [] for v in grid.variants}
            for draw in range(grid.draws):
                rng = _rng(self.ident, subset, c, h, wname, ctrl, draw)
                if not seeds:
                    exp_pos: list[int] = []
                elif ctrl == "rand_whole":
                    exp_pos = random_whole(rng, self.n, m, seed_pos)
                else:
                    exp_pos = random_same_files(rng, self.file_of_pos, seed_pos, m)
                for variant in grid.variants:
                    if variant == "list":
                        ranks = self.ranks_list(seed_pos, exp_pos)
                    else:
                        ranks = self.ranks_rrf(seed_pos + exp_pos, grid.rrf_k)
                    acc[variant].append(self.metrics(ranks))
            for variant in grid.variants:
                self.keys.append(control_key(self.vpre + variant, ctrl, subset, c, h, wname))
                self.rows.append([float(x) for x in np.mean(acc[variant], axis=0)])

    # ---- recency
    def run_recency(self, rg: RecencyGrid) -> None:
        for tau in rg.tau_days:
            prior = recency_prior(self.age_days, tau)
            for lam in rg.lam:
                s = blend(self.scores, prior, lam)
                rank_of = {}
                for p in self.union:
                    u = int(self.order[p])
                    sg = s[u]
                    rank_of[p] = 1 + int((s > sg).sum()) + int((s[:u] == sg).sum())
                self.add(recency_key(lam, tau), rank_of)


def evaluate_instance(
    arrays: dict[str, np.ndarray[Any, Any]],
    meta: Record,
    spec: EvalSpec,
    dense: dict[str, np.ndarray[Any, Any]] | None = None,
) -> tuple[Record, dict[str, np.ndarray[Any, Any]]]:
    """Evaluate one cached instance; return (metadata, arrays to store)."""
    n = int(meta["units"])
    pairs = {
        k[6:]: [(int(a), int(b)) for a, b in v] for k, v in arrays.items() if k.startswith("pairs_")
    }
    graph = FamilyGraph.from_pairs(n, pairs)
    table = subset_table()
    out: dict[str, np.ndarray[Any, Any]] = {}
    info: Record = {"levels": {}}
    keys_ref: list[str] | None = None
    aux_ref: list[str] | None = None
    for level in meta["levels"]:
        golds = {r: arrays[f"gold_{level}_{r}"] for r in READINGS}
        if not any(len(g) for g in golds.values()):
            continue
        lvl = _Level(
            f"{meta['instance']}|{level}",
            arrays[f"scores_{level}"],
            golds,
            arrays["file_of_unit"],
            arrays["age_days"],
            graph,
        )
        lvl.add("bm25", lvl.baseline_ranks())
        if spec.graph is not None:
            lvl.run_graph(spec.graph, table)
        if spec.weights is not None:
            grid = spec.graph or GraphGrid()
            lvl.run_weights(spec.weights, grid, table)
        if spec.recency is not None:
            lvl.run_recency(spec.recency)
        if spec.fusion is not None:
            if dense is None or f"dense_{level}" not in dense:
                raise ValueError(f"{meta['instance']}: no dense scores for {level}")
            _run_fusion(
                lvl, dense[f"dense_{level}"], arrays, graph, table, spec.fusion, meta, level, golds
            )
        if keys_ref is None:
            keys_ref, aux_ref = lvl.keys, lvl.aux_keys
        elif keys_ref != lvl.keys or aux_ref != lvl.aux_keys:
            raise RuntimeError("key order differs between levels of one instance")
        out[f"metrics_{level}"] = np.asarray(lvl.rows, dtype=np.float64)
        out[f"aux_{level}"] = np.asarray(lvl.aux_rows, dtype=np.float64).reshape(
            -1, 1 + len(READINGS)
        )
        info["levels"][level] = {
            "gold_units": int(len(golds["units"])),
            "gold_units_all": int(len(golds["units_all"])),
            "gold_units_nomod": int(len(golds["units_nomod"])),
            "gold_units_all_nomod": int(len(golds["units_all_nomod"])),
        }
    out["keys"] = np.asarray(keys_ref or [], dtype=str)
    out["aux_keys"] = np.asarray(aux_ref or [], dtype=str)
    return info, out


def _run_fusion(
    base: _Level,
    dense_scores: np.ndarray[Any, Any],
    arrays: dict[str, np.ndarray[Any, Any]],
    graph: FamilyGraph,
    table: dict[str, tuple[str, ...]],
    grid: GraphGrid,
    meta: Record,
    level: str,
    golds: dict[str, np.ndarray[Any, Any]],
) -> None:
    """Add the dense-only and BM25+dense fusion arms, and the graph on top of the fusion."""
    ident = f"{meta['instance']}|{level}"
    k = grid.rrf_k
    dense_lvl = _Level(
        ident, dense_scores, golds, arrays["file_of_unit"], arrays["age_days"], graph
    )
    dense_lvl.add("dense", dense_lvl.baseline_ranks())
    pos_b = base.pos.astype(np.float64)
    pos_d = dense_lvl.pos.astype(np.float64)
    fused_scores = 1.0 / (k + pos_b + 1.0) + 1.0 / (k + pos_d + 1.0)
    fz = _Level(
        ident,
        fused_scores,
        golds,
        arrays["file_of_unit"],
        arrays["age_days"],
        graph,
        fused=True,
        vpre="fz_",
    )
    fz.add("fused", fz.baseline_ranks())
    fz.run_graph(grid, table)
    base.keys += dense_lvl.keys + fz.keys
    base.rows += dense_lvl.rows + fz.rows
    base.aux_keys += fz.aux_keys
    base.aux_rows += fz.aux_rows


def write_eval(path: str, info: Record, arrays: dict[str, np.ndarray[Any, Any]]) -> None:
    """Write one evaluation file atomically."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp.npz"
    payload: dict[str, Any] = {"info": np.asarray(json.dumps(info, sort_keys=True)), **arrays}
    np.savez_compressed(tmp, **payload)
    os.replace(tmp, path)


def read_eval(path: str) -> tuple[Record, dict[str, np.ndarray[Any, Any]]]:
    """Read one evaluation file."""
    with np.load(path, allow_pickle=False) as data:
        arrays = {k: data[k] for k in data.files if k != "info"}
        info = json.loads(str(data["info"]))
    return info, arrays


def run_eval(
    cfg: Record, cache_dir: str, out_dir: str, dense_dir: str | None = None
) -> dict[str, int]:
    """Evaluate every cached instance whose role is in the specification; resumable.

    ``dense_dir`` holds one file per instance with the dense scores (pilot E6).
    """
    spec = spec_from_config(cfg)
    counts = {"evaluated": 0, "skipped_role": 0, "reused": 0}
    for name in sorted(os.listdir(cache_dir)):
        if not name.endswith(".npz"):
            continue
        arrays, meta = read_cache(os.path.join(cache_dir, name))
        if meta["role"] not in spec.roles:
            counts["skipped_role"] += 1
            continue
        ehash = eval_hash(cfg, str(meta["config_hash"]))
        out = os.path.join(out_dir, name)
        if os.path.exists(out):
            old, _ = read_eval(out)
            if old.get("eval_hash") == ehash:
                counts["reused"] += 1
                continue
        dense = None
        if spec.fusion is not None:
            if dense_dir is None or not os.path.exists(os.path.join(dense_dir, name)):
                counts["no_dense"] = counts.get("no_dense", 0) + 1
                continue
            with np.load(os.path.join(dense_dir, name), allow_pickle=False) as dz:
                dense = {k: dz[k] for k in dz.files}
        info, res = evaluate_instance(arrays, meta, spec, dense)
        info.update(
            eval_hash=ehash,
            instance=meta["instance"],
            role=meta["role"],
            dataset=meta["dataset"],
            folder=meta["folder"],
            repo_id=meta["repo_id"],
            units=meta["units"],
            e1_rank_mismatch=meta["e1_rank_mismatch"],
        )
        write_eval(out, info, res)
        counts["evaluated"] += 1
    return counts
