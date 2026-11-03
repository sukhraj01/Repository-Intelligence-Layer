# Derived figures quoted in the E-MINE-PILOT entry

Evidence class: measured (sums and ratios of logged values; the logs are named).

  (`m1_agreement.json`, `table.corpus_diff`).
- Listing pages of the pilot: 1,108 + 2,083 + 713 = 3,904 GraphQL calls in the three listing jobs; GraphQL points of the pilot:
  1,089 + 2,079 + 711 + 205 = 4,084 (`results/logs/mine_pilot_listing_shards_2026-11-02.json`, `results/logs/mine_pilot_2026-11-03.json`
  `sessions`). The slowest listing job took 9,248.5 s = 2.6 hours.
- Mined pull requests with at least one unparsed corpus file: 133 of 1,391 = 9.6% (`m2_summary.json`,
  `parse_failures.mined_prs_with_unparsed_corpus_file`).
- Side-table positives of the pilot (class and module units, DEV-016): 2,843 module + 1,350 class = 4,193. Command over the
  `pr_meta.json` files of the run root (not tracked, they hold function ids of 1,391 directories):
  `sum(1 for m in metas for p in m["positives"] if not p["in_corpus"])`, split by `p["unit_kind"]`.
