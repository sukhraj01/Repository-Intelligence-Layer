# CodeSearchNet

- **URL:** https://huggingface.co/datasets/code-search-net/code_search_net (card licence tag "other"). Schema-only check on 2026-10-17 via the dataset-server `first-rows` endpoint (python/test).
- **Parquet layout:** per-language `train` / `validation` / `test` files plus `all/`; python train is 521,785,752 B.
- **Fields:** `repository_name` (`owner/name`, example `soimort/you-get`), `func_path_in_repository`, `func_name`, `whole_func_string`, `language`, `func_code_string`, `func_code_tokens`, `func_documentation_string`, `func_documentation_tokens`, `split_name`, `func_code_url` (GitHub blob URL with commit).
- **Repository identifier: yes** (`repository_name`), so a repository-level filter is possible. Not fetched in bulk.

## Python split repository counts (measured, S4, job 24604: `data/held_out/pool_filter_report_codesearchnet_python.md`)

The three python parquet files (train 521,785,752 B, validation 30,742,555 B, test 28,744,352 B) were read on Ada for the `repository_name` column only. Rows: train 412,178, validation 23,107, test 22,176 (457,461 in all); distinct repositories 12,231 / 679 / 680 (13,590 over the union). Against the held-out list (605 repositories): 44 held-out repositories occur, 8,021 rows (1.75%) dropped, 449,440 rows and 13,546 repositories survive. Top dropped by rows: pypa/pipenv 1,726; mikedh/trimesh 708; pydata/xarray 523; Azure/azure-sdk-for-python 482; quantumlib/cirq 438. Survival is a measurement, not a choice of pool (ADR-001).

**Renames defeat an exact-name filter.** CodeSearchNet was built in 2019 and repository names have changed since. Of 51 surviving repositories that share a name with a held-out repository and were looked up on the GitHub API, 16 (1,603 rows) now resolve to a held-out repository (for example `pycqa/pylint` to `pylint-dev/pylint`, which is a SWE-bench Verified repository, `pycqa/astroid`, `samuelcolvin/pydantic`, `sdispater/poetry`, `pantsbuild/pex`); 2 no longer exist; none is a fork. Counts under both readings are in the pool report; the rule is Open question Q8.
