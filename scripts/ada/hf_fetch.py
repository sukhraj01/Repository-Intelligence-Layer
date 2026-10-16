"""Resumable, size-checked fetch of selected files from a Hugging Face dataset, stdlib only.

Why: huggingface_hub is not installed on Ada's system python and the data must not be cloned in
full. Uses HTTP Range to resume partial files, verifies the byte size against a tree listing
(see hf_list_tree.py), records sha256 in a provenance.json beside the files.
Idempotent: a file whose size already matches is skipped. Python 3.9 compatible.
Usage: hf_fetch.py REPO_ID LISTING.json DEST_DIR PREFIX [PREFIX ...]
  PREFIX is a path prefix inside the repo (e.g. data/LEVEL-2/SWE-bench_Verified/pallets__flask/).
"""
# ruff: noqa  (standalone stdlib tool; runs on Ada's python 3.9, prints to stdout by design)

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone


def download(url: str, dest: str, size: int) -> None:
    for attempt in range(8):
        have = os.path.getsize(dest) if os.path.exists(dest) else 0
        if have == size:
            return
        if have > size:
            os.remove(dest)
            have = 0
        req = urllib.request.Request(url, headers={"Range": f"bytes={have}-"})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp, open(dest, "ab") as out:
                while True:
                    block = resp.read(1 << 20)
                    if not block:
                        break
                    out.write(block)
        except Exception as exc:  # noqa: BLE001 - retry network errors
            print("retry", attempt, repr(exc), file=sys.stderr)
            time.sleep(2 ** min(attempt, 5))
    if os.path.getsize(dest) != size:
        raise RuntimeError(f"size mismatch for {dest}")


def main() -> None:
    repo, listing, dest_dir = sys.argv[1:4]
    prefixes = sys.argv[4:]
    entries = json.load(open(listing))["entries"]
    wanted = [
        e for e in entries if e["type"] == "file" and any(e["path"].startswith(p) for p in prefixes)
    ]
    prov = []
    t_all = time.time()
    for e in wanted:
        dest = os.path.join(dest_dir, e["path"])
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        t0 = time.time()
        download(
            f"https://huggingface.co/datasets/{repo}/resolve/main/{e['path']}", dest, e["size"]
        )
        dt = time.time() - t0
        h = hashlib.sha256()
        with open(dest, "rb") as fh:
            for block in iter(lambda: fh.read(1 << 20), b""):
                h.update(block)
        prov.append(
            {
                "path": e["path"],
                "bytes": e["size"],
                "sha256": h.hexdigest(),
                "lfs_oid": e.get("lfs_oid"),
                "sha256_matches_lfs_oid": (h.hexdigest() == e.get("lfs_oid"))
                if e.get("lfs_oid")
                else None,
                "fetch_seconds": round(dt, 3),
            }
        )
        print(e["path"], e["size"], round(dt, 2), "s", flush=True)
    doc = {
        "source": f"https://huggingface.co/datasets/{repo}",
        "listing": listing,
        "fetched_utc": datetime.now(timezone.utc).isoformat(),
        "total_seconds": round(time.time() - t_all, 2),
        "files": prov,
    }
    pj = os.path.join(dest_dir, "provenance.json")
    old = json.load(open(pj))["files"] if os.path.exists(pj) else []
    merged = {f["path"]: f for f in old}
    merged.update({f["path"]: f for f in prov})
    doc["files"] = [merged[k] for k in sorted(merged)]
    json.dump(doc, open(pj, "w"), indent=1)


if __name__ == "__main__":
    main()
