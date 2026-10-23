"""Cluster job bodies of the dense measurements X2: GPU gate, encoding run, latency and throughput.

Exploratory. The GPU job (``encode_job``) refuses to start unless a real CUDA matrix product agrees
with the CPU result on a card of compute capability 7.0 or more (``docs/COMPUTE.md``: one node had a
card the installed torch build cannot drive while ``torch.cuda.is_available()`` still said yes).
It then encodes the requested text stores with each encoder and cut, records throughput, peak device
memory, the model revision and a float16-against-float32 agreement check, and writes one JSON run
log.
``measure_job`` writes the latency rows (``query_encode``, ``dense_search``) and throughput rows
(``dense_encode``) of one encoder on the machine it runs on (CPU or GPU).

Kept compatible with Python 3.10.
"""

from __future__ import annotations

import glob
import json
import os
import platform
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np

from ril.bench.dense_measure import (
    DJANGO_UNITS,
    N_QUERIES,
    build_issue_like_queries,
    encode_throughput_rows,
    query_encode_rows,
    scale_matrix,
    search_rows,
    vm_hwm_kb,
    write_query_set,
)
from ril.bench.latency_harness import (
    LATENCY_COLUMNS,
    THROUGHPUT_COLUMNS,
    Row,
    append_rows,
)
from ril.evaluation.chunk_unit_pilot import hardware
from ril.evaluation.x2_dense import VectorStore, encode_store, read_store
from ril.retrieval.dense_encoder import ENCODERS, DenseEncoder

Record = dict[str, Any]
BATCH = {"coderankembed": 64, "qwen3-embedding-0.6b": 16}
"""Encoding batch sizes per encoder on an 11 GB card (a fit, not a tuned value)."""


def cuda_gate() -> Record:
    """Real CUDA matrix product checked against the CPU; raises if the card is unusable."""
    import torch  # type: ignore[import-not-found,unused-ignore]

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA not available")
    cap = torch.cuda.get_device_capability(0)
    if cap < (7, 0):
        raise RuntimeError(f"compute capability {cap} not supported by this build")
    g = torch.Generator().manual_seed(0)
    a = torch.randn(1024, 1024, generator=g)
    b = torch.randn(1024, 1024, generator=g)
    ref = a @ b
    got = (a.cuda() @ b.cuda()).cpu()
    torch.cuda.synchronize()
    err = float((got - ref).abs().max())
    if not err < 1e-2:
        raise RuntimeError(f"CUDA matmul disagrees with CPU (max abs error {err})")
    return {
        "device": torch.cuda.get_device_name(0),
        "capability": list(cap),
        "matmul_max_abs_error": err,
        "torch": torch.__version__,
        "cuda": torch.version.cuda,
    }


def model_revision(model_id: str) -> str | None:
    """Commit of the downloaded model repository (from the Hugging Face cache refs)."""
    home = os.environ.get("HF_HOME", os.path.expanduser("~/.cache/huggingface"))
    ref = os.path.join(home, "hub", "models--" + model_id.replace("/", "--"), "refs", "main")
    try:
        with open(ref, encoding="ascii") as handle:
            return handle.read().strip()
    except OSError:
        return None


def store_groups(
    prep_dir: str, kinds: Sequence[str], names: Sequence[str] | None
) -> dict[str, list[str]]:
    """``{store name: files}`` of the prepared text stores (``units``, ``chunks``, ``queries``)."""
    out: dict[str, list[str]] = {}
    if "units" in kinds:
        for p in sorted(glob.glob(os.path.join(prep_dir, "texts_units", "*.jsonl"))):
            repo = os.path.basename(p).split(".s")[0]
            out.setdefault(f"units__{repo}", []).append(p)
    if "chunks" in kinds:
        for p in sorted(glob.glob(os.path.join(prep_dir, "texts_chunks", "*.jsonl"))):
            out[f"chunks__{os.path.basename(p)[:-6]}"] = [p]
    if "queries" in kinds:
        for p in sorted(glob.glob(os.path.join(prep_dir, "queries", "*.jsonl"))):
            out[f"queries__{os.path.basename(p)[:-6]}"] = [p]
    if names:
        out = {k: v for k, v in out.items() if any(n in k for n in names)}
    return out


