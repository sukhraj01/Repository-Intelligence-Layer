"""Pool-rank measurement (E-POOL-RANKS): thin command line over ``ril.training.pool_rank_jobs``.

Subcommands (logic in ``ril/``):
  sample META HELD_OUT RENAME_CACHE OUT --per-stratum N --seed S [--bins B]
  bm25   LISTING OUT [--sample SAMPLE | --meta META] [--form code|pool] [--shard I N]
  dense  LISTING OUT LOG --teachers T [T ...] --cut C [--sample SAMPLE | --meta META] [--shard I N]
  dedup  LISTING META OUT --repos-per-bin N --seed S
  tables SAMPLE RANKS [RANKS ...] --config CONFIG --out-dir DIR [--dedup DEDUP]
         [--dense-log LOG ...]
         [--pool-sample POOL_SAMPLE]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sample")
    s.add_argument("meta")
    s.add_argument("held_out")
    s.add_argument("rename_cache")
    s.add_argument("out")
    s.add_argument("--per-stratum", type=int, required=True)
    s.add_argument("--seed", type=int, required=True)
    s.add_argument("--bins", type=int, default=4)
    for name in ("bm25", "dense"):
        q = sub.add_parser(name)
        q.add_argument("listing")
        q.add_argument("out")
        if name == "dense":
            q.add_argument("log")
            q.add_argument("--teachers", nargs="+", required=True)
            q.add_argument("--cut", type=int, required=True)
            q.add_argument("--batch-size", type=int, default=64)
        q.add_argument("--sample")
        q.add_argument("--meta")
        q.add_argument("--form", default="code")
        q.add_argument("--seed", type=int, default=0)
        q.add_argument("--shard", type=int, nargs=2, default=[0, 1])
        q.add_argument("--ahead", type=int, default=4)
    d = sub.add_parser("dedup")
    d.add_argument("listing")
    d.add_argument("meta")
    d.add_argument("out")
    d.add_argument("--repos-per-bin", type=int, required=True)
    d.add_argument("--seed", type=int, required=True)
    t = sub.add_parser("tables")
    t.add_argument("sample")
    t.add_argument("ranks", nargs="+")
    t.add_argument("--config", required=True)
    t.add_argument("--out-dir", required=True)
    t.add_argument("--dedup")
    t.add_argument("--dense-log", nargs="*", default=[])
    t.add_argument("--pool-sample")
    a = p.parse_args(argv)

    if a.cmd == "tables":
        from ril.analysis.x3_tables import write_tables

        res = write_tables(
            a.sample, a.ranks, a.config, a.out_dir, a.dedup, a.dense_log, a.pool_sample
        )
        sys.stdout.write(json.dumps(res, indent=1, sort_keys=True) + "\n")
        return 0
    from ril.training import pool_rank_jobs as jobs

    if a.cmd == "sample":
        doc = jobs.sample_job(
            a.meta,
            a.held_out,
            a.rename_cache,
            a.out,
            per_stratum=a.per_stratum,
            seed=a.seed,
            bins=a.bins,
        )
        res = {
            k: doc[k]
            for k in ("pool_instances", "pool_strata", "sample_strata", "size_edges_corpus_bytes")
        }
    elif a.cmd == "bm25":
        res = jobs.bm25_job(
            a.listing,
            a.out,
            sample_path=a.sample,
            meta_path=a.meta,
            form=a.form,
            seed=a.seed,
            shard=a.shard[0],
            shards=a.shard[1],
            ahead=a.ahead,
        )
    elif a.cmd == "dense":
        res = jobs.dense_job(
            a.listing,
            a.out,
            a.log,
            teachers=a.teachers,
            cut=a.cut,
            sample_path=a.sample,
            meta_path=a.meta,
            form=a.form,
            seed=a.seed,
            shard=a.shard[0],
            shards=a.shard[1],
            ahead=a.ahead,
            batch_size=a.batch_size,
        )
    else:
        res = jobs.dedup_job(a.listing, a.meta, a.out, repos_per_bin=a.repos_per_bin, seed=a.seed)
    sys.stdout.write(json.dumps(res, indent=1, sort_keys=True, default=str) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
