# SWE-bench Verified

- **URL:** https://huggingface.co/datasets/princeton-nlp/SWE-bench_Verified (retrieved 2026-10-17; fetched on Ada, read with pyarrow)
- **Files:** `data/test-00000-of-00001.parquet` (2,096,679 B), `README.md`.
- **Measured** (`results/tables/hf_metadata_summary.json`): 500 rows, 500 distinct `instance_id`, split `test`, 12 distinct repositories, `created_at` from 2013-01-25 to 2023-08-07.
- **Fields (all strings):** repo, instance_id, base_commit, patch, test_patch, problem_statement, hints_text, created_at, version, FAIL_TO_PASS, PASS_TO_PASS, environment_setup_commit, difficulty.
- **Naming:** `repo` is canonical `owner/name`: astropy/astropy 22, django/django 231, matplotlib/matplotlib 34, mwaskom/seaborn 2, pallets/flask 1, psf/requests 8, pydata/xarray 22, pylint-dev/pylint 10, pytest-dev/pytest 19, scikit-learn/scikit-learn 32, sphinx-doc/sphinx 44, sympy/sympy 75. `instance_id` is `owner__name-PR`.
- **Relation to CORE-Bench:** CORE-Bench L2 has 432 and L3 302 Verified queries (card = manifest). Per-repository, L2 counts are lower than the 500-row counts (django 188 vs 231, pytest 15 vs 19). Which instances are dropped is for the instance mapping.
- Licence: see dataset card (not re-read here).
