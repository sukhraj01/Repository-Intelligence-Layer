"""Teacher ranks of the candidate pool's positives: sample, read, rank, tabulate (E-POOL-RANKS).

Exploratory. Implements the data half of ``docs/EXPERIMENTS.md`` E-POOL-RANKS: for pool instances
(one directory per pull request of ``gangiswag/train_data`` python, layout in
``knowledge/datasets/sweloc.md``) every positive function is ranked against the other functions of
the same snapshot by similarity to the issue, under several teachers (two pretrained or fine-tuned
encoders and BM25). The ranks are the quality signal the FILTER and WEIGHT arms are defined on
(ADR-002, K-rank of SweRank); nothing here chooses a teacher, a K or a pool (``provisional:
ADR-001, ADR-002``).

Rank definition, taken from the published SweRank construction scripts (read 2026-10-25, see the
experiment entry): each positive is a separate instance whose candidates are the positive and every
*non-positive* function of the snapshot, so the other modified functions of the same pull request
are not competitors. ``rank`` here is that rank, 1-based, counting strictly higher scores (ties go
in the positive's favour, which matters only for BM25 zero scores); ``rank_all`` also counts the
other positives, and ``ties`` the non-positive functions with exactly the positive's score.

Text form: the pool stores each function as ``<id>\\n<code>``; the published mining script encoded
the code alone, so the default form strips a first line equal to the id (``TEXT_FORMS``).

Nothing that leaves the cluster holds text: the outputs are ids, ranks, counts and timings.
Kept compatible with Python 3.10 (the cluster's compute nodes).
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import urllib.request
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import asdict, dataclass
from typing import Any, Protocol

import numpy as np
import numpy.typing as npt

from ril.training import pool_check as pc

POOL_RANKS_VERSION = "pool-ranks/v1"
PROVISIONAL = "provisional: ADR-001, ADR-002"
K_CUTS: tuple[int, ...] = (10, 20, 40)
"""Rank cuts reported (SweRank K=20 under CodeRankEmbed; SweRank+ K=40 under SweRankEmbed-Small)."""
TEXT_FORMS: tuple[str, ...] = ("code", "pool")
"""``code``: the id line stripped (as the published mining script); ``pool``: the stored text."""

Record = dict[str, Any]
Floats = npt.NDArray[np.float64]
Fetch = Callable[[str, int, int], bytes]


# --------------------------------------------------------------------------------------------
# instances, strata, sample


@dataclass(frozen=True)
class PoolInstance:
    """One pool directory with what the sample is stratified on."""

    dir: str
    repo: str
    pr: int
    corpus_bytes: int
    positives: int
    held_out: bool
    size_bin: int

    @property
    def stratum(self) -> str:
        """Stratum label ``s<size bin>-<h|k>`` (h = held-out repository, k = kept)."""
        return f"s{self.size_bin}-{'h' if self.held_out else 'k'}"


def size_edges(sizes: Sequence[float], bins: int = 4) -> tuple[float, ...]:
    """Inner quantile edges of the corpus sizes (``bins - 1`` values, ascending)."""
    if bins < 1:
        raise ValueError("bins must be at least 1")
    return tuple(pc.percentile(list(sizes), 100.0 * i / bins) for i in range(1, bins))


def size_bin(size: float, edges: Sequence[float]) -> int:
    """Index of the size bin (0 = smallest); a size equal to an edge goes to the lower bin."""
    return sum(1 for e in edges if size > e)


def build_instances(
    meta_rows: Iterable[Mapping[str, Any]],
    is_held_out: Callable[[str], bool],
    bins: int = 4,
) -> tuple[list[PoolInstance], tuple[float, ...]]:
    """Pool instances from the pool-check metadata rows (``dir``, ``corpus_bytes``, ``positives``).

    The repository comes from the directory name (``owner__name-<PR>``); an unreadable name raises
    ``ValueError`` rather than being dropped silently.
    """
    rows = sorted(meta_rows, key=lambda r: str(r["dir"]))
    edges = size_edges([float(r["corpus_bytes"]) for r in rows], bins)
    out: list[PoolInstance] = []
    for r in rows:
        split = pc.split_instance_dir(str(r["dir"]))
        if split is None:
            raise ValueError(f"unreadable instance directory {r['dir']!r}")
        repo, pr = split
        out.append(
            PoolInstance(
                dir=str(r["dir"]),
                repo=repo,
                pr=pr,
                corpus_bytes=int(r["corpus_bytes"]),
                positives=int(r["positives"]),
                held_out=bool(is_held_out(repo)),
                size_bin=size_bin(float(r["corpus_bytes"]), edges),
            )
        )
    return out, edges


def seeded_key(seed: int, name: str) -> str:
    """Order key of a name under a seed (stable across Python versions and machines)."""
    return hashlib.sha256(f"{seed}:{name}".encode()).hexdigest()


def stratified_sample(
    instances: Sequence[PoolInstance], per_stratum: int, seed: int
) -> list[PoolInstance]:
    """``per_stratum`` instances of every stratum, first by the seeded order; sorted by directory.

    A stratum with fewer instances contributes all of them (the summary records the counts).
    """
    by: dict[str, list[PoolInstance]] = {}
    for inst in instances:
        by.setdefault(inst.stratum, []).append(inst)
    chosen: list[PoolInstance] = []
    for _, members in sorted(by.items()):
        members = sorted(members, key=lambda i: seeded_key(seed, i.dir))
        chosen.extend(members[:per_stratum])
    return sorted(chosen, key=lambda i: i.dir)


def stratum_totals(instances: Iterable[PoolInstance]) -> dict[str, dict[str, int]]:
    """Pool counts per stratum: directories, positives, corpus bytes."""
    out: dict[str, dict[str, int]] = {}
    for inst in instances:
        t = out.setdefault(inst.stratum, {"dirs": 0, "positives": 0, "corpus_bytes": 0})
        t["dirs"] += 1
        t["positives"] += inst.positives
        t["corpus_bytes"] += inst.corpus_bytes
    return dict(sorted(out.items()))


def instance_record(inst: PoolInstance) -> Record:
    """JSON form of an instance (for the sample file)."""
    rec = asdict(inst)
    rec["stratum"] = inst.stratum
    return rec


def instance_from_record(rec: Mapping[str, Any]) -> PoolInstance:
    """Inverse of :func:`instance_record`."""
    return PoolInstance(
        dir=str(rec["dir"]),
        repo=str(rec["repo"]),
        pr=int(rec["pr"]),
        corpus_bytes=int(rec["corpus_bytes"]),
        positives=int(rec["positives"]),
        held_out=bool(rec["held_out"]),
        size_bin=int(rec["size_bin"]),
    )


def group_members(
    members: Sequence[Mapping[str, Any]], prefix: str
) -> dict[str, dict[str, Mapping[str, Any]]]:
    """``{directory: {corpus, queries, qrels}}`` of a zip member table under ``prefix``.

    The same grouping as :func:`pool_check.pool_instances` for any top-level prefix (the pool's
    ``train/python/`` or the reference archive's ``swe_bench_verified/``); incomplete directories
    are left out.
    """
    out: dict[str, dict[str, Mapping[str, Any]]] = {}
    kinds = {"corpus.jsonl": "corpus", "queries.jsonl": "queries", "test.tsv": "qrels"}
    for m in members:
        name = str(m["name"])
        if not name.startswith(prefix) or name.endswith("/"):
            continue
        parts = name[len(prefix) :].split("/")
        kind = kinds.get(parts[-1])
        if kind is None or len(parts) not in (2, 3):
            continue
        out.setdefault(parts[0], {})[kind] = m
    return {k: v for k, v in sorted(out.items()) if len(v) == 3}


def reference_instances(
    groups: Mapping[str, Mapping[str, Mapping[str, Any]]], strip: str
) -> list[PoolInstance]:
    """Instances of a reference archive (one stratum ``s0-h``; positives read later from qrels).

    ``strip`` is a name prefix removed before the ``owner__name-<n>`` split (the reference archive
    names directories ``swe-bench-verified-function_<owner>__<name>-<n>``).
    """
    out: list[PoolInstance] = []
    for d, mem in sorted(groups.items()):
        split = pc.split_instance_dir(d[len(strip) :] if d.startswith(strip) else d)
        if split is None:
            raise ValueError(f"unreadable reference directory {d!r}")
        out.append(
            PoolInstance(
                dir=d,
                repo=split[0],
                pr=split[1],
                corpus_bytes=int(mem["corpus"]["uncompressed"]),
                positives=0,
                held_out=True,
                size_bin=0,
            )
        )
    return out


def order_by_repository(instances: Sequence[PoolInstance], seed: int) -> list[PoolInstance]:
    """Instances grouped by repository (so a per-repository vector cache can be reused)."""
    return sorted(instances, key=lambda i: (seeded_key(seed, i.repo), i.dir))


def shard_of(repo: str, shards: int) -> int:
    """Shard of a repository (all directories of a repository go to one shard)."""
    return int(hashlib.sha256(repo.encode()).hexdigest(), 16) % shards


# --------------------------------------------------------------------------------------------
# reading one instance from the archive


@dataclass(frozen=True)
class InstanceData:
    """What one directory holds, in memory only (never written)."""

    dir: str
    query: str
    ids: list[str]
    texts: list[str]
    positives: list[str]
    corpus_bytes: int


def code_text(fid: str, text: str, form: str = "code") -> str:
    """The text a teacher sees for one function (see ``TEXT_FORMS``)."""
    if form == "pool":
        return text
    if form != "code":
        raise ValueError(f"unknown text form {form!r}")
    head, sep, rest = text.partition("\n")
    return rest if sep and head.strip() == fid else text


def parse_instance(
    name: str, corpus: bytes, queries: bytes, qrels: bytes, form: str = "code"
) -> InstanceData:
    """Decode the three members of a directory into an :class:`InstanceData`.

    Raises ``ValueError`` if the directory does not hold exactly one query, if a corpus id repeats,
    or if a positive is not in the corpus (none of these occurred in the pool check; a silent
    repair would change ranks).
    """
    qrows = [json.loads(x) for x in pc.split_rows(queries.decode("utf-8"))]
    if len(qrows) != 1:
        raise ValueError(f"{name}: {len(qrows)} queries")
    ids: list[str] = []
    texts: list[str] = []
    for line in pc.split_rows(corpus.decode("utf-8")):
        row = json.loads(line)
        fid = str(row.get("_id"))
        ids.append(fid)
        texts.append(code_text(fid, str(row.get("text") or ""), form))
    if len(set(ids)) != len(ids):
        raise ValueError(f"{name}: repeated corpus ids")
    pos = [i for i, s in pc.parse_qrels(qrels.decode("utf-8")) if s > 0]
    known = set(ids)
    missing = [p for p in pos if p not in known]
    if missing:
        raise ValueError(f"{name}: {len(missing)} positives not in the corpus")
    return InstanceData(
        dir=name,
        query=str(qrows[0].get("text") or ""),
        ids=ids,
        texts=texts,
        positives=sorted(set(pos)),
        corpus_bytes=len(corpus),
    )


def http_fetch(url: str, first: int, last: int) -> bytes:
    """One HTTP range request with retries (network errors are retried, then raised)."""
    for attempt in range(6):
        try:
            req = urllib.request.Request(url, headers={"Range": f"bytes={first}-{last}"})
            with urllib.request.urlopen(req, timeout=180) as resp:
                data: bytes = resp.read()
                return data
        except OSError:
            if attempt == 5:
                raise
            time.sleep(2**attempt)
    raise RuntimeError("unreachable")


def fetch_instance(
    url: str, members: Mapping[str, Mapping[str, Any]], name: str, fetch: Fetch, form: str = "code"
) -> InstanceData:
    """Read one directory's corpus, query and qrels by range requests and parse them.

    ``members`` maps ``corpus``/``queries``/``qrels`` to zip member records (``offset``,
    ``compressed``, ``uncompressed``, ``method``) as :func:`pool_check.pool_instances` returns them.
    """
    blobs: dict[str, bytes] = {}
    small = [members["queries"], members["qrels"]]
    first, last = pc.span_for(small)
    blob = fetch(url, first, last)
    for kind in ("queries", "qrels"):
        m = members[kind]
        blobs[kind] = pc.decode_member(blob, int(m["offset"]) - first, m)
    c = members["corpus"]
    first, last = pc.span_for([c])
    blobs["corpus"] = pc.decode_member(fetch(url, first, last), 0, c)
    return parse_instance(name, blobs["corpus"], blobs["queries"], blobs["qrels"], form)


def prefetch(
    names: Sequence[str],
    load: Callable[[str], InstanceData],
    ahead: int = 4,
) -> Iterator[tuple[str, InstanceData | None, str | None]]:
    """Yield ``(name, data, error)`` in order while up to ``ahead`` later names are being fetched.

    Why: the GPU stage should not wait on the network; fetching runs in threads ahead of encoding.
    """
    with ThreadPoolExecutor(max_workers=max(1, ahead)) as ex:
        futs: dict[int, Future[InstanceData]] = {}
        for i, n in enumerate(names[:ahead]):
            futs[i] = ex.submit(load, n)
        for i, n in enumerate(names):
            nxt = i + ahead
            if nxt < len(names):
                futs[nxt] = ex.submit(load, names[nxt])
            fut = futs.pop(i)
            try:
                yield n, fut.result(), None
            except (OSError, ValueError, KeyError) as exc:
                yield n, None, f"{type(exc).__name__}: {str(exc)[:200]}"


# --------------------------------------------------------------------------------------------
# ranks


def positive_ranks(
    ids: Sequence[str], scores: npt.ArrayLike, positives: Iterable[str]
) -> list[Record]:
    """Rank of every positive among the non-positive functions (and among all), 1-based.

    ``rank`` = 1 + number of non-positive functions with a strictly higher score;
    ``rank_all`` = 1 + number of other functions (positives included) with a strictly higher score;
    ``ties`` = non-positive functions with exactly the same score.
    """
    s = np.asarray(scores, dtype=np.float64).reshape(-1)
    if s.shape[0] != len(ids):
        raise ValueError("one score per function expected")
    index = {fid: i for i, fid in enumerate(ids)}
    pos = sorted(set(positives))
    is_pos = np.zeros(len(ids), dtype=bool)
    for p in pos:
        is_pos[index[p]] = True
    neg = np.sort(s[~is_pos])
    allv = np.sort(s)
    out: list[Record] = []
    for p in pos:
        v = s[index[p]]
        greater_neg = int(neg.shape[0] - np.searchsorted(neg, v, side="right"))
        equal_neg = int(
            np.searchsorted(neg, v, side="right") - np.searchsorted(neg, v, side="left")
        )
        greater_all = int(allv.shape[0] - np.searchsorted(allv, v, side="right"))
        out.append(
            {"positive": p, "rank": 1 + greater_neg, "rank_all": 1 + greater_all, "ties": equal_neg}
        )
    return out


def bm25_scores(texts: Sequence[str], query: str) -> Floats:
    """BM25 score of every text for the query (reference form of ``ril.retrieval.bm25_index``)."""
    from ril.retrieval.bm25_index import BM25Index, tokenize

    index = BM25Index(tokenize(t) for t in texts)
    out: Floats = np.asarray(index.scores(tokenize(query)), dtype=np.float64)
    return out


class Encoder(Protocol):
    """The part of :class:`ril.retrieval.dense_encoder.DenseEncoder` used here."""

    def encode_documents(self, texts: Sequence[str], batch_size: int = 32) -> Any: ...

    def encode_query(self, query: str) -> Any: ...


class RepoVectorCache:
    """Document vectors of one repository keyed by text hash; cleared when the repository changes.

    Why: directories of one repository are snapshots of the same code at different commits, so most
    function texts repeat; a text is encoded once per repository. Encoding is deterministic per text
    up to batch composition (float16 padding effects are below rank resolution in practice; the run
    log records the hit rate so the saving is measured, not assumed).
    """

    def __init__(self) -> None:
        self.repo: str | None = None
        self.vectors: dict[str, Any] = {}
        self.hits = 0
        self.misses = 0

    def scores(
        self, repo: str, texts: Sequence[str], qvec: Any, encoder: Encoder, batch_size: int
    ) -> tuple[Floats, int]:
        """Inner products of the query vector with every text; returns (scores, texts encoded)."""
        if repo != self.repo:
            self.repo = repo
            self.vectors = {}
        keys = [hashlib.sha1(t.encode("utf-8")).hexdigest() for t in texts]
        todo: dict[str, str] = {}
        for k, t in zip(keys, texts, strict=True):
            if k not in self.vectors and k not in todo:
                todo[k] = t
        if todo:
            mat = np.asarray(encoder.encode_documents(list(todo.values()), batch_size))
            for k, row in zip(todo, mat, strict=True):
                self.vectors[k] = row
        self.misses += len(todo)
        self.hits += len(keys) - len(todo)
        q = np.asarray(qvec, dtype=np.float32).reshape(-1)
        mat_all = np.stack([self.vectors[k] for k in keys]).astype(np.float32)
        out: Floats = (mat_all @ q).astype(np.float64)
        return out, len(todo)


# --------------------------------------------------------------------------------------------
# resumable output


_LOCK = threading.Lock()


def append_jsonl(path: str, row: Mapping[str, Any]) -> None:
    """Append one JSON row (thread-safe, flushed)."""
    with _LOCK:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def read_jsonl(path: str) -> list[Record]:
    """Rows of a JSON-lines file (missing file = no rows; a torn last line is ignored)."""
    out: list[Record] = []
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def done_dirs(path: str) -> set[str]:
    """Directories already written to a rank file (resumability)."""
    return {str(r["dir"]) for r in read_jsonl(path)}


def rank_record(
    teacher: str, data: InstanceData, scores: npt.ArrayLike, extra: Mapping[str, Any]
) -> Record:
    """One output row: ranks of every positive of a directory under one teacher, no text."""
    return {
        "dir": data.dir,
        "teacher": teacher,
        "functions": len(data.ids),
        "corpus_bytes": data.corpus_bytes,
        "ranks": positive_ranks(data.ids, scores, data.positives),
        **dict(extra),
    }


# --------------------------------------------------------------------------------------------
# derived feature table


FEATURE_COLUMNS: tuple[str, ...] = (
    "instance_id",
    "positive_key",
    "positive_id",
    "repo",
    "held_out",
    "stratum",
    "functions",
    "positives_in_instance",
)


def positive_key(fid: str) -> str:
    """Stable 16-hex key of a pool function id (SHA-1 prefix), recomputable from the pool.

    Why: the tracked table carries keys, not the dataset's path strings; the plain ids stay in an
    untracked copy and the key joins the two.
    """
    return hashlib.sha1(fid.encode("utf-8")).hexdigest()[:16]


def feature_rows(
    instances: Mapping[str, PoolInstance],
    rank_rows: Iterable[Mapping[str, Any]],
    teachers: Sequence[str],
) -> list[Record]:
    """One row per (instance, positive): ids, repository, held-out flag and the rank per teacher.

    Columns ``rank_<teacher>`` (non-positive competitors) and ``rank_all_<teacher>``; a teacher
    with no row for the instance leaves the cells empty. Ids and integers only, no text.
    """
    by: dict[tuple[str, str], Record] = {}
    funcs: dict[str, int] = {}
    for row in rank_rows:
        t = str(row["teacher"])
        if t not in teachers:
            continue
        d = str(row["dir"])
        funcs[d] = int(row["functions"])
        for r in row["ranks"]:
            cell = by.setdefault((d, str(r["positive"])), {})
            cell[f"rank_{t}"] = int(r["rank"])
            cell[f"rank_all_{t}"] = int(r["rank_all"])
    out: list[Record] = []
    npos: dict[str, int] = {}
    for d, _ in by:
        npos[d] = npos.get(d, 0) + 1
    for (d, p), cell in sorted(by.items()):
        inst = instances[d]
        row_out: Record = {
            "instance_id": d,
            "positive_key": positive_key(p),
            "positive_id": p,
            "repo": inst.repo,
            "held_out": int(inst.held_out),
            "stratum": inst.stratum,
            "functions": funcs[d],
            "positives_in_instance": npos[d],
        }
        for t in teachers:
            row_out[f"rank_{t}"] = cell.get(f"rank_{t}", "")
            row_out[f"rank_all_{t}"] = cell.get(f"rank_all_{t}", "")
        out.append(row_out)
    return out


def feature_columns(teachers: Sequence[str]) -> list[str]:
    """Column order of the feature table."""
    cols = list(FEATURE_COLUMNS)
    cols += [f"rank_{t}" for t in teachers]
    cols += [f"rank_all_{t}" for t in teachers]
    return cols


# --------------------------------------------------------------------------------------------
# cost estimate


def gpu_hours_estimate(
    total_texts: float, texts_per_second: float, dedup_ratio: float = 1.0, encoders: int = 1
) -> float:
    """GPU-hours to encode ``total_texts`` at a measured rate, after within-repository dedup.

    ``dedup_ratio`` = distinct texts / all texts (measured); queries are negligible beside the
    corpora (one per directory) and are not counted.
    """
    if texts_per_second <= 0:
        raise ValueError("texts_per_second must be positive")
    if not 0 < dedup_ratio <= 1:
        raise ValueError("dedup_ratio must be in (0, 1]")
    return encoders * total_texts * dedup_ratio / texts_per_second / 3600.0
