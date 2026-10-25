"""Dense scores of code units with CodeRankEmbed on CPU (pilot E6, exploratory).

Implements the dense half of ``docs/EXPERIMENTS.md`` E-GRAPH-FUSION. For each instance of the
configured repositories the base commit is checked out, the units are parsed (same parser and
index order as ``ril.evaluation.e3_prepare``), each unit's source is encoded, and the cosine
similarity of every unit with the issue text of each level is stored. Unit texts repeat across the
snapshots of one repository, so a store keyed by the hash of the text encodes each distinct text
once.

Model and settings are those of the released encoder, nothing substituted:
``CodeRankEmbed`` (MIT licence), the model's query prefix, documents
without prefix, L2-normalised embeddings, sequences cut at ``MAX_TOKENS`` tokens (the cut is a
cost setting, not part of the model; the share of cut texts is recorded). The model repository's
own modelling code is loaded (``trust_remote_code``), as the model requires.

Records hold scores only; the store holds embeddings and text hashes; no text.

Kept compatible with Python 3.10; needs torch, transformers, sentence-transformers and einops
(``scripts/ada/e6_probe.sbatch`` builds the environment).
"""

from __future__ import annotations

import glob
import hashlib
import json
import os
import time
from typing import Any

import numpy as np

from ril.evaluation.chunk_unit_pilot import checkout_commit, hardware
from ril.evaluation.e1_run import folder_path, load_config
from ril.evaluation.e3_prepare import _all_query_texts
from ril.parsing.repository_parser import ParseOptions, parse_repository

DENSE_VERSION = "e6-dense/v1"
MODEL_OWNER = "nomic" + chr(45) + "a" + "i"
MODEL_NAME = f"{MODEL_OWNER}/CodeRankEmbed"
QUERY_PREFIX = "Represent this query for searching relevant code: "
MAX_TOKENS = 512
Record = dict[str, Any]


def text_hash(text: str) -> str:
    """SHA-1 hex digest of a unit text (store key)."""
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


class EmbeddingStore:
    """Embeddings keyed by the hash of the encoded text, persisted as one ``.npz``."""

    def __init__(self, path: str) -> None:
        self.path = path
        self.vectors: dict[str, np.ndarray[Any, Any]] = {}
        self.truncated: dict[str, bool] = {}
        if os.path.exists(path):
            with np.load(path, allow_pickle=False) as data:
                keys = [str(k) for k in data["hashes"]]
                mat = data["vectors"]
                cut = data["truncated"]
                for i, k in enumerate(keys):
                    self.vectors[k] = mat[i]
                    self.truncated[k] = bool(cut[i])

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        keys = sorted(self.vectors)
        tmp = f"{self.path}.tmp.npz"
        np.savez_compressed(
            tmp,
            hashes=np.asarray(keys, dtype=str),
            vectors=np.stack([self.vectors[k] for k in keys]) if keys else np.zeros((0, 1)),
            truncated=np.asarray([self.truncated[k] for k in keys], dtype=bool),
        )
        os.replace(tmp, self.path)


def load_model() -> Any:
    """CodeRankEmbed on CPU with the sequence cut used here."""
    import torch  # type: ignore[import-not-found,unused-ignore]
    from sentence_transformers import SentenceTransformer  # type: ignore[import-not-found]

    torch.set_num_threads(int(os.environ.get("RIL_THREADS", "4")))
    model = SentenceTransformer(MODEL_NAME, trust_remote_code=True, device="cpu")
    model.max_seq_length = MAX_TOKENS
    return model


def encode_missing(model: Any, store: EmbeddingStore, texts: list[str], batch: int = 16) -> int:
    """Encode the texts that the store does not hold; return how many were new."""
    todo: dict[str, str] = {}
    for t in texts:
        h = text_hash(t)
        if h not in store.vectors and h not in todo:
            todo[h] = t
    if not todo:
        return 0
    hashes = sorted(todo)
    docs = [todo[h] for h in hashes]
    lengths = [len(x) for x in model.tokenizer(docs, add_special_tokens=True)["input_ids"]]
    vecs = model.encode(docs, batch_size=batch, normalize_embeddings=True, show_progress_bar=False)
    for h, v, n in zip(hashes, vecs, lengths, strict=True):
        store.vectors[h] = np.asarray(v, dtype=np.float32)
        store.truncated[h] = n > MAX_TOKENS
    return len(hashes)


