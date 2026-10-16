# data/held_out/

The repositories that must never appear in training data: the union of CORE-Bench Level-2 and
Level-3 (the Rewrite variants name the same repositories) and SWE-bench Verified repositories.
**Tracked in git**; only repository names and counts are stored, never dataset text. Contract:
`specs/held_out_repos.md`. Rebuild with `python -I scripts/build_held_out.py`.

| File | Content |
|---|---|
| `held_out_repos.json`, `held_out_repos.sha256` | sorted canonical `owner/name` list with the sources of each repository, and its hash |
| `report.md` | repositories per source, union, overlaps, Loc-Bench reference, paired n |
| `pool_filter_report_<pool>.md` | instances and repositories before and after the filter, per candidate pool |
| `pool_kept_repos_<pool>.json` | repositories surviving the exact-name filter (input to the disjointness test) |
| `reference_loc_bench_repos.json` | Loc-Bench repositories, reported separately and not held out |
