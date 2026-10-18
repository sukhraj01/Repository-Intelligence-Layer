# Pool filter report: gangiswag_train_data_python

Pool: `gangiswag/train_data` train.zip, python folders (CANDIDATE, provisional; Open question Q7, not chosen as the pool). Unit counted: rows are instance directories `train/python/<owner>__<name>-<PR>/`; repository names are read from directory names in the zip central directory, nothing else was fetched.

Held-out list: `held_out_repos.json` (schema 2): exact canonical names of the core tier, current-name resolution (D1), Loc-Bench tier (D3); the fork network is a sensitivity row only. This is a measurement of survival, not a choice of training pool.

| rule (cumulative) | instances after | repositories after | repositories dropped |
|---|---|---|---|
| exact | 20,854 | 2,359 | 89 |
| +current_name | 20,800 | 2,356 | 92 |
| +loc_bench | 20,800 | 2,356 | 92 |
| sensitivity: +fork_network | 20,800 | 2,356 | 92 |


Before: 24,285 instances, 2,448 repositories. Current-name resolution covers 47 of 2,448 pool repositories (2,678 of 24,285 instances); every row after `exact` is a lower bound on full resolution.

## Before and after, against the Wave 1 lower bound

|  | Wave 1 (exact + same-name candidates only) | now (exact + cached current names) |
|---|---|---|
| repositories resolving to a held-out repository under its current name | 3 | 3 |
| instances in those repositories | 54 | 54 |
| instances after exact + current-name | n/a | 20,800 |


Repositories that the exact filter keeps and current-name resolution drops: airtai/faststream, jazzband/django-dbbackup, lepture/authlib.

## Top dropped repositories under the default rule set (by instances)

| repository | instances |
|---|---|
| deepset-ai/haystack | 140 |
| sdv-dev/sdv | 132 |
| hypothesisworks/hypothesis | 127 |
| open-telemetry/opentelemetry-python | 123 |
| pex-tool/pex | 113 |
| python-telegram-bot/python-telegram-bot | 112 |
| streamlink/streamlink | 109 |
| huggingface/datasets | 108 |
| mdanalysis/mdanalysis | 103 |
| pypa/pipenv | 100 |
| dbt-labs/dbt-core | 91 |
| python-pillow/pillow | 75 |
| pyomo/pyomo | 72 |
| facebookresearch/hydra | 71 |
| narwhals-dev/narwhals | 71 |


The fork-network row is a sensitivity report: it counts pool repositories that are forks whose parent or source is held out, among the repositories resolved so far. It is never applied as a filter (decision D1).
