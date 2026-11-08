"""Read-only survey for the evaluation-repository inventory (E-EVAL-REPOS), run as a CPU job.

Writes one JSON with (1) what the stored unit records and dense stores hold per repository,
(2) the repositories of the published pool and of the mining population, (3) a language sample of
the L2 corpora by HTTP range requests, (4) Python file counts of the bare clones. It reads; it
writes only the output file. Counts and flags only: no dataset text leaves the job.

Usage: eval_repo_survey.py OUT.json INPUT.json   (INPUT: {"folders": [{"key", "bytes"}], ...})
"""
# ruff: noqa  (standalone cluster tool; prints to stdout by design)

from __future__ import annotations

import concurrent.futures as cf
import glob
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

X2 = os.path.expanduser("~/ril_x2")
S2 = os.path.expanduser("~/ril_s2/raw")
HF = "https://huggingface.co/datasets/zhangfw123/CORE-Bench/resolve/main/data/"
RANGES, RANGE_BYTES = 6, 49152

PY_LINE = re.compile(
    r"^\s*(def \w+\(.*\)\s*(->\s*[^:]+)?:\s*(#.*)?$|class \w+(\(.*\))?:\s*$|from [\w.]+ import \w|"
    r"import [\w.]+( as \w+)?(, [\w.]+( as \w+)?)*\s*$|elif .*:\s*$|(else|try|finally):\s*$|"
    r"except\b.*:\s*$|if __name__ ==|async def \w+\()",
    re.M,
)
OTHER_LINE = re.compile(
    r"^\s*(func \w+|fn \w+|fun \w+|pub (fn|struct)|package \w+;?|#include|using namespace|"
    r"public (static |final )?(class|void|int)|private (static |final )?\w+|function \w+\(|"
    r"const \w+ = |export (default )?(function|class|const)|interface \w+|namespace \w+|impl\b|"
    r"let (mut )?\w+ =|import \w+ from |var \w+ =|end\s*$|require ['\"]|module \w+|"
    r"attr_(reader|accessor|writer)|elsif\b|unless\b|puts\b|def \w+(\(.*\))?\s*$)|;\s*$|^\s*\}\s*$",
    re.M,
)


def classify(text: str) -> str:
    """'python', 'other_code' or 'nocode' for one chunk (line-marker counts; a heuristic).

    Python markers are the ones other languages lack: a ``def`` or ``class`` line that ends in a
    colon, ``elif``, ``except``, ``from x import y``, ``if __name__``. A Ruby ``def`` without a
    colon counts for the other side.
    """
    py, other = len(PY_LINE.findall(text)), len(OTHER_LINE.findall(text))
    if py == 0 and other == 0:
        return "nocode"
    return "python" if py > other else "other_code"


def ranges_for(size: int):
    if size <= RANGES * RANGE_BYTES:
        return [(0, size - 1)]
    step = (size - RANGE_BYTES) // (RANGES - 1)
    return [(i * step, i * step + RANGE_BYTES - 1) for i in range(RANGES)]


def sample_folder(entry):
    key, size = entry["key"], int(entry["bytes"])
    counts = {"python": 0, "other_code": 0, "nocode": 0}
    errors = 0
    for lo, hi in ranges_for(size):
        for attempt in range(5):
            try:
                req = urllib.request.Request(
                    HF + key + "/corpus.jsonl", headers={"Range": f"bytes={lo}-{hi}"}
                )
                with urllib.request.urlopen(req, timeout=60) as resp:
                    blob = resp.read()
                break
            except Exception:
                blob, errors = b"", errors + 1
                time.sleep(3 * (attempt + 1))
        lines = blob.split(b"\n")
        if lo > 0:
            lines = lines[1:]  # first line is cut
        if hi < size - 1:
            lines = lines[:-1]  # last line is cut
        for ln in lines:
            if not ln.strip():
                continue
            try:
                counts[classify(json.loads(ln)["text"])] += 1
            except Exception:
                errors += 1
    return key, {**counts, "fetch_errors": errors, "ranges": len(ranges_for(size))}


