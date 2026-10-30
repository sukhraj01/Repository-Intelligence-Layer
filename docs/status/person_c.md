# Person C status

Updated 2026-10-30. Branch `c/eval-rq3`, based on `foundation-v0` (04da656).

## Current state

C1 apparatus is implemented: original-label L2/L3 Rewrite loader (D13); shared statistics,
paired repository-clustered intervals, power compatibility, BM25/cached dense scorer and
`make eval CONFIG=...`. API: `docs/EVAL_API.md`. Parent verification of exact commit 66d0f6f on
Python 3.11.18: 503 unit tests pass, three optional torch suites skip; full ruff/format and strict
mypy pass. Synthetic original/Rewrite smoke runs; published BM25 artifact values are pinned exactly.
Actual-corpus BM25 reproduction and paired dense dev ablation remain blocked, not passed by fixtures.

C1 synthetic config hash `66d0c46d7b3a0bf6ba2517d107a427a2ec52ce37525dff1851dcd2e29c462b3e`,
seed 0, 2,000 clustered draws: each level n=2 queries/2 repositories; Rewrite-original nDCG@10
-36.9070 pp [-36.9070,-36.9070], Recall@100 0 [0,0]. This measures intentional fixture anchor
removal. Shared statistics preserve nine archived MDE cells and 45 archived exact power cells.

C2 raw PR miner, CPU acquisition job, gated dense audit job and recorded-response pilot are built.
Every base-commit overlapping function/method is kept, including tests and ordinal collisions;
no retriever selects positives. Output is readable by the unchanged training reader. Request/PR
checkpoints, API reset/retry handling, both-side name resolution, Loc-Bench counts, content-audit
status, immutable history provenance and identity-validated score caches are implemented.
Standard two-parent merges are admitted; unsupported histories are quarantined and counted.
Added functions/files have no base target. Partial parses/discovery quarantine the whole PR.

Evidence class measured **synthetic plumbing only**: 200 repository candidates; 199/198/197 after
exact/current-name/Loc-Bench rules; 1,970 merged PRs; 1,773 issue-linked; 197 parse-incomplete;
1,379 retained PRs/1,576 positives. 7,688 mock transport calls; timing and memory in E-C2-RAW-PR.
BM25 no-positive-top-10 share 85.714% [85.714,85.714], n=1,379/197 repositories, 2,000 clustered
bootstrap draws, seed 0. Repeated synthetic templates explain the degenerate interval; this is
not scientific yield or rank evidence. Teacher-labelled archived comparisons exist in
`results/tables/c2_raw_pr_rank_comparison.csv`; 19.3% Verified uses SweRankEmbed-Small stored text.
Actual-data pilot/dense ranks have n=0; real content-overlap audit is blocked, never assumed zero.

C2 focused tests pass (19); full Python 3.11.18 unit suite: 522 pass, three optional torch skips.
Full ruff/format and strict mypy pass (114 modules). No local model load, encoding or training.
Logs and append-only evidence: `results/ledger_c.md`, E-C1-EVAL and E-C2-RAW-PR.

## Blockers and compute

Original/Rewrite corpora, pinned dense artifacts, read-only mining token and real held-out content
index are absent. Account C connection/quota/partition/card remain unverified in this checkout.
Synthetic memory does not size real snapshots: the miner and rank reader retain the selected pool
in memory, so measure real sample memory/disk before scaling. GPU-hours used: 0 of C's 8.
C2 mock gate passed; actual-data gate blocked. Limits above 200 repositories/2,000 PRs are rejected.
Full-scale mining waits for a real pilot and explicit engineer go. No cluster job was submitted.

## Requests for the lead

| Question | Options | Evidence class | Cheapest experiment | Recommendation | Meanwhile |
|---|---|---|---|---|---|
| Adopt shared statistics/timing API? | migrate consumers; retain duplicates | measured parity | owner runs table tests | preserve frozen outputs | compatibility exports; separate cache timing |
| Supply account C data/access? | real dev ablation and PR pilot; apparatus only | measured absence | verify allocation; stage one folder | supply corpora, pinned scores, read-only token/content index | D13/D17; no substitution |
| Support other merge histories? | validate squash/rebase patches; quarantine | measured Git fixture; reasoned coverage bias | compare two representative PR diffs | validate before admission | standard merge parents only |
| Expand mining after pilot? | approve measured scale; defer | measured synthetic only | real 200-repository pilot and memory probe | defer full scale pending yield/cost/ranks | provisional ADR-001, D1/D3; hard 200/2,000 caps |

## Next work

Verify account C and a real sample's memory/disk; run the bounded CPU mining pilot, report actual
held-out loss/parse/history yield/cost/content audit, then run pinned dense audit within budget.
Exact commands are in E-C2-RAW-PR. Obtain original/Rewrite dev inputs for C1. No design decision
was made. Full scale and live agent execution remain gated on the engineer's instructions.
