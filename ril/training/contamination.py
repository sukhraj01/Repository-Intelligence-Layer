"""Normalised function-hash probe for training-data contamination.

Implements the contamination probe of ``docs/EXPERIMENTS.md`` (E-CONTAM-PROBE). Question asked:
does a function of a benchmark repository, as it stands at an instance's base commit, occur
(up to formatting) as a ``document`` of a training corpus? A match is a *function-level* fact. It
does not show that the (query, document) pair was used in training, that the same repository
state was used, or that a model memorised anything; a non-match does not show absence (renamed
or edited copies are not detected, and only the scanned fields are searched).

Two hash levels, both over a single function definition:

* ``text``: the source with line endings normalised, common indentation removed, trailing
  whitespace removed and blank lines dropped. Comments and the docstring are kept, so this level
  finds copies that differ only in layout.
* ``ast``: the syntax tree without positions, with the docstring and decorators removed. This level
  also ignores comments, quoting style and layout. Names, arguments and body statements still have
  to agree.

Standard library only; the parser entry point used for the benchmark side is
``ril.parsing.repository_parser.parse_file``, so the probed functions are exactly the function and
method units of the CodeUnit definition.
"""

from __future__ import annotations

import ast
import hashlib
import json
import textwrap
import zlib
from collections import Counter
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

PROBE_VERSION = "contam-probe/v1"
"""Recorded with every probe run; part of its config hash."""


def normalise_text(source: str) -> str:
    """Layout-normalised source: ``\\n`` line ends, dedented, no trailing blanks, no empty lines."""
    text = source.replace("\r\n", "\n").replace("\r", "\n").replace("\t", "    ")
    text = textwrap.dedent(text)
    lines = [ln.rstrip() for ln in text.split("\n")]
    return "\n".join(ln for ln in lines if ln.strip())


