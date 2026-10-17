# data/held_out/

The repositories that must never appear in training data: the union of CORE-Bench Level-2 and
Level-3 (the Rewrite variants name the same repositories) and SWE-bench Verified repositories.
**Tracked in git**; only repository names and counts are stored, never dataset text. Contract:
`specs/held_out_repos.md`. Rebuild with `python -I scripts/build_held_out.py`.

List schema 2: `repos` is the core tier; `tiers.loc_bench` is a separate tier (held out by default,
switchable); `aliases` maps recorded names to current names. Matching: exact names plus current-name
resolution; the fork network is a sensitivity report only.

| File | Content |
|---|---|
| `held_out_repos.json`, `held_out_repos.sha256` | sorted canonical `owner/name` list with the sources of each repository, and its hash |
| `report.md` | repositories per source, union, overlaps, Loc-Bench reference, paired n |
| `pool_filter_report_<pool>.md` | instances and repositories before and after the filter, per candidate pool |
| `pool_kept_repos_<pool>.json` | repositories surviving the exact-name filter (input to the disjointness test) |
| `rename_cache.json` | current GitHub name, fork flag and fork parent/source per looked-up repository (names and flags only; filled on the cluster by `scripts/ada/resolve_renames.py`) |
| `reference_loc_bench_repos.json` | copy of the Loc-Bench tier inputs |
