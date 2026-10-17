"""Hop-decay graph expansion from retrieved seeds, and two ways to form the scored list (pilot E3).

Implements the intervention of ``docs/EXPERIMENTS.md`` E-GRAPH-SIGNAL (exploratory; the role of
the graph and the way a graph signal enters the fusion stack are open: Q30, ADR-003). Nothing
here is a design choice; the module offers the pieces, and the pilot reports what they do.

Seeds are the top-C units of a ranking by retrieval score (never gold units). From each seed a
breadth-first search over the chosen edge families (resolved edges, read as undirected) gives
every reached node its hop distance ``d``; its hop-decay score is ``max over seeds of
s_norm(seed) * gamma ** d`` for ``d <= hops`` (``s_norm`` is the seed's score divided by the best
score). A weighted variant multiplies one weight per edge family along the path instead of one
``gamma`` per hop (pilot E4). At most ``cap`` reached units are kept, best score first, ties by
retrieval rank.

Two ways to form the list that is scored (both exploratory implementation choices):

* ``list``: the retrieval list is edited. Seeds, then the expansion units in score order, then
  the rest of the retrieval list. Edit-style expansion as in agent pipelines.
* ``rrf``: the expansion is a second ranked list (seeds as hop 0, then expansion units by
  score), fused with the retrieval list by reciprocal rank fusion ``sum 1 / (k + rank)``.
  Rank-based fusion as in the frozen stack of ``docs/08_experimental_design.md``.

All functions work on *retrieval positions* (0-based position of a unit in the retrieval ranking)
unless stated, so that a rank is a pure function of integers.

Kept compatible with Python 3.10.
"""

from __future__ import annotations

from bisect import bisect_left
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

Ints = npt.NDArray[np.int64]
Floats = npt.NDArray[np.float64]

RRF_K = 60
"""Conventional reciprocal-rank-fusion constant; an implementation default, not a tuned value."""


@dataclass
class FamilyGraph:
    """Undirected adjacency per edge family over integer node indices.

    Indices ``0 .. n_units - 1`` are retrieval units (document order of the index); larger indices
    are nodes that cannot be returned (directories, configuration files) but can be traversed.
    """

    n_units: int
    adj: dict[str, dict[int, list[int]]]

    @classmethod
    def from_pairs(
        cls, n_units: int, pairs: Mapping[str, Iterable[tuple[int, int]]]
    ) -> FamilyGraph:
        """Build from ``family -> (a, b)`` pairs; each pair is added in both directions."""
        adj: dict[str, dict[int, list[int]]] = {}
        for fam, items in pairs.items():
            table: dict[int, set[int]] = {}
            for a, b in items:
                if a == b:
                    continue
                table.setdefault(int(a), set()).add(int(b))
                table.setdefault(int(b), set()).add(int(a))
            adj[fam] = {k: sorted(v) for k, v in table.items()}
        return cls(n_units, adj)

    def degree_summary(self) -> dict[str, int]:
        """Number of directed neighbour entries per family (twice the undirected edge count)."""
        return {f: sum(len(v) for v in t.values()) for f, t in sorted(self.adj.items())}


def bfs_distances(
    graph: FamilyGraph, families: Sequence[str], seed: int, hops: int
) -> dict[int, int]:
    """Hop distance (1..hops) from ``seed`` to every node reached over ``families``."""
    dist: dict[int, int] = {seed: 0}
    frontier = [seed]
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
    del dist[seed]
    return dist


def combine_uniform(
    dists: Sequence[Mapping[int, int]],
    seed_scores: Sequence[float],
    gamma: float,
    hops: int,
) -> dict[int, float]:
    """Hop-decay score ``max_s s_norm(s) * gamma ** d(s, v)`` over the seeds, for ``d <= hops``."""
    if len(dists) != len(seed_scores):
        raise ValueError("one distance map per seed score is required")
    out: dict[int, float] = {}
    for dmap, s in zip(dists, seed_scores, strict=True):
        for node, d in dmap.items():
            if d <= hops:
                v = s * gamma**d
                if v > out.get(node, 0.0):
                    out[node] = v
    return out


def expand_weighted(
    graph: FamilyGraph,
    weights: Mapping[str, float],
    seeds: Sequence[int],
    seed_scores: Sequence[float],
    hops: int,
) -> dict[int, float]:
    """Hop-decay score with one weight per edge family, multiplied along the best path.

    A family with weight 0 (or absent) is not traversed. With the same weight ``gamma`` for every
    family this equals :func:`combine_uniform` (a test checks it).
    """
    if len(seeds) != len(seed_scores):
        raise ValueError("one score per seed is required")
    tables = [(graph.adj[f], w) for f, w in sorted(weights.items()) if w > 0 and f in graph.adj]
    out: dict[int, float] = {}
    for seed, s in zip(seeds, seed_scores, strict=True):
        best: dict[int, float] = {seed: s}
        frontier: dict[int, float] = {seed: s}
        for _ in range(hops):
            fresh: dict[int, float] = {}
            for node, val in frontier.items():
                for table, w in tables:
                    for nb in table.get(node, ()):
                        v = val * w
                        if v > best.get(nb, 0.0) and v > fresh.get(nb, 0.0):
                            fresh[nb] = v
            for nb, v in fresh.items():
                best[nb] = v
            frontier = fresh
            if not frontier:
                break
        for node, v in best.items():
            if node != seed and v > out.get(node, 0.0):
                out[node] = v
    return out


