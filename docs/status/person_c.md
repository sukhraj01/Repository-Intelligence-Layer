# Person C status

Updated 2026-10-30. Branch `c/eval-rq3`, based on `foundation-v0` (04da656).

## Current state

C1 apparatus: original-label L2/L3 Rewrite loader (D13), shared exact/clustered statistics,
BM25/cached dense adapters and `make eval`. API: `docs/EVAL_API.md`. Commit 66d0f6f passed 503
unit tests/three optional torch skips, full lint and strict typing. Published BM25 artifact
values pinned; actual-corpus reproduction and dense paired dev ablation remain blocked.
Synthetic n=2 queries/2 repositories per level, seed 0/2,000 draws: Rewrite-original nDCG@10
-36.9070 pp [-36.9070,-36.9070], Recall@100 0 [0,0]; intentional fixture anchor removal only.
Config hash `66d0c46d7b3a0bf6ba2517d107a427a2ec52ce37525dff1851dcd2e29c462b3e`.

C2 raw PR miner preserves every base-commit overlapping function/method, including tests and
ordinal collisions, with unchanged training-reader compatibility, request/PR checkpoints,
rate-limit/retry handling, both-side name resolution, content-audit status and provenance.
Standard two-parent merges admitted; unsupported histories quarantined/counted. Added functions
have no base target; partial parses/discovery quarantine a PR. No retriever filters positives.
Measured synthetic plumbing: 200 candidates; 199/198/197 after exact/current-name/Loc-Bench;
1,970 merged PRs, 1,773 issue-linked, 197 parse-incomplete, 1,379 retained PRs/1,576 positives;
7,688 mock calls. BM25 no-positive-top-10 85.714% [85.714,85.714], n=1,379/197 repositories,
2,000 clustered draws, seed 0. Repeated templates explain the degenerate interval; no scientific
yield/rank evidence. Actual-data/dense audit n=0; actual content audit blocked, not zero.
Archived teacher-labelled comparison table includes CodeRankEmbed 15.3%, BM25 23.2%, and
19.3% Verified under SweRankEmbed-Small stored text. C2 commit 645925b passed 522 unit tests.

C3 agent interfaces and complete scripted fixture path now built: one retrieval boundary,
independent exact-edit application and executable hidden fixture tests, three conditions,
per-instance paired/discordance rows, usage/timing/source identities and exact statistics.
Five versioned papers read in full across 216 pages, including appendices/tables/numeric figures;
checked source notes are ready for the documentation owner. Historical criteria/options and
page-specific sources are in `docs/EVAL_API.md`; no current-release capability claim or ADR choice.
Agentless remains the existing provisional ADR-007 candidate, not a selected scaffold.

Measured synthetic plumbing only: 20 fixtures/4 artificial repositories per condition;
none/BM25/oracle resolve 4/12/16 (20/60/80%, intervals [20,20]/[60,60]/[80,80]); discordance
40/20/60% for BM25-none/BM25-oracle/none-oracle. These constructed patterns/degenerate intervals
are not real dev results. Synthetic accounting dollars .000508/.001298/.001262; actual dollars 0.
Illustrative fixture MDE at n=302/432 is reported only as arithmetic; scientific cost/discordance/
MDE unavailable at real n=0. Whole CLI 14.86 s, peak RSS 42,696 KiB; no model call or local load.
Config `4cf5f835395a8d01ba137a7a09e7c7e0d4bc29fecbf34314da750c062b764cb1`; source hash
`6503d2e1c30663ed7f7afb0b79f1bd892edffd431b4c7a544e57cb9b3a074de6`. Final log
`results/logs/c3_fixture_pilot_guarded_2026-10-30.json`. Not a published-scaffold replication.

Current unit suite: 538 pass/three optional torch skips; full ruff/format passes (282 files),
strict mypy passes (121 modules). Synthetic per-commit 20 latency/4 throughput rows stored in
C3 results. Append-only evidence: `results/ledger_c.md`, E-C1-EVAL, E-C2-RAW-PR, E-C3-AGENT-PILOT.

## Blockers and compute

Original/Rewrite corpora, pinned dense artifacts, read-only mining token, real held-out content
index and real agent dev inputs are absent. Account C connection/quota/partition/card unverified.
C2 pool remains in memory: measure real sample memory/disk before scaling. Above 200 repositories/
2,000 PRs rejected; full scale waits for real pilot and explicit engineer go. No cluster job.
No model selection/access/spend cap or reviewed real scaffold/harness; live gate fails closed.
Synthetic fixtures are trusted subprocess tests, not a live-code sandbox. GPU-hours used: 0 of 8.

## Requests for the lead

| Question | Options | Evidence class | Cheapest experiment | Recommendation | Meanwhile |
|---|---|---|---|---|---|
| Adopt shared statistics/timing API? | migrate consumers; retain duplicates | measured parity | owner runs table tests | preserve frozen outputs | compatibility exports; separate cache timing |
| Supply account C data/access? | real dev ablation and PR pilot; apparatus only | measured absence | verify allocation; stage one folder | supply corpora, pinned scores, read-only token/content index | D13/D17; no substitution |
| Support other merge histories? | validate squash/rebase patches; quarantine | measured Git fixture; reasoned coverage bias | compare two representative PR diffs | validate before admission | standard merge parents only |
| Expand mining after pilot? | approve measured scale; defer | measured synthetic only | real 200-repository pilot and memory probe | defer full scale pending yield/cost/ranks | provisional ADR-001, D1/D3; hard 200/2,000 caps |
| Which scaffold/boundary? | Agentless stage; SWE-agent/OpenHands tool | read in full | pinned offline adapter fixture | compare treatment isolation | provisional ADR-007; scripted only |
| Which model/spend? | hosted; pinned local | measured absence | capped paired dev pilot | obtain real cost/discordance | provisional ADR-008; no calls |
| Admit qualified paper notes? | owner integrates; retain separately | read in full | check five notes | preserve page qualifications | criteria sources only |

## Next work

C4: build paired/resumable/idempotent/spend-capped orchestration and diagnostics; dry-run 10
synthetic fixtures with two retrievers, verify deterministic replay or explicit mismatch reasons.
Then stage bounded real data and audited scaffold only when access/cap/approval gates clear.
Scientific pilot n=0, full mining scale and all design decisions remain open.
