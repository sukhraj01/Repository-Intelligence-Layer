"""Per-repository instance counts for candidate training pools that expose a repository identifier.

Why: the disjointness filter needs (repository, count) pairs for each pool that can be repo-filtered;
this derives them without keeping any pool content. Two pools:
  csn      CodeSearchNet python parquet files (column `repository_name`), read with pyarrow
  gangiswag  directory names inside the `gangiswag/train_data` train.zip central directory
           (`train/python/<owner>__<name>-<PR>/`), listed earlier by zip_remote_listing.py;
           candidate and provisional (Open question Q7), repository names come from directory names.
Implements specs/held_out_repos.md "Inputs" (candidate pools). Idempotent: reuses downloaded parquet.
Usage: pool_repo_counts.py csn WORKDIR OUT.json | pool_repo_counts.py gangiswag ZIPLIST.json OUT.json
"""
# ruff: noqa  (standalone tool; prints to stdout by design)

from __future__ import annotations

import json
import os
import re
import sys
import urllib.request
from collections import Counter

CSN = "https://huggingface.co/datasets/code-search-net/code_search_net/resolve/main/python/"
FILES = [
    "train-00000-of-00001.parquet",
    "validation-00000-of-00001.parquet",
    "test-00000-of-00001.parquet",
]


def fetch(url: str, dest: str) -> None:
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        return
    with urllib.request.urlopen(url, timeout=120) as r, open(dest + ".part", "wb") as o:
        while True:
            b = r.read(1 << 20)
            if not b:
                break
            o.write(b)
    os.replace(dest + ".part", dest)


def csn(workdir: str, out: str) -> None:
    import pyarrow.parquet as pq

    os.makedirs(workdir, exist_ok=True)
    per_split, total = {}, Counter()
    for f in FILES:
        dest = os.path.join(workdir, f)
        fetch(CSN + f, dest)
        t = pq.read_table(dest, columns=["repository_name"])
        c = Counter(t.column("repository_name").to_pylist())
        per_split[f.split("-")[0]] = {
            "rows": t.num_rows,
            "repos": len(c),
            "bytes": os.path.getsize(dest),
        }
        total.update(c)
    json.dump(
        {
            "pool": "code-search-net/code_search_net python",
            "splits": per_split,
            "rows": sum(total.values()),
            "repos": dict(sorted(total.items())),
        },
        open(out, "w"),
        indent=0,
    )
    print(per_split, sum(total.values()), len(total))


def gangiswag(ziplist: str, out: str) -> None:
    d = json.load(open(ziplist))
    pat = re.compile(r"^train/([^/]+)/([^/]+)/$")
    per_lang: dict = {}
    for m in d["members"]:
        g = pat.match(m["name"])
        if not g:
            continue
        lang, inst = g.groups()
        per_lang.setdefault(lang, []).append(inst)
    py = per_lang["python"]
    repos = Counter()
    unparsed = []
    for inst in py:
        base = inst.rsplit("-", 1)[0] if re.search(r"-\d+$", inst) else None
        if base is None or "__" not in base:
            unparsed.append(inst)
            continue
        owner, name = base.split("__", 1)
        repos[owner + "/" + name] += 1
    json.dump(
        {
            "pool": "gangiswag/train_data train.zip python (candidate, Q7)",
            "instances_all_languages": {k: len(v) for k, v in sorted(per_lang.items())},
            "python_instance_dirs": len(py),
            "python_repos": len(repos),
            "unparsed": unparsed,
            "repos": dict(sorted(repos.items())),
        },
        open(out, "w"),
        indent=0,
    )
    print(len(py), len(repos), len(unparsed))


if __name__ == "__main__":
    {"csn": csn, "gangiswag": gangiswag}[sys.argv[1]](sys.argv[2], sys.argv[3])
