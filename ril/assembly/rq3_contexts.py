"""Retrieved contexts of the executable subset, by arm and budget (E-RQ3-CONTEXTS, D108).

Implements ``docs/RQ3_PILOT.md`` ("Retrieved contexts") and ``specs/assembly.md``. For each member
of the subset the ranked list of an arm is assembled at each budget by ``ril.assembly.assemble``,
unchanged: the policy is the same for every arm, so only the ranked list differs (ADR-014).

An arm is a name, the key of the dense scores it reads (``None`` for none) and a scoring function
``(bm25, dense) -> scores``. The default arms are BM25, the untrained encoder's dense scores and
RRF over both; an arm for a trained checkpoint is one more ``Arm`` with that checkpoint's dense
array, with no change to the code below.

One query per instance (the issue text) gives one context per (arm, budget), whatever the level;
the level only decides which gold is looked for, which is why L2 and L3 coverage share contexts.

Output is deterministic: canonical JSON, gzip with a fixed header, sorted keys. The record of an
instance holds the context text and manifest of every (arm, budget) and its coverage rows.

Kept compatible with Python 3.10.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import random
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np

from ril.assembly.assemble import Assembled, Candidate, UnitText, assemble, snapshot_of
from ril.assembly.config import ASSEMBLY_VERSION, AssemblyConfig
from ril.assembly.gold import gold_in_context
from ril.assembly.measure import snapshot_units
from ril.assembly.tokens import ApproxTokenizer, Tokenizer
from ril.evaluation.e3_prepare import read_cache
from ril.evaluation.x2_eval import positions, rrf_scores
from ril.retrieval.bm25_index import order_by_score

RQ3_CONTEXTS_VERSION = "rq3-contexts/v1"
LEVELS = ("L2", "L3")
FILE_READING = "units_all"
"""Reading whose gold units name every file with a found positive (module units included)."""
UNIT_READING = "units_all_nomod"
"""Primary unit-level reading (D18): every overlapped unit, module residuals left out."""
READINGS = (FILE_READING, UNIT_READING)

Record = dict[str, Any]
Arr = np.ndarray[Any, Any]
ScoreFn = Callable[[Arr, "Arr | None"], Arr]


@dataclass(frozen=True)
class Arm:
    """A first stage: ``score(bm25, dense)`` over the snapshot, reading ``dense_key`` if given."""

    name: str
    dense_key: str | None
    score: ScoreFn
    stages: tuple[str, ...] = ()
    """Signals named in the manifest (kept, not used by the policy)."""


def _bm25_only(bm25: Arr, dense: Arr | None) -> Arr:
    return np.asarray(bm25, dtype=np.float64)


def _dense_only(bm25: Arr, dense: Arr | None) -> Arr:
    if dense is None:
        raise ValueError("the dense arm needs dense scores")
    return np.asarray(dense, dtype=np.float64)


def rrf_arm_score(rrf_k: int) -> ScoreFn:
    """Reciprocal-rank fusion of BM25 and dense (rank based, ties by lower index, as in D102)."""

    def score(bm25: Arr, dense: Arr | None) -> Arr:
        if dense is None:
            raise ValueError("rrf needs dense scores")
        return rrf_scores([positions(bm25), positions(dense)], rrf_k)

    return score


def default_arms(rrf_k: int, dense_key: str = "dense_L2") -> tuple[Arm, ...]:
    """BM25, untrained dense and RRF over both (the arms that need no trained checkpoint)."""
    return (
        Arm("bm25", None, _bm25_only, ("bm25",)),
        Arm("dense", dense_key, _dense_only, ("dense",)),
        Arm("rrf", dense_key, rrf_arm_score(rrf_k), ("bm25", "dense")),
    )


@dataclass(frozen=True)
class ContextSpec:
    """What decides the bytes besides the inputs (stated before the run, D108)."""

    budgets: tuple[int, ...]
    max_unit_tokens: int
    candidates: int
    rrf_k: int
    query_level: str = "L2"

    def spec_hash(self, tokenizer: str, arms: Sequence[Arm]) -> str:
        payload = {
            **asdict(self),
            "arms": [a.name for a in arms],
            "version": RQ3_CONTEXTS_VERSION,
            "assembly": ASSEMBLY_VERSION,
            "tokenizer": tokenizer,
        }
        blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def candidates_for(
    arm: Arm, bm25: Arr, dense: Arr | None, unit_ids: list[str], n_top: int
) -> list[Candidate]:
    """The ``n_top`` best units of the arm in rank order; ``stages`` names the signals used."""
    scores = arm.score(bm25, dense)
    order = order_by_score(scores)[:n_top]
    return [Candidate(unit_ids[int(i)], float(scores[int(i)]), arm.stages) for i in order]


def budget_binding(out: Assembled) -> bool:
    """Whether the budget kept a candidate out (at least one ``does_not_fit`` skip)."""
    return any(s.reason == "does_not_fit" for s in out.manifest.skipped)


def level_gold(
    arrays: Mapping[str, Arr], level: str, unit_ids: Sequence[str], files: Mapping[str, str]
) -> dict[str, tuple[list[str], list[str]]]:
    """``{reading: (gold unit ids, gold files)}`` of a level; readings with no gold are left out."""
    out: dict[str, tuple[list[str], list[str]]] = {}
    for reading in READINGS:
        key = f"gold_{level}_{reading}"
        if key not in arrays or len(arrays[key]) == 0:
            continue
        gold = [unit_ids[int(i)] for i in arrays[key]]
        out[reading] = (gold, sorted({files[u] for u in gold}))
    return out


def build_instance(
    meta: Mapping[str, Any],
    arrays: Mapping[str, Arr],
    dense: Mapping[str, Arr],
    units: Sequence[UnitText],
    spec: ContextSpec,
    arms: Sequence[Arm],
    tok: Tokenizer,
) -> Record:
    """Record of one instance: contexts, manifests and coverage rows for every arm and budget."""
    ids = [u.unit_id for u in units]
    files = {u.unit_id: u.file for u in units}
    snap = snapshot_of(units)
    bm25 = arrays[f"scores_{spec.query_level}"]
    golds = {lv: level_gold(arrays, lv, ids, files) for lv in LEVELS}
    contexts: Record = {}
    rows: list[Record] = []
    for arm in arms:
        d = dense.get(arm.dense_key) if arm.dense_key else None
        if arm.dense_key and d is None:
            raise ValueError(f"{meta['instance']}: no dense scores {arm.dense_key!r}")
        if d is not None and len(d) != len(units):
            raise ValueError(f"{meta['instance']}: dense has {len(d)} units, snapshot {len(units)}")
        cands = candidates_for(arm, bm25, d, ids, spec.candidates)
        for budget in spec.budgets:
            out = assemble(cands, snap, AssemblyConfig(budget, spec.max_unit_tokens), tok)
            m = out.manifest
            contexts[f"{arm.name}|{budget}"] = {
                "context": out.context,
                "manifest": json.loads(m.to_json()),
            }
            for level in LEVELS:
                for reading, (gold_units, gold_files) in golds[level].items():
                    g = gold_in_context(m, gold_units, gold_files)
                    rows.append(
                        {
                            "instance": meta["instance"],
                            "level": level,
                            "arm": arm.name,
                            "budget": budget,
                            "reading": reading,
                            "n_gold_units": g.n_units,
                            "units_in": g.units_in,
                            "units_intact": g.units_intact,
                            "n_gold_files": g.n_files,
                            "files_in": g.files_in,
                        }
                    )
    return {
        "version": RQ3_CONTEXTS_VERSION,
        "instance": meta["instance"],
        "repo_id": meta["repo_id"],
        "base_commit": meta["base_commit"],
        "units": len(units),
        "spec_hash": spec.spec_hash(tok.name, arms),
        "tokenizer": tok.name,
        "contexts": contexts,
        "coverage": rows,
    }


# --------------------------------------------------------------------------- bytes on disk


def encode_record(record: Mapping[str, Any]) -> bytes:
    """Canonical JSON, gzip with a fixed header: the same record gives the same bytes."""
    blob = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return gzip.compress(blob.encode("utf-8"), compresslevel=6, mtime=0)


def decode_record(data: bytes) -> Record:
    out: Record = json.loads(gzip.decompress(data).decode("utf-8"))
    return out


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def write_atomic(path: str, data: bytes) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(f"{path}.tmp", "wb") as handle:
        handle.write(data)
    os.replace(f"{path}.tmp", path)


# --------------------------------------------------------------------------- the cluster run


@dataclass(frozen=True)
class InputGroup:
    """Where the caches and dense scores of a set of instances live (first match wins)."""

    cache_dir: str
    dense_dir: str


def locate(groups: Sequence[InputGroup], instance: str) -> tuple[str, str] | None:
    """Cache and dense-score paths of ``instance``, from the first group that has both."""
    for g in groups:
        c = os.path.join(g.cache_dir, f"{instance}.npz")
        d = os.path.join(g.dense_dir, f"{instance}.npz")
        if os.path.exists(c) and os.path.exists(d):
            return c, d
    return None


def read_dense(path: str) -> dict[str, Arr]:
    with np.load(path, allow_pickle=False) as dz:
        return {k: dz[k] for k in dz.files if k.startswith("dense_")}


def vector_checks(arrays: Mapping[str, Arr], dense: Mapping[str, Arr]) -> Record:
    """Whether the L3 query gave the same scores as the L2 query (identical texts, D108)."""
    out: Record = {}
    if "scores_L3" in arrays:
        out["bm25_L3_equals_L2"] = bool(np.array_equal(arrays["scores_L3"], arrays["scores_L2"]))
    if "dense_L3" in dense:
        out["dense_L3_equals_L2"] = bool(np.array_equal(dense["dense_L3"], dense["dense_L2"]))
    return out


def build_one(
    instance: str,
    paths: tuple[str, str],
    repo_cache: str,
    work_dir: str,
    spec: ContextSpec,
    arms: Sequence[Arm],
    tok: Tokenizer,
) -> tuple[Record | None, Record]:
    """(record, info) of one instance; a failure gives ``None`` and the reason in ``info``."""
    from ril.evaluation.chunk_unit_pilot import checkout_commit

    t0 = time.perf_counter()
    arrays, meta = read_cache(paths[0])
    dense = read_dense(paths[1])
    repo_dir = str(meta["repo_id"]).replace("/", "__")
    work = os.path.join(work_dir, repo_dir)
    status = checkout_commit(
        os.path.join(repo_cache, f"{repo_dir}.git"), work, str(meta["base_commit"])
    )
    if status != "ok":
        return None, {"instance": instance, "reason": status}
    units = snapshot_units(work, str(meta["repo_id"]))
    if len(units) != int(meta["units"]):
        return None, {
            "instance": instance,
            "reason": f"unit_count {len(units)} != cache {meta['units']}",
        }
    record = build_instance(meta, arrays, dense, units, spec, arms, tok)
    info: Record = {
        "instance": instance,
        "seconds": round(time.perf_counter() - t0, 2),
        **vector_checks(arrays, dense),
    }
    return record, info


def run_build(
    members: Sequence[str],
    groups: Sequence[InputGroup],
    repo_cache: str,
    work_dir: str,
    out_dir: str,
    spec: ContextSpec,
    arms: Sequence[Arm],
    *,
    shard: tuple[int, int] = (0, 1),
    only: Sequence[str] | None = None,
) -> Record:
    """Build every member of the shard; resumable (a file carrying the spec hash is kept)."""
    tok = ApproxTokenizer()
    shash = spec.spec_hash(tok.name, arms)
    mine = [m for n, m in enumerate(sorted(members)) if n % shard[1] == shard[0]]
    if only is not None:
        mine = [m for m in mine if m in set(only)]
    counts = {"built": 0, "reused": 0, "failed": 0}
    failures: list[Record] = []
    infos: list[Record] = []
    for instance in mine:
        out = os.path.join(out_dir, "instances", f"{instance}.json.gz")
        if os.path.exists(out):
            with open(out, "rb") as handle:
                if decode_record(handle.read()).get("spec_hash") == shash:
                    counts["reused"] += 1
                    continue
        paths = locate(groups, instance)
        if paths is None:
            counts["failed"] += 1
            failures.append({"instance": instance, "reason": "no_inputs"})
            continue
        record, info = build_one(instance, paths, repo_cache, work_dir, spec, arms, tok)
        if record is None:
            counts["failed"] += 1
            failures.append(info)
            continue
        write_atomic(out, encode_record(record))
        counts["built"] += 1
        infos.append(info)
    return {"counts": counts, "failures": failures, "infos": infos, "spec_hash": shash}


def compare_dirs(first: str, second: str, instances: Sequence[str]) -> Record:
    """SHA-256 of the instance files of two builds, per instance, and the number that differ."""
    rows: list[Record] = []
    for iid in instances:
        a = sha256_file(os.path.join(first, "instances", f"{iid}.json.gz"))
        b = sha256_file(os.path.join(second, "instances", f"{iid}.json.gz"))
        rows.append({"instance": iid, "first": a, "second": b, "equal": a == b})
    return {"n": len(rows), "differ": sum(1 for r in rows if not r["equal"]), "rows": rows}


def draw_instances(members: Sequence[str], n: int, seed: int) -> list[str]:
    """``n`` members drawn with ``seed`` from the sorted list (independent of directory order)."""
    return sorted(random.Random(seed).sample(sorted(members), min(n, len(members))))


# --------------------------------------------------------------------------- the archive


def write_archive(out_dir: str, archive: str, budget: int) -> Record:
    """One tar.gz of the contexts at ``budget``: ``<arm>/<instance>.txt`` and ``.manifest.json``.

    Entries are sorted, with fixed owner, mode and time, and gzip has a fixed header, so the same
    records give the same archive bytes. The SHA-256 of the archive is written beside it.
    """
    import io
    import tarfile

    names = sorted(f for f in os.listdir(os.path.join(out_dir, "instances")) if f.endswith(".gz"))
    files: dict[str, bytes] = {}
    for name in names:
        with open(os.path.join(out_dir, "instances", name), "rb") as handle:
            rec = decode_record(handle.read())
        for key, ctx in rec["contexts"].items():
            arm, b = key.split("|")
            if int(b) != budget:
                continue
            base = f"{arm}/{rec['instance']}"
            files[f"{base}.txt"] = ctx["context"].encode("utf-8")
            files[f"{base}.manifest.json"] = json.dumps(
                ctx["manifest"], sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w", format=tarfile.PAX_FORMAT) as tar:
        for path in sorted(files):
            info = tarfile.TarInfo(f"contexts_b{budget}/{path}")
            info.size = len(files[path])
            info.mtime = 0
            info.mode = 0o644
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            tar.addfile(info, io.BytesIO(files[path]))
    data = gzip.compress(raw.getvalue(), compresslevel=6, mtime=0)
    write_atomic(archive, data)
    digest = hashlib.sha256(data).hexdigest()
    write_atomic(f"{archive}.sha256", f"{digest}  {os.path.basename(archive)}\n".encode())
    return {"files": len(files), "bytes": len(data), "sha256": digest}
