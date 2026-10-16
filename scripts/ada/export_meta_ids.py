"""Export (repo, instance_id) pairs from the SWE-bench Verified and Loc-Bench parquet files.

Why: the held-out list and the paired analysis need only repository names and instance ids; this
keeps the large text columns (patches, issue text) out of every file that leaves the cluster.
Implements specs/held_out_repos.md "Inputs". Needs pyarrow (python3 -m venv venv_pa; pip install pyarrow).
Usage: export_meta_ids.py OUT.json PARQUET [PARQUET ...]   (key = parent-directory name of 'data')
"""
# ruff: noqa  (standalone tool)

from __future__ import annotations

import json
import os
import sys

import pyarrow.parquet as pq

out = {}
for path in sys.argv[2:]:
    t = pq.read_table(path, columns=["repo", "instance_id"])
    key = os.path.basename(os.path.dirname(os.path.dirname(path))) + "/" + os.path.basename(path)
    out[key] = {
        "rows": t.num_rows,
        "pairs": sorted(zip(t.column("repo").to_pylist(), t.column("instance_id").to_pylist())),
    }
json.dump(out, open(sys.argv[1], "w"), indent=0)
print({k: v["rows"] for k, v in out.items()})