def select_expansion(
    scores: Mapping[int, float],
    seed_units: Iterable[int],
    position: Ints,
    n_units: int,
    cap: int,
) -> list[int]:
    """Units (no seeds, no traversal-only nodes) with a positive score, best first, at most ``cap``.

    ``position[u]`` is the retrieval position of unit ``u`` and breaks ties (earlier first).
    """
    skip = set(seed_units)
    cand = [(-v, int(position[u]), u) for u, v in scores.items() if u < n_units and u not in skip]
    cand = [c for c in cand if c[0] < 0]
    cand.sort()
    return [u for _, _, u in cand[:cap]]


# --------------------------------------------------------------------------- scored lists


def list_variant_ranks(
    gold_pos: Sequence[int], seed_pos: Sequence[int], expansion_pos: Sequence[int]
) -> list[int]:
    """1-based ranks of gold positions when the list is seeds, expansion, then the rest.

    ``seed_pos`` and ``expansion_pos`` are retrieval positions in list order; the rest keeps
    retrieval order with the first two groups removed.
    """
    front = list(seed_pos) + list(expansion_pos)
    if len(set(front)) != len(front):
        raise ValueError("seeds and expansion units must be distinct")
    rank_of = {p: i + 1 for i, p in enumerate(front)}
    removed = sorted(front)
    m = len(front)
    return [rank_of[g] if g in rank_of else m + g - bisect_left(removed, g) + 1 for g in gold_pos]


def rrf_base(n: int, k: int = RRF_K) -> Floats:
    """Retrieval-list contribution ``1 / (k + rank)`` for ranks ``1 .. n`` (reused across calls)."""
    base: Floats = 1.0 / (k + np.arange(1, n + 1, dtype=np.float64))
    return base


def rrf_ranks(
    n: int,
    gold_pos: Sequence[int],
    graph_list_pos: Sequence[int],
    k: int = RRF_K,
    base: Floats | None = None,
) -> list[int]:
    """1-based ranks of gold positions after fusing the retrieval list with a graph list.

    Retrieval position ``p`` contributes ``1 / (k + p + 1)``; the graph list contributes
    ``1 / (k + r)`` at its rank ``r``. Ties go to the earlier retrieval position.
    """
    final: Floats = (rrf_base(n, k) if base is None else base).copy()
    if len(graph_list_pos):
        gl = np.asarray(graph_list_pos, dtype=np.int64)
        if len(np.unique(gl)) != len(gl):
            raise ValueError("graph list positions must be distinct")
        final[gl] += 1.0 / (k + np.arange(1, len(gl) + 1, dtype=np.float64))
    out: list[int] = []
    for g in gold_pos:
        sg = final[g]
        out.append(1 + int((final > sg).sum()) + int((final[:g] == sg).sum()))
    return out


def rrf_graph_list(
    seed_pos: Sequence[int],
    seed_scores: Sequence[float],
    expansion_pos: Sequence[int],
    expansion_scores: Sequence[float],
) -> list[int]:
    """Graph list for fusion: seeds (hop 0, their own score) and expansion units, best first.

    Ties keep retrieval order. Returned as retrieval positions.
    """
    items = list(zip(seed_pos, seed_scores, strict=True)) + list(
        zip(expansion_pos, expansion_scores, strict=True)
    )
    items.sort(key=lambda t: (-t[1], t[0]))
    return [p for p, _ in items]


# --------------------------------------------------------------------------- chance controls


def random_whole(rng: np.random.Generator, n: int, m: int, exclude: Sequence[int]) -> list[int]:
    """``m`` distinct positions in random order, drawn from all positions but ``exclude``."""
    mask = np.ones(n, dtype=bool)
    if len(exclude):
        mask[np.asarray(exclude, dtype=np.int64)] = False
    cand = np.flatnonzero(mask)
    take = min(m, len(cand))
    return [int(x) for x in rng.choice(cand, size=take, replace=False)]


def random_same_files(
    rng: np.random.Generator, file_of_pos: Ints, seed_pos: Sequence[int], m: int
) -> list[int]:
    """``m`` random positions from the files of the seeds (seeds excluded), topped up from the
    whole index when those files hold fewer than ``m`` other units, so the size always matches."""
    n = len(file_of_pos)
    seed_arr = np.asarray(seed_pos, dtype=np.int64)
    mask = np.isin(file_of_pos, file_of_pos[seed_arr]) if len(seed_arr) else np.zeros(n, bool)
    if len(seed_arr):
        mask[seed_arr] = False
    cand = np.flatnonzero(mask)
    take = min(m, len(cand))
    chosen = [int(x) for x in rng.choice(cand, size=take, replace=False)] if take else []
    if take < m:
        more = random_whole(rng, n, m - take, [*seed_pos, *chosen])
        chosen += more
    return chosen
