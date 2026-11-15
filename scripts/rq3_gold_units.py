"""Units edited by the reference patch, per instance (CPU, no model call).

  rq3_gold_units.py PARQUET SUBSET REPO_CACHE OUT.json [--seed N]

Reads the patch column of the benchmark table, the base-commit text of each edited file from the
bare repository cache, and writes the gold unit ids per instance. Thin wrapper; logic in
``ril/analysis/rq3_gold_units.py``. Implements ``docs/experiments/B.md``
E-RQ3-FAILURE-BREAKDOWN.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ril.analysis.rq3_gold_units import (  # noqa: E402
    GOLD_UNITS_VERSION,
    ReadBase,
    gold_units_all,
    summarise,
)
from ril.util.log import get_logger  # noqa: E402
from ril.util.seed import set_seed  # noqa: E402

log = get_logger("rq3_gold_units")


def _reader(cache: str, base: dict[str, str]) -> Callable[[str, str], ReadBase]:
    def make(iid: str, repo: str) -> ReadBase:
        bare = os.path.join(cache, repo.replace("/", "__") + ".git")

        def read(path: str) -> str | None:
            res = subprocess.run(
                ["git", "--git-dir", bare, "show", f"{base[iid]}:{path}"],
                capture_output=True,
                check=False,
            )
            return res.stdout.decode("utf-8", "replace") if res.returncode == 0 else None

        return read

    return make


def main(argv: list[str] | None = None) -> int:
    import pyarrow.parquet as pq

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("parquet")
    ap.add_argument("subset")
    ap.add_argument("repo_cache")
    ap.add_argument("out")
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args(argv)
    set_seed(a.seed)
    subset = json.loads(Path(a.subset).read_text(encoding="utf-8"))
    ids = [str(e["instance_id"]) if isinstance(e, dict) else str(e) for e in subset["executable"]]
    table = pq.read_table(
        os.path.expanduser(a.parquet), columns=["instance_id", "repo", "base_commit", "patch"]
    ).to_pylist()
    rows = {str(r["instance_id"]): r for r in table if str(r["instance_id"]) in set(ids)}
    missing = [i for i in ids if i not in rows]
    if missing:
        log.error("refused: %d instances without a patch row", len(missing))
        return 3
    patches = {i: (str(rows[i]["repo"]), str(rows[i]["patch"])) for i in ids}
    base = {i: str(rows[i]["base_commit"]) for i in ids}
    out = gold_units_all(patches, _reader(os.path.expanduser(a.repo_cache), base))
    record = {
        "version": GOLD_UNITS_VERSION,
        "source": "reference patch mapped onto base-commit units (ril.data_mining.mapping, D63)",
        "instances": out,
        "summary": summarise(out, ids),
    }
    Path(a.out).write_text(json.dumps(record, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    log.info("summary %s", json.dumps(record["summary"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
