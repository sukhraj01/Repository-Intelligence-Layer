# Pool filter report: codesearchnet_python

Pool: CodeSearchNet python (train, validation, test parquet files). Unit counted: rows are functions (comment-code pairs); `repository_name` identifies the repository.

Held-out list: `held_out_repos.json` (schema 2): exact canonical names of the core tier, current-name resolution (D1), Loc-Bench tier (D3); the fork network is a sensitivity row only. This is a measurement of survival, not a choice of training pool.

| rule (cumulative) | instances after | repositories after | repositories dropped |
|---|---|---|---|
| exact | 449,440 | 13,546 | 44 |
| +current_name | 447,837 | 13,530 | 60 |
| +loc_bench | 444,037 | 13,518 | 72 |
| sensitivity: +fork_network | 444,037 | 13,518 | 72 |


Before: 457,461 instances, 13,590 repositories. Current-name resolution covers 60 of 13,590 pool repositories (7,351 of 457,461 instances); every row after `exact` is a lower bound on full resolution.

## Before and after, against the Wave 1 lower bound

|  | Wave 1 (exact + same-name candidates only) | now (exact + cached current names) |
|---|---|---|
| repositories resolving to a held-out repository under its current name | 16 | 16 |
| instances in those repositories | not counted | 1,603 |
| instances after exact + current-name | n/a | 447,837 |


Repositories that the exact filter keeps and current-name resolution drops: ajbosco/dag-factory, albu/albumentations, django-dbbackup/django-dbbackup, fizzadar/pyinfra, fmfn/bayesianoptimization, github/octodns, jjkester/django-auditlog, pantsbuild/pex, pycqa/astroid, pycqa/pylint, rare-technologies/smart_open, samuelcolvin/pydantic, sdispater/poetry, spulec/moto, warner/magic-wormhole, zalando/patroni.

## Top dropped repositories under the default rule set (by instances)

| repository | instances |
|---|---|
| pypa/pipenv | 1,726 |
| pandas-dev/pandas | 1,633 |
| mikedh/trimesh | 708 |
| secdev/scapy | 578 |
| ray-project/ray | 535 |
| pydata/xarray | 523 |
| azure/azure-sdk-for-python | 482 |
| pycqa/pylint | 481 |
| quantumlib/cirq | 438 |
| pycqa/astroid | 383 |
| pgmpy/pgmpy | 347 |
| spotify/luigi | 326 |
| ibis-project/ibis | 293 |
| aiogram/aiogram | 281 |
| kubernetes-client/python | 266 |


The fork-network row is a sensitivity report: it counts pool repositories that are forks whose parent or source is held out, among the repositories resolved so far. It is never applied as a filter (decision D1).
