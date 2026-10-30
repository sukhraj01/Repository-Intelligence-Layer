"""Build paired dense score artifacts using the existing encoder on the compute cluster."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from ril.evaluation.core_bench import CoreBenchFolder, read_split
from ril.evaluation.rewrite import folder_hashes
from ril.retrieval.dense_encoder import ENCODERS, DenseEncoder, local_snapshot


def write_score_cache(
    path: Path,
    original: CoreBenchFolder,
    rewrite: CoreBenchFolder,
    encoder: DenseEncoder,
    *,
    batch_size: int = 16,
    max_score_bytes: int = 512 * 2**20,
) -> dict[str, Any]:
    """Encode both wordings against one document store, with an explicit score-memory ceiling.

    Two float32 score matrices and the adapter's two float64 copies require at most 24 bytes per
    query-document pair (excluding vectors, model, text and compression buffers). This guard is
    only a score-array bound; measure full peak memory on the target node before scaling.
    """
    if [q.query_id for q in original.queries] != [q.query_id for q in rewrite.queries]:
        raise ValueError("paired query order differs")
    if original.corpus_ids != rewrite.corpus_ids or original.qrels != rewrite.qrels:
        raise ValueError("paired corpus ids and qrels must match")
    score_bytes = 24 * len(original.queries) * len(original.corpus_ids)
    if score_bytes > max_score_bytes or batch_size < 1:
        raise ValueError("score-array memory estimate exceeds ceiling or batch size is invalid")
    documents = encoder.encode_documents(original.corpus_texts, batch_size=batch_size)
    original_queries = encoder.encode_queries(
        [q.text for q in original.queries], batch_size=batch_size
    )
    rewrite_queries = encoder.encode_queries(
        [q.text for q in rewrite.queries], batch_size=batch_size
    )
    metadata = {
        "encoder": encoder.spec.name,
        "revision": encoder.spec.revision,
        "max_tokens": encoder.spec.max_tokens,
        "query_template": encoder.spec.query_template,
        "normalization": "L2, dot-product similarity",
        "score_dtype": "float32",
        "score_memory_bound_bytes": score_bytes,
        **folder_hashes(original, rewrite),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp.npz")
    np.savez_compressed(
        temporary,
        corpus_ids=original.corpus_ids,
        query_ids=[q.query_id for q in original.queries],
        original_scores=original_queries @ documents.T,
        rewrite_scores=rewrite_queries @ documents.T,
        metadata=json.dumps(metadata, sort_keys=True),
    )
    os.replace(temporary, path)
    return metadata


def main() -> None:
    """Cluster-only encoding; cached weights and a working CUDA card are required."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--max-score-bytes", type=int, default=512 * 2**20)
    args = parser.parse_args()
    if os.environ.get("RIL_CLUSTER") != "1":
        raise RuntimeError("encoding runs on the compute cluster; set RIL_CLUSTER=1 there")
    # This entry point is never invoked by local tests or CPU evaluation.
    import importlib

    torch = importlib.import_module("torch")
    if not torch.cuda.is_available():
        raise RuntimeError("a working CUDA card is required")
    torch.ones((2, 2), device="cuda") @ torch.ones((2, 2), device="cuda")
    torch.cuda.synchronize()
    cfg = yaml.safe_load(Path(args.config).read_text())
    spec = ENCODERS[cfg["retriever"]["encoder"]].with_max_tokens(cfg["retriever"]["max_tokens"])
    if cfg["retriever"]["revision"] != spec.revision:
        raise ValueError("configuration revision differs from the pinned encoder")
    encoder = DenseEncoder.load(
        spec, device="cuda", dtype="float16", local_dir=local_snapshot(spec)
    )
    for folder in cfg["folders"]:
        for level in folder["levels"]:
            original = read_split(cfg["data_root"], level, folder["dataset"], folder["folder"])
            rewrite = read_split(
                cfg["data_root"], level, folder["dataset"], folder["folder"], rewrite=True
            )
            path = (
                Path(cfg["retriever"]["cache_root"])
                / level
                / folder["dataset"]
                / f"{folder['folder']}.npz"
            )
            metadata = write_score_cache(
                path,
                original,
                rewrite,
                encoder,
                batch_size=args.batch_size,
                max_score_bytes=args.max_score_bytes,
            )
            metadata["config_sha256"] = hashlib.sha256(Path(args.config).read_bytes()).hexdigest()
            path.with_suffix(".json").write_text(
                json.dumps(metadata, sort_keys=True, indent=2) + "\n"
            )


if __name__ == "__main__":
    main()
