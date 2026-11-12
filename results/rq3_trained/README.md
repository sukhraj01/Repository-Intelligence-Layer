# Trained arms of RQ3: planning table

`block4_plan_18_models.csv` is the output of `ril.evaluation.rq3_trained.plan_jobs` for the 18 mined models
(six cells including the conditional FILTER-SweRankEmbed-Small cell, seeds 100 to 102, 100 updates), in both orders
(`protocol`, `primary_first`). It is **planned, not measured**: cost per model is the planning constant 0.68 GPU-hours
(0.377 measured for the 341 built instances plus about 0.29 projected for the 36 earlier ones), Block 4 cap 6.0 with
0.377 spent. No model exists yet; manifest hashes are absent. Rebuilt by the call in `docs/experiments/B.md`
(entry E-RQ3-TRAINED-ARMS); the real plan is printed from the retained manifests by
`scripts/rq3_trained_arm.py plan --retained-root DIR`.

`dry_run_report.json` (when present) is the result of the dev-set dry run of `scripts/ada/rq3_trained_dryrun.sbatch`.
