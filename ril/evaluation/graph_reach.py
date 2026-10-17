"""Graph reach of a positive set, with a chance control (pilot E-GRAPH-REACH, exploratory).

Question: starting from the units that the L2 positives of an instance map to, how many hops
away are the units that the L3 positives map to, over each family of graph edges, and how does
that compare with what a randomly chosen set of units of the same size would show? A dense
graph reaches everything within a few hops, so the number that means something is the excess
over chance, never the share alone.

Edge subsets (``SUBSETS``) are unions of edge families over resolved edges only; every subset
is read as undirected except the two directed invoke variants. ``import`` and ``co_change`` edges
join file (module) units, so alone they can only reach a function through a module-residual
positive; the ``*_contain`` subsets add the containment tree so that a file-level relation
can lead to the units inside the file (the control separates what that adds from chance).
The exploratory families (``tests``, ``configures``, ``co_change``) are labelled exploratory
wherever they appear.

Controls, per positive ``p`` with ``k`` mapped units (the draw keeps ``k``, so a chunk that
spans three units is compared with three random units):

* ``same_files``: ``k`` units drawn from the units of the files ``p`` lies in;
* ``whole_repo``: ``k`` units drawn from the whole snapshot;
* ``whole_repo_kind``: as ``whole_repo`` but from units of the same kind (unit type and test
  flag) as ``p``'s primary unit, so that the single residual ``module`` unit per file is not
  compared with the many functions.

L2 units are never drawn (a positive that is already an L2 unit is excluded from the study).
Draws are seeded per (instance, chunk, control), so a rerun is byte-identical.

Kept compatible with Python 3.10.
"""

from __future__ import annotations

import hashlib
import random
from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass

from ril.parsing.code_unit import CodeUnit
from ril.parsing.repo_graph import Edge

HOP_LIMITS: tuple[int, int, int] = (1, 2, 3)
"""The reported neighbourhood sizes."""

CONTROLS: tuple[str, ...] = ("same_files", "whole_repo", "whole_repo_kind")
CO_CHANGE_SUPPORTS: tuple[int, ...] = (2, 3, 5)
DEFAULT_DRAWS = 200


@dataclass(frozen=True)
class SubsetSpec:
    """An edge subset: families (``co_change`` carries its support), direction and status."""

    name: str
    families: tuple[str, ...]
    direction: str = "both"  # both | fwd (src to dst) | rev (dst to src)
    exploratory: bool = False


def _co(n: int) -> str:
    return f"co_change@{n}"


SUBSETS: tuple[SubsetSpec, ...] = (
    SubsetSpec("invoke_both", ("invoke",)),
    SubsetSpec("invoke_fwd", ("invoke",), "fwd"),
    SubsetSpec("invoke_rev", ("invoke",), "rev"),
    SubsetSpec("import", ("import",)),
    SubsetSpec("inherit", ("inherit", "override")),
    SubsetSpec("contain", ("contain",)),
    SubsetSpec("tests", ("tests",), exploratory=True),
    SubsetSpec("configures", ("configures",), exploratory=True),
    SubsetSpec("co_change_n2", (_co(2),), exploratory=True),
    SubsetSpec("co_change_n3", (_co(3),), exploratory=True),
    SubsetSpec("co_change_n5", (_co(5),), exploratory=True),
    SubsetSpec("invoke_contain", ("invoke", "contain")),
    SubsetSpec("import_contain", ("import", "contain")),
    SubsetSpec("co_change_n2_contain", (_co(2), "contain"), exploratory=True),
    SubsetSpec("co_change_n3_contain", (_co(3), "contain"), exploratory=True),
    SubsetSpec("co_change_n5_contain", (_co(5), "contain"), exploratory=True),
    SubsetSpec("core", ("contain", "import", "invoke", "inherit", "override")),
    SubsetSpec(
        "all_minus_contain",
        ("import", "invoke", "inherit", "override", "tests", "configures", _co(3)),
        exploratory=True,
    ),
    SubsetSpec(
        "all",
        ("contain", "import", "invoke", "inherit", "override", "tests", "configures", _co(3)),
        exploratory=True,
    ),
)
"""Edge subsets of the pilot (``inherit`` includes ``override``; ``all``: co-change support 3)."""

SUBSET_NAMES: tuple[str, ...] = tuple(s.name for s in SUBSETS)


# --------------------------------------------------------------------------- edges and distances


def edge_pairs(
    edges: Iterable[Edge], co_change: dict[int, list[Edge]] | None = None
) -> dict[str, list[tuple[str, str]]]:
    """Resolved ``(src, dst)`` pairs per family; ``co_change@N`` keys come from ``co_change``."""
    pairs: dict[str, list[tuple[str, str]]] = {}
    for e in edges:
        if e.status == "resolved" and e.src != e.dst:
            pairs.setdefault(e.type, []).append((e.src, e.dst))
    for n, cc in (co_change or {}).items():
        pairs[_co(n)] = [(e.src, e.dst) for e in cc if e.status == "resolved"]
    return pairs


