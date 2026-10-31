# Person C status

Updated 2026-10-31 UTC. Branch `c/eval-rq3`, based on `foundation-v0` (04da656).

## Current state

C1 apparatus (0141176): original-label L2/L3 Rewrite loader (D13), shared exact/clustered
statistics, BM25/cached-dense adapters and `make eval`; published BM25 artifact values pinned.
Synthetic n=2 queries/2 repositories per level: Rewrite-original nDCG@10 -36.9070 pp
[-36.9070,-36.9070], Recall@100 0 [0,0], 2,000 draws, seed 0; intentional anchor-removal fixture.
Actual dev BM25 completed per operator: L2n442/6repos,L3n238/3repos per condition.
Rewrite-original L2 nDCG/Recall +1.9258/+2.4049pp;95%intervals include0.
L3 -2.0436pp[-2.6646,-0.9102]/-1.6005pp[-1.7655,-1.3556];only3repository clusters.
Aggregates match registration; full query-pair/interval/timing artifact audit pending.
Dense paired ablation remains gated. API: `docs/EVAL_API.md`.

C2 raw PR miner (e3ee90d): every base-commit overlapping function/method retained, including
tests/ordinal collisions; unchanged training reader, resumable request/PR state, rate limits,
both-side current names and content-audit provenance. Standard two-parent merges only;
unsupported histories and partial discovery/parsing quarantined. No retriever filters positives.
Measured synthetic plumbing: 200 candidates; 199/198/197 after exact/current-name/Loc-Bench;
1,970 merged PRs, 1,773 linked, 197 parse-incomplete, 1,379 retained/1,576 positives; 7,688 mock calls.
BM25 no-positive-top-10 85.714% [85.714,85.714], n=1,379/197 artificial repositories, 2,000 draws,
seed 0. Repeated templates explain the degenerate interval; no scientific yield/rank evidence.
Published comparison retained; actual-data/dense/content audit n=0, blocked rather than zero yield.

C3 agent boundary (969b3bd): public issues/source go to one retrieval tool and scripted repair;
hidden trusted executable tests independently grade exact edits. Gold file names reach only the
oracle and post-call report join. Five versioned scaffold papers read in full across 216 pages;
qualified criteria and page-specific sources in EVAL_API, owner integration pending. Agentless
remains the provisional ADR-007 candidate; no scaffold selected or published replica claimed.
Synthetic 20 fixtures/4 artificial repositories per condition: none/BM25/oracle resolve4/12/16
(20/60/80%, clustered intervals [20,20]/[60,60]/[80,80]); discordance40/20/60% for BM25-none/
BM25-oracle/none-oracle. Synthetic dollars .000508/.001298/.001262; actual dollars0. Fixture
MDE arithmetic at n302/432 is illustrative only; real cost/discordance/MDE remain unmeasured.
C3 final log: `results/logs/c3_fixture_pilot_guarded_2026-10-30.json`.

C4 fixture runner (e0e29d4): fixed model/scaffold/seed/temperature/tasks, configurable retrieval boundary,
atomic checksummed checkpoints and exclusive invocation lock. Durable conservative synthetic
reservations precede dispatch; unknown calls never replay or refund. Quote violations persistently
halt dispatch and expose observed usage/cap breach. Resume rejects config/source/retriever/task/
gold/reference/hidden-grader identity drift and corrupted/missing state. Incomplete pairs block all
paired statistics; unknown outcomes never become resolved=false. Reports retain every gold hit,
missing count and attempted-edit file proxy; this does not measure attention or causation.

Measured C4 plumbing: requested/completed20/20 pairs, complete paired instances10/10, missing0;
BM25/oracle6/8 of10, clustered95% [60,60]/[80,80]%, 2,000 draws, seed0, two artificial repositories.
Discordance20% [20,20], oracle-BM25 +20pp [20,20], only-first/second0/2, exact McNemar p=.5.
Failures not-retrieved/retrieved-not-used/used-wrong: BM25 2/2/0; oracle0/2/0. Wrong-gold-edit,
abstention and multi-gold tests cover categories even where default table counts are zero.
Synthetic observed/reserved/cap dollars .001258/.164734/1; actual dollars0, unknown calls0.
First CLI2.29s, peakRSS42,240KiB; not model performance. Two same-seed resumes reused20pairs,
0new calls; all9data artifacts byte-identical. Independent fresh10x2 replay matches semantic rows,
statistics, diagnostics and budget; timing/test-log/output-identity exclusions declared.
Config `017ac065f974e9e64d31768681943a1f338de2925ac0d008585d85d90ca4bdcf`;
source `448a951830ee8b17168d99eea8ff79b8a960ef91920319af8ef1747b42cb1953`.
Artifacts: `results/rq3/c4_paired_fixture_2026-10-30/`; audits under `results/logs/c4_*`.

