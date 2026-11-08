# RQ3 pilot analysis (E-RQ3-PILOT-RESULT, D109)

Tables computed from the stored call log of the pilot (400 units, 565 calls), its 200 prepared prompts and the
stored per-query assembly rows. Nothing was called and nothing was run on the cluster. Exploratory, 100 dev
instances; no resolved rate exists for them.

- Code: `ril/analysis/rq3_pilot_analysis.py`, `scripts/rq3_pilot_analysis.py`, tests `tests/unit/test_rq3_pilot_analysis.py`.
- Command: `python -I scripts/rq3_pilot_analysis.py <log dir> <prepared dir> results/rq3_pilot/analysis --seed 0`
- Inputs (kept outside the repository; SHA-256): `calls.jsonl` fa944ddf12aac5198b417c8953768589b5c171a22c9e4eeff29f9dd79c749a3a,
  `items.jsonl` 4434e8c6b8bdbe0239b1c47769b7ecaab170e1edb59da50b18dbf77d5bbfc2cb; prepare configuration
  `configs/experiments/rq3_pilot_prepare.yaml` SHA-256 a8ec4fc94cc902a0ef71f6b89aeeedbc0bb788db4a7672a45a25d88717935d09.
- Gold in context: `results/rq3/assembly_gold_2026-11-06/assembly_gold_query_rows.csv`, joined to the prompts by the
  SHA-256 of the context (200 of 200 matched; level L2, budget 8,000; file level reading `units_all`, unit level
  `units_all_nomod`). Dev cells: `results/tables/assembly/assembly_gold_summary.csv`; executable-subset coverage:
  `results/rq3_contexts/rq3_contexts_coverage.csv`.
- Seed 0 (bootstrap), 10,000 resamples over instances; Wilson intervals for shares. Hardware: laptop, 8 GB, no GPU, CPU only.
- No prompt or reply text is stored here. `rq3_pilot_units.csv` has one row per (instance, arm, run) without text or hashes.

| file | analysis |
|---|---|
| `rq3_pilot_cost.csv` | 1: calls, tokens, latency, 429 / 5xx per unit and instance |
| `rq3_pilot_faults_*.csv` | 2: usability by arm and run, fault classes, follow-ups, rescue, edit text in the excerpts |
| `rq3_pilot_contrast_*.csv`, `rq3_pilot_by_repository.csv` | 3: BM25 against RRF (strata, discordance, standardised gap, size, bytes) |
| `rq3_pilot_run_to_run.csv` | 4: agreement of the two runs |
| `rq3_pilot_retrieval.csv`, `rq3_pilot_extrapolation_executable.csv` | 5: gold in context, pilot against dev; estimate for the executable subset |
| `rq3_pilot_cost_per_arm_run.csv`, `rq3_pilot_cost_grids.csv` | 6: cost of the full runs (estimated) |
| `rq3_pilot_power_context.csv` | 7: placeholder table at n = 377 beside the pilot's discordances |
