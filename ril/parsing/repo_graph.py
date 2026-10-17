"""The RepoGraph: a typed edge store for one repository snapshot (DRAFT v0).

Implements ``specs/repo_graph.md`` (DRAFT v0, ADR-011). This module makes no design choice the
spec leaves open: the edge record carries the required fields (type, src, dst, status,
derivation, candidates) and the optional ones (site, target_text) are stored for every edge so
that any later policy can be applied by a reader (``provisional: ADR-011``, Q-G7). No edge
carries a confidence score.

Serialization is canonical (sorted keys, compact separators, UTF-8, edges in a total order) so
that a rebuild from the same inputs is byte-identical.

Kept compatible with Python 3.10.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field

REPO_GRAPH_SCHEMA_VERSION = "v0-draft"
"""Recorded with every graph artifact; bumped by the spec's change control only."""

EDGE_TYPES: tuple[str, ...] = (
    "contain",
    "import",
    "invoke",
    "inherit",
    "override",
    "tests",
    "configures",
    "co_change",
)
CORE_EDGE_TYPES: tuple[str, ...] = ("contain", "import", "invoke", "inherit", "override")
STATUSES: tuple[str, ...] = ("resolved", "ambiguous", "unresolved", "external")
NODE_KINDS: tuple[str, ...] = ("directory", "file", "class", "function", "method", "config")


@dataclass(frozen=True)
class Edge:
    """One typed relation (or one syntactic site, for ``invoke``)."""

    type: str
    src: str
    dst: str  # node id when resolved; "" otherwise
    status: str
    derivation: str  # resolver rule that produced the edge
    candidates: tuple[str, ...] = ()
    site: str = ""  # "path:line:col" of the syntactic site
    target_text: str = ""  # the target as written, for non-resolved edges

    def __post_init__(self) -> None:
        if self.type not in EDGE_TYPES:
            raise ValueError(f"unknown edge type {self.type!r}")
        if self.status not in STATUSES:
            raise ValueError(f"unknown status {self.status!r}")
        if self.status == "resolved" and not self.dst:
            raise ValueError("a resolved edge needs a dst")
        if self.status != "resolved" and self.dst:
            raise ValueError("only a resolved edge carries a dst")
        if self.status == "ambiguous" and not self.candidates:
            raise ValueError("an ambiguous edge needs its candidate set")

    def sort_key(self) -> tuple[str, str, str, str, str, str, str]:
        """Total order used for canonical output."""
        return (
            self.type,
            self.src,
            self.site,
            self.dst,
            self.derivation,
            self.target_text,
            "|".join(self.candidates),
        )

    def to_dict(self) -> dict[str, object]:
        d = asdict(self)
        d["candidates"] = list(self.candidates)
        return d

    def to_json(self) -> str:
        return canonical_json(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Edge:
        raw_candidates = data.get("candidates", [])
        candidates = (
            tuple(str(c) for c in raw_candidates) if isinstance(raw_candidates, list) else ()
        )
        return cls(
            type=str(data["type"]),
            src=str(data["src"]),
            dst=str(data["dst"]),
            status=str(data["status"]),
            derivation=str(data["derivation"]),
            candidates=candidates,
            site=str(data.get("site", "")),
            target_text=str(data.get("target_text", "")),
        )


def canonical_json(obj: object) -> str:
    """Deterministic JSON: sorted keys, compact separators, no ASCII escaping."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


@dataclass
class RepoGraph:
    """Nodes, edges and the metadata a graph artifact must record (spec, "Version constant")."""

    meta: dict[str, object]
    nodes: dict[str, tuple[str, str]]  # id -> (kind, path)
    edges: list[Edge] = field(default_factory=list)

    def sort(self) -> None:
        """Put the edges in the canonical total order."""
        self.edges.sort(key=Edge.sort_key)

    def nodes_jsonl(self) -> bytes:
        lines = [
            canonical_json({"id": nid, "kind": kind, "path": path}) + "\n"
            for nid, (kind, path) in sorted(self.nodes.items())
        ]
        return "".join(lines).encode("utf-8")

    def edges_jsonl(self, types: Iterable[str] | None = None) -> bytes:
        wanted = set(types) if types is not None else None
        out = [e.to_json() + "\n" for e in self.edges if wanted is None or e.type in wanted]
        return "".join(out).encode("utf-8")

    def meta_json(self) -> bytes:
        return (canonical_json(self.meta) + "\n").encode("utf-8")

    def digest(self) -> str:
        """SHA-256 over meta, nodes and edges (the determinism test compares this)."""
        h = hashlib.sha256()
        for part in (self.meta_json(), self.nodes_jsonl(), self.edges_jsonl()):
            h.update(len(part).to_bytes(8, "big"))
            h.update(part)
        return h.hexdigest()

    def status_table(self) -> dict[str, dict[str, int]]:
        """Edge counts per family and status (the per-status coverage table)."""
        table: dict[str, Counter[str]] = {}
        for e in self.edges:
            table.setdefault(e.type, Counter())[e.status] += 1
        return {t: {s: table[t].get(s, 0) for s in STATUSES} for t in EDGE_TYPES if t in table}

    def rule_table(self, edge_type: str) -> dict[str, dict[str, int]]:
        """Counts per (derivation rule, status) for one family."""
        out: dict[str, Counter[str]] = {}
        for e in self.edges:
            if e.type == edge_type:
                out.setdefault(e.derivation, Counter())[e.status] += 1
        return {r: dict(sorted(c.items())) for r, c in sorted(out.items())}

    def adjacency(
        self, types: Iterable[str] = CORE_EDGE_TYPES
    ) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
        """Forward and reverse adjacency over resolved edges of the given families.

        Neighbour lists are sorted and deduplicated; self-loops are dropped.
        """
        wanted = set(types)
        fwd: dict[str, set[str]] = {}
        rev: dict[str, set[str]] = {}
        for e in self.edges:
            if e.type in wanted and e.status == "resolved" and e.src != e.dst:
                fwd.setdefault(e.src, set()).add(e.dst)
                rev.setdefault(e.dst, set()).add(e.src)
        return (
            {k: sorted(v) for k, v in sorted(fwd.items())},
            {k: sorted(v) for k, v in sorted(rev.items())},
        )
