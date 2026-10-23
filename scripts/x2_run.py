"""Dense and fusion measurements X2: cluster stages and local evaluation. Thin wrapper.

Usage (cluster, from the work directory):
  x2_run.py prep-units E1_CONFIG META_JSON REPO_CACHE E3_CACHE WORK_DIR PREP_DIR
            --roles dev [test] [--shard I K]
  x2_run.py prep-queries E1_CONFIG DATA_ROOT E3_CACHE PREP_DIR --roles dev test
  x2_run.py prep-chunks E1_CONFIG DATA_ROOT PREP_DIR --roles dev [test]
  x2_run.py encode PREP_DIR ENC_ROOT LOG_JSON --encoders NAME.. --cuts 512 1024
            --kinds units queries
            [--names SUBSTR..]
  x2_run.py score-units PREP_DIR ENC_DIR OUT_DIR --cut N --roles dev [test]
  x2_run.py score-chunks E1_CONFIG DATA_ROOT OUT_DIR --variants NAME=ENC_DIR.. --roles dev [test]
  x2_run.py measure ENCODER CUT PREP_DIR ENC_DIR QUERY_SET_DIR LOG_DIR RUN_LOG --device cpu|cuda
            --store REPO_DIR --sample N
Stores on the cluster hold text; outputs hold scores, ranks, hashes and counts.
"""

from __future__ import annotations

import argparse
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
        choices=[
            "prep-units",
            "prep-queries",
            "prep-chunks",
            "encode",
            "score-units",
            "score-chunks",
            "measure",
        ],
    )
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--roles", nargs="+", default=["dev"])
    ap.add_argument("--shard", nargs=2, type=int, default=[0, 1])
    ap.add_argument("--encoders", nargs="+", default=[])
    ap.add_argument("--cuts", nargs="+", type=int, default=[512])
    ap.add_argument("--cut", type=int, default=512)
    ap.add_argument("--kinds", nargs="+", default=["units", "queries"])
    ap.add_argument("--names", nargs="*", default=None)
    ap.add_argument("--variants", nargs="*", default=[])
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--store", default="")
    ap.add_argument("--sample", type=int, default=128)
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    set_seed(args.seed)
    log = get_logger("x2")
    roles = set(args.roles)
    from ril.evaluation import x2_dense as xd

    if args.stage == "prep-units":
        e1_cfg, meta_json, repo_cache, e3_cache, work_dir, prep_dir = args.paths
        with open(meta_json, encoding="utf-8") as handle:
            meta = json.load(handle)
        res = xd.prepare_units(
            e1_cfg,
            roles,
            meta,
            repo_cache,
            e3_cache,
            work_dir,
            prep_dir,
            shard=(args.shard[0], args.shard[1]),
        )
        path = os.path.join(prep_dir, f"prep_units_s{args.shard[0]}.json")
        Path(path).write_text(json.dumps(res, indent=1), encoding="utf-8")
        log.info("prepared %d, failures %d", res["prepared"], len(res["failures"]))
    elif args.stage == "prep-queries":
        e1_cfg, data_root, e3_cache, prep_dir = args.paths
        res = xd.prepare_queries(e1_cfg, roles, data_root, prep_dir)
        res["dev_l2_issue_word_counts"] = xd.issue_word_counts(e1_cfg, data_root)
        Path(prep_dir, "prep_queries.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
        Path(prep_dir, "dev_scale.json").write_text(
            json.dumps(xd.dev_scale(e3_cache)), encoding="utf-8"
        )
    elif args.stage == "prep-chunks":
        e1_cfg, data_root, prep_dir = args.paths
        res = xd.prepare_chunks(e1_cfg, roles, data_root, prep_dir)
        name = "_".join(sorted(roles))
        Path(prep_dir, f"prep_chunks_{name}.json").write_text(
            json.dumps(res, indent=1), encoding="utf-8"
        )
    elif args.stage == "encode":
        from ril.evaluation.x2_jobs import encode_job

        prep_dir, enc_root, log_json = args.paths
        encode_job(prep_dir, enc_root, args.encoders, args.cuts, args.kinds, args.names, log_json)
    elif args.stage == "score-units":
        prep_dir, enc_dir, out_dir = args.paths
        res = xd.score_units(prep_dir, enc_dir, out_dir, args.cut, roles=roles)
        log.info("scored %d, missing store %d", res["scored"], len(res["missing_store"]))
    elif args.stage == "score-chunks":
        e1_cfg, data_root, out_dir = args.paths
        variants = dict(v.split("=", 1) for v in args.variants)
        res = xd.score_chunks(e1_cfg, roles, data_root, variants, out_dir)
        log.info("chunk folders scored: %d", res["folders_scored"])
    elif args.stage == "measure":
        from ril.evaluation.x2_jobs import measure_job

        encoder, cut, prep_dir, enc_dir, qs_dir, log_dir, run_log = args.paths
        with open(os.path.join(prep_dir, "prep_queries.json"), encoding="utf-8") as handle:
            counts = json.load(handle)["dev_l2_issue_word_counts"]
        store = sorted(Path(prep_dir, "texts_units").glob(f"{args.store}.s*.jsonl"))[0]
        measure_job(
            encoder,
            int(cut),
            prep_dir,
            enc_dir,
            qs_dir,
            log_dir,
            run_log,
            device=args.device,
            identifiers_store=str(store),
            word_counts=counts,
            dev_scale_units=args.store,
            sample_n=args.sample,
            seed=args.seed,
            threads=args.threads,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
