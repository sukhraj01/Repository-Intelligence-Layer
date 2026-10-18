"""Pool check of gangiswag/train_data (python): metadata by HTTP range requests, no full download.

Why: the candidate pool is a 23.6 GB archive; its queries and qrels are tiny and sit next to each
instance's corpus, so one range request per instance returns them. Logic lives in
``ril.training.pool_check`` (unit-tested); this file does the network and the bookkeeping.
Idempotent: finished instances are read back from the cache files and skipped.

Usage:
  pool_check.py WORKDIR LISTING.json IDS_ALL.json VERIFIED_REF.json OUT.json SEED SAMPLE [THREADS]
WORKDIR gets ``pool_meta.jsonl`` (every instance) and ``pool_sample.jsonl`` (sampled corpora).
Python 3.9 compatible, standard library only, no print of dataset text.
"""
# ruff: noqa  (standalone cluster tool; prints progress to stdout by design)

from __future__ import annotations

import json
import os
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from ril.training import pool_check as pc  # noqa: E402

LOCK = threading.Lock()


def fetch(url: str, first: int, last: int) -> bytes:
    for attempt in range(6):
        try:
            req = urllib.request.Request(url, headers={"Range": f"bytes={first}-{last}"})
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read()
        except Exception as exc:  # network errors are retried, then raised
            if attempt == 5:
                raise
            time.sleep(2**attempt)
    raise RuntimeError("unreachable")


def read_jsonl(path: str) -> dict:
    out: dict = {}
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            if line.strip():
                row = json.loads(line)
                out[row["dir"]] = row
    return out


def append(path: str, row: dict) -> None:
    with LOCK:
        with open(path, "a", encoding="utf-8") as h:
            h.write(json.dumps(row, sort_keys=True) + "\n")


def meta_task(url: str, name: str, inst: dict, path: str) -> None:
    q, r, c = inst["queries"], inst["qrels"], inst["corpus"]
    first, last = pc.span_for([q, r])
    blob = fetch(url, first, last)
    q_text = pc.decode_member(blob, int(q["offset"]) - first, q).decode("utf-8")
    r_text = pc.decode_member(blob, int(r["offset"]) - first, r).decode("utf-8")
    queries = [pc.parse_query(x) for x in pc.split_rows(q_text)]
    qrels = pc.parse_qrels(r_text)
    append(
        path,
        {
            "dir": name,
            "queries": queries,
            "qrel_rows": len(qrels),
            "positives": sum(1 for _, s in qrels if s > 0),
            "qrel_ids": [i for i, s in qrels if s > 0],
            "corpus_bytes": int(c["uncompressed"]),
            "corpus_compressed": int(c["compressed"]),
        },
    )


def sample_task(url: str, name: str, inst: dict, meta: dict, path: str) -> None:
    c = inst["corpus"]
    first, last = pc.span_for([c])
    blob = fetch(url, first, last)
    text = pc.decode_member(blob, 0, c).decode("utf-8")
    info = pc.parse_corpus(text)
    ids = set(info.pop("ids"))
    pos = meta[name]["qrel_ids"]
    info.update(
        {
            "dir": name,
            "positives": meta[name]["positives"],
            "positives_in_corpus": sum(1 for p in pos if p in ids),
            "corpus_bytes": int(c["uncompressed"]),
        }
    )
    append(path, info)


def run_pool(tasks, label: str, threads: int, err_path: str) -> None:
    """tasks: list of (instance name, callable). A failing instance is logged, not fatal."""
    done = [0]
    t0 = time.time()

    def wrap(item):
        name, fn = item
        try:
            fn()
        except Exception as exc:
            append(
                err_path,
                {
                    "dir": name,
                    "stage": label,
                    "error": "%s: %s" % (type(exc).__name__, str(exc)[:200]),
                },
            )
        with LOCK:
            done[0] += 1
            if done[0] % 500 == 0:
                print(label, done[0], "of", len(tasks), round(time.time() - t0), "s", flush=True)

    with ThreadPoolExecutor(max_workers=threads) as ex:
        list(ex.map(wrap, tasks))


