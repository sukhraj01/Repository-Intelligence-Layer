"""Summarise the format of fetched CORE-Bench sample repositories (aggregates only, no text).

Why: determine fields, id format, qrels semantics, positives per query and the role of the
per-query `filtered_corpus_id` list, from real bytes. Output is numbers only so it can be copied
off the cluster and committed. Run with `python3 -I`. Stdlib only, Python 3.9 compatible.
Usage: analyze_core_bench_sample.py DATA_ROOT OUT.json
"""
# ruff: noqa  (standalone stdlib tool; runs on Ada's python 3.9, prints to stdout by design)

from __future__ import annotations

import collections
import json
import os
import re
import statistics
import sys

UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
PATH_LIKE = re.compile(r"^(?:#\s*)?[\w./-]+\.(?:py|rst|md|txt|cfg|toml|ini|yml|yaml)\b")


def rows(path: str):
    with open(path) as fh:
        for line in fh:
            if line.strip():
                yield json.loads(line)


def kind(text: str) -> str:
    """Coarse heuristic only; real label-quality work is S4."""
    s = text.lstrip()
    if re.match(r"^(def |class |async def |@)", s):
        return "code_def_or_class"
    if re.match(r"^(import |from \S+ import )", s):
        return "code_imports_head"
    if re.search(r"^\s*(def |class )", text, re.M):
        return "code_contains_def"
    if re.search(r"^\.\. |^[=\-~^]{4,}$|:\w+:`", text, re.M):
        return "doc_rst_like"
    if re.search(r"^(#{1,4} |\* |- )", text, re.M) and not re.search(r"[(){};]=?", text[:200]):
        return "doc_md_like"
    if re.search(r"^\s*\[[\w.:-]+\]\s*$|^\w[\w.-]*\s*=\s*\S", text, re.M):
        return "config_like"
    return "other_code_or_text"


def pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p * len(xs)))] if xs else None


def main() -> None:
    root, out = sys.argv[1:3]
    res = {}
    for lvl in sorted(os.listdir(root)):
        for ds in sorted(os.listdir(os.path.join(root, lvl))):
            for repo in sorted(os.listdir(os.path.join(root, lvl, ds))):
                b = os.path.join(root, lvl, ds, repo)
                if not os.path.isdir(b):
                    continue
                r = {"files": sorted(os.listdir(b))}
                corpus, ctext = {}, {}
                if os.path.exists(b + "/corpus.jsonl"):
                    keys = collections.Counter()
                    lens = []
                    uuid_ok = 0
                    for c in rows(b + "/corpus.jsonl"):
                        keys[tuple(sorted(c))] += 1
                        corpus[c["_id"]] = len(c["text"])
                        ctext[c["_id"]] = c["text"]
                        lens.append(len(c["text"]))
                        uuid_ok += bool(UUID.match(c["_id"]))
                    r["corpus"] = {
                        "rows": sum(keys.values()),
                        "distinct_ids": len(corpus),
                        "field_sets": {",".join(k): v for k, v in keys.items()},
                        "uuid_ids": uuid_ok,
                        "chars_mean": round(statistics.mean(lens), 1),
                        "chars_p50": pct(lens, 0.5),
                        "chars_p95": pct(lens, 0.95),
                        "chars_max": max(lens),
                        "distinct_texts": len(set(ctext.values())),
                        "text_starts_with_path": sum(
                            bool(PATH_LIKE.match(t)) for t in ctext.values()
                        ),
                    }
                qkeys = collections.Counter()
                queries = {}
                fsz, fsub, qtext_len = [], 0, []
                for q in rows(b + "/queries.jsonl"):
                    qkeys[tuple(sorted(q))] += 1
                    queries[q["_id"]] = q
                    qtext_len.append(len(q["text"]))
                    f = q.get("filtered_corpus_id")
                    if f is not None:
                        fsz.append(len(f))
                        if corpus:
                            fsub += all(x in corpus for x in f)
                r["queries"] = {
                    "rows": sum(qkeys.values()),
                    "field_sets": {",".join(k): v for k, v in qkeys.items()},
                    "text_chars_mean": round(statistics.mean(qtext_len), 1),
                    "filtered_len_list": fsz,
                    "filtered_subset_of_corpus": fsub,
                    "id_examples": list(queries)[:2],
                }
                if fsz and corpus:
                    union = set()
                    for q in queries.values():
                        union.update(q.get("filtered_corpus_id", []))
                    r["queries"]["filtered_union"] = len(union)
                    r["queries"]["corpus_minus_union"] = len(set(corpus) - union)
                if os.path.exists(b + "/qrels.jsonl"):
                    qr = list(rows(b + "/qrels.jsonl"))
                    per = collections.Counter(x["query_id"] for x in qr)
                    r["qrels"] = {
                        "rows": len(qr),
                        "fields": sorted(qr[0]) if qr else [],
                        "scores": dict(collections.Counter(x["score"] for x in qr)),
                        "queries_with_qrels": len(per),
                        "queries_without_qrels": len(set(queries) - set(per)),
                        "pos_per_query": dict(collections.Counter(per.values())),
                        "pos_per_query_mean": round(statistics.mean(per.values()), 2)
                        if per
                        else None,
                        "pos_per_query_max": max(per.values()) if per else None,
                        "qrel_in_corpus": sum(x["corpus_id"] in corpus for x in qr)
                        if corpus
                        else None,
                        "qrel_in_own_filtered": sum(
                            x["corpus_id"]
                            in set(queries[x["query_id"]].get("filtered_corpus_id", []))
                            for x in qr
                            if x["query_id"] in queries
                        ),
                        "distinct_corpus_ids": len({x["corpus_id"] for x in qr}),
                        "positive_kinds_heuristic": dict(
                            collections.Counter(
                                kind(ctext[x["corpus_id"]]) for x in qr if x["corpus_id"] in ctext
                            )
                        ),
                        "positive_chars_mean": round(
                            statistics.mean(
                                [corpus[x["corpus_id"]] for x in qr if x["corpus_id"] in corpus]
                                or [0]
                            ),
                            1,
                        ),
                    }
                if os.path.exists(b + "/qrels/test.tsv"):
                    lines = open(b + "/qrels/test.tsv").read().splitlines()
                    r["tsv"] = {
                        "header": lines[0],
                        "rows": len(lines) - 1,
                        "scores": dict(collections.Counter(l.split("\t")[2] for l in lines[1:])),
                    }
                res[f"{lvl}/{ds}/{repo}"] = r
    json.dump(res, open(out, "w"), indent=1, sort_keys=True)
    print("wrote", out, len(res))


if __name__ == "__main__":
    main()