def fp16_agreement(encoder: DenseEncoder, texts: Sequence[str]) -> Record:
    """Cosine between float16 and float32 vectors of the same texts (the run uses float16)."""
    import torch  # type: ignore[import-not-found,unused-ignore]

    model: Any = encoder.backend
    half = encoder.encode_documents(texts, 8)
    model.float()
    full = encoder.encode_documents(texts, 8)
    model.half()
    torch.cuda.empty_cache()
    cos = (half * full).sum(axis=1)
    return {"n": len(texts), "min_cosine": float(cos.min()), "mean_cosine": float(cos.mean())}


def encode_job(
    prep_dir: str,
    enc_root: str,
    encoders: Sequence[str],
    cuts: Sequence[int],
    kinds: Sequence[str],
    names: Sequence[str] | None,
    log_path: str,
    *,
    dtype: str = "float16",
) -> Record:
    """Encode the selected stores with every encoder and cut on the GPU; one JSON run log."""
    import torch  # type: ignore[import-not-found,unused-ignore]

    log: Record = {"gate": cuda_gate(), "hardware": hardware(), "runs": []}
    groups = store_groups(prep_dir, kinds, names)
    for name in encoders:
        for cut in sorted(cuts):
            spec = ENCODERS[name].with_max_tokens(cut)
            t_load = time.perf_counter()
            enc = DenseEncoder.load(spec, device="cuda", dtype=dtype)
            run: Record = {
                "encoder": name,
                "model_id": spec.model_id,
                "revision": model_revision(spec.model_id),
                "max_tokens": cut,
                "dtype": dtype,
                "batch_size": BATCH[name],
                "load_seconds": round(time.perf_counter() - t_load, 1),
                "query_template": spec.query_template,
                "stores": [],
            }
            out_dir = os.path.join(enc_root, f"{name}__t{cut}")
            torch.cuda.reset_peak_memory_stats()
            t0 = time.perf_counter()
            shorter = [c for c in sorted(cuts) if c < cut]
            for store, files in sorted(groups.items()):
                reuse = None
                if shorter:
                    prev = os.path.join(enc_root, f"{name}__t{shorter[-1]}", f"{store}.npz")
                    reuse = (prev, shorter[-1])
                res = encode_store(
                    enc,
                    files,
                    store,
                    out_dir,
                    batch_size=BATCH[name],
                    is_query=store.startswith("queries__"),
                    reuse=reuse,
                )
                run["stores"].append(res)
            run["seconds_total"] = round(time.perf_counter() - t0, 1)
            run["peak_gpu_mem_mb"] = round(torch.cuda.max_memory_allocated() / 2**20, 1)
            sample = _sample_texts(groups, 64, seed=0)
            if sample:
                run["fp16_vs_fp32"] = fp16_agreement(enc, sample)
            run["eos_check"] = _eos_check(enc)
            log["runs"].append(run)
            del enc
            torch.cuda.empty_cache()
            _dump(log_path, log)
    return log


def _eos_check(enc: DenseEncoder) -> Record:
    """Whether the tokenizer appends an end token after the cut (last-token pooling needs it)."""
    tok = enc.backend.tokenizer
    ids = tok(
        ["x " * 5000], add_special_tokens=True, truncation=True, max_length=enc.spec.max_tokens
    )
    last = ids["input_ids"][0][-1]
    return {
        "last_id_after_cut": int(last),
        "eos_token_id": getattr(tok, "eos_token_id", None),
        "sep_token_id": getattr(tok, "sep_token_id", None),
        "length_after_cut": len(ids["input_ids"][0]),
        "default_prompt_name": getattr(enc.backend, "default_prompt_name", None),
    }


def _sample_texts(groups: dict[str, list[str]], n: int, seed: int) -> list[str]:
    unit_stores = [v for k, v in sorted(groups.items()) if k.startswith("units__")]
    if not unit_stores:
        return []
    texts = read_store(unit_stores[0])
    keys = sorted(texts)
    rng = np.random.default_rng(seed)
    pick = rng.choice(len(keys), size=min(n, len(keys)), replace=False)
    return [texts[keys[int(i)]] for i in sorted(pick)]


def _dump(path: str, obj: Record) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(f"{path}.tmp", "w", encoding="utf-8") as handle:
        json.dump(obj, handle, indent=1, sort_keys=True, default=str)
    os.replace(f"{path}.tmp", path)


