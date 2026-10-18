"""Export instance id, repository, base commit and creation date of SWE-bench Verified (no text).

Why: the pool check compares pool (repository, PR) pairs and base commits with Verified; the large
text columns stay on the cluster. Needs pyarrow. Usage: pool_check_ref.py PARQUET OUT.json
"""
# ruff: noqa  (standalone cluster tool)

from __future__ import annotations

import json
import sys

import pyarrow.parquet as pq

t = pq.read_table(sys.argv[1], columns=["instance_id", "repo", "base_commit", "created_at"])
rows = t.to_pydict()
out = {
    i: {"repo": r, "base_commit": b, "created_at": str(c)}
    for i, r, b, c in zip(
        rows["instance_id"], rows["repo"], rows["base_commit"], rows["created_at"]
    )
}
json.dump(out, open(sys.argv[2], "w"), indent=0, sort_keys=True)
print("verified rows", len(out))
