"""Derive per-level/per-dataset size and count tables from the CORE-Bench tree listing and manifest.

Why: answers Q6 (disk) and the repo-naming question without touching dataset text. Reads
data/raw/core_bench/{listing_tree,manifest}.json (untracked), writes counts and byte sizes to results/tables/ (the per-folder size list stays beside the raw files). Run with `python3 -I`. Implements specs/held_out_repos.md "Inputs".
"""
# ruff: noqa  (standalone stdlib tool; runs on Ada's python 3.9, prints to stdout by design)

from __future__ import annotations

import collections
import csv
import json
import sys
from pathlib import Path

RAW = Path(sys.argv[1])
OUT = Path(sys.argv[2])
listing = json.loads((RAW / "listing_tree.json").read_text())["entries"]
manifest = json.loads((RAW / "manifest.json").read_text())

bytes_by = collections.defaultdict(lambda: collections.Counter())
folders = collections.defaultdict(set)
folder_rows = []
for e in listing:
    if e["type"] != "file" or not e["path"].startswith("data/"):
        continue
    p = e["path"].split("/")
    lvl, ds, repo, fn = p[1], p[2], p[3], "/".join(p[4:])
    key = (lvl, ds)
    bytes_by[key][fn] += e["size"]
    folders[key].add(repo)
    folder_rows.append((lvl, ds, repo, fn, e["size"]))

with open(OUT / "core_bench_listing_summary.csv", "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(
        [
            "level",
            "dataset",
            "folders",
            "folders_without_double_underscore",
            "corpus_bytes",
            "queries_bytes",
            "qrels_jsonl_bytes",
            "qrels_tsv_bytes",
            "total_bytes",
        ]
    )
    for key in sorted(bytes_by):
        b = bytes_by[key]
        odd = sum("__" not in r for r in folders[key])
        w.writerow(
            [
                *key,
                len(folders[key]),
                odd,
                b["corpus.jsonl"],
                b["queries.jsonl"],
                b["qrels.jsonl"],
                b["qrels/test.tsv"],
                sum(b.values()),
            ]
        )

with open(RAW / "folder_sizes.csv", "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["level", "dataset", "folder", "file", "bytes"])
    w.writerows(sorted(folder_rows))

with open(OUT / "core_bench_manifest_counts.csv", "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["level", "dataset", "repos", "queries", "corpus", "qrels", "positive_qrels"])
    for lvl, l in manifest["levels"].items():
        for ds, dd in sorted(l["datasets"].items()):
            c = collections.Counter()
            for v in dd["repos"].values():
                c.update(v)
            w.writerow(
                [
                    lvl,
                    ds,
                    len(dd["repos"]),
                    c["queries"],
                    c["corpus"],
                    c["qrels"],
                    c["positive_qrels"],
                ]
            )

tot = sum(sum(b.values()) for b in bytes_by.values())
l23 = sum(sum(b.values()) for k, b in bytes_by.items() if k[0] in ("LEVEL-2", "LEVEL-3"))
print(
    json.dumps(
        {
            "total_data_bytes": tot,
            "level2_level3_only_bytes": l23,
            "folders_total": sum(len(v) for v in folders.values()),
        }
    )
)
