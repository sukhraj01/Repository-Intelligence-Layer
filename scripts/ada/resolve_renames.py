"""Resolve current GitHub names for held-out and pool repositories (decision D1).

Reads the pool's repository counts and the held-out list, looks up every repository that has no
final answer in the rename cache, and writes the cache back. The order is: the SWE-bench Verified
repositories, then pool repositories sharing a name part with a held-out one, then the rest by
descending instance count, so a rate-limited run covers the most useful names first.

Authentication: if ``GITHUB_TOKEN`` is set it is used as a read-only bearer token (public-repo
scope is enough); it is never printed, logged or written. Without it the API allows 60 requests
per hour per address and the run stops at the limit, reporting what was not checked; rerun later or
with a token and it continues where it stopped. Idempotent and resumable.

Usage (needs the ``ril`` package on the path, stdlib only otherwise, Python 3.9+):
  python3 -I resolve_renames.py RIL_ROOT CACHE.json POOL_REPOS.json HELD_OUT.json OUT_STATS.json DATE [MAX_REQUESTS]
"""
# ruff: noqa: T201, E501

from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> None:
    root, cache_p, pool_p, held_p, stats_p, date = sys.argv[1:7]
    max_req = int(sys.argv[7]) if len(sys.argv) > 7 else None
    sys.path.insert(0, root)
    from ril.training.rename_resolution import (
        GitHubTransport,
        load_cache,
        priority_order,
        rate_limit_remaining,
        resolve_names,
        save_cache,
    )

    transport = GitHubTransport.from_env()
    cache = load_cache(Path(cache_p))
    pool = json.load(open(pool_p))["repos"]
    held = json.load(open(held_p))
    verified = sorted(r for r, srcs in held["repos"].items() if "Verified" in srcs)
    order = verified + [
        n for n in priority_order(list(pool), list(held["repos"]), pool) if n not in verified
    ]
    before = rate_limit_remaining(transport)
    print("authenticated:", transport.authenticated, "| rate limit remaining:", before)
    stats = resolve_names(order, cache, transport, date, max_requests=max_req, reserve=2)
    save_cache(
        Path(cache_p), cache, note="names and flags only; see ril/training/rename_resolution.py"
    )
    after = rate_limit_remaining(transport)
    doc = {
        "date": date,
        "authenticated": transport.authenticated,
        "rate_limit_before": before,
        "rate_limit_after": after,
        "names_requested": stats.requested,
        "already_final": stats.already_final,
        "looked_up": stats.looked_up,
        "not_checked": len(stats.not_checked),
        "failed": list(stats.failed),
        "stopped_by_rate_limit": stats.stopped_by_rate_limit,
        "cache_entries": len(cache),
    }
    json.dump(doc, open(stats_p, "w"), indent=1, sort_keys=True)
    print(json.dumps(doc, sort_keys=True))


if __name__ == "__main__":
    main()