def main() -> None:
    work, listing, ids_all, ver_ref, out, seed, k = sys.argv[1:8]
    threads = int(sys.argv[8]) if len(sys.argv) > 8 else 8
    seed_i, k_i = int(seed), int(k)
    os.makedirs(work, exist_ok=True)
    z = json.load(open(listing))
    url = z["url"]
    inst = pc.pool_instances(z["members"], "python")
    meta_path = os.path.join(work, "pool_meta.jsonl")
    sample_path = os.path.join(work, "pool_sample.jsonl")
    meta = read_jsonl(meta_path)
    todo = [n for n in inst if n not in meta]
    print("instances", len(inst), "cached", len(meta), "to fetch", len(todo), flush=True)
    t0 = time.time()
    err_path = os.path.join(work, "pool_errors.jsonl")
    run_pool(
        [(n, lambda n=n: meta_task(url, n, inst[n], meta_path)) for n in todo],
        "meta",
        threads,
        err_path,
    )
    meta = read_jsonl(meta_path)
    t_meta = time.time() - t0
    chosen = pc.sample_names(sorted(meta), k_i, seed_i)
    smp = read_jsonl(sample_path)
    todo_s = [n for n in chosen if n not in smp]
    t1 = time.time()
    run_pool(
        [(n, lambda n=n: sample_task(url, n, inst[n], meta, sample_path)) for n in todo_s],
        "sample",
        threads,
        err_path,
    )
    smp = read_jsonl(sample_path)
    errors = [json.loads(x) for x in open(err_path)] if os.path.exists(err_path) else []
    t_sample = time.time() - t1

    ids = json.load(open(ids_all))
    refs: dict = {}
    for folder, info in ids.items():
        if folder.startswith("Rewrite-"):
            continue
        level, dataset = folder.split("/")[0], folder.split("/")[1]
        qids = list(info.get("qrels_query_ids", {}))
        refs.setdefault("core_bench_" + level.lower(), set()).update(qids)
        refs.setdefault("core_bench_" + level.lower() + "/" + dataset, set()).update(qids)
        refs.setdefault("core_bench_any", set()).update(qids)
    ver = json.load(open(ver_ref))
    refs["swe_bench_verified_500"] = set(ver)
    refs = {k_: sorted(v) for k_, v in sorted(refs.items())}

    pool_pairs = []
    unreadable = []
    for name, row in meta.items():
        p = pc.split_instance_dir(name)
        if p is None:
            unreadable.append(name)
        else:
            pool_pairs.append(p)
    overlap = pc.pr_overlap(pool_pairs, refs)

    ver_commits = {v["base_commit"] for v in ver.values()}
    base_commit_hits = sorted(
        n for n, r in meta.items() if any(q.get("base_commit") in ver_commits for q in r["queries"])
    )
    # consistency of the directory name with the query metadata
    repo_mismatch = []
    queries_per_dir = {}
    meta_key_sets = {}
    for name, row in meta.items():
        queries_per_dir[len(row["queries"])] = queries_per_dir.get(len(row["queries"]), 0) + 1
        for q in row["queries"]:
            meta_key_sets[tuple(q["meta_keys"])] = meta_key_sets.get(tuple(q["meta_keys"]), 0) + 1
            p = pc.split_instance_dir(name)
            if q.get("repo") and p and q["repo"].lower() != p[0]:
                repo_mismatch.append(name)
    rows = list(meta.values())
    sample_rows = [smp[n] for n in chosen if n in smp]
    dist_all = pc.positives_summary(rows)
    sample_pos = pc.positives_summary(sample_rows)
    small_corpus = sum(1 for r in sample_rows if r["functions"] <= 40)
    summary = {
        "source": url,
        "instances": len(inst),
        "instances_read": len(meta),
        "fetch_errors": len(errors),
        "fetch_error_kinds": sorted({e["error"][:60] for e in errors})[:10],
        "unreadable_dir_names": unreadable,
        "queries_per_instance_dir": {str(k_): v for k_, v in sorted(queries_per_dir.items())},
        "query_metadata_key_sets": {"|".join(k_): v for k_, v in meta_key_sets.items()},
        "dir_vs_metadata_repo_mismatch": len(repo_mismatch),
        "distinct_repos": len({p[0] for p in pool_pairs}),
        "distinct_pairs": len(set(pool_pairs)),
        "qrel_rows_total": sum(r["qrel_rows"] for r in rows),
        "positives_all_instances": dist_all,
        "overlap": overlap,
        "base_commit_hits_with_verified": len(base_commit_hits),
        "base_commit_hit_dirs": base_commit_hits[:50],
        "corpus_bytes_all": pc.describe([float(r["corpus_bytes"]) for r in rows]),
        "sample": {
            "seed": seed_i,
            "k": k_i,
            "read": len(sample_rows),
            "dirs": chosen,
            "functions_per_instance": pc.describe([float(r["functions"]) for r in sample_rows]),
            "distinct_ids_equal_functions": sum(
                1 for r in sample_rows if r["functions"] == r["distinct_ids"]
            ),
            "positives": sample_pos,
            "positives_found_in_corpus": sum(r["positives_in_corpus"] for r in sample_rows),
            "positives_total": sum(r["positives"] for r in sample_rows),
            "instances_with_corpus_at_most_40_functions": small_corpus,
            "corpus_row_keys": sorted({k_ for r in sample_rows for k_ in r["row_keys"]}),
            "corpus_metadata_keys": sorted({k_ for r in sample_rows for k_ in r["meta_keys"]}),
        },
        "seconds": {"meta": round(t_meta, 1), "sample": round(t_sample, 1)},
        "threads": threads,
    }
    json.dump(summary, open(out, "w"), indent=1, sort_keys=True)
    print("wrote", out)


if __name__ == "__main__":
    main()
