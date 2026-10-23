"""Dense scores of code units and benchmark chunks for the dense and fusion measurements (X2).

Exploratory. Implements the data half of ``docs/EXPERIMENTS.md`` E-DENSE-FUSION and supersedes the
CPU-only design of ``ril.evaluation.e6_dense`` (never run; one CPU job was estimated at about 30
hours). The work is split so that no GPU is held while the CPU prepares data:

1. ``prepare_units`` / ``prepare_chunks`` / ``prepare_queries`` (CPU job): check out each cached
   instance's base commit, parse it once per class-unit source form (Q28, ``provisional: ADR-013``),
   and write per instance the hash of every unit's text in index order (sorted unit id, the order
   of the pilot-E3 cache); distinct texts go to one text store per repository (unit texts) or per
   repository (chunk texts of the CORE-Bench folders); queries to one store per folder and level.
2. ``encode_stores`` (GPU job): encode every distinct text of a store once per encoder and cut,
   in resumable pieces; record token counts before the cut so the share of cut texts is known.
3. ``score_units`` / ``score_chunks`` (CPU job): cosine of each unit (chunk) with the query of each
   level, written per instance in the format the pilot-E3 evaluation reads (``dense_<level>``), and
   per chunk folder the ranks of the positives under BM25, dense and RRF of the two.

Stores on the cluster hold text (repository code and benchmark text, never tracked); everything
that leaves the cluster holds scores, ranks, hashes and counts only.

Kept compatible with Python 3.10.
"""

from __future__ import annotations

import glob
import hashlib
import json
import os
import time
from collections.abc import Iterable, Sequence
from typing import Any

import numpy as np

from ril.evaluation.chunk_unit_pilot import checkout_commit, hardware
from ril.evaluation.core_bench import read_folder
from ril.evaluation.e1_run import folder_path, load_config, params_of
from ril.evaluation.e3_prepare import read_cache
from ril.parsing.repository_parser import CLASS_SOURCE_FORMS, ParseOptions, parse_repository
from ril.retrieval.bm25_index import BM25Index, tokenize

X2_DENSE_VERSION = "x2-dense/v1"
PIECE = 4096
"""Texts per resumable encoding piece."""
RRF_KS: tuple[int, ...] = (1, 5, 10, 20, 40, 60, 100, 200)
"""RRF constants written for the chunk-level records (k is tuned on dev only)."""
Record = dict[str, Any]


def text_hash(text: str) -> str:
    """SHA-1 hex digest of a text (store key)."""
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def query_key(level: str, dataset: str, folder: str, query_id: str) -> str:
    """Key of one query in the query store."""
    return f"{level}|{dataset}|{folder}|{query_id}"


# --------------------------------------------------------------------------- text stores


def read_store(paths: Iterable[str]) -> dict[str, str]:
    """``{hash: text}`` from one or more JSON-lines store files (later duplicates ignored)."""
    out: dict[str, str] = {}
    for path in paths:
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    row = json.loads(line)
                    out.setdefault(str(row["h"]), str(row["t"]))
    return out


