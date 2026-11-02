# Mined training set: measurements

Tables and logs of E-MINE-PILOT (`docs/experiments/B.md`). Evidence class of every table: measured, exploratory,
outside the pre-registered RQ tables. A table here comes from a run on the live API; nothing in this folder is produced
from recorded or synthetic responses (those exist only in the test suite).

**Status 2026-11-02:** no table yet. The read-only token is not available on the cluster, so the live stages (validation
on five repositories, the 200-repository pilot, the rank measurement) have not run.

## Reading rule for the rank comparison (written before it runs)

The measure is the share of mined directories with no positive in the top 10 under a teacher (BM25, CodeRankEmbed,
SweRankEmbed-Small), with the published definition of the rank (`ril/training/pool_ranks.py`), a directory-level Wilson
interval and a repository-clustered bootstrap interval beside it. It is compared with the published pool and the
never-filtered Verified export of E-POOL-RANKS, teacher by teacher.

- The comparison counts only with **at least 100 mined directories that have a positive**. With fewer it is reported as
  "too small to compare", together with the number of pull requests that the measured yield says are needed.
- Two shares are called different only if each lies outside the other's interval. Otherwise: indistinguishable at this size.
- Repository mix differs between the sets (the mined repositories are those of the pool; the Verified export is a different
  repository set); this is stated beside the table and no difference is attributed to selection from this comparison alone.
- A mocked or recorded response never enters a table or a ledger row.

## Files

Run roots live under the cluster home (`~/ril_mine/runs/<name>`), not here: they hold issue text. From a run root:
`<run root>/summary.json` (yield, selection, parse failures, link quality), `<run root>/provenance.json`, `<run root>/budget.json`, `<run root>/state.jsonl`.
Tables derived from them are written here with the command that produced them quoted next to the numbers.
