# Mined training set: measurements

Tables and logs of E-MINE-PILOT (`docs/experiments/B.md`). Evidence class of every table: measured, exploratory,
outside the pre-registered RQ tables. A table here comes from a run on the live API; nothing in this folder is produced
from recorded or synthetic responses (those exist only in the test suite).

**Status 2026-11-03:** M1 done (`m1_agreement.md`, `m1_agreement.json`, hand-check file `handcheck_20.md`, untracked). M2 to M4 tables are
added below as they finish, each with the command that produced it. The token and the API were available (checked 2026-11-02).

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

## Amendments to the rank reading rule, written before M3 runs (2026-11-03, after M1 and the cost estimate)

M1 showed that the pool's corpora hold no test-file function and none of its positives lies in a test file
(`m1_agreement.md`). The shares are therefore measured in two readings, both stated here before any rank exists:

- **as mined** (`READING=all`): the corpora and positives as the miner wrote them (test-file functions in the candidate set,
  test positives kept, D69);
- **pool-like** (`READING=non_test`): no test-file function in the corpora, no test positive, directories without a positive
  outside tests dropped. This is the reading whose construction is closest to the pool's; it is the one a comparison with the
  published shares is read from. The as-mined reading is reported beside it and is not compared with the pool's shares.

The stage limit is 2 GPU-hours. The measured cost (`rank-estimate`, at the rate named in the table) decides how many directories
the dense passes can take: BM25 (CPU) runs on every directory of a reading, the dense teachers on the first N directories of
the seeded order `sha256("0:<directory>")` that the reading keeps, N chosen from the estimate so that three dense passes fit
under the limit (DEV-022). The reading rule below applies to the number of directories **with a positive in the set a share is
measured on** (all for BM25, N for the dense teachers). Two shares are compared only if both sets have at least 100 such
directories; the mined repositories are those of the published pool (so not a different repository mix from the pool), the
Verified export is a different repository set (stated beside the table).

## Files

Run roots live under the cluster home (`~/ril_mine/runs/<name>`), not here: they hold issue text. From a run root:
`<run root>/summary.json` (yield, selection, parse failures, link quality), `<run root>/provenance.json`, `<run root>/budget.json`, `<run root>/state.jsonl`.
Tables derived from them are written here with the command that produced them quoted next to the numbers.
