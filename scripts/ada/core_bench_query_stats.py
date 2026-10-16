"""Mean query length and candidate-list sizes per CORE-Bench folder, streamed, stdlib only (Ada, Python 3.9).

Why: the card reports "Avg.Q Len" (1,558.5 for L2, 1,074.4 for L3); this measures it from the bytes
(characters of the query `text`, averaged over queries) and records the size of each query's
`filtered_corpus_id` list, which defines the per-query candidate set. Numbers only; no text is kept.
Implements specs/held_out_repos.md acceptance "card vs measured". Idempotent: finished folders skipped.
Usage: core_bench_query_stats.py LISTING.json OUT.json [WORKERS]
"""
# ruff: noqa  (standalone stdlib tool; runs on Ada's python 3.9)

from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

BASE = "https://huggingface.co/datasets/zhangfw123/CORE-Bench/resolve/main/"


def stats(path):
    n = chars = cand_sum = cand_min = cand_max = 0
    cand_min = None
    with urllib.request.urlopen(urllib.request.Request(BASE + path), timeout=120) as resp:
        for line in resp:
            if not line.strip():
                continue
            o = json.loads(line)
            n += 1
            chars += len(o.get("text", ""))
            c = len(o.get("filtered_corpus_id", []))
            cand_sum += c
            cand_max = max(cand_max, c)
            cand_min = c if cand_min is None else min(cand_min, c)
    return dict(
        queries=n, text_chars=chars, cand_sum=cand_sum, cand_min=cand_min, cand_max=cand_max
    )


def work(path):
    for attempt in range(6):
        try:
            return path, stats(path)
        except Exception as exc:  # noqa: BLE001 - retry network errors
            print("retry", path, attempt, repr(exc), file=sys.stderr, flush=True)
            time.sleep(2 ** min(attempt, 5))
    return path, None


def main():
    listing, out = sys.argv[1:3]
    workers = int(sys.argv[3]) if len(sys.argv) > 3 else 4
    done = json.load(open(out)) if os.path.exists(out) else {}
    entries = json.load(open(listing))["entries"]
    size = {e["path"]: e["size"] for e in entries}
    paths = sorted(
        (
            e["path"]
            for e in entries
            if e["type"] == "file"
            and e["path"].endswith("/queries.jsonl")
            and e["path"].split("/")[1] in ("LEVEL-2", "LEVEL-3")
            and e["path"] not in done
        ),
        key=lambda p: -size[p],
    )
    print("todo", len(paths), flush=True)
    t0 = time.time()
    with ThreadPoolExecutor(workers) as ex:
        for i, (p, r) in enumerate(ex.map(work, paths), 1):
            if r is not None:
                done[p] = r
            if i % 50 == 0:
                json.dump(done, open(out, "w"))
                print(i, round(time.time() - t0), "s", flush=True)
    json.dump(done, open(out, "w"))
    print("finished", len(done), round(time.time() - t0), "s", flush=True)


if __name__ == "__main__":
    main()
