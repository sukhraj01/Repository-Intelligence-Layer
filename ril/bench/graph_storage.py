"""Storage options for the RepoGraph, measured side by side (S1 to S7, ``specs/repo_graph.md``).

Implements the storage measurement of ``specs/parse_one_repo.md`` (ADR-011 input). No option is
chosen here: each backend writes the same graph, loads it in a fresh process and answers the same
1-hop and 2-hop expansion queries; the harness records build time, size, load time, peak resident
memory and expansion latency p50/p95/p99 (cold and warm) per repository and hardware spec.

Expansion (batch size 1, one query = three seed units): the set of units reached within ``k`` hops
over the resolved edges of the five core families (``contain``, ``import``, ``invoke``, ``inherit``,
``override``), followed in both directions, seeds excluded. The query reads only the store, as a
retrieval-time graph signal would (role A of ``docs/GRAPH_DESIGN.md``).

Backends: ``jsonl`` (S7 canonical file + dict adjacency), ``parquet`` (S1 Parquet edge list + CSR
arrays), ``sqlite`` (S2 indexed table queried directly) and ``sqlite_cache`` (S2 with an in-memory
adjacency cache), ``networkx`` (S3), ``rustworkx`` (S4), ``kuzu`` (S5, an embedded graph database),
``sidecar`` (S6 per-file JSON files). S3 and S4 load a compact tab-separated adjacency file.

Kept compatible with Python 3.10.
"""

from __future__ import annotations

import json
import os
import platform
import random
import resource
import shutil
import sqlite3
import sys
import time
from collections import defaultdict
from collections.abc import Callable, Sequence
from typing import Any, Protocol, cast

import numpy as np
import numpy.typing as npt

from ril.parsing.repo_graph import CORE_EDGE_TYPES, Edge, RepoGraph

BACKENDS: tuple[str, ...] = (
    "jsonl",
    "parquet",
    "sqlite",
    "sqlite_cache",
    "networkx",
    "rustworkx",
    "kuzu",
    "sidecar",
)
SEEDS_PER_QUERY = 3
IntArray = npt.NDArray[np.int64]


class Store(Protocol):
    """A loaded graph that answers expansion queries."""

    def expand(self, seeds: Sequence[str], hops: int) -> set[str]: ...

    def reset(self) -> None: ...


def core_pairs(graph: RepoGraph) -> list[tuple[str, str]]:
    """Sorted unique (src, dst) pairs of resolved core edges, self-loops dropped."""
    pairs = {
        (e.src, e.dst)
        for e in graph.edges
        if e.type in CORE_EDGE_TYPES and e.status == "resolved" and e.src != e.dst
    }
    return sorted(pairs)


def _bfs(neighbours: Callable[[str], Sequence[str]], seeds: Sequence[str], hops: int) -> set[str]:
    seen = set(seeds)
    frontier = list(seeds)
    for _ in range(hops):
        nxt: list[str] = []
        for n in frontier:
            for m in neighbours(n):
                if m not in seen:
                    seen.add(m)
                    nxt.append(m)
        frontier = nxt
    return seen - set(seeds)


def build_query_set(graph: RepoGraph, n: int, seed: int) -> list[str]:
    """``n`` queries of three seed unit ids each, drawn from units that have a resolved edge.

    Seeds are code units (class, function, method) of non-test files with at least one resolved
    core edge besides ``contain``, so the expansion has something to follow; the draw is seeded.
    """
    touched: set[str] = set()
    for e in graph.edges:
        if (
            e.type in ("import", "invoke", "inherit", "override")
            and e.status == "resolved"
            and e.src != e.dst
        ):
            touched.add(e.src)
            touched.add(e.dst)
    pool = sorted(
        nid
        for nid in touched
        if nid in graph.nodes
        and graph.nodes[nid][0] in ("class", "function", "method")
        and not _is_test_path(graph.nodes[nid][1])
    )
    rng = random.Random(seed)
    return ["|".join(rng.sample(pool, SEEDS_PER_QUERY)) for _ in range(n)]


