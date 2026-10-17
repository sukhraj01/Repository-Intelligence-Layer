# Pool filter report: gangiswag_train_data_python

Pool: `gangiswag/train_data` train.zip, python folders (CANDIDATE, provisional; Open question Q7, not chosen as the pool). Unit counted: rows are instance directories `train/python/<owner>__<name>-<PR>/`; repository names are read from directory names in the zip central directory, nothing else was fetched.

Held-out list: `held_out_repos.json` (exact canonical names, no fork rule, no Loc-Bench). This is a measurement of survival, not a choice of training pool.

|  | instances | repositories |
|---|---|---|
| before | 24,285 | 2,448 |
| after (exact-name filter) | 20,854 | 2,359 |
| surviving | 85.87 % | 96.36 % |


Held-out repositories present in the pool: 89.

Top dropped repositories (by instances):

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


## Sensitivity to the two open rules (both reported, neither chosen)

| rule | instances after | repositories after |
|---|---|---|
| exact names only (above) | 20,854 | 2,359 |
| exact names + Loc-Bench repositories (open question) | 20,854 | 2,359 |
| exact names + current-name resolution of 10 same-name candidates checked on GitHub | 20,800 | 2,356 |


Fork / near-duplicate evidence: 10 surviving pool repositories (81 instances) share a repository name with a held-out repository under a different owner. 10 of them were looked up through the unauthenticated GitHub API (60 requests per hour); 0 were not checked. Among the checked: 3 resolve to a held-out repository under its current name (a rename or ownership transfer, so the exact-name filter lets them through): airtai/faststream, jazzband/django-dbbackup, lepture/authlib; 0 are forks whose fork-network root or parent is held out; 0 no longer exist. Renamed repositories whose name part differs, and forks with other names, cannot be found this way: this is a lower bound.
