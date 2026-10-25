"""Evaluation hook of the training stack: score a trained checkpoint on the dev repositories.

Implements item 4 of the training-stack plan with the X2 machinery unchanged
(``docs/EXPERIMENTS.md`` E-DENSE-FUSION): the checkpoint encodes the prepared text stores of the
development repositories (``ril.evaluation.x2_dense.encode_store``), unit scores are written in the
pilot-E3 layout (``score_units``), the first-stage evaluation runs on the E3 cache
(``ril.evaluation.x2_eval.run_x2_eval``: BM25, dense, RRF of the two at a stated ``k``), chunk-level
ranks come from ``score_chunks`` (filter-first, the CORE-Bench reading), and the tables are the X2
paired rows (``ril.analysis.x2_tables``: mean over queries, query-level and repository-clustered
intervals, decision D17; both gold readings of D18 at unit level).

Output: ``unit_rows.csv`` and ``chunk_rows.csv`` in the run's result directory and an ``evaluation``
section in its ``results.json``. Baseline variants already encoded by X2 (e.g. the untrained base
encoder) can be named; each trained variant is then also paired against them.

Tuning discipline: roles default to ``dev``. A ``test`` role is refused unless the configuration
carries ``deliberate_test`` (a label stating why, e.g. the leakage pilot), and then runs as an X2
confirmation (one stated ``k``).

Kept compatible with Python 3.10.
"""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from typing import Any

from ril.analysis.e3_tables import load_eval_dir
from ril.analysis.x2_tables import chunk_rows, load_chunk_dir, unit_rows, write_csv
from ril.evaluation.e1_run import load_config
from ril.evaluation.x2_dense import encode_store, score_chunks, score_units
from ril.evaluation.x2_eval import run_x2_eval

CHECKPOINT_EVAL_VERSION = "checkpoint-eval/v1"
PROVISIONAL = "provisional: ADR-006 (rrf k, cut)"
Record = dict[str, Any]


def stores_for(
    e1_config_path: str, prep_dir: str, roles: Sequence[str], chunks: bool
) -> dict[str, list[str]]:
    """Text stores of the roles' repositories and folders: ``{store name: files}``."""
    cfg = load_config(e1_config_path)
    repos: set[str] = set()
    qnames: set[str] = set()
    for spec in cfg["folders"]:
        if spec["role"] not in roles:
            continue
        if spec.get("units"):
            repos.add(spec["repo"].replace("/", "__"))
        for level in spec["levels"]:
            qnames.add(f"{level}__{spec['dataset']}__{spec['folder']}")
    out: dict[str, list[str]] = {}
    tdir = os.path.join(prep_dir, "texts_units")
    if os.path.isdir(tdir):
        for f in sorted(os.listdir(tdir)):
            repo = f.split(".s")[0]
            if f.endswith(".jsonl") and repo in repos:
                out.setdefault(f"units__{repo}", []).append(os.path.join(tdir, f))
    for q in sorted(qnames):
        p = os.path.join(prep_dir, "queries", f"{q}.jsonl")
        if os.path.exists(p):
            out[f"queries__{q}"] = [p]
    if chunks:
        for r in sorted(repos):
            p = os.path.join(prep_dir, "texts_chunks", f"{r}.jsonl")
            if os.path.exists(p):
                out[f"chunks__{r}"] = [p]
    return out


def _columns(variant: str, baselines: Sequence[str], k: int) -> list[tuple[str, str, str | None]]:
    cols: list[tuple[str, str, str | None]] = [("bm25", "bm25", None)]
    for b in baselines:
        cols += [(f"dense:{b}", f"dense|{b}", "bm25"), (f"rrf:{b}", f"rrf|{b}|k{k}", "bm25")]
    ref_d = f"dense:{baselines[0]}" if baselines else "bm25"
    ref_r = f"rrf:{baselines[0]}" if baselines else "bm25"
    cols += [
        (f"dense:{variant}", f"dense|{variant}", ref_d),
        (f"rrf:{variant}", f"rrf|{variant}|k{k}", ref_r),
    ]
    return cols


def _chunk_columns(
    variant: str, baselines: Sequence[str], k: int
) -> list[tuple[str, str, str | None]]:
    cols: list[tuple[str, str, str | None]] = [("bm25", "bm25", None)]
    for b in baselines:
        cols += [(f"dense:{b}", b, "bm25"), (f"rrf:{b}", f"rrf{k}__{b}", "bm25")]
    ref_d = f"dense:{baselines[0]}" if baselines else "bm25"
    ref_r = f"rrf:{baselines[0]}" if baselines else "bm25"
    cols += [(f"dense:{variant}", variant, ref_d), (f"rrf:{variant}", f"rrf{k}__{variant}", ref_r)]
    return cols