def _is_test_path(path: str) -> bool:
    from ril.parsing.path_rules import is_test_path

    return is_test_path(path)


# --------------------------------------------------------------------------- jsonl (S7)


class _AdjStore:
    def __init__(self, adj: dict[str, list[str]]) -> None:
        self.adj = adj

    def expand(self, seeds: Sequence[str], hops: int) -> set[str]:
        return _bfs(lambda n: self.adj.get(n, ()), seeds, hops)

    def reset(self) -> None:
        return None


def _undirected_adj(pairs: Sequence[tuple[str, str]]) -> dict[str, list[str]]:
    adj: dict[str, set[str]] = defaultdict(set)
    for a, b in pairs:
        adj[a].add(b)
        adj[b].add(a)
    return {k: sorted(v) for k, v in adj.items()}


def write_jsonl(graph: RepoGraph, path: str) -> None:
    os.makedirs(path, exist_ok=True)
    with open(os.path.join(path, "nodes.jsonl"), "wb") as handle:
        handle.write(graph.nodes_jsonl())
    with open(os.path.join(path, "edges.jsonl"), "wb") as handle:
        handle.write(graph.edges_jsonl(CORE_EDGE_TYPES))


def load_jsonl(path: str) -> Store:
    pairs: list[tuple[str, str]] = []
    with open(os.path.join(path, "edges.jsonl"), encoding="utf-8") as handle:
        for line in handle:
            d = json.loads(line)
            if d["status"] == "resolved" and d["src"] != d["dst"]:
                pairs.append((d["src"], d["dst"]))
    return _AdjStore(_undirected_adj(pairs))


# ------------------------------------------------------------------ compact adjacency (S3, S4)


def write_tsv(graph: RepoGraph, path: str) -> None:
    os.makedirs(path, exist_ok=True)
    with open(os.path.join(path, "adjacency.tsv"), "w", encoding="utf-8") as handle:
        for a, b in core_pairs(graph):
            handle.write(f"{a}\t{b}\n")


