"""Does a CORE-Bench per-query candidate list equal the repository snapshot at the instance base commit?

Why: the benchmark paper says the evaluator keeps, for each query, only the chunks visible at the
pull-request state. If that is the whole snapshot at the base commit, evaluation is whole-snapshot
retrieval and the candidate list size should equal the number of chunks of that snapshot. This
script tests it on data: for each Verified instance of the given repositories it checks out the
base commit, locates every corpus chunk in the snapshot files by exact text (then stripped text),
and reports (a) precision: share of the candidate list that occurs in the snapshot, (b) recall:
share of the corpus chunks that occur in the snapshot and are in the candidate list, (c) file
coverage of the snapshot by the located chunks. Counts only; no chunk text is written.
Cites docs/06_core_bench.md "evaluation protocol". Python 3.9 + pyarrow (base commits come from the
SWE-bench Verified parquet). Deterministic apart from the seeded sample of non-list chunks.
Usage: core_bench_snapshot_check.py DATA_ROOT PARQUET REPO_CACHE OUT.json SEED MAX_RECALL_SAMPLE REPO [REPO ...]
  DATA_ROOT holds data/LEVEL-2/SWE-bench_Verified/<REPO>/{corpus.jsonl,queries.jsonl}; REPO is owner__name.
"""
# ruff: noqa  (standalone tool; runs on Ada's python 3.9, prints to stdout by design)

from __future__ import annotations

import bisect
import json
import os
import platform
import random
import subprocess
import sys
import tarfile
import io
from collections import Counter, defaultdict
from datetime import datetime, timezone


def sh(cmd, cwd=None):
    return subprocess.run(cmd, cwd=cwd, check=True, capture_output=True).stdout


def ensure_clone(owner, name, cache):
    path = os.path.join(cache, "%s__%s.git" % (owner, name))
    if not os.path.isdir(path):
        sh(
            [
                "git",
                "clone",
                "--bare",
                "--quiet",
                "https://github.com/%s/%s.git" % (owner, name),
                path,
            ]
        )
    return path


def snapshot_files(git_dir, commit):
    """Return {path: text} for every UTF-8 decodable file at the commit."""
    raw = sh(["git", "--git-dir", git_dir, "archive", commit])
    out = {}
    with tarfile.open(fileobj=io.BytesIO(raw)) as tf:
        for m in tf:
            if not m.isfile():
                continue
            data = tf.extractfile(m).read()
            try:
                out[m.name] = data.decode("utf-8")
            except UnicodeDecodeError:
                out[m.name] = data.decode("latin-1")
    return out


class Blob:
    """All files joined by a separator that cannot occur inside a chunk, with offset to file lookup."""

    SEP = "\x00\x01\x00"

    def __init__(self, files):
        self.names = sorted(files)
        parts, self.starts, pos = [], [], 0
        for n in self.names:
            self.starts.append(pos)
            parts.append(files[n])
            pos += len(files[n]) + len(self.SEP)
        self.text = self.SEP.join(parts)
        self.files = files

    def locate(self, needle):
        i = self.text.find(needle)
        if i < 0:
            return None
        k = bisect.bisect_right(self.starts, i) - 1
        return self.names[k], i - self.starts[k], len(needle)


