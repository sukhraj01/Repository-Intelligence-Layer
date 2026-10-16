"""Extract chosen members from a remote ZIP via HTTP Range (central-directory listing from
zip_remote_listing.py, which must include offsets). Stdlib only, Python 3.9 compatible.
Usage: zip_remote_extract.py URL LISTING.json DEST_DIR MEMBER [MEMBER ...]
"""
# ruff: noqa  (standalone stdlib tool; runs on Ada's python 3.9, prints to stdout by design)

from __future__ import annotations

import json
import os
import struct
import sys
import urllib.request
import zlib


def rng(url: str, start: int, end: int) -> bytes:
    req = urllib.request.Request(url, headers={"Range": f"bytes={start}-{end}"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def main() -> None:
    url, listing, dest = sys.argv[1:4]
    by_name = {m["name"]: m for m in json.load(open(listing))["members"]}
    for name in sys.argv[4:]:
        m = by_name[name]
        hdr = rng(url, m["offset"], m["offset"] + 29)
        nlen, elen = struct.unpack("<HH", hdr[26:30])
        start = m["offset"] + 30 + nlen + elen
        raw = rng(url, start, start + m["compressed"] - 1)
        data = raw if m["method"] == 0 else zlib.decompress(raw, -15)
        assert len(data) == m["uncompressed"], name
        out = os.path.join(dest, name)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        open(out, "wb").write(data)
        print(name, len(data))


if __name__ == "__main__":
    main()
