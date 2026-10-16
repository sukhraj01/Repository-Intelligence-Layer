# Loc-Bench

Two public versions of the same benchmark exist; the master document's "660 examples" matches V0.2, not V1.

| | czlll/Loc-Bench_V1 | czlll/Loc-Bench_V0.2 |
|---|---|---|
| Rows (measured) | 560 | 660 |
| Distinct repositories (measured) | 165 | 210 |
| Files | `data/test-*.parquet` (3,084,430 B) | `data/test-*.parquet` and `data/split-*.parquet` (3,913,633 / 3,929,908 B), table-identical |
| Categories (measured) | Bug Report 242, Feature Request 150, Performance Issue 139, Security Vulnerability 29 | Bug Report 275, Feature Request 216, Performance Issue 140, Security Vulnerability 29 |
| Created at | 2015-11-07 to 2025-02-07; 366 of 560 on or after 2024-10-01 | 2015-11-07 to 2025-02-09; 465 of 660 on or after 2024-10-01 |

- V1 instance ids are a strict subset of V0.2 (560 shared, 100 only in V0.2); V1 repositories are a subset of V0.2 repositories (165 of 165).
- Fields: repo, instance_id, base_commit, patch, test_patch, problem_statement, hints_text, created_at (epoch ms, int64), labels, category, edit_functions, added_functions, edit_functions_length. `edit_functions` entries look like `path/to/file.py:Class.method`, non-empty in every row.
- **Discrepancies:** the master document gives categories bug 282, feature 203, security 31, performance 144 (sum 660); neither version matches. "Post-Oct-2024" is not true of every row in either version (see dates above).
- Fetched where: Ada login node (`scripts/ada/hf_fetch.py`); parsed locally with pyarrow. Overlap with SWE-bench Verified repositories exists (for example django/django, matplotlib/matplotlib, scikit-learn/scikit-learn, sphinx-doc/sphinx, sympy/sympy, pylint-dev/pylint). Whether Loc-Bench is held out is an open decision (ADR-005), not made here.

## Overlap with the held-out list (measured, S4: `data/held_out/reference_loc_bench_repos.json`, `data/held_out/report.md`)

The held-out list is the union of CORE-Bench L2, L3 and SWE-bench Verified repositories (605). Loc-Bench V1 has 165 repositories, of which 37 are already in that list and 128 are not; V0.2 has 210, of which 41 are in the list and 169 are not. Loc-Bench repositories are reported separately and are **not** in the list (ADR-005, Open question Q9). Effect on a pool if they were also held out (reported, not chosen): CodeSearchNet python 449,440 to 445,640 instances and 13,546 to 13,534 repositories; the `gangiswag/train_data` python candidate unchanged (no Loc-Bench-only repository appears in it).