Validation: 577 unit passes/3 optional Torch skips (56.47s); 39 C4 cases; 60 additional CPU
integration/leakage/reproducibility passes/5 expected skips (four Torch, one absent checkout).
Ruff/format285 files and strict mypy122 modules pass. Per-commit20latency/4throughput stub rows
under `results/rq3/c4_commit_stubs_2026-10-30`; C4 cold retrieval rows in each run directory.
Stubs are not model encoding/training measurements. Evidence: `results/ledger_c.md`, E-C1–C4.

C1 launch preparation: pinned dev-only manifest/plan/acquire/verify CLI and separate CPU staging,
BM25, GPU-cache and CPU dense-evaluation templates are ready. Exact folder identity allowlist,
upstream checksums, strict range validation, durable partial/source provenance and restart-aware
disk bounds are mock-tested. Colab now reports36files checksum-verified at pinned revision
23da5d97a8a4495d4bd6d5616aa86d5a12a60699; all9folder pairs loaded/indexed in125.72s.
Capacity peakRSS2788168KiB versus12141277184bytes available; subsequent BM25 completed
with waited-child peakRSS2914944KiB. No model fetched.
Validation:41focused and618full unit passes/3Torchskips;lint288files/mypy123modules;4shell
syntax/local-refusal gates. Standard20latency/4throughput rows are synthetic CPU stubs only.
Commands/gates: `docs/EVAL_API.md`;validation log `results/logs/c1_rewrite_launch_validation_2026-10-31.json`.

Colab setup: user selected Colab instead of Ada. A generated CPU/GPU notebook kit uses a
checksum-pinned committed source ZIP, isolated Python3.11,25CPU/47GPU exact dependency pins,
explicit current-VM host receipt and separate CPU acquisition/GPU encoding. Native local locks
and verified Drive snapshots preserve completed work; one active VM per store is required.
Default notebook cells run setup and synthetic checks only; real jobs remain opt-in.
Validation:684unit/60additional CPU passes, documented optional skips;lint292/mypy124pass. Source
archives retain the pinned original commit and explicit unavailable Git status. Operator-supplied
CPU readiness report matches the kit source/profile,26CPU/buildpins and runtime-proof checksum:
Colab x86_64/2CPU,projectPython3.11.18,hostPython3.13,noGPU. Data/capacity operator reports
locally matched; actual BM25 summary received; CUDA/GPU,reset-restoration/model work pending. Evidence:
`results/logs/c_colab_cpu_ready_2026-10-31.json`, `c_colab_capacity_2026-10-31.json`.
E-C1-COLAB-DEV freezes paired BM25 config hash ce0c977b4f6a93cd5c0615846170090e7389ebc341825fa4bc4f2f69d8b75452;
run dev-v1 complete per operator,6GiBaddresscap/8GiBavailable preflight; matched runtime.
Results:`results/logs/c1_colab_bm25_dev_v1_2026-10-31.json`;12 exact CSV rows beside other tables.

## Blockers and compute

Original/Rewrite dev sources verified per operator; pinned dense artifacts, real agent tasks,
read-only mining token and held-out content index absent. Account C access is unavailable; allocation/partition/card unverified.
C2 real sample memory/disk/yield/ranks must be measured before expansion; hard caps remain
200repositories/2,000PRs. No real pilot go, no full-scale mining, no model/provider selection.
Live execution still fails closed: reviewed adapter/scaffold, pinned model, official trusted
harness, staged dev data and explicit spend authorization are required. Fixture subprocesses are
not a sandbox for real repository code. Actual agent dev n=0;agent cost/discordance/MDE=null.
GPU-hours used0 of8; actual dollars0; no cluster job. Build-only teaching backlog remains;
no project understanding or learning completion is claimed.

## Requests for the lead

| Question | Options | Evidence class | Cheapest experiment | Recommendation | Meanwhile |
|---|---|---|---|---|---|
| API/paper integration? | adopt; retain | measured/read-full | owner parity/note checks | integrate compatible evidence | exports; qualified notes |
| Data/access? | stage; defer | measured absence | allocation plus one folder | supply inputs/token/index | D13/D17; no substitution |
| Mining histories/scale? | validate/expand; defer | measured mock | real 200-repo pilot/two diffs | defer expansion | ADR-001; 200/2,000 caps |
| Scaffold/boundary? | Agentless-stage; SWE-agent/OpenHands | read-full | pinned offline adapter fixture | compare isolation | ADR-007; scripted only |
| Model/spend? | hosted; pinned-local | measured absence | capped dev pairs | obtain cost/noise | ADR-008; no calls |
| Q45 test/estimate? | hypothesis-test; interval-estimate | reasoned | repeated dev pairs | state worthwhile effect | unmeasured; no selection |

## Next work

Lead/owners integrate compatible API/paper notes and roadmap evidence; supply bounded inputs/access,
collect and audit completed Colab BM25 artifacts, then review fixed scaffold/model/treatment adapter,
grading harness and spend cap.
Run the authorized repeated dev pilot before mining expansion or RQ3 power/design decisions.
All scientific conclusions and final-test settings remain open; no push performed.

Commit messages were shortened on2026-10-31; all five corresponding file trees are identical.
Historical measurement IDs remain intact; mapping: `results/logs/c_commit_reword_2026-10-31.json`.