def measure_job(
    encoder_name: str,
    cut: int,
    prep_dir: str,
    enc_dir: str,
    query_set_dir: str,
    log_dir: str,
    run_log: str,
    *,
    device: str,
    identifiers_store: str,
    word_counts: Sequence[int],
    dev_scale_units: str,
    sample_n: int,
    seed: int = 0,
    threads: int = 4,
) -> Record:
    """Latency (``query_encode``, ``dense_search``) and throughput (``dense_encode``) rows."""
    import torch  # type: ignore[import-not-found,unused-ignore]

    if device == "cuda":
        gate = cuda_gate()
    else:
        torch.set_num_threads(threads)
        gate = {"device": "cpu", "threads": threads}
    spec = ENCODERS[encoder_name].with_max_tokens(cut)
    rss0 = vm_hwm_kb()
    enc = DenseEncoder.load(spec, device=device, dtype="float16" if device == "cuda" else "float32")
    if device == "cuda":
        torch.cuda.reset_peak_memory_stats()
    rss_load = vm_hwm_kb()
    idents = [json.loads(x)["t"] for x in open(identifiers_store, encoding="utf-8")]
    queries = build_issue_like_queries(idents, word_counts, N_QUERIES, seed)
    qid = f"qenc-{encoder_name}-t{cut}-v1"
    queries = write_query_set(Path(query_set_dir) / f"{qid}.txt", queries)
    lat: list[Row] = query_encode_rows(enc, queries, qid, seed)
    qlen = enc.token_lengths([spec.query_text(q) for q in queries])

    # flat exact search: dev scale (real vectors of one snapshot) and django scale
    units_vs = VectorStore([os.path.join(enc_dir, f"units__{dev_scale_units}.npz")])
    qvecs = enc.encode_queries(queries, 8)
    qmap = {q: qvecs[i] for i, q in enumerate(queries)}
    allv = np.concatenate(units_vs.mats)
    with open(os.path.join(prep_dir, "dev_scale.json"), encoding="utf-8") as handle:
        dev_n = int(json.load(handle)["units"])
    scales = {"dev": dev_n, "django": DJANGO_UNITS}
    for scale, rows in scales.items():
        mat = scale_matrix(allv, rows, seed)
        tag = f"dsearch-{encoder_name}-{scale}{'-torch' if device == 'cuda' else ''}-v1"
        write_query_set(Path(query_set_dir) / f"{tag}.txt", queries)
        lat += search_rows(mat, qmap, tag, seed, device=device)

    # throughput on a fixed sample of development unit texts
    texts = _sample_texts({"units__x": [identifiers_store]}, sample_n, seed)
    if device == "cuda":
        torch.cuda.reset_peak_memory_stats()
    repo = os.path.basename(identifiers_store).split(".")[0]
    wl = f"dense-units-{repo}-n{sample_n}-{encoder_name}-t{cut}-v1"
    tput = encode_throughput_rows(enc, texts, wl, 8 if device == "cpu" else 16, seed)
    peak = round(torch.cuda.max_memory_allocated() / 2**20, 1) if device == "cuda" else None
    append_rows(Path(log_dir) / "latency_log.csv", LATENCY_COLUMNS, lat)
    append_rows(Path(log_dir) / "throughput_log.csv", THROUGHPUT_COLUMNS, tput)
    rec: Record = {
        "encoder": encoder_name,
        "max_tokens": cut,
        "device": device,
        "gate": gate,
        "host": platform.node(),
        "revision": model_revision(spec.model_id),
        "query_set": qid,
        "query_tokens": {
            "p50": float(np.percentile(qlen, 50)),
            "p95": float(np.percentile(qlen, 95)),
            "max": int(max(qlen)),
            "share_cut": float(np.mean(np.asarray(qlen) > cut)),
        },
        "scales": scales,
        "dim": int(allv.shape[1]),
        "sample_n": len(texts),
        "throughput_workload": wl,
        "peak_gpu_mem_mb_encode_sample": peak,
        "vm_hwm_kb_before_load": rss0,
        "vm_hwm_kb_after_load": rss_load,
        "vm_hwm_kb_end": vm_hwm_kb(),
        "latency_rows": [
            {
                k: r[k]
                for k in ("query_set_id", "stage", "cache_state", "p50_ms", "p95_ms", "p99_ms", "n")
            }
            for r in lat
        ],
        "throughput_rows": [
            {k: r[k] for k in ("workload_id", "units", "seconds", "units_per_s")} for r in tput
        ],
        "hardware": hardware(),
    }
    _dump(run_log, rec)
    return rec
