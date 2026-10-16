# SWE-bench Verified

- **URL:** https://huggingface.co/datasets/princeton-nlp/SWE-bench_Verified (retrieved 2026-10-17; fetched on Ada, read with pyarrow)
- **Files:** `data/test-00000-of-00001.parquet` (2,096,679 B), `README.md`.
- **Measured** (S2, `results/tables/hf_metadata_summary.json`): 500 rows, 500 distinct `instance_id`, split `test`, 12 distinct repositories, `created_at` from 2013-01-25 to 2023-08-07.
- **Fields (all strings):** repo, instance_id, base_commit, patch, test_patch, problem_statement, hints_text, created_at, version, FAIL_TO_PASS, PASS_TO_PASS, environment_setup_commit, difficulty.
- **Naming:** `repo` is canonical `owner/name`: astropy/astropy 22, django/django 231, matplotlib/matplotlib 34, mwaskom/seaborn 2, pallets/flask 1, psf/requests 8, pydata/xarray 22, pylint-dev/pylint 10, pytest-dev/pytest 19, scikit-learn/scikit-learn 32, sphinx-doc/sphinx 44, sympy/sympy 75. `instance_id` is `owner__name-PR`.
- **Relation to CORE-Bench:** CORE-Bench L2 has 432 and L3 302 Verified queries (card = manifest). Per-repository, L2 counts are lower than the 500-row counts (django 188 vs 231, pytest 15 vs 19). 
- **Instance mapping (measured, S4, `results/tables/paired_n.json`):** all 432 L2 and all 302 L3 `SWE-bench_Verified` query ids are Verified `instance_id`s (0 absent), and the 302 L3 instances are a subset of the 432 L2 instances. So 432 instances carry both an L2 label set and an executable test, and 302 carry L2, L3 and a test. Dropped from L2 relative to the 500 rows: django 43, sympy 6, sklearn 6, pytest 4, xarray 4, matplotlib 2, sphinx 2, pylint 1 (per-repository table in `knowledge/datasets/core_bench.md`). Which rows the CORE-Bench authors dropped, and why, is not documented.
- **Repository check (measured, S4):** the 12 repositories equal the repositories of the CORE-Bench L2 and L3 `SWE-bench_Verified` folders; they are held out (`data/held_out/held_out_repos.json`, source label `Verified`).
- Licence: see dataset card (not re-read here).