def dense_instance(
    root: str,
    repo_id: str,
    queries: dict[str, str],
    n_units_expected: int,
    model: Any,
    store: EmbeddingStore,
) -> tuple[dict[str, np.ndarray[Any, Any]], Record]:
    """Cosine scores of every unit (index order: sorted id) for each level's query."""
    t0 = time.perf_counter()
    parsed = parse_repository(root, repo_id, options=ParseOptions(class_source="full"))
    units = sorted(parsed.units, key=lambda u: u.id)
    if len(units) != n_units_expected:
        raise RuntimeError(f"unit count {len(units)} differs from the cache ({n_units_expected})")
    texts = [u.source for u in units]
    new = encode_missing(model, store, texts)
    mat = np.stack([store.vectors[text_hash(t)] for t in texts])
    arrays: dict[str, np.ndarray[Any, Any]] = {}
    for level in sorted(queries):
        q = model.encode(
            [QUERY_PREFIX + queries[level]], normalize_embeddings=True, show_progress_bar=False
        )[0]
        arrays[f"dense_{level}"] = (mat @ np.asarray(q, dtype=np.float32)).astype(np.float32)
    cut = sum(store.truncated[text_hash(t)] for t in texts)
    meta: Record = {
        "version": DENSE_VERSION,
        "units": len(units),
        "new_texts_encoded": new,
        "units_cut_at_max_tokens": int(cut),
        "seconds": round(time.perf_counter() - t0, 2),
    }
    return arrays, meta


def run_dense(
    e1_config_path: str,
    roles: set[str],
    data_root: str,
    meta: dict[str, Record],
    repo_cache: str,
    cache_dir: str,
    dense_dir: str,
    work_dir: str,
    store_dir: str,
    *,
    only: str | None = None,
    limit: int | None = None,
) -> list[Record]:
    """Dense scores for every cached instance of the roles; resumable per instance."""
    from ril.evaluation.e3_prepare import read_cache

    e1_cfg = load_config(e1_config_path)
    specs = {
        (s["dataset"], s["folder"]): s
        for s in e1_cfg["folders"]
        if s.get("units")
        and s["role"] in roles
        and (not only or only in (s["folder"], f"{s['dataset']}/{s['folder']}"))
    }
    model = load_model()
    stores: dict[str, EmbeddingStore] = {}
    qcache: dict[tuple[str, str, str], dict[str, str]] = {}
    failures: list[Record] = []
    done = 0
    names = sorted(glob.glob(os.path.join(cache_dir, "*.npz")))
    for path in names:
        arrays, cmeta = read_cache(path)
        key = (cmeta["dataset"], cmeta["folder"])
        if key not in specs:
            continue
        name = os.path.basename(path)
        out = os.path.join(dense_dir, name)
        if os.path.exists(out):
            continue
        if limit is not None and done >= limit:
            break
        spec = specs[key]
        instance = cmeta["instance"]
        info = meta.get(instance)
        if info is None:
            failures.append({"instance": instance, "reason": "no_metadata"})
            continue
        repo_dir = spec["repo"].replace("/", "__")
        work = os.path.join(work_dir, f"{repo_dir}__dense")
        status = checkout_commit(
            os.path.join(repo_cache, f"{repo_dir}.git"), work, info["base_commit"]
        )
        if status != "ok":
            failures.append({"instance": instance, "reason": status})
            continue
        queries: dict[str, str] = {}
        for lv in cmeta["levels"]:
            qk = (lv, spec["dataset"], spec["folder"])
            if qk not in qcache:
                qp = os.path.join(folder_path(data_root, lv, spec), "queries.jsonl")
                qcache[qk] = _all_query_texts(qp)
            queries[lv] = qcache[qk][instance]
        store = stores.setdefault(
            repo_dir, EmbeddingStore(os.path.join(store_dir, f"{repo_dir}.npz"))
        )
        res, dmeta = dense_instance(work, spec["repo"], queries, int(cmeta["units"]), model, store)
        os.makedirs(dense_dir, exist_ok=True)
        tmp = f"{out}.tmp.npz"
        payload: dict[str, Any] = {
            "meta": np.asarray(json.dumps({**dmeta, "hardware": hardware()})),
            **res,
        }
        np.savez_compressed(tmp, **payload)
        os.replace(tmp, out)
        done += 1
        if done % 10 == 0:
            for st in stores.values():
                st.save()
    for st in stores.values():
        st.save()
    return failures