def append_store(path: str, texts: Iterable[str], seen: set[str]) -> int:
    """Append texts whose hash is not in ``seen`` (updated in place); return how many."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    n = 0
    with open(path, "a", encoding="utf-8") as handle:
        for t in texts:
            h = text_hash(t)
            if h in seen:
                continue
            seen.add(h)
            handle.write(json.dumps({"h": h, "t": t}) + "\n")
            n += 1
    return n


def _seen_of(path: str) -> set[str]:
    return set(read_store([path])) if os.path.exists(path) else set()


# --------------------------------------------------------------------------- prepare (CPU)


def _specs(e1_cfg: Record, roles: set[str], *, units: bool) -> dict[tuple[str, str], Record]:
    return {
        (s["dataset"], s["folder"]): s
        for s in e1_cfg["folders"]
        if s["role"] in roles and (s.get("units") or not units)
    }


def prepare_units(
    e1_config_path: str,
    roles: set[str],
    meta: dict[str, Record],
    repo_cache: str,
    cache_dir: str,
    work_dir: str,
    out_dir: str,
    *,
    shard: tuple[int, int] = (0, 1),
    forms: Sequence[str] = CLASS_SOURCE_FORMS,
) -> Record:
    """Unit-text hashes per instance (one array per class-source form) and the text stores.

    Resumable per instance; ``shard = (i, k)`` takes every k-th cached instance from i.
    """
    e1_cfg = load_config(e1_config_path)
    specs = _specs(e1_cfg, roles, units=True)
    names = sorted(glob.glob(os.path.join(cache_dir, "*.npz")))
    failures: list[Record] = []
    done = 0
    seen: dict[str, set[str]] = {}
    for ordinal, path in enumerate(names):
        if ordinal % shard[1] != shard[0]:
            continue
        _, cmeta = read_cache(path)
        key = (cmeta["dataset"], cmeta["folder"])
        if key not in specs:
            continue
        out = os.path.join(out_dir, "units", os.path.basename(path))
        if os.path.exists(out):
            continue
        instance = cmeta["instance"]
        info = meta.get(instance)
        if info is None:
            failures.append({"instance": instance, "reason": "no_metadata"})
            continue
        repo_dir = specs[key]["repo"].replace("/", "__")
        work = os.path.join(work_dir, f"{repo_dir}__s{shard[0]}")
        status = checkout_commit(
            os.path.join(repo_cache, f"{repo_dir}.git"), work, info["base_commit"]
        )
        if status != "ok":
            failures.append({"instance": instance, "reason": status})
            continue
        t0 = time.perf_counter()
        arrays: dict[str, Any] = {}
        ids_ref: list[str] | None = None
        store = os.path.join(out_dir, "texts_units", f"{repo_dir}.s{shard[0]}.jsonl")
        if store not in seen:
            seen[store] = _seen_of(store)
        for form in forms:
            parsed = parse_repository(work, specs[key]["repo"], options=ParseOptions(form))
            units = sorted(parsed.units, key=lambda u: u.id)
            ids = [u.id for u in units]
            if ids_ref is None:
                ids_ref = ids
            elif ids != ids_ref:
                raise RuntimeError(f"{instance}: unit ids differ between class-source forms")
            if len(units) != int(cmeta["units"]):
                raise RuntimeError(f"{instance}: {len(units)} units, cache has {cmeta['units']}")
            texts = [u.source for u in units]
            append_store(store, texts, seen[store])
            arrays[f"hashes_{form}"] = np.asarray([text_hash(t) for t in texts], dtype="U40")
        meta_out = {
            "version": X2_DENSE_VERSION,
            "instance": instance,
            "repo_dir": repo_dir,
            "role": cmeta["role"],
            "dataset": cmeta["dataset"],
            "folder": cmeta["folder"],
            "levels": cmeta["levels"],
            "units": int(cmeta["units"]),
            "seconds": round(time.perf_counter() - t0, 2),
        }
        os.makedirs(os.path.dirname(out), exist_ok=True)
        tmp = f"{out}.tmp.npz"
        np.savez_compressed(tmp, meta=np.asarray(json.dumps(meta_out)), **arrays)
        os.replace(tmp, out)
        done += 1
    return {"prepared": done, "failures": failures, "shard": list(shard), "hardware": hardware()}


def prepare_queries(e1_config_path: str, roles: set[str], data_root: str, out_dir: str) -> Record:
    """Query texts of every folder and level of the roles, one store file per folder and level."""
    e1_cfg = load_config(e1_config_path)
    counts: dict[str, int] = {}
    for spec in e1_cfg["folders"]:
        if spec["role"] not in roles:
            continue
        for level in spec["levels"]:
            qpath = os.path.join(folder_path(data_root, level, spec), "queries.jsonl")
            if not os.path.exists(qpath):
                continue
            name = f"{level}__{spec['dataset']}__{spec['folder']}"
            out = os.path.join(out_dir, "queries", f"{name}.jsonl")
            os.makedirs(os.path.dirname(out), exist_ok=True)
            n = 0
            with open(qpath, encoding="utf-8") as src, open(f"{out}.tmp", "w") as dst:
                for line in src:
                    if not line.strip():
                        continue
                    row = json.loads(line)
                    k = query_key(level, spec["dataset"], spec["folder"], str(row["_id"]))
                    dst.write(json.dumps({"h": k, "t": str(row["text"])}) + "\n")
                    n += 1
            os.replace(f"{out}.tmp", out)
            counts[name] = n
    return {"queries": counts}


def issue_word_counts(e1_config_path: str, data_root: str, level: str = "L2") -> list[int]:
    """Word counts of the development issues of one level (numbers only; latency query set)."""
    e1_cfg = load_config(e1_config_path)
    out: list[int] = []
    for spec in e1_cfg["folders"]:
        if spec["role"] != "dev" or level not in spec["levels"]:
            continue
        qpath = os.path.join(folder_path(data_root, level, spec), "queries.jsonl")
        with open(qpath, encoding="utf-8") as handle:
            out += [len(str(json.loads(x)["text"]).split()) for x in handle if x.strip()]
    return sorted(out)


def dev_scale(cache_dir: str) -> Record:
    """Median unit count of the cached development snapshots (the "dev scale" of search latency)."""
    counts = []
    for path in sorted(glob.glob(os.path.join(cache_dir, "*.npz"))):
        _, meta = read_cache(path)
        if meta["role"] == "dev":
            counts.append(int(meta["units"]))
    if not counts:
        raise ValueError("no development instances in the cache")
    return {"units": int(np.median(counts)), "snapshots": len(counts), "max": max(counts)}


def prepare_chunks(e1_config_path: str, roles: set[str], data_root: str, out_dir: str) -> Record:
    """Distinct chunk texts of every folder and level of the roles, one store per repository.

    Only folders whose repository also has unit records (``units: true``), so that the chunk-level
    and unit-level numbers describe the same repositories."""
    e1_cfg = load_config(e1_config_path)
    counts: dict[str, Record] = {}
    seen: dict[str, set[str]] = {}
    for spec in e1_cfg["folders"]:
        if spec["role"] not in roles or not spec.get("units"):
            continue
        repo_dir = spec["repo"].replace("/", "__")
        store = os.path.join(out_dir, "texts_chunks", f"{repo_dir}.jsonl")
        if store not in seen:
            seen[store] = _seen_of(store)
        for level in spec["levels"]:
            path = folder_path(data_root, level, spec)
            if not os.path.isdir(path):
                continue
            folder = read_folder(path)
            new = append_store(store, folder.corpus_texts, seen[store])
            counts[f"{level}__{spec['dataset']}__{spec['folder']}"] = {
                "chunks": len(folder.corpus_texts),
                "new_distinct": new,
            }
    return {"chunks": counts}


# --------------------------------------------------------------------------- encode (GPU)


def _piece_paths(out_dir: str, store_name: str) -> str:
    return os.path.join(out_dir, "parts", store_name)


def encode_store(
    encoder: Any,
    store_paths: Sequence[str],
    store_name: str,
    out_dir: str,
    *,
    batch_size: int,
    piece: int = PIECE,
    is_query: bool = False,
    reuse: tuple[str, int] | None = None,
) -> Record:
    """Encode every distinct text of a store into ``<out_dir>/<store_name>.npz``; resumable.

    Texts are ordered by character length (then hash) and encoded in pieces of ``piece``; a
    finished piece is a file and is skipped on a rerun; pieces are removed once merged. The merged
    file holds the hashes (sorted), float16 vectors, and token counts before the cut.

    ``reuse = (merged store at a shorter cut, that cut)``: a text that the shorter cut did not
    shorten gets the same input at this cut, so its vector is taken over instead of re-encoded
    (only texts longer than the shorter cut are encoded again).
    """
    final = os.path.join(out_dir, f"{store_name}.npz")
    if os.path.exists(final):
        return {"store": store_name, "reused": True}
    texts = read_store(store_paths)
    pdir = _piece_paths(out_dir, store_name)
    os.makedirs(pdir, exist_ok=True)
    taken = 0
    skip: set[str] = set()
    if reuse is not None and os.path.exists(reuse[0]):
        with np.load(reuse[0], allow_pickle=False) as d:
            keep = d["ntok"] <= reuse[1]
            rh = [str(h) for h in d["hashes"][keep]]
            skip = set(rh)
            rpath = os.path.join(pdir, "reused.npz")
            if not os.path.exists(rpath):
                np.savez(
                    f"{rpath}.tmp.npz",
                    hashes=np.asarray(rh, dtype=str),
                    vectors=d["vectors"][keep],
                    ntok=d["ntok"][keep],
                )
                os.replace(f"{rpath}.tmp.npz", rpath)
            taken = len(rh)
    hashes = sorted((h for h in texts if h not in skip), key=lambda h: (len(texts[h]), h))
    t0 = time.perf_counter()
    encoded = 0
    for start in range(0, len(hashes), piece):
        ppath = os.path.join(pdir, f"{start:09d}.npz")
        if os.path.exists(ppath):
            continue
        hs = hashes[start : start + piece]
        docs = [texts[h] for h in hs]
        ntok = encoder.token_lengths(
            [encoder.spec.query_text(d) for d in docs] if is_query else docs
        )
        vecs = (
            encoder.encode_queries(docs, batch_size)
            if is_query
            else (encoder.encode_documents(docs, batch_size))
        )
        tmp = f"{ppath}.tmp.npz"
        np.savez(
            tmp,
            hashes=np.asarray(hs, dtype=str),
            vectors=vecs.astype(np.float16),
            ntok=np.asarray(ntok, dtype=np.int32),
        )
        os.replace(tmp, ppath)
        encoded += len(hs)
    seconds = time.perf_counter() - t0
    parts = sorted(glob.glob(os.path.join(pdir, "*.npz")))
    hs_all: list[str] = []
    vecs_all: list[Any] = []
    ntok_all: list[Any] = []
    for p in parts:
        with np.load(p, allow_pickle=False) as d:
            hs_all += [str(x) for x in d["hashes"]]
            vecs_all.append(d["vectors"])
            ntok_all.append(d["ntok"])
    order = np.argsort(np.asarray(hs_all, dtype=str), kind="stable")
    mat = np.concatenate(vecs_all)[order] if vecs_all else np.zeros((0, 1), np.float16)
    ntok = np.concatenate(ntok_all)[order] if ntok_all else np.zeros(0, np.int32)
    if len(set(hs_all)) != len(texts):
        raise RuntimeError(f"{store_name}: {len(set(hs_all))} vectors for {len(texts)} texts")
    tmp = f"{final}.tmp.npz"
    np.savez(tmp, hashes=np.asarray(hs_all, dtype=str)[order], vectors=mat, ntok=ntok)
    os.replace(tmp, final)
    for p in parts:
        os.remove(p)
    cut = int((ntok > encoder.spec.max_tokens).sum())
    return {
        "store": store_name,
        "texts": len(texts),
        "taken_from_shorter_cut": taken,
        "encoded_now": encoded,
        "seconds_now": round(seconds, 2),
        "texts_per_s_now": round(encoded / seconds, 2) if encoded and seconds > 0 else None,
        "tokens_fed": int(np.minimum(ntok, encoder.spec.max_tokens).sum()),
        "cut_at_max_tokens": cut,
        "share_cut": round(cut / max(1, len(ntok)), 4),
    }


class VectorStore:
    """Encoded vectors of one or more stores, looked up by text hash."""

    def __init__(self, paths: Iterable[str]) -> None:
        self.index: dict[str, tuple[int, int]] = {}
        self.mats: list[np.ndarray[Any, Any]] = []
        self.ntok: list[np.ndarray[Any, Any]] = []
        for p in paths:
            with np.load(p, allow_pickle=False) as d:
                k = len(self.mats)
                self.mats.append(d["vectors"].astype(np.float32))
                self.ntok.append(d["ntok"])
                for i, h in enumerate(d["hashes"]):
                    self.index.setdefault(str(h), (k, i))

    def matrix(self, hashes: Sequence[str]) -> np.ndarray[Any, Any]:
        """Rows for the hashes, in order (float32)."""
        rows = [self.index[h] for h in hashes]
        if not rows:
            return np.zeros((0, self.mats[0].shape[1] if self.mats else 1), np.float32)
        return np.stack([self.mats[k][i] for k, i in rows])

    def tokens(self, hashes: Sequence[str]) -> np.ndarray[Any, Any]:
        """Token counts before the cut, in order."""
        return np.asarray([self.ntok[k][i] for k, i in (self.index[h] for h in hashes)])


# --------------------------------------------------------------------------- score (CPU)


def score_units(
    prep_dir: str,
    enc_dir: str,
    out_dir: str,
    max_tokens: int,
    *,
    roles: set[str],
    forms: Sequence[str] = CLASS_SOURCE_FORMS,
) -> Record:
    """Per-instance dense scores (``dense_<level>`` for the ``full`` form, ``dense_<level>__<form>``
    for the other forms) in the pilot-E3 layout; resumable per instance."""
    queries = VectorStore(sorted(glob.glob(os.path.join(enc_dir, "queries__*.npz"))))
    stores: dict[str, VectorStore] = {}
    done = 0
    missing: list[str] = []
    for path in sorted(glob.glob(os.path.join(prep_dir, "units", "*.npz"))):
        out = os.path.join(out_dir, os.path.basename(path))
        if os.path.exists(out):
            continue
        with np.load(path, allow_pickle=False) as d:
            meta = json.loads(str(d["meta"]))
            hashes = {f: [str(x) for x in d[f"hashes_{f}"]] for f in forms}
        if meta["role"] not in roles:
            continue
        sp = os.path.join(enc_dir, f"units__{meta['repo_dir']}.npz")
        if not os.path.exists(sp):
            missing.append(meta["instance"])
            continue
        if meta["repo_dir"] not in stores:
            stores = {meta["repo_dir"]: VectorStore([sp])}
        vs = stores[meta["repo_dir"]]
        arrays: dict[str, Any] = {}
        mats = {f: vs.matrix(hashes[f]) for f in forms}
        for level in meta["levels"]:
            qk = query_key(level, meta["dataset"], meta["folder"], meta["instance"])
            if qk not in queries.index:
                continue
            q = queries.matrix([qk])[0]
            for f in forms:
                key = f"dense_{level}" if f == "full" else f"dense_{level}__{f}"
                arrays[key] = (mats[f] @ q).astype(np.float32)
        ntok = vs.tokens(hashes["full"])
        info = {
            "version": X2_DENSE_VERSION,
            "units": meta["units"],
            "units_cut_at_max_tokens": int((ntok > max_tokens).sum()),
            "max_tokens": max_tokens,
        }
        os.makedirs(out_dir, exist_ok=True)
        tmp = f"{out}.tmp.npz"
        np.savez_compressed(tmp, meta=np.asarray(json.dumps(info)), **arrays)
        os.replace(tmp, out)
        done += 1
    return {"scored": done, "missing_store": missing}


def rank_among(scores: np.ndarray[Any, Any], cand: np.ndarray[Any, Any]) -> np.ndarray[Any, Any]:
    """1-based rank of every candidate among the candidates (ties by lower corpus index)."""
    s = scores[cand]
    order = np.lexsort((cand, -s))
    ranks = np.empty(len(cand), dtype=np.int64)
    ranks[order] = np.arange(1, len(cand) + 1)
    return ranks


def score_chunks(
    e1_config_path: str,
    roles: set[str],
    data_root: str,
    enc_dirs: dict[str, str],
    out_dir: str,
    *,
    ks: Sequence[int] = RRF_KS,
) -> Record:
    """Ranks of every positive chunk under BM25, each dense variant and RRF(BM25, dense) per k.

    Filter-first reading: each query is ranked among its own candidate list (the snapshot of its
    base commit), not the whole folder. One JSON file per (level, folder); resumable.
    """
    e1_cfg = load_config(e1_config_path)
    params = params_of(e1_cfg)
    done = 0
    for spec in e1_cfg["folders"]:
        if spec["role"] not in roles or not spec.get("units"):
            continue
        repo_dir = spec["repo"].replace("/", "__")
        for level in spec["levels"]:
            path = folder_path(data_root, level, spec)
            name = f"{level}__{spec['dataset']}__{spec['folder']}"
            out = os.path.join(out_dir, f"{name}.json")
            if os.path.exists(out) or not os.path.isdir(path):
                continue
            t0 = time.perf_counter()
            folder = read_folder(path)
            hashes = [text_hash(t) for t in folder.corpus_texts]
            index = BM25Index((tokenize("\n" + t) for t in folder.corpus_texts), params)
            pos_of = {cid: i for i, cid in enumerate(folder.corpus_ids)}
            dense: dict[str, tuple[np.ndarray[Any, Any], VectorStore]] = {}
            for vname, edir in enc_dirs.items():
                vs = VectorStore([os.path.join(edir, f"chunks__{repo_dir}.npz")])
                qs = VectorStore(sorted(glob.glob(os.path.join(edir, "queries__*.npz"))))
                dense[vname] = (vs.matrix(hashes), qs)
            records: list[Record] = []
            n = len(folder.corpus_ids)
            for q in folder.queries:
                cand = (
                    np.arange(n, dtype=np.int64)
                    if q.candidates is None
                    else np.fromiter(
                        sorted({pos_of[c] for c in q.candidates if c in pos_of}), dtype=np.int64
                    )
                )
                where = {int(c): i for i, c in enumerate(cand)}
                pos = sorted(pos_of[c] for c in folder.qrels[q.query_id] if c in pos_of)
                pos = [p for p in pos if p in where]
                rb = rank_among(index.scores(tokenize(q.text)), cand)
                rec: Record = {
                    "query_id": q.query_id,
                    "n_candidates": int(len(cand)),
                    "n_positives": len(folder.qrels[q.query_id]),
                    "n_positives_in_candidates": len(pos),
                    "bm25": [int(rb[where[p]]) for p in pos],
                }
                for vname, (mat, qs) in dense.items():
                    qk = query_key(level, spec["dataset"], spec["folder"], q.query_id)
                    qv = qs.matrix([qk])[0]
                    rd = rank_among(mat @ qv, cand)
                    rec[vname] = [int(rd[where[p]]) for p in pos]
                    for k in ks:
                        fused = 1.0 / (k + rb) + 1.0 / (k + rd)
                        # rank among candidates by fused score, ties by BM25 rank
                        order = np.lexsort((rb, -fused))
                        rr = np.empty(len(cand), dtype=np.int64)
                        rr[order] = np.arange(1, len(cand) + 1)
                        rec[f"rrf{k}__{vname}"] = [int(rr[where[p]]) for p in pos]
                records.append(rec)
            os.makedirs(out_dir, exist_ok=True)
            with open(f"{out}.tmp", "w", encoding="utf-8") as handle:
                json.dump(
                    {
                        "version": X2_DENSE_VERSION,
                        "level": level,
                        "dataset": spec["dataset"],
                        "folder": spec["folder"],
                        "role": spec["role"],
                        "repo": spec["repo"],
                        "corpus_chunks": n,
                        "variants": sorted(enc_dirs),
                        "rrf_ks": list(ks),
                        "seconds": round(time.perf_counter() - t0, 2),
                        "hardware": hardware(),
                        "records": records,
                    },
                    handle,
                )
            os.replace(f"{out}.tmp", out)
            done += 1
    return {"folders_scored": done}
