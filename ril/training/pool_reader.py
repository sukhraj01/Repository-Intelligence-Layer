"""Pool reader for retriever training: stream selected pool instances, filter, yield examples.

Implements the data entry of the RQ2 training stack (``docs/08_experimental_design.md``, "The four
supervision arms"; ``docs/04_data_and_ground_truth.md``, "Dataset assignment by stage", stage A).
The pool is ``gangiswag/train_data`` python minus the held-out list (``provisional: ADR-001``,
decision D22); one zip directory per pull request (layout in ``knowledge/datasets/sweloc.md``).

What it does, in order:

1. **Select** directory names from the zip listing: drop every directory whose repository is held
   out (list v2, core plus the Loc-Bench tier, aliases and the rename cache: decisions D1, D3; the
   same predicate as the pool-rank measurement), and, when a per-instance feature table is given
   (the E-POOL-RANKS table, ``results/tables/x3_pool_ranks_features.csv``), keep only the
   directories it covers. Every drop is counted, never silent (:class:`ReaderStats`).
2. **Stream** each kept directory by HTTP range requests at its central-directory offsets (the X3
   access code: ``ril.training.pool_ranks.fetch_instance``), fetched ahead in threads.
3. **Yield** a :class:`PoolExample`: the issue text, the positive functions (qrels score > 0), the
   negative candidates (every other function of the snapshot), the repository and the ids.

Text never leaves the machine that reads it: examples live in memory, or in an untracked cache file
on the cluster (:func:`write_cache`), as the X2 text stores do. Which text form the encoder sees is
``provisional: ADR-002`` (default ``code``: the id line stripped, as the published mining script).

Kept compatible with Python 3.10 (the cluster's compute nodes).
"""

from __future__ import annotations

import csv
import gzip
import io
import json
import os
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from typing import Any

from ril.training import pool_check as pc
from ril.training import pool_ranks as pr

POOL_READER_VERSION = "pool-reader/v1"
PROVISIONAL = "provisional: ADR-001, ADR-002"
POOL_PREFIX = "train/python/"
Record = dict[str, Any]


@dataclass(frozen=True)
class PoolExample:
    """One training instance (a pull request): query, positives, negative candidates, ids.

    ``positive_ids`` and ``candidate_ids`` are the pool's function ids (``path.py/Class/name``);
    ``candidate_ids`` holds every function of the snapshot that is not a positive.
    """

    instance_id: str
    repo: str
    pr: int
    query: str
    positive_ids: tuple[str, ...]
    positive_texts: tuple[str, ...]
    candidate_ids: tuple[str, ...]
    candidate_texts: tuple[str, ...]
    masked_ids: tuple[str, ...] = ()
    """Functions that are neither positive nor negative for this example (positives a filter
    dropped); they never enter its loss, also not as another example's in-batch document."""

    def __post_init__(self) -> None:
        if not self.positive_ids:
            raise ValueError(f"{self.instance_id}: no positive")
        if len(self.positive_ids) != len(self.positive_texts):
            raise ValueError(f"{self.instance_id}: positive ids and texts differ in length")
        if len(self.candidate_ids) != len(self.candidate_texts):
            raise ValueError(f"{self.instance_id}: candidate ids and texts differ in length")
        if set(self.positive_ids) & set(self.candidate_ids):
            raise ValueError(f"{self.instance_id}: a positive is also a candidate")

    @property
    def ids(self) -> tuple[str, ...]:
        """Every function id of the snapshot, positives first."""
        return self.positive_ids + self.candidate_ids