def norm(text):
    """Line endings unified; chunkers often do this before splitting."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def ext(path):
    b = os.path.basename(path)
    return os.path.splitext(b)[1].lower() or b


def main():
    data_root, parquet, cache, out_path, seed, max_recall, *repos = sys.argv[1:]
    seed, max_recall = int(seed), int(max_recall)
    import pyarrow.parquet as pq

    tbl = pq.read_table(parquet, columns=["instance_id", "base_commit"]).to_pydict()
    base = dict(zip(tbl["instance_id"], tbl["base_commit"]))
    rng = random.Random(seed)
    result = {
        "script": "scripts/ada/core_bench_snapshot_check.py",
        "run_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "host": platform.node(),
        "python": platform.python_version(),
        "git": sh(["git", "--version"]).decode().strip(),
        "seed": seed,
        "max_recall_sample": max_recall,
        "repos": {},
    }
    for repo in repos:
        owner, name = repo.split("__", 1)
        folder = os.path.join(data_root, "data/LEVEL-2/SWE-bench_Verified", repo)
        corpus = {}
        with open(os.path.join(folder, "corpus.jsonl"), encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                corpus[r["_id"]] = r["text"]
        queries = []
        with open(os.path.join(folder, "queries.jsonl"), encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                queries.append((r["_id"], r["filtered_corpus_id"]))
        git_dir = ensure_clone(owner, name, cache)
        per_inst = []
        for qid, flist in sorted(queries):
            commit = base[qid]
            try:
                files = snapshot_files(git_dir, commit)
            except subprocess.CalledProcessError:
                try:
                    sh(["git", "--git-dir", git_dir, "fetch", "--quiet", "origin", commit])
                    files = snapshot_files(git_dir, commit)
                except subprocess.CalledProcessError:
                    per_inst.append(
                        {
                            "instance": qid,
                            "base_commit": commit,
                            "error": "base commit not fetchable",
                        }
                    )
                    print(repo, qid, "base commit not fetchable", flush=True)
                    continue
            blob = Blob(files)
            _nb = []

            def norm_blob():
                if not _nb:
                    _nb.append(Blob({k: norm(v) for k, v in files.items()}))
                return _nb[0]

            inlist = set(flist)
            loc_cache = {}

            def where(cid):
                if cid not in loc_cache:
                    t = corpus[cid]
                    loc = blob.locate(t)
                    tier = "exact"
                    if loc is None and t.strip() != t:
                        loc = blob.locate(t.strip())
                        tier = "stripped"
                    if loc is None:
                        nloc = norm_blob().locate(norm(t).strip())
                        if nloc is not None:
                            loc, tier = nloc, "normalised"
                    loc_cache[cid] = (loc, tier if loc else "none")
                return loc_cache[cid]

            tiers = Counter()
            ext_hit = Counter()
            covered = defaultdict(list)
            for cid in flist:
                loc, tier = where(cid)
                tiers[tier] += 1
                if loc:
                    ext_hit[ext(loc[0])] += 1
                    covered[loc[0]].append((loc[1], loc[1] + loc[2]))
            none_ids = [c for c in flist if where(c)[1] == "none"]
            none_diag = {
                "with_carriage_return": sum(1 for c in none_ids if "\r" in corpus[c]),
                "with_non_ascii": sum(
                    1 for c in none_ids if any(ord(ch) > 127 for ch in corpus[c])
                ),
                "mean_chars": round(sum(len(corpus[c]) for c in none_ids) / len(none_ids), 1)
                if none_ids
                else None,
            }
            others = [c for c in corpus if c not in inlist]
            sample = others if len(others) <= max_recall else rng.sample(sorted(others), max_recall)
            merged = {}
            for p_, iv_ in covered.items():
                out_iv = []
                for s_, e_ in sorted(iv_):
                    if out_iv and s_ <= out_iv[-1][1]:
                        out_iv[-1][1] = max(out_iv[-1][1], e_)
                    else:
                        out_iv.append([s_, e_])
                merged[p_] = out_iv

            def inside_listed_region(loc):
                p_, s_, n_ = loc
                for a_, b_ in merged.get(p_, []):
                    if a_ <= s_ and s_ + n_ <= b_:
                        return True
                return False

            recall_miss = 0
            miss_in_listed_region = 0
            miss_dup_of_list_text = 0
            list_texts = {corpus[c] for c in flist}
            for c in sample:
                loc, _tier = where(c)
                if loc is None:
                    continue
                recall_miss += 1
                if inside_listed_region(loc):
                    miss_in_listed_region += 1
                if corpus[c] in list_texts:
                    miss_dup_of_list_text += 1
            # file coverage: files with an extension that appears among located chunks
            ext_in_snapshot = Counter(ext(p) for p in files if ext(p) in ext_hit)
            files_hit = {p for p in covered}
            ext_files_hit = Counter(ext(p) for p in files_hit)
            cov_chars = 0
            tot_chars = 0
            for p, t in files.items():
                if ext(p) not in ext_hit:
                    continue
                tot_chars += len(t)
                iv = sorted(covered.get(p, []))
                cur_end, c = -1, 0
                for s, e in iv:
                    s = max(s, cur_end)
                    if e > s:
                        c += e - s
                        cur_end = e
                cov_chars += c
            per_inst.append(
                {
                    "instance": qid,
                    "base_commit": commit,
                    "snapshot_files_text": len(files),
                    "list_size": len(flist),
                    "list_in_snapshot_exact": tiers["exact"],
                    "list_in_snapshot_stripped": tiers["stripped"],
                    "list_in_snapshot_line_endings_normalised": tiers["normalised"],
                    "unlocated_list_chunk_diagnostics": none_diag,
                    "list_not_in_snapshot": tiers["none"],
                    "non_list_chunks_total": len(others),
                    "non_list_chunks_sampled": len(sample),
                    "non_list_sampled_found_in_snapshot": recall_miss,
                    "of_those_inside_a_region_covered_by_list_chunks": miss_in_listed_region,
                    "of_those_with_text_identical_to_a_list_chunk": miss_dup_of_list_text,
                    "of_those_in_uncovered_files_or_regions": recall_miss - miss_in_listed_region,
                    "ext_in_list": dict(ext_hit.most_common(8)),
                    "files_of_those_exts_in_snapshot": sum(ext_in_snapshot.values()),
                    "files_of_those_exts_with_a_chunk": sum(ext_files_hit.values()),
                    "char_coverage_of_those_files": round(cov_chars / tot_chars, 4)
                    if tot_chars
                    else None,
                }
            )
            print(
                repo,
                qid,
                per_inst[-1]["list_size"],
                dict(tiers),
                recall_miss,
                miss_in_listed_region,
                "/",
                len(sample),
                flush=True,
            )
        result["repos"][repo] = {"corpus_rows": len(corpus), "instances": per_inst}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1, sort_keys=True)


if __name__ == "__main__":
    main()
