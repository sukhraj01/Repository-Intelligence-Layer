# M1: mined positives against the published pool's (E-MINE-PILOT question 1)

Evidence class: **measured, exploratory**. Live GitHub API, job 54256 (validation, `u22`), code at commit `6cbd3bf`
(run root `~/ril_mine/runs/m1b`, listings from the run of 2026-11-02). Table data: `m1_agreement.json` (one row per
pull request: ids only, no text). Command that produced it:

    python3 -I scripts/mine_pilot.py agreement runs/m1b runs/m1b/agreement.json --listing ~/ril_s2/raw/ziplist_train.json

**Sample (DEV-025).** Five repositories of the seeded order of the 5,000-directory population (libsast, esphome,
py-evm, airflow, pyapacheatlas; their linked merged pull requests number 4 + 2,000 + 121 + 5,544 + 20). Pull requests
that the published pool holds and that have a closing reference are mined first: 45 of them (libsast 1, esphome 0,
py-evm 28, airflow 8, pyapacheatlas 8). 17 further pull requests of the seeded order were mined before the stage was
stopped (62 attempted in all: 54 mined, 5 with no Python change, 3 quarantined as `changed_file_unparseable:syntax-other`).
**42 pull requests are in both sets and mined** (the 3 quarantined ones are pool pull requests that the miner could not
parse; that is a 3 of 45 yield loss on the pool's own pull requests). The yield of this sample is not a yield estimate
(published pull requests first).

## Agreement of the positive sets (42 pull requests)

| reading | exact match | mean Jaccard | median Jaccard | extra mined (not in pool) | missing (in pool, not mined) |
|---|---|---|---|---|---|
| all positives | 9 of 42 (21.4%) | 0.690 | 0.707 | 320 in 33 PRs | 0 |
| outside test files | 20 of 42 (47.6%) | 0.823 | 0.985 | 148 in 22 PRs | 0 |

Every pool positive of these pull requests is a mined positive (0 missing in both readings). The pool's positives total
708; none lies in a test file (the dataset card's statement holds on these 42 pull requests, D85). Of the 320 extras,
172 (53.8%) are in test files (D9 path rule). Over all 54 mined directories, 194 of 1,065 mined positives (18.2%) are in
test files; this is a published-first sample, so the share is not an estimate for the whole set.

## What the 148 extras outside test files are

| class of the extra | count | reading |
|---|---|---|
| in the pool's corpus, a pure insertion (no old line removed in the function) | 42 | the pool does not label a function whose only change is added lines |
| in the pool's corpus, the whole function removed by the pull request | 53 | the pool labels 87 other whole-function removals, so removal alone does not separate them |
| not in the pool's corpus, defined with `async def` | 43 | the pool's corpus has no async functions of these snapshots |
| not in the pool's corpus, other | 9 | not explained |
| in the pool's corpus, other | 1 | not explained |

Agreement if one more kind of positive is dropped from the mined set (outside test files; computed from the stored
positives, `agreement.VARIANTS`):

| mined set | exact match | mean Jaccard | extra | missing |
|---|---|---|---|---|
| outside test files | 20 of 42 (47.6%) | 0.823 | 148 | 0 |
| minus pure insertions | 27 of 42 (64.3%) | 0.904 | 104 | 0 |
| minus whole-function removals | 14 of 42 (33.3%) | 0.761 | 91 | 87 |
| minus both | 20 of 42 (47.6%) | 0.841 | 47 | 87 |
| minus both, and only functions in the pool's corpus | 25 of 42 (59.5%) | 0.894 | 1 | 87 |

Reading: dropping pure insertions raises agreement without losing a pool positive; dropping whole-function removals loses
87 pool positives, so the pool does include removed functions. No single rule found here reproduces the pool: with all
three differences removed 59.5% still match exactly, and the 87 missing are the price of dropping removals. The pool's
construction rule is not documented in the sources read; this is an **open question**, not a finding about which set is right.

## The corpora differ as well (candidate sets, not only labels)

Over the 42 pull requests the corpus ids of the two sets have a median Jaccard of 0.62 (range 0.41 to 0.82; 144,657
functions in both). Functions only in the mined corpus: 165,847 in test paths, 4,637 `async def` outside tests, 3,934
other; only in the pool's corpus: 4,152. The pool's corpus has no test-file functions and (in the snapshots examined) no
async functions, and it holds functions that the miner's corpus does not (the miner skips vendored directories such as
`_vendor` and takes top-level functions and methods only). Whether the pool's snapshot is the same commit as the
merge base used here is not established. The consequence for M3: rank shares of the mined set describe a candidate set
with test functions in it; the ranks are not comparable with the pool's unless the test functions are removed from the
corpus (a labelled variant, not the default).

## Hand-check

`results/mining/handcheck_20.md` (untracked: third-party issue text and diffs): 20 mined pull requests of seed 0 with the
issue title, the changed hunks (first 30 lines of at most 6 Python files) and the mined positives. It reports what the miner
stored beside the diff. It claims no correctness; the engineer reads it.

## Live-shape assumptions from the M0 entry, checked against the live API

- `baseRefOid` of a merged pull request is not the compare base: the miner uses the merge base of the compare response
  (as designed); both are stored (`base_commit`, `base_ref_oid`).
- `closingIssuesReferences` returned linked issues for merged pull requests; 133 of the 2,145 linked pull requests of the
  first four repositories have a body reference that is not in the closing list (regex-only recall, counted, not used;
  `summary.json` of the 20-pull-request smoke session `runs/validation`, `links.prs_with_regex_ref_not_in_closing_refs`).
- Compare `files` and `patch`: patches were present for Python files in all mined pull requests; no `patch_missing`
  quarantine occurred in this sample.
- A shallow fetch of an arbitrary commit by SHA from github.com works (`git fetch --depth 1 <url> <sha>`).
