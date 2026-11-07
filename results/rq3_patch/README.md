# results/rq3_patch/

Conversion of edit blocks to the executor's patch (decision D110, entry `E-RQ3-PATCHAPPLY` in `docs/experiments/B.md`).
Exploratory, 100 development instances for the apply rates; 20 executable instances for the end-to-end check.
No model was called, no resolved rate exists for the dev instances.

| File | What |
|---|---|
| `rq3_patch_apply_by_arm.csv` | the 349 usable pilot units by first stage and in total, outcome counts under the exact and the tolerant reading, usable-and-applying counts with Wilson intervals over the 400 units of each arm |
| `rq3_patch_apply_rescue.csv` | exact-failing units, how many the tolerant reading applies, and how many applying units a stricter base-text rule (no overlap between blocks of one file) would fail |
| `rq3_patch_apply_blocks.csv` | each block on its own: exact outcome by where its SEARCH text is found (in the excerpts shown, in the named file at the base commit) |
| `rq3_patch_apply_units.csv` | one row per usable unit (instance, arm, run, blocks, outcome per reading); no reply text |
| `validation_draw.json` | the seeded draw of 20 executable instances (seed 0) and its strata |
| `validation_gold_derived.csv` | gold-derived edits: conversion, tree check against the gold patch, executor result per instance |
| `runs/job_64288/`, `runs/job_64304/` | executor result rows, run metadata and failure logs of the validation (the second job reran two instances after a node name-resolution failure) |

Code: `ril/agent/providers/patch_convert.py`, `ril/evaluation/gold_edits.py`, `ril/evaluation/patch_validation.py`,
`ril/analysis/rq3_patch_apply.py`, `scripts/rq3_patch.py`, jobs `scripts/ada/rq3_patch/`. Tests: `tests/unit/test_patch_convert.py`,
`test_gold_edits.py`, `test_patch_validation.py`, `test_rq3_patch_apply.py`.

Commands (inputs are kept outside the repository; SHA-256 of the inputs: `calls.jsonl` fa944ddf12aac5198b417c8953768589b5c171a22c9e4eeff29f9dd79c749a3a,
`items.jsonl` 4434e8c6b8bdbe0239b1c47769b7ecaab170e1edb59da50b18dbf77d5bbfc2cb, snapshots 2975774c07455355dd0d6e9b5a012723ca3e3842533785b7f445ee4032fb3f33):

```
python -I scripts/rq3_patch.py needed LOG PREPARED needed.json
sbatch scripts/ada/rq3_patch/snapshot.sbatch            # base-commit text of the 120 named files (job 64286)
python -I scripts/rq3_patch.py table LOG PREPARED snapshots.jsonl results/rq3_patch
python -I scripts/rq3_patch.py draw results/rq3_exec/executable_instances_v1.json results/rq3_patch/validation_draw.json --n 20 --seed 0
sbatch scripts/ada/rq3_patch/validate.sbatch            # derive, convert, tree check, executor (job 64288)
```

Hardware: tables on the laptop (8 GB, CPU only); snapshot and validation jobs on account A, node-local `$TMPDIR`.
Snapshots are public repository text and stay with the inputs, not in this directory.