def example_from_data(data: pr.InstanceData) -> PoolExample:
    """Build an example from a parsed directory (positives in the qrels order, sorted)."""
    split = pc.split_instance_dir(data.dir)
    if split is None:
        raise ValueError(f"unreadable instance directory {data.dir!r}")
    repo, prn = split
    pos = set(data.positives)
    text_of = dict(zip(data.ids, data.texts, strict=True))
    cand = [(i, t) for i, t in zip(data.ids, data.texts, strict=True) if i not in pos]
    return PoolExample(
        instance_id=data.dir,
        repo=repo,
        pr=prn,
        query=data.query,
        positive_ids=tuple(data.positives),
        positive_texts=tuple(text_of[p] for p in data.positives),
        candidate_ids=tuple(i for i, _ in cand),
        candidate_texts=tuple(t for _, t in cand),
    )


# --------------------------------------------------------------------------- feature table


@dataclass
class FeatureTable:
    """Per-positive teacher ranks of the E-POOL-RANKS feature table (ids and integers only).

    The tracked table keys positives by ``positive_key`` (SHA-1 prefix of the pool id,
    :func:`ril.training.pool_ranks.positive_key`); the untracked copy also carries the plain
    ``positive_id``. Lookups go through the key, so both forms behave the same.
    """

    teachers: tuple[str, ...]
    ranks: dict[tuple[str, str], dict[str, int]] = field(default_factory=dict)
    positives_of: dict[str, set[str]] = field(default_factory=dict)

    def instances(self) -> set[str]:
        """Directories the table covers."""
        return set(self.positives_of)

    def rank(self, instance_id: str, positive_id: str, teacher: str) -> int | None:
        """Rank of one positive under one teacher (``rank`` column: non-positive competitors)."""
        cell = self.ranks.get((instance_id, pr.positive_key(positive_id)))
        if cell is None:
            return None
        return cell.get(teacher)

    def covers(self, instance_id: str, positive_ids: Iterable[str]) -> bool:
        """Whether every positive of the instance has a row (a key mismatch: a different pool)."""
        keys = self.positives_of.get(instance_id)
        if keys is None:
            return False
        return all(pr.positive_key(p) in keys for p in positive_ids)


