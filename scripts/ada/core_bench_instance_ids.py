"""Stream CORE-Bench query ids and qrels query ids per folder, stdlib only (Ada, Python 3.9).

Why: CORE-Bench folder names are truncated and are not repository names, so the canonical repository
of a folder has to be read from the instance ids inside it. queries.jsonl is dominated by per-query
candidate id lists (up to 174 MB per Verified folder); this script streams each file, keeps only the
`_id` of every row, and never stores query text or candidate lists.
Implements specs/held_out_repos.md "Inputs". Idempotent: a folder whose output file exists is skipped.
Usage: core_bench_instance_ids.py LISTING.json OUT_DIR [WORKERS]
Output: OUT_DIR/<level>/<dataset>/<folder>.json with
  {queries_ids, queries_rows, queries_bytes, qrels_rows, qrels_query_ids: {id: n_positives}, ...}
"""
# ruff: noqa  (standalone stdlib tool; runs on Ada's python 3.9, prints to stdout by design)

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

ID_RE = re.compile(r'"_id"\s*:\s*"((?:[^"\\]|\\.)*)"')
QID_RE = re.compile(r'"query[-_]id"\s*:\s*"((?:[^"\\]|\\.)*)"')
BASE = "https://huggingface.co/datasets/zhangfw123/CORE-Bench/resolve/main/"


def open_stream(path: str):
    req = urllib.request.Request(BASE + path)
    return urllib.request.urlopen(req, timeout=120)


def stream_queries(path: str):
    ids, rows, nbytes = [], 0, 0
    with open_stream(path) as resp:
        for line in resp:
            nbytes += len(line)
            if not line.strip():
                continue
            m = ID_RE.search(line[:4000].decode("utf-8", "replace"))
            if m is None:
                obj = json.loads(line)
                ids.append(obj["_id"])
            else:
                ids.append(json.loads('"' + m.group(1) + '"'))
            rows += 1
    return ids, rows, nbytes


def stream_qrels(path: str):
    counts, rows, nbytes, scores = {}, 0, 0, {}
    with open_stream(path) as resp:
        for line in resp:
            nbytes += len(line)
            if not line.strip():
                continue
            obj = json.loads(line)
            q = obj.get("query_id", obj.get("query-id"))
            counts[q] = counts.get(q, 0) + 1
            s = str(obj.get("score"))
            scores[s] = scores.get(s, 0) + 1
            rows += 1
    return counts, rows, nbytes, scores


def work(job):
    entry_dir, files, out_dir = job
    rel = entry_dir[len("data/") :]
    out = os.path.join(out_dir, rel + ".json")
    if os.path.exists(out):
        return rel, "skip"
    res = {"folder_path": entry_dir}
    for attempt in range(6):
        try:
            if "queries.jsonl" in files:
                ids, rows, nb = stream_queries(entry_dir + "/queries.jsonl")
                res.update(queries_ids=ids, queries_rows=rows, queries_bytes=nb)
            if "qrels.jsonl" in files:
                c, rows, nb, sc = stream_qrels(entry_dir + "/qrels.jsonl")
                res.update(qrels_query_ids=c, qrels_rows=rows, qrels_bytes=nb, qrels_scores=sc)
            break
        except Exception as exc:  # noqa: BLE001 - retry network errors
            print("retry", rel, attempt, repr(exc), file=sys.stderr, flush=True)
            time.sleep(2 ** min(attempt, 5))
    else:
        return rel, "FAILED"
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out + ".tmp", "w") as fh:
        json.dump(res, fh)
    os.replace(out + ".tmp", out)
    return rel, "ok"


def main() -> None:
    listing, out_dir = sys.argv[1], sys.argv[2]
    workers = int(sys.argv[3]) if len(sys.argv) > 3 else 4
    entries = json.load(open(listing))["entries"]
    folders = {}
    for e in entries:
        if e["type"] != "file":
            continue
        parts = e["path"].split("/")
        if (
            len(parts) == 5
            and parts[0] == "data"
            and parts[1] in ("LEVEL-2", "LEVEL-3", "Rewrite-LEVEL-2", "Rewrite-LEVEL-3")
        ):
            folders.setdefault("/".join(parts[:4]), set()).add(parts[4])
    jobs = [(k, v, out_dir) for k, v in sorted(folders.items())]
    print("folders", len(jobs), flush=True)
    t0 = time.time()
    done = 0
    with ThreadPoolExecutor(workers) as ex:
        for rel, status in ex.map(work, jobs):
            done += 1
            if status != "skip" and done % 25 == 0 or status == "FAILED":
                print(done, rel, status, round(time.time() - t0), "s", flush=True)
    print("finished", round(time.time() - t0), "s", flush=True)


if __name__ == "__main__":
    main()
