"""Per-instance extras for the structure measurements X1 (class-unit source, ambiguous-site policy).

Exploratory. Implements the preparation half of ``docs/EXPERIMENTS.md`` E-CLASS-SOURCE and
E-AMBIG-POLICY. For one benchmark instance checked out at its base commit it

* parses the snapshot once per class-unit source form (``CLASS_SOURCE_FORMS``, open question Q28,
  ``provisional: ADR-013``), checks that the unit ids are the same in every form, builds the BM25
  index of each form and stores the scores of each level's issue text, the index size and the
  parse and index times;
* builds the typed graph of the ``full`` form (the graph does not depend on the form) and stores
  every ambiguous ``invoke`` site with its candidate set and receiver evidence
  (``ril.parsing.ambiguity_policy``; Q35, Q36);
* stores the gold unit indices of four readings: pilot M's mapping (``units``), every overlapped
  unit (``units_all``, decision D18), and each without module units (``units_nomod``,
  ``units_all_nomod``; the latter is D18's primary reading for graph questions).

The arrays line up with the pilot-E3 cache of the same instance (unit order = sorted unit id);
``ril.evaluation.x1_eval`` checks that the ``full`` scores equal the E3 cache's BM25 scores before
it uses anything. No text is stored.

Kept compatible with Python 3.10.
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
from ril.evaluation.e1_run import folder_path, load_config, params_of
from ril.evaluation.e3_prepare import (
    NOMOD_OF,
    READINGS,
    _all_query_texts,
    is_module_id,
    write_cache,
)
from ril.parsing.ambiguity_policy import EVIDENCE_KINDS, ambiguous_sites, evidence_counts
from ril.parsing.call_graph import RESOLVER_NAME, RESOLVER_VERSION, GraphBuilder
from ril.parsing.code_unit import CODEUNIT_SCHEMA_VERSION
from ril.parsing.repository_parser import (
    CLASS_SOURCE_FORMS,
    PARSER_VERSION,
    ParseOptions,
    parse_repository,
)
from ril.retrieval.bm25_index import BM25Index, BM25Params, tokenize

X1_PREPARE_VERSION = "x1-prepare/v1"
X1_READINGS: tuple[str, ...] = READINGS
DERIVATIONS: tuple[str, ...] = ("name-match", "multiple-definitions", "other")
Record = dict[str, Any]


def x1_hash(e1_cfg: Record, params: BM25Params) -> str:
    """SHA-256 over everything besides the data that decides an extras file."""
    payload = {
        "version": X1_PREPARE_VERSION,
        "bm25": {"k1": params.k1, "b": params.b},
        "forms": list(CLASS_SOURCE_FORMS),
        "evidence": list(EVIDENCE_KINDS),
        "parser": PARSER_VERSION,
        "resolver": f"{RESOLVER_NAME}/{RESOLVER_VERSION}",
        "codeunit_schema": CODEUNIT_SCHEMA_VERSION,
        "e1_seed": e1_cfg["seed"],
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def gold_readings(e1_record: Record) -> dict[str, dict[str, set[str]]]:
    """``{level: {reading: gold unit ids}}`` for the four readings of :data:`X1_READINGS`."""
    out: dict[str, dict[str, set[str]]] = {}
    for p in e1_record["positives"]:
        if p["status"] != "found":
            continue
        slot = out.setdefault(p["level"], {r: set() for r in X1_READINGS})
        slot["units"].update(p["units"])
        slot["units_all"].update(p["units_all"])
        for nomod, src in NOMOD_OF.items():
            slot[nomod].update(u for u in p[src] if not is_module_id(u))
    return out


def index_size(index: BM25Index) -> Record:
    """Size of a BM25 index: documents, tokens, vocabulary, postings and array bytes."""
    postings = int(index._docs.shape[0])  # noqa: SLF001 - size accounting only
    return {
        "docs": int(index.n_docs),
        "tokens": int(index.doc_len.sum()),
        "vocab": len(index.vocab),
        "postings": postings,
        "array_bytes": int(
            index._weights.nbytes + index._docs.nbytes + index._starts.nbytes  # noqa: SLF001
        ),
    }


def derivation_code(derivation: str) -> int:
    """0 name match on an unknown receiver, 1 several definitions of one name, 2 other."""
    if derivation.endswith("name-match"):
        return 0
    if derivation.endswith("multiple-definitions"):
        return 1
    return 2


def prepare_x1_instance(
    root: str,
    repo_id: str,
    queries: dict[str, str],
    e1_record: Record,
    params: BM25Params,
    chash: str,
) -> tuple[dict[str, np.ndarray[Any, Any]], Record]:
    """Arrays and metadata of one instance (``root`` is checked out at the base commit)."""
    seconds: dict[str, float] = {}
    sizes: dict[str, Record] = {}
    source_chars: dict[str, int] = {}
    arrays: dict[str, np.ndarray[Any, Any]] = {}
    ids_ref: list[str] | None = None
    parsed_full = None
    for form in CLASS_SOURCE_FORMS:
        t0 = time.perf_counter()
        parsed = parse_repository(root, repo_id, options=ParseOptions(class_source=form))
        seconds[f"parse_{form}"] = round(time.perf_counter() - t0, 3)
        units = sorted(parsed.units, key=lambda u: u.id)
        ids = [u.id for u in units]
        if ids_ref is None:
            ids_ref = ids
        elif ids != ids_ref:
            raise RuntimeError(f"{repo_id}: unit ids differ between class-source forms")
        if form == "full":
            parsed_full = parsed
        source_chars[form] = sum(len(u.source) for u in units)
        t1 = time.perf_counter()
        index = BM25Index((tokenize(u.source) for u in units), params)
        seconds[f"bm25_index_{form}"] = round(time.perf_counter() - t1, 3)
        sizes[form] = index_size(index)
        for level, text in sorted(queries.items()):
            arrays[f"scores_{level}_{form}"] = index.scores(tokenize(text))
    assert ids_ref is not None and parsed_full is not None
    index_of = {uid: i for i, uid in enumerate(ids_ref)}
    n_class = sum(1 for u in parsed_full.units if u.unit_type == "class")

    t2 = time.perf_counter()
    graph = GraphBuilder(parsed_full).build()
    seconds["graph"] = round(time.perf_counter() - t2, 3)
    t3 = time.perf_counter()
    sites = ambiguous_sites(parsed_full, graph)
    seconds["evidence"] = round(time.perf_counter() - t3, 3)
    resolved_pairs = {
        (index_of[e.src], index_of[e.dst])
        for e in graph.edges
        if e.type == "invoke"
        and e.status == "resolved"
        and e.src != e.dst
        and e.src in index_of
        and e.dst in index_of
    }
    site_src: list[int] = []
    site_size: list[int] = []
    site_ev: list[list[int]] = []
    site_der: list[int] = []
    cand_site: list[int] = []
    cand_unit: list[int] = []
    for s in sites:
        if s.src not in index_of:
            continue
        k = len(site_src)
        site_src.append(index_of[s.src])
        site_size.append(s.size)
        site_ev.append([int(kind in s.evidence) for kind in EVIDENCE_KINDS])
        site_der.append(derivation_code(s.derivation))
        for c in s.candidates:
            if c in index_of:
                cand_site.append(k)
                cand_unit.append(index_of[c])
    arrays["amb_src"] = np.asarray(site_src, dtype=np.int32)
    arrays["amb_size"] = np.asarray(site_size, dtype=np.int32)
    arrays["amb_evidence"] = np.asarray(site_ev, dtype=np.int8).reshape(-1, len(EVIDENCE_KINDS))
    arrays["amb_derivation"] = np.asarray(site_der, dtype=np.int8)
    arrays["amb_cand_site"] = np.asarray(cand_site, dtype=np.int32)
    arrays["amb_cand_unit"] = np.asarray(cand_unit, dtype=np.int32)

    gold = gold_readings(e1_record)
    missing = 0
    for level in sorted(gold):
        if f"scores_{level}_full" not in arrays:
            continue
        for reading in X1_READINGS:
            wanted = sorted(gold[level][reading])
            kept = [index_of[u] for u in wanted if u in index_of]
            missing += len(wanted) - len(kept)
            arrays[f"gold_{level}_{reading}"] = np.asarray(kept, dtype=np.int32)

    status = graph.status_table().get("invoke", {})
    meta: Record = {
        "version": X1_PREPARE_VERSION,
        "config_hash": chash,
        "repo_id": repo_id,
        "units": len(ids_ref),
        "class_units": n_class,
        "units_sha256": hashlib.sha256("\n".join(ids_ref).encode("utf-8")).hexdigest(),
        "source_chars": source_chars,
        "index_size": sizes,
        "seconds": seconds,
        "invoke_status": status,
        "resolved_invoke_pairs": len(resolved_pairs),
        "ambiguous": evidence_counts(sites),
        "gold_ids_not_in_units": missing,
        "levels": sorted({k.split("_")[1] for k in arrays if k.startswith("scores_")}),
        "hardware": hardware(),
    }
    return arrays, meta


def run_x1_prepare(
    e1_config_path: str,
    roles: set[str],
    data_root: str,
    meta: dict[str, Record],
    repo_cache: str,
    out_cache: str,
    work_dir: str,
    out_dir: str,
    e1_units_dir: str,
    *,
    only: str | None = None,
    limit: int | None = None,
    shard: tuple[int, int] = (0, 1),
) -> list[Record]:
    """Prepare the extras of every instance of the unit-level folders with a role in ``roles``.

    Same work list, sharding and resumability as ``ril.evaluation.e3_prepare.run_prepare``.
    """
    e1_cfg = load_config(e1_config_path)
    params = params_of(e1_cfg)
    chash = x1_hash(e1_cfg, params)
    specs = {
        (s["dataset"], s["folder"]): s
        for s in e1_cfg["folders"]
        if s.get("units")
        and s["role"] in roles
        and (not only or only in (s["folder"], f"{s['dataset']}/{s['folder']}"))
    }
    records: list[Record] = []
    for path in sorted(glob.glob(os.path.join(e1_units_dir, "*.json"))):
        with open(path, encoding="utf-8") as handle:
            rec = json.load(handle)
        if (rec["dataset"], rec["folder"]) in specs:
            records.append(rec)
    records.sort(key=lambda r: r["instance"])
    qtext: dict[tuple[str, str, str], dict[str, str]] = {}
    failures: list[Record] = []
    done = 0
    for ordinal, rec in enumerate(records):
        if ordinal % shard[1] != shard[0]:
            continue
        if limit is not None and done >= limit:
            break
        spec = specs[(rec["dataset"], rec["folder"])]
        instance = rec["instance"]
        out = os.path.join(out_cache, f"{instance}.npz")
        if _current(out, chash):
            continue
        info = meta.get(instance)
        if info is None:
            failures.append({"instance": instance, "reason": "no_metadata"})
            continue
        repo_dir = spec["repo"].replace("/", "__")
        work = os.path.join(work_dir, f"{repo_dir}__s{shard[0]}")
        status = checkout_commit(
            os.path.join(repo_cache, f"{repo_dir}.git"), work, info["base_commit"]
        )
        if status != "ok":
            failures.append({"instance": instance, "reason": status})
            continue
        queries: dict[str, str] = {}
        for lv in spec["levels"]:
            key = (lv, spec["dataset"], spec["folder"])
            if key not in qtext:
                qpath = os.path.join(folder_path(data_root, lv, spec), "queries.jsonl")
                qtext[key] = _all_query_texts(qpath) if os.path.exists(qpath) else {}
            if instance in qtext[key]:
                queries[lv] = qtext[key][instance]
        arrays, meta_out = prepare_x1_instance(work, spec["repo"], queries, rec, params, chash)
        meta_out.update(
            instance=instance,
            role=spec["role"],
            dataset=spec["dataset"],
            folder=spec["folder"],
            base_commit=info["base_commit"],
        )
        write_cache(out, arrays, meta_out)
        done += 1
    os.makedirs(out_dir, exist_ok=True)
    with open(
        os.path.join(out_dir, f"x1_prepare_failures_s{shard[0]}.json"), "w", encoding="utf-8"
    ) as handle:
        json.dump(
            {"failures": failures, "hardware": hardware(), "config_hash": chash, "prepared": done},
            handle,
        )
    return failures


def _current(path: str, chash: str) -> bool:
    if not os.path.exists(path):
        return False
    try:
        with np.load(path, allow_pickle=False) as data:
            return bool(json.loads(str(data["meta"])).get("config_hash") == chash)
    except (OSError, ValueError, KeyError):
        return False