def stores():
    import numpy as np

    out = {}
    for p in sorted(glob.glob(X2 + "/prep/units/*.npz")):
        z = np.load(p, allow_pickle=False)
        meta = json.loads(str(z["meta"]))
        repo = meta["repo_dir"]
        d = out.setdefault(
            repo,
            {
                "unit_records": 0,
                "units": [],
                "seconds": [],
                "dense": 0,
                "distinct_unit_texts": 0,
                "instances": [],
                "dense_instances": [],
            },
        )
        d["unit_records"] += 1
        d["instances"].append(meta["instance"])
        d["units"].append(int(meta["units"]))
        d["seconds"].append(float(meta.get("seconds", 0.0)))
        if os.path.exists(X2 + "/dense/coderankembed__t512/" + os.path.basename(p)):
            d["dense"] += 1
            d["dense_instances"].append(meta["instance"])
    for p in sorted(glob.glob(X2 + "/prep/texts_units/*.jsonl")):
        repo = os.path.basename(p).rsplit(".s", 1)[0]
        n = sum(1 for _ in open(p, "rb"))
        out.setdefault(
            repo,
            {
                "unit_records": 0,
                "units": [],
                "seconds": [],
                "dense": 0,
                "distinct_unit_texts": 0,
                "instances": [],
                "dense_instances": [],
            },
        )["distinct_unit_texts"] += n
    return out


def bare_clones():
    out = {}
    for p in sorted(glob.glob(X2 + "/repo_cache/*.git")):
        try:
            names = subprocess.run(
                ["git", "--git-dir", p, "ls-tree", "-r", "--name-only", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.split("\n")
            out[os.path.basename(p)[:-4]] = {
                "py_files_at_head": sum(1 for n in names if n.endswith(".py")),
                "files_at_head": sum(1 for n in names if n),
            }
        except Exception as exc:
            out[os.path.basename(p)[:-4]] = {"error": type(exc).__name__}
    return out


def population(held_out_path, rename_cache):
    from ril.data_mining.jobs import pool_directory_names
    from ril.data_mining.population import select_population
    from ril.training.pool_check import split_instance_dir
    from ril.training.pool_rank_jobs import held_out_predicate

    names = pool_directory_names(S2 + "/ziplist_train.json")
    raw = {}
    for n in names:
        sp = split_instance_dir(n)
        raw[sp[0]] = raw.get(sp[0], 0) + 1
    pred = held_out_predicate(held_out_path, rename_cache)
    pop = select_population(names, is_held_out=pred, seed=0, pool_size=5000)
    mining = {}
    for n in pop.directories:
        mining[split_instance_dir(n)[0]] = mining.get(split_instance_dir(n)[0], 0) + 1
    kept_after_filter = {r: c for r, c in raw.items() if not pred(r)}
    return {
        "raw_pool_repos": raw,
        "pool_after_filter_repos": kept_after_filter,
        "mining_population_repos": mining,
        "counts": dict(pop.counts),
        "pool_dirs_listed": len(names),
    }


def main():
    out_path, in_path = sys.argv[1], sys.argv[2]
    spec = json.load(open(in_path))
    t0 = time.time()
    doc = {"survey_version": "eval-repo-survey/v2", "started_unix": int(t0)}
    doc["stores"] = stores()
    doc["bare_clones"] = bare_clones()
    doc["population"] = population(spec["held_out_path"], spec.get("rename_cache_path"))
    doc["language"] = {}
    with cf.ThreadPoolExecutor(8) as pool:
        for key, res in pool.map(sample_folder, spec["folders"]):
            doc["language"][key] = res
    doc["seconds"] = round(time.time() - t0, 1)
    tmp = out_path + ".tmp"
    json.dump(doc, open(tmp, "w"), sort_keys=True)
    os.replace(tmp, out_path)
    print("done", doc["seconds"], "s;", len(doc["language"]), "folders sampled")


main()
