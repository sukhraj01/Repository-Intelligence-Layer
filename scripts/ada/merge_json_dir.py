"""Merge a directory tree of per-folder JSON files into one JSON object keyed by relative path.

Why: some CORE-Bench folders differ only by letter case (for example two spellings of one
repository inside one dataset), which collide on case-insensitive filesystems such as macOS, so
per-folder files cannot be copied to a laptop safely. One merged file keeps the keys distinct.
Usage: merge_json_dir.py DIR OUT.json
"""
# ruff: noqa  (standalone tool)

import json
import os
import sys

root, out = sys.argv[1:3]
merged = {}
for r, _, files in os.walk(root):
    for f in files:
        if f.endswith(".json"):
            p = os.path.join(r, f)
            merged[os.path.relpath(p, root)[: -len(".json")]] = json.load(open(p))
json.dump(merged, open(out, "w"), sort_keys=True)
print(out, len(merged), os.path.getsize(out))