def _read_tsv(path: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    with open(os.path.join(path, "adjacency.tsv"), encoding="utf-8") as handle:
        for line in handle:
            a, _, b = line.rstrip("\n").partition("\t")
            out.append((a, b))
    return out


class _NxStore:
    def __init__(self, pairs: Sequence[tuple[str, str]]) -> None:
        import networkx as nx

        self.g = nx.Graph()
        self.g.add_edges_from(pairs)

    def expand(self, seeds: Sequence[str], hops: int) -> set[str]:
        g = self.g
        return _bfs(lambda n: list(g.neighbors(n)) if n in g else [], seeds, hops)

    def reset(self) -> None:
        return None


class _RxStore:
    def __init__(self, pairs: Sequence[tuple[str, str]]) -> None:
        import rustworkx as rx

        self.index: dict[str, int] = {}
        self.names: list[str] = []
        self.g = rx.PyGraph(multigraph=False)
        for a, b in pairs:
            self.g.add_edge(self._node(a), self._node(b), None)

    def _node(self, name: str) -> int:
        i = self.index.get(name)
        if i is None:
            i = self.g.add_node(name)
            self.index[name] = i
            self.names.append(name)
        return i

    def expand(self, seeds: Sequence[str], hops: int) -> set[str]:
        start = {self.index[s] for s in seeds if s in self.index}
        seen = set(start)
        frontier = list(start)
        for _ in range(hops):
            nxt: list[int] = []
            for n in frontier:
                for m in self.g.neighbors(n):
                    if m not in seen:
                        seen.add(m)
                        nxt.append(m)
            frontier = nxt
        return {self.names[i] for i in seen - start}

    def reset(self) -> None:
        return None


# --------------------------------------------------------------------------- parquet (S1)


def write_parquet(graph: RepoGraph, path: str) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    os.makedirs(path, exist_ok=True)
    edges = graph.edges
    table = pa.table(
        {
            "type": [e.type for e in edges],
            "src": [e.src for e in edges],
            "dst": [e.dst for e in edges],
            "status": [e.status for e in edges],
            "derivation": [e.derivation for e in edges],
            "candidates": [list(e.candidates) for e in edges],
            "site": [e.site for e in edges],
            "target_text": [e.target_text for e in edges],
        }
    )
    pq.write_table(table, os.path.join(path, "edges.parquet"), compression="zstd")


class _CsrStore:
    def __init__(self, src: list[str], dst: list[str]) -> None:
        names = sorted(set(src) | set(dst))
        self.index = {n: i for i, n in enumerate(names)}
        self.names = names
        a = np.fromiter((self.index[s] for s in src), dtype=np.int64, count=len(src))
        b = np.fromiter((self.index[d] for d in dst), dtype=np.int64, count=len(dst))
        both_src = np.concatenate([a, b])
        both_dst = np.concatenate([b, a])
        order = np.argsort(both_src, kind="stable")
        self.targets: IntArray = both_dst[order]
        counts = np.bincount(both_src, minlength=len(names))
        self.offsets: IntArray = np.concatenate([[0], np.cumsum(counts)]).astype(np.int64)

    def expand(self, seeds: Sequence[str], hops: int) -> set[str]:
        start = [self.index[s] for s in seeds if s in self.index]
        seen = set(start)
        frontier = list(start)
        off, tgt = self.offsets, self.targets
        for _ in range(hops):
            nxt: list[int] = []
            for n in frontier:
                for m in tgt[off[n] : off[n + 1]].tolist():
                    if m not in seen:
                        seen.add(m)
                        nxt.append(m)
            frontier = nxt
        return {self.names[i] for i in seen - set(start)}

    def reset(self) -> None:
        return None


def load_parquet(path: str) -> Store:
    import pyarrow.compute as pc
    import pyarrow.parquet as pq

    table = pq.read_table(
        os.path.join(path, "edges.parquet"), columns=["type", "src", "dst", "status"]
    )
    mask = pc.and_(
        pc.and_(
            pc.is_in(table["type"], value_set=_arrow_strings(CORE_EDGE_TYPES)),
            pc.equal(table["status"], "resolved"),
        ),
        pc.not_equal(table["src"], table["dst"]),
    )
    table = table.filter(mask)
    return _CsrStore(table["src"].to_pylist(), table["dst"].to_pylist())


def _arrow_strings(values: Sequence[str]) -> Any:
    import pyarrow as pa

    return pa.array(list(values))


# --------------------------------------------------------------------------- sqlite (S2)


def write_sqlite(graph: RepoGraph, path: str) -> None:
    os.makedirs(path, exist_ok=True)
    db = os.path.join(path, "graph.sqlite")
    if os.path.exists(db):
        os.remove(db)
    con = sqlite3.connect(db)
    con.execute(
        "CREATE TABLE edges (type TEXT, src TEXT, dst TEXT, status TEXT, derivation TEXT, "
        "candidates TEXT, site TEXT, target_text TEXT)"
    )
    con.executemany(
        "INSERT INTO edges VALUES (?,?,?,?,?,?,?,?)",
        [
            (
                e.type,
                e.src,
                e.dst,
                e.status,
                e.derivation,
                json.dumps(list(e.candidates)),
                e.site,
                e.target_text,
            )
            for e in graph.edges
        ],
    )
    con.execute("CREATE INDEX idx_type_src ON edges (type, src)")
    con.execute("CREATE INDEX idx_type_dst ON edges (type, dst)")
    con.commit()
    con.close()


class _SqliteStore:
    _SQL_OUT = "SELECT dst FROM edges WHERE type = ? AND src = ? AND status = 'resolved'"
    _SQL_IN = "SELECT src FROM edges WHERE type = ? AND dst = ? AND status = 'resolved'"

    def __init__(self, path: str, cache: bool) -> None:
        self.path = os.path.join(path, "graph.sqlite")
        self.con = sqlite3.connect(self.path)
        self.cache: dict[str, list[str]] | None = None
        if cache:
            rows = self.con.execute(
                "SELECT src, dst FROM edges WHERE status = 'resolved' AND src <> dst AND type IN ("
                + ",".join("?" * len(CORE_EDGE_TYPES))
                + ")",
                CORE_EDGE_TYPES,
            ).fetchall()
            self.cache = _undirected_adj([(a, b) for a, b in rows])

    def _neighbours(self, node: str) -> list[str]:
        if self.cache is not None:
            return self.cache.get(node, [])
        out: set[str] = set()
        for t in CORE_EDGE_TYPES:
            out.update(r[0] for r in self.con.execute(self._SQL_OUT, (t, node)))
            out.update(r[0] for r in self.con.execute(self._SQL_IN, (t, node)))
        out.discard(node)
        return sorted(out)

    def expand(self, seeds: Sequence[str], hops: int) -> set[str]:
        return _bfs(self._neighbours, seeds, hops)

    def reset(self) -> None:
        if self.cache is None:  # direct mode: a cold call reopens the database connection
            self.con.close()
            self.con = sqlite3.connect(self.path)


# --------------------------------------------------------------------------- kuzu (S5)


def write_kuzu(graph: RepoGraph, path: str) -> None:
    import kuzu

    if os.path.exists(path):
        shutil.rmtree(path)
    os.makedirs(path)
    nodes_csv = os.path.join(path, "nodes.csv")
    edges_csv = os.path.join(path, "edges.csv")
    pairs = [
        (e.src, e.dst, e.type)
        for e in graph.edges
        if e.type in CORE_EDGE_TYPES and e.status == "resolved" and e.src != e.dst
    ]
    ids = sorted({a for a, _, _ in pairs} | {b for _, b, _ in pairs})
    import csv

    with open(nodes_csv, "w", newline="", encoding="utf-8") as handle:
        w = csv.writer(handle)
        for i in ids:
            w.writerow([i])
    with open(edges_csv, "w", newline="", encoding="utf-8") as handle:
        w = csv.writer(handle)
        for a, b, t in pairs:
            w.writerow([a, b, t])
    db = kuzu.Database(os.path.join(path, "db"))
    con = kuzu.Connection(db)
    con.execute("CREATE NODE TABLE N(id STRING, PRIMARY KEY (id))")
    con.execute("CREATE REL TABLE E(FROM N TO N, type STRING)")
    con.execute(f'COPY N FROM "{nodes_csv}" (header=false)')
    con.execute(f'COPY E FROM "{edges_csv}" (header=false)')
    del con, db
    os.remove(nodes_csv)
    os.remove(edges_csv)


class _KuzuStore:
    def __init__(self, path: str) -> None:
        self.path = os.path.join(path, "db")
        self._open()

    def _open(self) -> None:
        import kuzu

        self.db = kuzu.Database(self.path, read_only=True)
        self.con = kuzu.Connection(self.db)

    def expand(self, seeds: Sequence[str], hops: int) -> set[str]:
        res = self.con.execute(
            f"MATCH (a:N)-[:E*1..{hops}]-(b:N) WHERE a.id IN $seeds RETURN DISTINCT b.id",
            {"seeds": list(seeds)},
        )
        assert not isinstance(res, list)
        out: set[str] = set()
        while res.has_next():
            row = cast(list[Any], res.get_next())
            out.add(str(row[0]))
        return out - set(seeds)

    def reset(self) -> None:
        del self.con, self.db
        self._open()


# --------------------------------------------------------------------------- sidecars (S6)


def _sidecar_name(file: str) -> str:
    return file.replace("/", "__") + ".json"


def write_sidecars(graph: RepoGraph, path: str) -> None:
    """One JSON file per source file holding the edges whose source lies in that file."""
    if os.path.exists(path):
        shutil.rmtree(path)
    os.makedirs(path)
    by_file: dict[str, list[Edge]] = defaultdict(list)
    for e in graph.edges:
        if e.type in CORE_EDGE_TYPES:
            node = graph.nodes.get(e.src)
            key = node[1] if node and node[0] != "directory" else "_directories"
            by_file[key].append(e)
    for file, edges in sorted(by_file.items()):
        with open(os.path.join(path, _sidecar_name(file)), "w", encoding="utf-8") as handle:
            json.dump([e.to_dict() for e in edges], handle, sort_keys=True, separators=(",", ":"))


def load_sidecars(path: str) -> Store:
    pairs: list[tuple[str, str]] = []
    for name in sorted(os.listdir(path)):
        with open(os.path.join(path, name), encoding="utf-8") as handle:
            for d in json.load(handle):
                if d["status"] == "resolved" and d["src"] != d["dst"]:
                    pairs.append((d["src"], d["dst"]))
    return _AdjStore(_undirected_adj(pairs))


# --------------------------------------------------------------------------- registry of backends


def writer(name: str) -> Callable[[RepoGraph, str], None]:
    return {
        "jsonl": write_jsonl,
        "parquet": write_parquet,
        "sqlite": write_sqlite,
        "sqlite_cache": write_sqlite,
        "networkx": write_tsv,
        "rustworkx": write_tsv,
        "kuzu": write_kuzu,
        "sidecar": write_sidecars,
    }[name]


def loader(name: str) -> Callable[[str], Store]:
    def nx_loader(p: str) -> Store:
        return _NxStore(_read_tsv(p))

    def rx_loader(p: str) -> Store:
        return _RxStore(_read_tsv(p))

    return {
        "jsonl": load_jsonl,
        "parquet": load_parquet,
        "sqlite": lambda p: _SqliteStore(p, cache=False),
        "sqlite_cache": lambda p: _SqliteStore(p, cache=True),
        "networkx": nx_loader,
        "rustworkx": rx_loader,
        "kuzu": lambda p: _KuzuStore(p),
        "sidecar": load_sidecars,
    }[name]


def preimport(name: str) -> float:
    """Import the third-party library a backend needs and return the seconds it took.

    Library import time is reported separately so that ``write`` and ``load`` times describe the
    store, not the interpreter loading a package once per process.
    """
    t0 = time.perf_counter()
    libs = {
        "parquet": ("pyarrow", "pyarrow.parquet", "pyarrow.compute"),
        "networkx": ("networkx",),
        "rustworkx": ("rustworkx",),
        "kuzu": ("kuzu",),
    }
    for mod in libs.get(name, ()):
        __import__(mod)
    return time.perf_counter() - t0


def dir_size(path: str) -> int:
    """Total bytes of a file or directory tree."""
    if os.path.isfile(path):
        return os.path.getsize(path)
    total = 0
    for dirpath, _dirs, files in os.walk(path):
        for f in files:
            total += os.path.getsize(os.path.join(dirpath, f))
    return total


def peak_rss_mb() -> float:
    """Peak resident set size of this process in MB.

    On Linux the ``VmHWM`` line of ``/proc/self/status`` is the high-water mark of the current
    address space; ``ru_maxrss`` is not used there because a process started by ``fork`` and
    ``exec`` inherits the parent's maximum, which made every step of a measurement run report the
    orchestrator's size. Elsewhere ``ru_maxrss`` (bytes on macOS) is used.
    """
    status = "/proc/self/status"
    if os.path.exists(status):
        with open(status, encoding="ascii", errors="replace") as handle:
            for line in handle:
                if line.startswith("VmHWM:"):
                    return int(line.split()[1]) / 1024
    raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return raw / (1024 * 1024) if sys.platform == "darwin" else raw / 1024


def timed(fn: Callable[[], Any]) -> tuple[Any, float]:
    t0 = time.perf_counter()
    out = fn()
    return out, time.perf_counter() - t0


def platform_tag() -> str:
    return f"{platform.system()}-{platform.machine()}"
