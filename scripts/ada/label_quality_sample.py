"""Classify the qrels positives of a seeded sample of CORE-Bench L2 instances (numbers only).

Why: L2 labels are chunks aligned to the PR patch by file and line range, so a positive can be a
docstring, an import block, a comment, a test or a config chunk rather than the code that was
fixed. This script reads corpus.jsonl and qrels.jsonl of the given repositories, samples
instances with a fixed seed, classifies every positive chunk with a crude text heuristic, and
writes counts only (no chunk text leaves the cluster). Observations, not a quality verdict.
Implements the label-quality step of specs/held_out_repos.md. Python 3.9, stdlib only.
Usage: label_quality_sample.py DATA_ROOT OUT.json SEED N_INSTANCES REPO [REPO ...]
  DATA_ROOT holds data/LEVEL-2/SWE-bench_Verified/<REPO>/{corpus.jsonl,qrels.jsonl}
"""
# ruff: noqa  (standalone stdlib tool; runs on Ada's python 3.9)

from __future__ import annotations

import json
import os
import random
import re
import sys
from collections import Counter, defaultdict

IMPORT_RE = re.compile(r"^\s*(import |from \S+ import )")
DEF_RE = re.compile(r"^\s*(async\s+def |def |class )")
SECTION_RE = re.compile(r"^\s*\[[^\]]+\]\s*$")
KV_RE = re.compile(r"^\s*[A-Za-z0-9_.\-]+\s*[=:]\s*\S")
RST_RE = re.compile(r"^(\s*\.\. \S|\s*[=\-~^]{3,}\s*$|\s*:\w+[^:]*:)")


def classify(text: str) -> str:
    lines = [l for l in text.splitlines() if l.strip()]
    if not lines:
        return "empty"
    n = len(lines)
    imp = sum(1 for l in lines if IMPORT_RE.match(l))
    com = sum(1 for l in lines if l.lstrip().startswith("#"))
    defs = sum(1 for l in lines if DEF_RE.match(l))
    rst = sum(1 for l in lines if RST_RE.match(l))
    sect = sum(1 for l in lines if SECTION_RE.match(l))
    kv = sum(1 for l in lines if KV_RE.match(l))
    test_names = len(
        re.findall(r"\bdef test_\w+|\bclass Test\w+|\bimport pytest\b|\bunittest\b", text)
    )
    if imp / n >= 0.6:
        return "imports"
    if com / n >= 0.6:
        return "comments"
    if test_names >= 1 and defs >= 1:
        return "test"
    if defs == 0 and (sect >= 1 or kv / n >= 0.6) and imp == 0 and rst == 0:
        return "config"
    if defs == 0 and rst / n >= 0.2:
        return "docs"
    return "code"


def load_qrels(path: str):
    pos = defaultdict(list)
    for line in open(path):
        if line.strip():
            o = json.loads(line)
            pos[o["query_id"]].append(o["corpus_id"])
    return pos


def main() -> None:
    root, out, seed, n = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
    repos = sys.argv[5:]
    base = os.path.join(root, "data", "LEVEL-2", "SWE-bench_Verified")
    per_repo_pos = {}
    for r in repos:
        per_repo_pos[r] = load_qrels(os.path.join(base, r, "qrels.jsonl"))
    universe = sorted((r, q) for r in repos for q in per_repo_pos[r])
    rng = random.Random(seed)
    sample = sorted(rng.sample(universe, min(n, len(universe))))
    wanted = defaultdict(set)
    for r, q in sample:
        wanted[r].update(per_repo_pos[r][q])
    texts = {}
    for r in repos:
        for line in open(os.path.join(base, r, "corpus.jsonl")):
            if line.strip():
                o = json.loads(line)
                if o["_id"] in wanted[r]:
                    texts[(r, o["_id"])] = o["text"]
    cls = Counter()
    by_repo = defaultdict(Counter)
    starts_def = mid = 0
    lens = []
    per_inst = []
    for r, q in sample:
        ids = per_repo_pos[r][q]
        kinds = []
        for c in ids:
            t = texts.get((r, c))
            if t is None:
                kinds.append("missing")
                continue
            k = classify(t)
            kinds.append(k)
            cls[k] += 1
            by_repo[r][k] += 1
            lens.append(len(t))
            first = next((l for l in t.splitlines() if l.strip()), "")
            if DEF_RE.match(first):
                starts_def += 1
            else:
                mid += 1
        per_inst.append(
            {"repo": r, "instance": q, "positives": len(ids), "kinds": dict(Counter(kinds))}
        )
    # population view (all instances of the repos): positives per instance
    pop = Counter()
    for r in repos:
        for q, ids in per_repo_pos[r].items():
            pop["single" if len(ids) == 1 else "multiple"] += 1
    npos = [len(per_repo_pos[r][q]) for r, q in sample]
    doc = {
        "seed": seed,
        "n_sample": len(sample),
        "repos": repos,
        "instances_per_repo_population": {r: len(per_repo_pos[r]) for r in repos},
        "sample_instances_per_repo": dict(Counter(r for r, _ in sample)),
        "positives_in_sample": sum(npos),
        "sample_single_positive": sum(1 for x in npos if x == 1),
        "sample_multiple_positive": sum(1 for x in npos if x > 1),
        "population_single_vs_multiple_instances": dict(pop),
        "class_counts": dict(cls),
        "class_counts_by_repo": {r: dict(c) for r, c in by_repo.items()},
        "positive_chunk_starts_at_def": starts_def,
        "positive_chunk_starts_elsewhere": mid,
        "positive_chunk_mean_chars": (sum(lens) / len(lens)) if lens else None,
        "classifier": "line-ratio text heuristic (imports>=60%, comments>=60%, test markers, config key/section, rst markers), crude",
        "per_instance": per_inst,
    }
    json.dump(doc, open(out, "w"), indent=1)
    print(json.dumps({k: v for k, v in doc.items() if k != "per_instance"}, indent=1))


if __name__ == "__main__":
    main()
