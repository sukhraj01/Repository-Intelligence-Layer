"""Unit records, BM25 caches and text stores of the executable subset of Verified. Thin wrapper.

Usage (cluster, from the work directory):
  rq3_units.py inputs SUBSET.json VERIFIED.parquet META.json QUERIES.json
  rq3_units.py prepare CONFIG DATA_ROOT META QUERIES REPO_CACHE CACHE E1_DIR WORK OUT [--shard I K]
  rq3_units.py prep-units CONFIG META REPO_CACHE CACHE WORK PREP [--shard I K]
  rq3_units.py prep-queries OUT PREP
  rq3_units.py count PREP OUT.json [--already STORE_DIR ...]
  rq3_units.py score PREP ENC_DIR OUT_DIR [--cut 512]
  rq3_units.py check PREP ENC_DIR OUT.json [--extra FILE ...]
Implements ``docs/RQ3_PILOT.md`` (D107). Logic lives in ``ril/evaluation/rq3_units.py``.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ril.util.log import get_logger  # noqa: E402
from ril.util.seed import set_seed  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "stage",
        choices=["inputs", "prepare", "prep-units", "prep-queries", "count", "score", "check"],
    )
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--shard", nargs=2, type=int, default=[0, 1])
    ap.add_argument("--already", nargs="*", default=[])
    ap.add_argument("--extra", nargs="*", default=[])
    ap.add_argument("--cut", type=int, default=512)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    set_seed(args.seed)
    log = get_logger("rq3_units")
    from ril.evaluation import rq3_units as ru

    shard = (args.shard[0], args.shard[1])
    if args.stage == "inputs":
        subset_path, parquet, meta_out, queries_out = args.paths
        import pyarrow.parquet as pq

        subset = json.loads(Path(subset_path).read_text(encoding="utf-8"))
        rows = pq.read_table(parquet).to_pylist()
        meta, queries = ru.build_inputs(subset, rows)
        Path(meta_out).write_text(json.dumps(meta, sort_keys=True), encoding="utf-8")
        Path(queries_out).write_text(json.dumps(queries, sort_keys=True), encoding="utf-8")
        log.info("inputs for %d members", len(meta))
        return 0
    if args.stage == "prepare":
        cfg, data_root, meta_p, queries_p, repo_cache, cache, e1_dir, work, out = args.paths
        meta = json.loads(Path(meta_p).read_text(encoding="utf-8"))
        queries = json.loads(Path(queries_p).read_text(encoding="utf-8"))
        fails = ru.prepare_members(
            cfg, data_root, meta, queries, repo_cache, cache, e1_dir, work, out, shard=shard
        )
        log.info("failures: %d", len(fails))
        return 0 if not fails else 2
    if args.stage == "prep-units":
        cfg, meta_p, repo_cache, cache, work, prep = args.paths
        meta = json.loads(Path(meta_p).read_text(encoding="utf-8"))
        res = ru.prepare_unit_texts(cfg, meta, repo_cache, cache, work, prep, shard=shard)
        Path(prep, f"prep_units_s{shard[0]}.json").write_text(
            json.dumps(res, indent=1), encoding="utf-8"
        )
        log.info("prepared %d, failures %d", res["prepared"], len(res["failures"]))
        return 0 if not res["failures"] else 2
    if args.stage == "prep-queries":
        out, prep = args.paths
        res = ru.prepare_query_store(out, prep)
        Path(prep, "prep_queries.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
        return 0
    if args.stage == "count":
        prep, out_json = args.paths
        already: set[str] = set()
        for d in args.already:
            for p in sorted(glob.glob(os.path.join(d, "*.jsonl"))):
                already.update(ru.read_store([p]))
        res = ru.distinct_counts(prep, already)
        res["texts_in_stores"] = ru.store_texts(prep)
        res["rule"] = ru.encoding_rule(res["distinct_to_encode"], res["distinct_texts"])
        Path(out_json).write_text(json.dumps(res, indent=1, sort_keys=True), encoding="utf-8")
        log.info("%s", json.dumps(res["rule"]))
        return 0
    if args.stage == "score":
        prep, enc_dir, out_dir = args.paths
        res = ru.score_members(prep, enc_dir, out_dir, args.cut)
        log.info("scored %d, missing store %d", res["scored"], len(res["missing_store"]))
        return 0 if not res["missing_store"] else 2
    prep, enc_dir, out_json = args.paths
    res = ru.missing_vectors(prep, enc_dir, args.extra)
    Path(out_json).write_text(json.dumps(res, indent=1, sort_keys=True), encoding="utf-8")
    log.info("checked %d texts, missing %d", res["texts_checked"], res["missing"])
    return 0 if res["missing"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
