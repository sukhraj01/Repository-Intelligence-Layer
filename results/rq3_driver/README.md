# results/rq3_driver/

The RQ3 driver, the held-out model-check slice, the prompts of the executable subset, the replay test, the power table with
run-to-run noise and the cost model (decisions D111 to D114, entry `E-RQ3-DRIVER` in `docs/experiments/B.md`).
No model was called. Nothing here is a resolved rate.

| File | What |
|---|---|
| `heldout_v1.json` | the frozen held-out slice: 50 of the 377 executable instances, seed 0, rule and places per repository (D111); the other 327 are the confirmatory instances |
| `ids_heldout.txt`, `ids_confirmatory.txt` | the two instance lists, one id per line |
| `prepare_report.json` | (superseded by `results/rq3_pseudonymise/`, D120) prompts built from the stored 8,000-token contexts: counts, rejection counts by screen finding and arm, issue-source agreement, prefix identity across arms |
| `prepare_sendable_by_set.csv` | per set and repository: instances whose three prompts all pass the screen, some pass, none pass, and RRF prompts that pass |
| `replay/replay_table.csv`, `replay/results.jsonl`, `replay/meta.json` | the replay test on the real executor (job 64590): 20 gold-derived edit sets and 10 broken variants, expected against observed outcome class |
| `rq3_power_run_noise.csv`, `rq3_power_run_noise_mdd.csv`, `rq3_power_run_noise_assumptions.json` | power of the primary contrast by simulation (N = 327 and N = 232, k = 1 to 3), minimum detectable difference at power 0.8, and which inputs are assumptions |
| `rq3_power_placeholder.csv` | the earlier McNemar table at the same N, kept beside the new one |
| `rq3_cost_model.csv`, `rq3_cost_graded_check_cap.json` | cost of one arm-run and of the grids per candidate price pair (tokens measured in the pilot, prices estimated and unverified), and the recommended cap for the graded check |

Code: `ril/agent/providers/{driver,holdout,spend,model_choice,rq3_prompts,replay_variants,cluster}.py`,
`ril/analysis/{rq3_results,rq3_power_noise,rq3_cost}.py`, `scripts/rq3_driver.py`, jobs `scripts/ada/rq3_driver/`.
Tests: `tests/unit/test_rq3_{holdout,driver,prompts_and_variants,results,driver_cli}.py`.
Commands (seed 0): `python -I scripts/rq3_driver.py heldout results/rq3_exec/executable_instances_v1.json results/rq3_driver/heldout_v1.json`;
`python -I scripts/rq3_driver.py power results/rq3_driver --n 327 232 --sims 500 --permutations 2000 --seed 0`;
`python -I scripts/rq3_driver.py cost results/rq3_driver`.
Hardware of the power and cost runs: laptop, 8 GB, CPU only; the prompt and replay jobs ran on account A (CPU, jobs in `results/logs/ada_jobs.csv`, session RQ3D).
