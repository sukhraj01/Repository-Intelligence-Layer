"""Look up current name, fork status and fork-network root for a short list of GitHub repositories.

Why: whether forks and near-duplicates of held-out repositories are held out too is an open design
question, and the first step is to measure how many pool repositories are in fact forks, renames or
mirrors of a held-out one. Unauthenticated GitHub API (60 requests per hour per address), so the list
must be short; it stops at the limit and records which names were not checked. No credentials.
Usage: github_repo_check.py REPOS.txt OUT.json   (one owner/name per line)
"""
# ruff: noqa  (standalone stdlib tool)

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request


def main() -> None:
    names = [l.strip() for l in open(sys.argv[1]) if l.strip()]
    out = {"checked": {}, "not_checked": [], "rate_limit_remaining_last": None}
    for i, name in enumerate(names):
        req = urllib.request.Request(
            f"https://api.github.com/repos/{name}",
            headers={"Accept": "application/vnd.github+json", "User-Agent": "ril-held-out-check"},
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                rem = r.headers.get("X-RateLimit-Remaining")
                d = json.load(r)
            out["checked"][name] = {
                "status": 200,
                "full_name": d.get("full_name"),
                "fork": d.get("fork"),
                "parent": (d.get("parent") or {}).get("full_name"),
                "source": (d.get("source") or {}).get("full_name"),
                "archived": d.get("archived"),
                "pushed_at": d.get("pushed_at"),
            }
        except urllib.error.HTTPError as exc:
            rem = exc.headers.get("X-RateLimit-Remaining") if exc.headers else None
            out["checked"][name] = {"status": exc.code}
            if exc.code in (403, 429):
                del out["checked"][name]
                out["not_checked"] = names[i:]
                break
        out["rate_limit_remaining_last"] = rem
        time.sleep(0.3)
    json.dump(out, open(sys.argv[2], "w"), indent=1, sort_keys=True)
    print(len(out["checked"]), "checked,", len(out["not_checked"]), "not checked")


if __name__ == "__main__":
    main()