def adjacency(pairs: dict[str, list[tuple[str, str]]], spec: SubsetSpec) -> dict[str, list[str]]:
    """Neighbour lists (sorted, deduplicated) of the subset, in the direction it prescribes."""
    out: dict[str, set[str]] = {}
    for fam in spec.families:
        for a, b in pairs.get(fam, []):
            if spec.direction in ("both", "fwd"):
                out.setdefault(a, set()).add(b)
            if spec.direction in ("both", "rev"):
                out.setdefault(b, set()).add(a)
    return {k: sorted(v) for k, v in out.items()}


def distances(adj: dict[str, list[str]], sources: Iterable[str]) -> dict[str, int]:
    """Multi-source breadth-first distance in hops from ``sources`` to every reachable node."""
    dist: dict[str, int] = {}
    queue: deque[str] = deque()
    for s in sorted(set(sources)):
        dist[s] = 0
        queue.append(s)
    while queue:
        node = queue.popleft()
        d = dist[node] + 1
        for nxt in adj.get(node, ()):
            if nxt not in dist:
                dist[nxt] = d
                queue.append(nxt)
    return dist


def min_distance(dist: dict[str, int], targets: Iterable[str]) -> int | None:
    """Smallest distance over ``targets``; ``None`` when none is reachable."""
    best: int | None = None
    for t in targets:
        d = dist.get(t)
        if d is not None and (best is None or d < best):
            best = d
    return best


# --------------------------------------------------------------------------- controls


def stable_rng(*parts: object) -> random.Random:
    """A generator seeded from the parts by hashing (identical across runs and platforms)."""
    digest = hashlib.sha256("\x1f".join(str(p) for p in parts).encode("utf-8")).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def unit_kind(u: CodeUnit) -> str:
    """Unit type plus the test flag: the stratum of the kind-matched control."""
    return f"{u.unit_type}{'+test' if u.is_test else ''}"


@dataclass(frozen=True)
class ControlPools:
    """Candidate pools of one instance; the L2 units are already removed."""

    by_file: dict[str, list[str]]
    whole: list[str]
    by_kind: dict[str, list[str]]


def control_pools(units: list[CodeUnit], excluded: set[str]) -> ControlPools:
    """Pools of unit ids for the three controls, without ``excluded`` (the L2 units)."""
    by_file: dict[str, list[str]] = {}
    by_kind: dict[str, list[str]] = {}
    whole: list[str] = []
    for u in sorted(units, key=lambda x: x.id):
        if u.id in excluded:
            continue
        by_file.setdefault(u.file, []).append(u.id)
        by_kind.setdefault(unit_kind(u), []).append(u.id)
        whole.append(u.id)
    return ControlPools(by_file, whole, by_kind)


def draw_pool(control: str, pools: ControlPools, files: Iterable[str], kind: str) -> list[str]:
    """The pool a control draws from for a positive in ``files`` whose primary kind is ``kind``."""
    if control == "same_files":
        pool: set[str] = set()
        for f in files:
            pool.update(pools.by_file.get(f, ()))
        return sorted(pool)
    if control == "whole_repo":
        return pools.whole
    if control == "whole_repo_kind":
        return pools.by_kind.get(kind, [])
    raise ValueError(f"unknown control {control!r}")


def draw_sets(pool: list[str], k: int, draws: int, rng: random.Random) -> list[tuple[str, ...]]:
    """``draws`` random sets of ``k`` pool units (the whole pool each time when it is smaller)."""
    if not pool:
        return []
    take = min(k, len(pool))
    if take == len(pool):
        return [tuple(pool)] * draws
    return [tuple(rng.sample(pool, take)) for _ in range(draws)]


def control_shares(sets: list[tuple[str, ...]], dist: dict[str, int]) -> dict[str, float] | None:
    """Share of the drawn sets that fall within each hop limit of the L2 units (``dist``).

    ``unreachable`` is the share of sets with no path at all. ``None`` when nothing was drawn.
    """
    if not sets:
        return None
    within = {h: 0 for h in HOP_LIMITS}
    unreachable = 0
    for chosen in sets:
        d = min_distance(dist, chosen)
        if d is None:
            unreachable += 1
            continue
        for h in HOP_LIMITS:
            if d <= h:
                within[h] += 1
    n = len(sets)
    out = {f"le{h}": within[h] / n for h in HOP_LIMITS}
    out["unreachable"] = unreachable / n
    return out


def observed_shares(d: int | None) -> dict[str, float]:
    """Indicator form of one observed distance, aligned with :func:`control_shares`."""
    out = {f"le{h}": float(d is not None and d <= h) for h in HOP_LIMITS}
    out["unreachable"] = float(d is None)
    return out
