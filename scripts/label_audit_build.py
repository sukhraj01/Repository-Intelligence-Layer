"""Build the pull-request label sheets of the noise audit (draw, extract, sheets).

Usage: python -I scripts/label_audit_build.py STAGE --ranks-bm25 FILE --store DIR --work DIR
           --out DIR --key-dir DIR [--ranks-dense FILE] [--seed N]
STAGE is ``draw``, ``extract``, ``sheets`` or ``all``. ``extract`` needs GITHUB_TOKEN in the
environment (never printed). A thin wrapper around ``ril.evaluation.label_audit_jobs``.
"""

# ruff: noqa: T201

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ril.evaluation import label_audit_jobs as jobs  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("stage", choices=("draw", "extract", "sheets", "all"))
    ap.add_argument("--ranks-bm25", required=True)
    ap.add_argument("--ranks-dense", default=None)
    ap.add_argument("--store", required=True, help="mined store root (cas/ and pr/)")
    ap.add_argument("--work", required=True, help="scratch directory (materialised directories)")
    ap.add_argument("--out", type=Path, required=True, help="sheets and sample record")
    ap.add_argument("--key-dir", type=Path, required=True, help="key file (readers never see it)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--per-stratum", type=int, default=200)
    ap.add_argument("--overlap", type=int, default=100)
    a = ap.parse_args()

    def log(msg: str) -> None:
        print(msg, flush=True)

    d, doc = jobs.draw_job(
        a.ranks_bm25, a.ranks_dense, seed=a.seed, per_stratum=a.per_stratum, overlap_total=a.overlap
    )
    a.out.mkdir(parents=True, exist_ok=True)
    a.key_dir.mkdir(parents=True, exist_ok=True)
    raw = a.key_dir / "pairs_raw.jsonl"
    if a.stage in ("draw", "all"):
        print(json.dumps(doc, indent=1, sort_keys=True))
    if a.stage in ("extract", "all"):
        from ril.data_mining.github_api import (
            ApiClient,
            ClientConfig,
            UrllibTransport,
            token_from_env,
        )
        from ril.data_mining.snapshot import GitSnapshots

        if token_from_env() is None:
            print("BLOCKED: GITHUB_TOKEN is not set")
            return 3
        client = ApiClient(UrllibTransport(), token=token_from_env(), config=ClientConfig())
        snapshots = GitSnapshots(str(Path(a.work) / "git"), workers=2)
        try:
            res = jobs.extract_job(
                d, a.store, a.work, str(raw), client=client, snapshots=snapshots, log=log
            )
        finally:
            snapshots.close()
        doc["extraction"] = res
        doc["api_budget"] = client.budget.to_dict()
    if a.stage in ("sheets", "all"):
        res = jobs.sheets_job(d, str(raw), str(a.out), str(a.key_dir))
        doc["sheets"] = res
        doc["truncation_rules"] = dict(jobs.truncation_rules())
        (a.out / "sample_meta.json").write_text(
            json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(json.dumps(res, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
