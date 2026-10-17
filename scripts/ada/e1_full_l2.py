"""Chunk-level BM25 over every original L2 folder, one folder at a time (pilot E1, exploratory).

Why: the benchmark card's BM25 reference (nDCG@10 13.0, Recall@100 38.8) averages all 5,061 L2
queries; a like-for-like comparison needs every folder. Disk is limited, so each folder is fetched,
scored and deleted. Resumable: a folder whose output exists with the same configuration hash is
skipped. Needs ~/ril_s2/scripts/hf_fetch.py and ~/ril_s2/raw/listing_root.json.

Usage: e1_full_l2.py CONFIG LISTING HF_FETCH RAW_DIR OUT_DIR
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ril.evaluation.e1_run import config_hash, load_config, run_chunk_level  # noqa: E402
from ril.util.log import get_logger  # noqa: E402


def main() -> int:
    cfg_path, listing, hf_fetch, raw_dir, out_dir = sys.argv[1:6]
    cfg = load_config(cfg_path)
    log = get_logger("e1_full_l2")
    log.info("config hash %s, %d folders", config_hash(cfg), len(cfg["folders"]))
    failed = 0
    for i, spec in enumerate(cfg["folders"]):
        key = f"{spec['dataset']}__{spec['folder']}"
        out = os.path.join(out_dir, "chunk", f"L2__{key}.json")
        if os.path.exists(out):
            continue
        prefix = f"data/LEVEL-2/{spec['dataset']}/{spec['folder']}/"
        done = subprocess.run(
            [sys.executable, hf_fetch, "zhangfw123/CORE-Bench", listing, raw_dir, prefix],
            capture_output=True,
            text=True,
        )
        if done.returncode != 0:
            log.error("fetch failed for %s: %s", prefix, done.stderr[-300:])
            failed += 1
            continue
        try:
            run_chunk_level(cfg, raw_dir, out_dir, only=f"{spec['dataset']}/{spec['folder']}")
        finally:
            shutil.rmtree(
                os.path.join(raw_dir, "data", "LEVEL-2", spec["dataset"], spec["folder"]), True
            )
        if i % 20 == 0:
            log.info("folder %d of %d (%s)", i + 1, len(cfg["folders"]), key)
    log.info("failed folders: %d", failed)
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
