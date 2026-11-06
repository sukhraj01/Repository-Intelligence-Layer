# results/rq3_exec/

Executable subset of SWE-bench Verified for RQ3 (decision D106, entry `E-RQ3-EXEC` in `docs/experiments/B.md`).

| File | What |
|---|---|
| `executable_instances_v1.json` | the frozen subset: 377 members (cost, policy, departures) and 123 exclusions with reason |
| `repo_table.csv` | per repository: instances, built in both runs, executable |
| `subset_vs_500.csv` | the subset against the 500 by repository, difficulty, L2 and L3 label availability |
| `cost_per_instance.json` | seconds per instance and run (p50, p95, p99), peak memory, time by phase |
| `coverage_table.csv` | executable instances with L2, L3 labels and stored unit records, per repository |
| `unit_build_estimate.csv`, `units_probe/` | estimate of building unit records, and the unit counts it rests on |
| `power_at_n.csv` | minimum detectable difference at N = 377 (placeholder discordances) |
| `older_python_recovery.csv` | instances that needed Python older than 3.8, by repository |
| `runs/<name>/shard_*/results.jsonl`, `meta.json` | one row per (instance, run); `pilot_*` pilots; `full` first pass; `full_x`, `full_s` supplements (later directories replace earlier ones for the instances they hold); `era2` era-dated pass; `full_y`, `full_z`, `era3` stopped or superseded, kept for the record |

Policies in priority order for the subset: `latest` = `full`, `full_x`, `full_y`, `full_z`, `full_s`; then `era` = `era2`.
Regenerate: `python scripts/rq3_exec.py report SPECS --policy latest=... --policy era=... --out-dir results/rq3_exec`
(specifications are rebuilt with `make-specs` from the Verified table and the benchmark package's sources; they are not stored).
