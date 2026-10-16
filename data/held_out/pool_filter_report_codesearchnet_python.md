# Pool filter report: codesearchnet_python

Pool: CodeSearchNet python (train, validation, test parquet files). Unit counted: rows are functions (comment-code pairs); `repository_name` identifies the repository.

Held-out list: `held_out_repos.json` (exact canonical names, no fork rule, no Loc-Bench). This is a measurement of survival, not a choice of training pool.

|  | instances | repositories |
|---|---|---|
| before | 457,461 | 13,590 |
| after (exact-name filter) | 449,440 | 13,546 |
| surviving | 98.25 % | 99.68 % |


Held-out repositories present in the pool: 44.

Top dropped repositories (by instances):

| repository | instances |
|---|---|
| pypa/pipenv | 1,726 |
| mikedh/trimesh | 708 |
| pydata/xarray | 523 |
| azure/azure-sdk-for-python | 482 |
| quantumlib/cirq | 438 |
| pgmpy/pgmpy | 347 |
| ibis-project/ibis | 293 |
| aiogram/aiogram | 281 |
| kubernetes-client/python | 266 |
| delph-in/pydelphin | 237 |
| dpkp/kafka-python | 237 |
| unidata/metpy | 234 |
| gitpython-developers/gitpython | 229 |
| serge-sans-paille/pythran | 207 |
| quantecon/quantecon.py | 206 |


## Sensitivity to the two open rules (both reported, neither chosen)

| rule | instances after | repositories after |
|---|---|---|
| exact names only (above) | 449,440 | 13,546 |
| exact names + Loc-Bench repositories (open question) | 445,640 | 13,534 |
| exact names + current-name resolution of 51 same-name candidates checked on GitHub | 447,837 | 13,530 |


Fork / near-duplicate evidence: 51 surviving pool repositories (3,532 instances) share a repository name with a held-out repository under a different owner. 51 of them were looked up through the unauthenticated GitHub API (60 requests per hour); 0 were not checked. Among the checked: 16 resolve to a held-out repository under its current name (a rename or ownership transfer, so the exact-name filter lets them through): ajbosco/dag-factory, albu/albumentations, django-dbbackup/django-dbbackup, fizzadar/pyinfra, fmfn/bayesianoptimization, github/octodns, jjkester/django-auditlog, pantsbuild/pex, pycqa/astroid, pycqa/pylint, rare-technologies/smart_open, samuelcolvin/pydantic, sdispater/poetry, spulec/moto, warner/magic-wormhole, zalando/patroni; 0 are forks whose fork-network root or parent is held out; 2 no longer exist. Renamed repositories whose name part differs, and forks with other names, cannot be found this way: this is a lower bound.
