# CodeSearchNet

- **URL:** https://huggingface.co/datasets/code-search-net/code_search_net (card licence tag "other"). Schema-only check on 2026-10-17 via the dataset-server `first-rows` endpoint (python/test).
- **Parquet layout:** per-language `train` / `validation` / `test` files plus `all/`; python train is 521,785,752 B.
- **Fields:** `repository_name` (`owner/name`, example `soimort/you-get`), `func_path_in_repository`, `func_name`, `whole_func_string`, `language`, `func_code_string`, `func_code_tokens`, `func_documentation_string`, `func_documentation_tokens`, `split_name`, `func_code_url` (GitHub blob URL with commit).
- **Repository identifier: yes** (`repository_name`), so a repository-level filter is possible. Not fetched in bulk.
