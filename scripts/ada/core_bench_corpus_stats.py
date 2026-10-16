"""Count corpus rows and chunk lengths per CORE-Bench folder by streaming, stdlib only (Ada, Python 3.9).

Why: the card's corpus-chunk totals (9,377,120 L2; 2,609,581 L3) and the paper's mean chunk length are
the only headline statistics that the manifest alone cannot verify; this reads the real corpus.jsonl
bytes once and keeps numbers only (rows, characters, id length classes), never text.
Implements specs/held_out_repos.md acceptance "card vs measured". Idempotent: finished folders skipped.
Usage: core_bench_corpus_stats.py LISTING.json OUT_DIR [WORKERS]
"""
# ruff: noqa  (standalone stdlib tool; runs on Ada's python 3.9, prints to stdout by design)

from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

BASE = "https://huggingface.co/datasets/zhangfw123/CORE-Bench/resolve/main/"


def stats(path: str):
    rows = chars = maxc = 0
    bad = 0
    ids = set()
    uuid_like = 0
    nbytes = 0
    with urllib.request.urlopen(urllib.request.Request(BASE + path), timeout=120) as resp:
        for line in resp:
            nbytes += len(line)
            if not line.strip():
                continue
            o = json.loads(line)
            t = o.get("text")
            _id = o.get("_id")
            if not isinstance(t, str) or not isinstance(_id, str):
                bad += 1
                continue
            rows += 1
            n = len(t)
            chars += n
            maxc = max(maxc, n)
            ids.add(_id)
            if len(_id) == 36 and _id.count("-") == 4:
                uuid_like += 1
    return dict(
        rows=rows,
        chars=chars,
        max_chars=maxc,
        bad_rows=bad,
        distinct_ids=len(ids),
        uuid_like_ids=uuid_like,
        bytes=nbytes,
    )


def work(job):
    path, out_dir = job
    rel = path[len("data/") :]
    out = os.path.join(out_dir, rel + ".json")
    if os.path.exists(out):
        return rel, "skip"
    for attempt in range(6):
        try:
            res = stats(path)
            break
        except Exception as exc:  # noqa: BLE001 - retry network errors
            print("retry", rel, attempt, repr(exc), file=sys.stderr, flush=True)
            time.sleep(2 ** min(attempt, 5))
    else:
        return rel, "FAILED"
    res["path"] = path
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out + ".tmp", "w") as fh:
        json.dump(res, fh)
    os.replace(out + ".tmp", out)
    return rel, "ok"


def main() -> None:
    listing, out_dir = sys.argv[1], sys.argv[2]
    workers = int(sys.argv[3]) if len(sys.argv) > 3 else 4
    entries = json.load(open(listing))["entries"]
    paths = sorted(
        e["path"]
        for e in entries
        if e["type"] == "file"
        and e["path"].endswith("/corpus.jsonl")
        and e["path"].split("/")[1] in ("LEVEL-2", "LEVEL-3")
    )
    # biggest first keeps the tail short
    size = {e["path"]: e["size"] for e in entries}
    paths.sort(key=lambda p: -size[p])
    print("corpus files", len(paths), "bytes", sum(size[p] for p in paths), flush=True)
    t0 = time.time()
    done = 0
    with ThreadPoolExecutor(workers) as ex:
        for rel, status in ex.map(work, [(p, out_dir) for p in paths]):
            done += 1
            if done % 25 == 0 or status == "FAILED":
                print(done, rel, status, round(time.time() - t0), "s", flush=True)
    print("finished", round(time.time() - t0), "s", flush=True)


if __name__ == "__main__":
    main()
