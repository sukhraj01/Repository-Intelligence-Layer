"""List a Hugging Face dataset tree (with byte sizes) over plain HTTP, stdlib only.

Why: the dataset viewer for CORE-Bench is broken and a full clone is 32 GB; the tree API gives
every file path and size without downloading content. Python 3.9 compatible (Ada system python).
Usage: hf_list_tree.py REPO_ID SUBPATH OUT.json
"""
# ruff: noqa  (standalone stdlib tool; runs on Ada's python 3.9, prints to stdout by design)

from __future__ import annotations

import json
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone

API = "https://huggingface.co/api/datasets/{repo}/tree/main/{path}?recursive=true&limit=1000"


def fetch(url: str) -> tuple[list, str | None]:
    for attempt in range(6):
        try:
            with urllib.request.urlopen(urllib.request.Request(url), timeout=60) as resp:
                link = resp.headers.get("Link", "")
                m = re.search(r'<([^>]+)>;\s*rel="next"', link)
                return json.loads(resp.read()), (m.group(1) if m else None)
        except Exception as exc:  # noqa: BLE001 - retry any network error, then re-raise
            if attempt == 5:
                raise
            time.sleep(2**attempt)
            print("retry", attempt, repr(exc), file=sys.stderr)
    raise RuntimeError("unreachable")


def main() -> None:
    repo, sub, out = sys.argv[1:4]
    url = API.format(repo=repo, path=sub)
    entries: list = []
    pages = 0
    while url:
        page, url = fetch(url)
        entries.extend(page)
        pages += 1
    doc = {
        "source": f"https://huggingface.co/datasets/{repo}",
        "subpath": sub,
        "fetched_utc": datetime.now(timezone.utc).isoformat(),
        "pages": pages,
        "entries": [
            {
                "path": e["path"],
                "type": e["type"],
                "size": e.get("size"),
                "oid": e.get("oid"),
                "lfs_oid": (e.get("lfs") or {}).get("oid"),
            }
            for e in entries
        ],
    }
    with open(out, "w") as fh:
        json.dump(doc, fh)
    print(len(entries), "entries,", pages, "pages")


if __name__ == "__main__":
    main()