def eval_checkpoint(
    encoder: Any,
    cfg: Mapping[str, Any],
    *,
    e1_config: str,
    prep_dir: str,
    cache_dir: str,
    data_root: str,
    work_dir: str,
    result_dir: str,
    baseline_enc_dirs: Mapping[str, str] | None = None,
    dense_root: str | None = None,
) -> Record:
    """Score ``encoder`` (a trained model with the ``DenseEncoder`` interface) and write the tables.

    ``cfg``: ``variant`` (name of this checkpoint's scores), ``roles``, ``rrf_k``, ``batch_size``,
    ``chunks`` (bool), ``seed``, optional ``baselines`` (variants whose unit scores exist under
    ``dense_root`` and whose encoded stores are in ``baseline_enc_dirs``), optional
    ``deliberate_test``. Resumable: every X2 stage skips finished pieces.
    """
    variant = str(cfg["variant"])
    roles = [str(r) for r in cfg["roles"]]
    k = int(cfg["rrf_k"])
    baselines = [str(b) for b in cfg.get("baselines", [])]
    seed = int(cfg["seed"])
    if "test" in roles and not cfg.get("deliberate_test"):
        raise ValueError("test repositories are evaluated only with a 'deliberate_test' label")
    enc_dir = os.path.join(work_dir, "enc", variant)
    droot = dense_root or os.path.join(work_dir, "dense")
    stores = stores_for(e1_config, prep_dir, roles, bool(cfg["chunks"]))
    encoded = [
        encode_store(
            encoder,
            files,
            name,
            enc_dir,
            batch_size=int(cfg["batch_size"]),
            is_query=name.startswith("queries__"),
        )
        for name, files in sorted(stores.items())
    ]
    scored = score_units(
        prep_dir,
        enc_dir,
        os.path.join(droot, variant),
        int(encoder.spec.max_tokens),
        roles=set(roles),
        forms=("full",),
    )
    first: Record = {"variants": [*baselines, variant]}
    if "test" in roles:
        first["rrf_k_of"] = {v: k for v in first["variants"]}
        ecfg: Record = {"roles": roles, "confirm": True, "first": first}
    else:
        first["rrf_ks"] = [k]
        ecfg = {"roles": roles, "first": first}
    eval_dir = os.path.join(work_dir, "eval", variant)
    counts = run_x2_eval(ecfg, cache_dir, droot, eval_dir)
    tab = load_eval_dir(eval_dir)
    urows: list[Record] = []
    for group in roles:
        urows += unit_rows(tab, group, _columns(variant, baselines, k), seed)
    out: Record = {
        "version": CHECKPOINT_EVAL_VERSION,
        "provisional": PROVISIONAL,
        "variant": variant,
        "roles": roles,
        "rrf_k": k,
        "baselines": baselines,
        "deliberate_test": cfg.get("deliberate_test"),
        "stores_encoded": encoded,
        "units_scored": scored,
        "x2_eval": counts,
        "unit_queries": len(tab.rows),
    }
    os.makedirs(result_dir, exist_ok=True)
    write_csv(os.path.join(result_dir, "unit_rows.csv"), urows)
    if cfg["chunks"]:
        enc_dirs = {variant: enc_dir, **dict(baseline_enc_dirs or {})}
        chunk_dir = os.path.join(work_dir, "chunks", variant)
        out["chunks_scored"] = score_chunks(
            e1_config, set(roles), data_root, enc_dirs, chunk_dir, ks=(k,)
        )
        rows, cols = load_chunk_dir(chunk_dir)
        crows: list[Record] = []
        for group in roles:
            crows += chunk_rows(rows, cols, group, _chunk_columns(variant, baselines, k), seed)
        write_csv(os.path.join(result_dir, "chunk_rows.csv"), crows)
        out["chunk_queries"] = len(rows)
    out["headline"] = [
        r
        for r in urows
        if r["reading"] == "units_all_nomod"
        and (
            (r["level"] == "L2" and r["metric"] == "ndcg10")
            or (r["level"] == "L3" and r["metric"] == "recall100")
        )
    ]
    return out
