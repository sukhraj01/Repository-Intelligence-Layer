"""Count distinct unit texts and characters over a spread of snapshots per repository (no model).

Usage: e6_count.py CACHE_DIR META_JSON REPO_CACHE WORK_DIR PER_REPO
"""

from __future__ import annotations

import glob
import json
import os
import sys
from collections import defaultdict

from ril.evaluation.chunk_unit_pilot import checkout_commit
from ril.evaluation.e3_prepare import read_cache
from ril.evaluation.e6_dense import text_hash
from ril.parsing.repository_parser import ParseOptions, parse_repository

cache_dir, meta_json, repo_cache, work_dir, per_repo = sys.argv[1:6]
meta = json.load(open(meta_json))
by_repo: dict[str, list[tuple[str, str]]] = defaultdict(list)
for p in sorted(glob.glob(os.path.join(cache_dir, "*.npz"))):
    _, m = read_cache(p)
    if m["role"] == "dev":
        by_repo[m["repo_id"]].append((m["instance"], m["base_commit"]))
for repo, items in sorted(by_repo.items()):
    k = int(per_repo)
    step = max(1, len(items) // k)
    chosen = items[::step][:k]
    seen: dict[str, int] = {}
    per_snapshot = []
    for _, commit in chosen:
        rd = repo.replace("/", "__")
        work = os.path.join(work_dir, rd + "__cnt")
        if checkout_commit(os.path.join(repo_cache, rd + ".git"), work, commit) != "ok":
            continue
        units = parse_repository(work, repo, options=ParseOptions(class_source="full")).units
        per_snapshot.append(len(units))
        for u in units:
            seen.setdefault(text_hash(u.source), len(u.source))
    chars = sum(seen.values())
    sys.stdout.write(
        json.dumps(
            {
                "repo": repo,
                "instances": len(items),
                "sampled": len(chosen),
                "units_per_snapshot": per_snapshot,
                "distinct_texts": len(seen),
                "chars": chars,
                "mean_chars": round(chars / max(len(seen), 1)),
            }
        )
        + "\n"
    )
