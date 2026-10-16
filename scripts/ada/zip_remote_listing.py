"""List the members of a remote ZIP (names, sizes) using HTTP Range requests on its central directory.

Why: gangiswag/train_data holds multi-GB zips with no card; the central directory (at the end of
the file) tells what is inside without downloading the archive. Stdlib only, Python 3.9 compatible.
Usage: zip_remote_listing.py URL OUT.json
"""
# ruff: noqa  (standalone stdlib tool; runs on Ada's python 3.9, prints to stdout by design)

from __future__ import annotations

import json
import struct
import sys
import urllib.request


def rng(url: str, start: int, end: int) -> bytes:
    req = urllib.request.Request(url, headers={"Range": f"bytes={start}-{end}"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def total_size(url: str) -> int:
    req = urllib.request.Request(url, headers={"Range": "bytes=0-0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return int(r.headers["Content-Range"].split("/")[1])


def main() -> None:
    url, out = sys.argv[1:3]
    size = total_size(url)
    tail = rng(url, max(0, size - 70000), size - 1)
    i = tail.rfind(b"PK\x05\x06")
    _, _, _, n_entries, _, cd_size, cd_off = struct.unpack("<IHHHHII", tail[i : i + 20])
    j = tail.rfind(b"PK\x06\x07")
    if n_entries == 0xFFFF or cd_off == 0xFFFFFFFF or j >= 0:
        loc = struct.unpack("<IIQI", tail[j : j + 20])
        z64 = rng(url, loc[2], loc[2] + 55)
        (_, _, _, _, _, _, n_entries, _, cd_size, cd_off) = struct.unpack("<IQHHIIQQQQ", z64[:56])
    cd = rng(url, cd_off, cd_off + cd_size - 1)
    members, p = [], 0
    while p < len(cd) and cd[p : p + 4] == b"PK\x01\x02":
        (_, _, _, flag, comp, _, _, crc, csize, usize, nlen, elen, clen, _, _, _, off) = (
            struct.unpack("<IHHHHHHIIIHHHHHII", cd[p : p + 46])
        )
        name = cd[p + 46 : p + 46 + nlen].decode("utf-8", "replace")
        extra = cd[p + 46 + nlen : p + 46 + nlen + elen]
        q = 0
        while q + 4 <= len(extra):
            tag, sz = struct.unpack("<HH", extra[q : q + 4])
            if tag == 1:  # zip64 extended information
                vals, r = [], q + 4
                for present in (usize == 0xFFFFFFFF, csize == 0xFFFFFFFF, off == 0xFFFFFFFF):
                    if present:
                        vals.append(struct.unpack("<Q", extra[r : r + 8])[0])
                        r += 8
                    else:
                        vals.append(None)
                usize = vals[0] if vals[0] is not None else usize
                csize = vals[1] if vals[1] is not None else csize
                off = vals[2] if vals[2] is not None else off
            q += 4 + sz
        members.append(
            {
                "name": name,
                "uncompressed": usize,
                "compressed": csize,
                "method": comp,
                "offset": off,
            }
        )
        p += 46 + nlen + elen + clen
    json.dump(
        {
            "url": url,
            "zip_bytes": size,
            "entries_declared": n_entries,
            "central_dir_bytes": cd_size,
            "members": members,
        },
        open(out, "w"),
    )
    print(url.split("/")[-1], "size", size, "declared", n_entries, "parsed", len(members))


if __name__ == "__main__":
    main()
