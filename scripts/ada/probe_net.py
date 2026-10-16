"""Probe reachability and throughput of Hugging Face / GitHub from the machine it runs on.

Why: answers Q2 (can Ada reach the sources, how fast). Stdlib only, Python 3.9 compatible.
Usage: probe_net.py [RANGE_BYTES]. Fetches the first RANGE_BYTES of one public corpus file via an
HTTP Range request, discards it, prints one JSON line per measurement.
"""
# ruff: noqa  (standalone stdlib tool; runs on Ada's python 3.9, prints to stdout by design)

from __future__ import annotations

import json
import socket
import sys
import time
import urllib.request

HF_FILE = (
    "https://huggingface.co/datasets/zhangfw123/CORE-Bench/resolve/main/"
    "data/LEVEL-2/SWE-bench_Verified/astropy__astropy/corpus.jsonl"
)


def timed_head(url: str) -> dict:
    t0 = time.time()
    try:
        with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=30) as r:
            return {"url": url, "status": r.status, "seconds": round(time.time() - t0, 3)}
    except Exception as exc:  # noqa: BLE001
        return {"url": url, "error": repr(exc), "seconds": round(time.time() - t0, 3)}


def main() -> None:
    nbytes = int(sys.argv[1]) if len(sys.argv) > 1 else 50_000_000
    print(json.dumps({"host": socket.gethostname()}))
    for u in (
        "https://huggingface.co",
        "https://github.com",
        "https://raw.githubusercontent.com",
        "https://pypi.org",
    ):
        print(json.dumps(timed_head(u)))
    req = urllib.request.Request(HF_FILE, headers={"Range": f"bytes=0-{nbytes - 1}"})
    t0 = time.time()
    got = 0
    with urllib.request.urlopen(req, timeout=120) as r:
        status = r.status
        while True:
            b = r.read(1 << 20)
            if not b:
                break
            got += len(b)
    dt = time.time() - t0
    print(
        json.dumps(
            {
                "range_bytes_requested": nbytes,
                "bytes_received": got,
                "status": status,
                "seconds": round(dt, 2),
                "MB_per_s": round(got / dt / 1e6, 2),
            }
        )
    )


if __name__ == "__main__":
    main()
