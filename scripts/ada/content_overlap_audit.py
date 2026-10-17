"""Content-overlap audit of pool repositories against held-out corpora (decision D1).

Held-out side: every line of the CORE-Bench corpora found under SAMPLE_ROOT (the nine sample
folders: Level-2, Level-3 and Rewrite-Level-2 of flask, requests and seaborn), hashed after
normalisation. Pool side: for each audited repository, one seeded instance of the pool zip is
extracted by HTTP Range request and its function rows are scored. Controls: held-out chunks offered
as pool units (must score 1.0) and a seeded random sample of unrelated repositories (chance level).
Only counts and repository names leave the cluster: no corpus or pool text is written.

Targeted repositories are the pool repositories whose name part contains flask, requests or
seaborn (candidates for forks, mirrors or vendored copies); the random sample is drawn from the
rest. Stdlib only, Python 3.9+. Needs the ``ril`` package on the path.

Usage: content_overlap_audit.py RIL_ROOT SAMPLE_ROOT ZIP_LISTING.json POOL_REPOS.json OUT.json SEED N_RANDOM
"""
# ruff: noqa: T201, E501

from __future__ import annotations

import hashlib
import json
import random
import struct
import sys
import urllib.request
import zlib
from pathlib import Path

MAX_MEMBER_BYTES = 30_000_000
TARGET_WORDS = ("flask", "requests", "seaborn")


def rng(url: str, start: int, end: int) -> bytes:
    req = urllib.request.Request(url, headers={"Range": f"bytes={start}-{end}"})
    with urllib.request.urlopen(req, timeout=120) as r:  # noqa: S310
        return r.read()


def extract(url: str, m: dict) -> bytes:
    hdr = rng(url, m["offset"], m["offset"] + 29)
    nlen, elen = struct.unpack("<HH", hdr[26:30])
    start = m["offset"] + 30 + nlen + elen
    raw = rng(url, start, start + m["compressed"] - 1)
    data = raw if m["method"] == 0 else zlib.decompress(raw, -15)
    assert len(data) == m["uncompressed"]
    return data


def main() -> None:
    root, sample_root, listing_p, pool_p, out_p, seed_s, n_rand_s = sys.argv[1:8]
    seed, n_rand = int(seed_s), int(n_rand_s)
    sys.path.insert(0, root)
    from ril.parsing.unit_id import id_to_pool, pool_to_id
    from ril.training.content_overlap import audit_repo, build_index

    rnd = random.Random(seed)
    # held-out side -------------------------------------------------------------------------
    corpora = sorted(Path(sample_root).glob("**/corpus.jsonl"))
    texts: list[str] = []
    per_folder = {}
    for c in corpora:
        rows = [json.loads(line)["text"] for line in open(c, encoding="utf-8") if line.strip()]
        per_folder[str(c.relative_to(sample_root).parent)] = len(rows)
        texts.extend(rows)
    index = build_index(texts)
    # controls: held-out chunks as pool units -----------------------------------------------
    chunks = rnd.sample(texts, min(300, len(texts)))
    control_pos = audit_repo("control/held-out-chunks", chunks, index)
    # pool side ------------------------------------------------------------------------------
    listing = json.load(open(listing_p))
    url = listing["url"]
    members = {}
    for m in listing["members"]:
        parts = m["name"].split("/")
        if len(parts) == 4 and parts[1] == "python" and parts[3] == "corpus.jsonl":
            if m["uncompressed"] <= MAX_MEMBER_BYTES:
                dirname = parts[2]
                repo = dirname.rsplit("-", 1)[0].replace("__", "/", 1).casefold()
                members.setdefault(repo, []).append(m)
    pool_counts = json.load(open(pool_p))["repos"]
    repos = sorted(r for r in pool_counts if r in members)
    targeted = [r for r in repos if any(w in r.split("/", 1)[1] for w in TARGET_WORDS)]
    others = [r for r in repos if r not in set(targeted)]
    sample = rnd.sample(others, min(n_rand, len(others)))
    results = []
    ids_total = ids_ok = 0
    id_failures: dict[str, int] = {}
    for kind, names in (("targeted", targeted), ("random", sample)):
        for repo in names:
            m = rnd.choice(sorted(members[repo], key=lambda x: x["name"]))
            data = extract(url, m)
            units = []
            for line in data.decode("utf-8", "replace").splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                text = row.get("text", "")
                pid = row.get("_id", "")
                ids_total += 1
                try:  # D11: pool id -> unit id -> pool id must be the identity
                    ok = id_to_pool(pool_to_id(pid)) == pid
                    if not ok:
                        id_failures["round_trip_differs"] = (
                            id_failures.get("round_trip_differs", 0) + 1
                        )
                    ids_ok += ok
                except ValueError as exc:
                    key = str(exc).split(":")[0][:60]
                    id_failures[key] = id_failures.get(key, 0) + 1
                units.append(text.split("\n", 1)[1] if "\n" in text else text)
            r = audit_repo(repo, units, index)
            results.append(
                {
                    "kind": kind,
                    "repo": repo,
                    "member": m["name"].split("/")[2],
                    "rows": len(units),
                    "scored": r.units_scored,
                    "covered": r.units_covered,
                    "share": round(r.share, 4),
                }
            )
    doc = {
        "seed": seed,
        "held_out_side": {
            "folders": per_folder,
            "chunks": len(texts),
            "distinct_informative_line_hashes": len(index),
            "corpus_files_sha256_prefix": {
                str(c.relative_to(sample_root)): hashlib.sha256(c.read_bytes()).hexdigest()[:12]
                for c in corpora
            },
        },
        "control_positive": {
            "units_scored": control_pos.units_scored,
            "covered": control_pos.units_covered,
        },
        "pool_id_round_trip": {
            "ids": ids_total,
            "ok": ids_ok,
            "failures_by_reason": id_failures,
        },
        "targeted_repos_found": len(targeted),
        "random_sample_size": len(sample),
        "results": results,
    }
    json.dump(doc, open(out_p, "w"), indent=1, sort_keys=True)
    tgt = [r for r in results if r["kind"] == "targeted"]
    rnd_r = [r for r in results if r["kind"] == "random"]
    print(
        "held-out chunks",
        len(texts),
        "| positive control",
        control_pos.units_covered,
        "/",
        control_pos.units_scored,
    )
    print("targeted", len(tgt), "max share", max((r["share"] for r in tgt), default=None))
    print("pool ids", ids_total, "round trip ok", ids_ok, id_failures)
    print("random", len(rnd_r), "max share", max((r["share"] for r in rnd_r), default=None))


if __name__ == "__main__":
    main()
