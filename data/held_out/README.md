# data/held_out/

The repositories that must never appear in training data: the union of CORE-Bench Level-2,
Level-3 (and REWRITE variants) and SWE-bench Verified repositories. **Tracked in git.** Empty until
the held-out list is built. Contract: `specs/held_out_repos.md`.

Expected contents: `held_out_repos.json`, `held_out_repos.sha256`, `report.md`, and one
`pool_filter_report_<pool>.md` per candidate training pool.
