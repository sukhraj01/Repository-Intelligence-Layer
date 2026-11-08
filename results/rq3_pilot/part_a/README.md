# RQ3 pilot, part A: can resolved rate be measured on the cluster?

Measured 2026-11-06 on account A (CPU jobs, partition `u22`, node-local `/tmp`; nothing deleted).
Scripts: `scripts/ada/rq3_feasibility/`. The home path and login name in the outputs are replaced by
`$HOME` and `<user>`. Reading and answers: `docs/RQ3_PILOT.md`, entry `E-RQ3-PILOT-PREP`.

| Job | Output | What it shows |
|---|---|---|
| 61759 | `probe_a1_job61759.out` | no container runtime on PATH; user namespaces 0; network status of 19 hosts; the Verified parquet (sha256 `a45b1fe4...`) fetched from the dataset hub |
| 61762 | `probe_a2_job61762.out` | dead end: the `uv` download was cut at the job's timeout (a truncated archive), nothing after it ran |
| 61768 | `probe_a3_job61768.out` | the container module's tarball extracted node-locally: the image builds, running it fails on user namespaces; `uv` 0.13.7; `swebench` 5.0.2 installed |
| 61776 | `probe_a4_job61776.out` | dead end: `swebench` 5.x no longer carries the per-repository install specifications |
| 61790 | `probe_a5_job61790.out`, `a_verified_census.json`, `a_gold_checks.json` | `swebench` 4.1.0 pinned; census of the 500 Verified instances; gold-patch checks on four instances |
| 61882 | `probe_a6_job61882.out`, `a_env_census.json` | environment census (80 environments, Python versions, pre-install steps); flask retry with `pytest<8` |
| 61885 | `probe_a7_job61885.out`, `a_env_table.csv` | joint table of Python version by pre-install step, per (repository, version) |

`a_gold_checks.json` holds, per step, the exit status, seconds and the largest resident size of any child
process so far (a cumulative maximum, not per step), with the tail of each output. The flask entry in it
is the first attempt (unpinned pytest); the retry is in the job 61882 output.