def load_feature_table(path: str) -> FeatureTable:
    """Read a feature table CSV (tracked keys-only form or untracked form with plain ids)."""
    with open(path, encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        cols = reader.fieldnames or []
        teachers = tuple(
            c[len("rank_") :]
            for c in cols
            if c.startswith("rank_") and not c.startswith("rank_all_")
        )
        table = FeatureTable(teachers=teachers)
        for row in reader:
            inst = row["instance_id"]
            key = row.get("positive_key") or pr.positive_key(row["positive_id"])
            cell: dict[str, int] = {}
            for t in teachers:
                v = row.get(f"rank_{t}", "")
                if v not in ("", None):
                    cell[t] = int(v)
            table.ranks[(inst, key)] = cell
            table.positives_of.setdefault(inst, set()).add(key)
    return table


# --------------------------------------------------------------------------- selection


@dataclass
class ReaderStats:
    """Survival counts of the selection and the stream (recorded in every run log)."""

    listed: int = 0
    held_out_dropped: int = 0
    not_in_table_dropped: int = 0
    selected: int = 0
    fetch_errors: int = 0
    positives_not_in_table: int = 0
    no_positive: int = 0
    yielded: int = 0
    errors: list[Record] = field(default_factory=list)

    def to_dict(self) -> Record:
        """JSON form (the error list is cut to its first 20 rows)."""
        d = asdict(self)
        d["errors"] = d["errors"][:20]
        return d


def select_instances(
    names: Iterable[str],
    *,
    is_held_out: Callable[[str], bool],
    table: FeatureTable | None = None,
    stats: ReaderStats | None = None,
) -> list[str]:
    """Directory names kept by the held-out list and (if given) the feature table, sorted.

    An unreadable directory name raises ``ValueError``: a silent drop would change the pool.
    """
    st = stats if stats is not None else ReaderStats()
    covered = table.instances() if table is not None else None
    kept: list[str] = []
    for name in sorted(set(names)):
        st.listed += 1
        split = pc.split_instance_dir(name)
        if split is None:
            raise ValueError(f"unreadable instance directory {name!r}")
        if is_held_out(split[0]):
            st.held_out_dropped += 1
            continue
        if covered is not None and name not in covered:
            st.not_in_table_dropped += 1
            continue
        kept.append(name)
    st.selected = len(kept)
    return kept


def load_listing(
    listing_path: str, prefix: str = POOL_PREFIX
) -> tuple[str, dict[str, dict[str, Any]]]:
    """``(archive url, {directory: {corpus, queries, qrels}})`` from a zip listing with offsets."""
    with open(listing_path, encoding="utf-8") as handle:
        z = json.load(handle)
    groups = pr.group_members(z["members"], prefix)
    return str(z["url"]), {k: dict(v) for k, v in groups.items()}


def read_pool(
    url: str,
    members: Mapping[str, Mapping[str, Mapping[str, Any]]],
    names: Sequence[str],
    *,
    fetch: pr.Fetch = pr.http_fetch,
    form: str = "code",
    ahead: int = 4,
    table: FeatureTable | None = None,
    stats: ReaderStats | None = None,
) -> Iterator[PoolExample]:
    """Stream the named directories by range request and yield one example per directory.

    A directory that cannot be fetched or parsed is counted and logged, not yielded. When a feature
    table is given, a directory whose positives do not all have a row is counted
    (``positives_not_in_table``) and not yielded: its teacher ranks would be missing.
    """
    st = stats if stats is not None else ReaderStats()
    for name, data, err in pr.prefetch(
        list(names), lambda d: pr.fetch_instance(url, members[d], d, fetch, form), ahead
    ):
        if data is None:
            st.fetch_errors += 1
            st.errors.append({"dir": name, "error": err})
            continue
        if not data.positives:
            st.no_positive += 1
            continue
        if table is not None and not table.covers(name, data.positives):
            st.positives_not_in_table += 1
            continue
        st.yielded += 1
        yield example_from_data(data)


# --------------------------------------------------------------------------- local cache


def write_cache(path: str, examples: Iterable[PoolExample]) -> int:
    """Write examples to a gzip JSON-lines cache (cluster only, holds text, never tracked)."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    n = 0
    tmp = f"{path}.tmp"
    # a fixed header time and no file name: the same examples give the same bytes on any run
    with (
        open(tmp, "wb") as raw,
        gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz,
        io.TextIOWrapper(gz, encoding="utf-8") as handle,
    ):
        for ex in examples:
            handle.write(json.dumps(asdict(ex), sort_keys=True) + "\n")
            n += 1
    os.replace(tmp, path)
    return n


def read_cache(path: str) -> list[PoolExample]:
    """Examples back from :func:`write_cache`, in file order."""
    return _read_cache(path, None)


def read_cache_shared(path: str) -> list[PoolExample]:
    """The same examples as :func:`read_cache`, with one copy of each distinct id and text.

    A repository's snapshot repeats most of its functions from one pull request to the next, so
    the plain reader holds the same text many times. Every value compares equal to the plain
    reader's; only the number of string objects in memory differs.
    """
    return _read_cache(path, {})


def _read_cache(path: str, pool: dict[str, str] | None) -> list[PoolExample]:
    def one(value: str) -> str:
        if pool is None:
            return value
        return pool.setdefault(value, value)

    out: list[PoolExample] = []
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            r = json.loads(line)
            out.append(
                PoolExample(
                    instance_id=str(r["instance_id"]),
                    repo=str(r["repo"]),
                    pr=int(r["pr"]),
                    query=str(r["query"]),
                    positive_ids=tuple(one(x) for x in r["positive_ids"]),
                    positive_texts=tuple(one(x) for x in r["positive_texts"]),
                    candidate_ids=tuple(one(x) for x in r["candidate_ids"]),
                    candidate_texts=tuple(one(x) for x in r["candidate_texts"]),
                    masked_ids=tuple(one(x) for x in r.get("masked_ids", ())),
                )
            )
    return out