def _digest(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8", "surrogatepass")).hexdigest()[:32]


def text_hash(source: str) -> str | None:
    """Hash of the layout-normalised source; ``None`` for an empty source."""
    norm = normalise_text(source)
    return _digest(norm) if norm else None


def _strip_docstring(node: ast.AST) -> None:
    body = getattr(node, "body", None)
    if (
        isinstance(body, list)
        and body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        del body[0]
        if not body:
            body.append(ast.Pass())


def _single_def(tree: ast.Module) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    """The only top-level statement if it is a function definition, else ``None``."""
    if len(tree.body) == 1:
        node = tree.body[0]
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return node
    return None


def ast_hash(source: str) -> str | None:
    """Hash of the function's syntax tree (docstring and decorators removed), or ``None``.

    See :func:`ast_hash_and_size` for the variant that also returns the node count.
    """
    return ast_hash_and_size(source)[0]


def ast_hash_and_size(source: str) -> tuple[str | None, int]:
    """Syntax-tree hash and the number of syntax-tree nodes of the stripped function (0 if none).

    The node count lets a report separate generic one-liners (``def __repr__``, getters) from
    functions large enough that an exact structural match is informative.

    ``None`` when the text does not parse (for example Python 2 syntax) or is not exactly one
    function definition. The source is dedented first, so a method cut out of a class parses.
    """
    try:
        tree = ast.parse(textwrap.dedent(source.replace("\r\n", "\n").replace("\r", "\n")))
    except (SyntaxError, ValueError, RecursionError, MemoryError):
        return None, 0
    node = _single_def(tree)
    if node is None:
        return None, 0
    node.decorator_list = []
    try:
        for inner in ast.walk(node):
            if isinstance(inner, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
                _strip_docstring(inner)
        size = sum(1 for _ in ast.walk(node))
        return _digest(ast.dump(node, annotate_fields=False, include_attributes=False)), size
    except RecursionError:  # a very deeply nested expression: no ast hash, the text hash remains
        return None, 0


@dataclass(frozen=True)
class FunctionHashes:
    """Both hash levels of one function (``ast`` may be ``None``)."""

    text: str | None
    ast: str | None
    nodes: int = 0


def function_hashes(source: str) -> FunctionHashes:
    """Both hashes of a function's source text (and the node count behind the ast hash)."""
    h, n = ast_hash_and_size(source)
    return FunctionHashes(text=text_hash(source), ast=h, nodes=n)


class ProbeSet:
    """Hashes of the probed functions, each mapped to the repositories (and a count) it came from.

    ``add`` records a function once per (repository, level, hash); ``origin`` keeps the first
    repository and the number of distinct snapshots the hash was seen in, which is all a report
    needs. No source text is stored.
    """

    def __init__(self) -> None:
        self.text: dict[str, set[str]] = {}
        self.ast: dict[str, set[str]] = {}
        self.nodes: dict[str, int] = {}
        self.functions = 0

    def add(self, repo: str, hashes: FunctionHashes) -> None:
        self.functions += 1
        if hashes.text is not None:
            self.text.setdefault(hashes.text, set()).add(repo)
        if hashes.ast is not None:
            self.ast.setdefault(hashes.ast, set()).add(repo)
            self.nodes[hashes.ast] = hashes.nodes

    def match(self, hashes: FunctionHashes) -> tuple[set[str], set[str]]:
        """Repositories matched at the text level and at the ast level."""
        t = self.text.get(hashes.text, set()) if hashes.text is not None else set()
        a = self.ast.get(hashes.ast, set()) if hashes.ast is not None else set()
        return t, a

    def to_json(self) -> str:
        """Canonical JSON (sorted) so a probe set can be saved and compared byte for byte."""
        doc = {
            "version": PROBE_VERSION,
            "functions": self.functions,
            "text": {k: sorted(v) for k, v in sorted(self.text.items())},
            "ast": {k: sorted(v) for k, v in sorted(self.ast.items())},
            "nodes": dict(sorted(self.nodes.items())),
        }
        return json.dumps(doc, sort_keys=True, separators=(",", ":"))

    @classmethod
    def from_json(cls, blob: str) -> ProbeSet:
        doc = json.loads(blob)
        if doc.get("version") != PROBE_VERSION:
            raise ValueError(f"probe set version {doc.get('version')!r} != {PROBE_VERSION!r}")
        out = cls()
        out.functions = int(doc["functions"])
        out.text = {k: set(v) for k, v in doc["text"].items()}
        out.ast = {k: set(v) for k, v in doc["ast"].items()}
        out.nodes = {k: int(v) for k, v in doc.get("nodes", {}).items()}
        return out


@dataclass
class ScanCounts:
    """Counts of one scan of a corpus slice (no text)."""

    rows: int = 0
    rows_bad_json: int = 0
    documents: int = 0
    documents_with_ast_hash: int = 0
    text_hits: int = 0
    ast_hits: int = 0
    any_hits: int = 0
    negatives: int = 0
    negative_text_hits: int = 0
    negative_ast_hits: int = 0

    def as_dict(self) -> dict[str, int]:
        return dict(self.__dict__)


def iter_documents(
    lines: Iterable[str], fields: tuple[str, ...] = ("document",)
) -> Iterator[tuple[str, str]]:
    """Yield ``(field, code)`` for every scanned code string of every JSON line.

    ``fields`` may name ``document`` (a string) and ``negatives`` (a list of strings). Bad lines
    and wrong-typed values are skipped and counted by the caller through :func:`scan_lines`.
    """
    for line in lines:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        for name in fields:
            value = row.get(name)
            if isinstance(value, str):
                yield name, value
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, str):
                        yield name, item


def scan_lines(
    lines: Iterable[str],
    probe: ProbeSet,
    *,
    negatives: bool = False,
    hits: list[dict[str, Any]] | None = None,
    max_hits: int = 10000,
) -> ScanCounts:
    """Hash the documents (and optionally negatives) of JSON lines and count probe matches.

    A hit record keeps only the matched hashes, the repositories and the row index, never text.
    """
    counts = ScanCounts()
    for idx, line in enumerate(lines):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            counts.rows_bad_json += 1
            continue
        if not isinstance(row, dict):
            counts.rows_bad_json += 1
            continue
        counts.rows += 1
        doc = row.get("document")
        if isinstance(doc, str):
            counts.documents += 1
            h = function_hashes(doc)
            if h.ast is not None:
                counts.documents_with_ast_hash += 1
            t_repos, a_repos = probe.match(h)
            counts.text_hits += bool(t_repos)
            counts.ast_hits += bool(a_repos)
            if t_repos or a_repos:
                counts.any_hits += 1
                if hits is not None and len(hits) < max_hits:
                    hits.append(
                        {
                            "row": idx,
                            "field": "document",
                            "text_hash": h.text if t_repos else None,
                            "ast_hash": h.ast if a_repos else None,
                            "repos": sorted(t_repos | a_repos),
                        }
                    )
        if negatives:
            for neg in row.get("negatives") or []:
                if not isinstance(neg, str):
                    continue
                counts.negatives += 1
                h = function_hashes(neg)
                t_repos, a_repos = probe.match(h)
                counts.negative_text_hits += bool(t_repos)
                counts.negative_ast_hits += bool(a_repos)
    return counts


def merge_counts(parts: Iterable[Mapping[str, int]]) -> dict[str, int]:
    """Sum the count dictionaries of several slices."""
    total: Counter[str] = Counter()
    for p in parts:
        total.update(p)
    return dict(total)


def gz_lines(chunks: Iterable[bytes], *, drop_partial: bool = False) -> Iterator[str]:
    """Decode the lines of a gzip stream delivered in chunks (a stream cut short is allowed).

    With ``drop_partial`` the unfinished last line of a cut stream is dropped (slice of a shard);
    otherwise it is yielded. Invalid UTF-8 is replaced, never raised: a bad byte costs one row at
    most. A corrupt gzip body raises ``zlib.error``.
    """
    dec = zlib.decompressobj(31)
    tail = b""
    for chunk in chunks:
        data = tail + dec.decompress(chunk)
        parts = data.split(b"\n")
        tail = parts.pop()
        for part in parts:
            yield part.decode("utf-8", "replace")
    tail += dec.flush()
    if tail and not drop_partial:
        yield tail.decode("utf-8", "replace")


NODE_BUCKETS: tuple[tuple[str, int, int], ...] = (
    ("under 20 nodes", 0, 20),
    ("20 to 49", 20, 50),
    ("50 to 99", 50, 100),
    ("100 or more", 100, 10**9),
)
"""Syntax-tree size classes of a matched function (``ast.walk`` node count)."""


def summarize_scan(
    shard_results: Sequence[Mapping[str, Any]], sizes: Mapping[str, int]
) -> dict[str, Any]:
    """Totals and hit breakdowns over scanned shards.

    ``shard_results`` are the per-shard output records (``counts`` and ``hits``); ``sizes`` maps an
    ast hash to its node count. Hits are classed by node count and by whether the hash belongs to
    one repository or several (a hash shared by several repositories is a generic function). A hit
    whose ast hash is absent (text-level match only) goes to ``no ast hash``.
    """
    totals = merge_counts(r["counts"] for r in shard_results)
    buckets: Counter[str] = Counter()
    by_repo: Counter[str] = Counter()
    multi = 0
    distinct: set[str] = set()
    n_hits = 0
    for r in shard_results:
        for hit in r["hits"]:
            n_hits += 1
            h = hit.get("ast_hash")
            if h is None:
                buckets["no ast hash"] += 1
            else:
                distinct.add(h)
                n = sizes.get(h, 0)
                label = next(
                    (name for name, lo, hi in NODE_BUCKETS if lo <= n < hi), "unknown size"
                )
                buckets[label] += 1
            repos = hit["repos"]
            multi += len(repos) > 1
            for rp in repos:
                by_repo[rp] += 1
    return {
        "shards": len(shard_results),
        "totals": totals,
        "hit_records": n_hits,
        "hit_records_with_several_repos": multi,
        "distinct_hit_ast_hashes": len(distinct),
        "hits_by_node_bucket": {name: buckets.get(name, 0) for name, _, _ in NODE_BUCKETS}
        | {k: v for k, v in buckets.items() if k not in {n for n, _, _ in NODE_BUCKETS}},
        "hits_by_repo": dict(sorted(by_repo.items())),
    }
