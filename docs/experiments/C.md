# Experiments: workstream C

Append-only log, entries by this workstream only. Rules, interpretation rules and the index of all entries are in
`docs/EXPERIMENTS.md`; the same rules apply here. Entry ids are unique across all experiment logs.

## Registry

| ID | RQ | What varies | Held fixed | Seeds | Primary outputs | Status |
|---|---|---|---|---|---|---|

## E-C1-EVAL: shared retrieval evaluation and Rewrite pairing, apparatus, 2026-10-30

D13 and D17 are retained. The shared evaluator scores released chunks, not D18 unit gold.
Original qrels/candidates/corpus order are authoritative for both wordings. L2/L3 are separate,
paired by dataset/folder/query identity, clustered by canonical repository. No setting is chosen
from Verified. Actual dev configurations include ansible alongside openlibrary/qutebrowser for L3.

| Run | Evidence class | Config hash | n | 95% interval | Seed | Result / gate |
|---|---|---|---|---|---|---|
| c1-eval-fixture-host312 | measured, synthetic apparatus | `66d0c46d7b3a0bf6ba2517d107a427a2ec52ce37525dff1851dcd2e29c462b3e` | 2 queries, 2 repositories per level | nDCG delta -36.9070 pp [-36.9070,-36.9070]; Recall delta [0,0], 2000 repository-clustered draws | 0 | CPU entry point completes under preliminary host Python 3.12.3; intentionally removed anchors; no scientific Rewrite claim |
| Published BM25 artifact regression | measured correctness check, not a new corpus reproduction | `8681e08cb825b99e7000c1a286cf9c3c4efc865c80f4f1cb212b9c3df043f317` | 3 archived aggregate rows | not applicable: deterministic equality to recorded precision | 0 | Verified L2 11.9392/46.7412, L3 22.1917/33.8884; all-L2 mean of dataset folder means 13.0029/38.818; paper rounding matches |
| Power/statistics compatibility | measured correctness check, calculation | `8681e08cb825b99e7000c1a286cf9c3c4efc865c80f4f1cb212b9c3df043f317` | 9 archived MDE cells, 45 archived exact power cells | not applicable: deterministic numerical agreement | 0 | 2026-10-18 cells retained; compatibility bootstrap equals existing table implementation for shared draws |
| Actual-data BM25/dense Rewrite dev ablation | blocked, no measurement | hashes assigned when ready configurations run | 0 | unavailable | 0 | original/Rewrite corpora and pinned dense caches absent; account C not verified; no GPU used |

The synthetic result is a fixture invariant, not an estimate of rewriting's effect. Dense plumbing
is tested with explicitly synthetic score arrays; actual CodeRankEmbed caches use its pinned
revision, sequence limit 1024 and the existing encoder. Cached-score timing is lookup only and
must not be compared with BM25 or a real dense search. Clustered uncertainty with few repositories
is coarse; primary science waits for the registered dev data run. GPU-hours used: 0.

Implementation contract and exact commands: `docs/EVAL_API.md`. Existing analysis table modules
are outside C ownership; the lead must migrate them to the shared statistics after review.

## E-C2-RAW-PR: raw PR miner and recorded-response pilot, apparatus, 2026-10-30

Evidence class: measured **synthetic plumbing only**. Configuration
`configs/experiments/c_raw_pr_pilot.yaml`, hash
`7bd4a210bfc82de113b99d5549c60b27911d2dadfe8767687c1edf996dec9280`, seed 0.
Source, implementation and interpretation: `ril/data_mining/c_miner.py`; CLI `scripts/c_mine_prs.py`.
Log `results/logs/c2_raw_pr_mock_pilot_2026-10-30.json`; comparison
`results/tables/c2_raw_pr_rank_comparison.csv`. Actual-data acquisition has n=0; no scientific
estimate of mining yield, live API cost, content overlap or dense ranks follows from these fixtures.
GPU-hours used: 0.

| Synthetic stage | Count or cost | Interval |
|---|---:|---|
| Python repository candidates selected | 200 | deterministic fixture count, not applicable |
| After exact core / current name / Loc-Bench | 199 / 198 / 197 | deterministic fixture count, not applicable |
| Merged PRs / linked PRs / linked issues | 1,970 / 1,773 / 1,773 | deterministic fixture count, not applicable |
| Parse-incomplete / no overlapping base function | 197 / 197 | deterministic fixture count, not applicable |
| Kept PRs / positive functions | 1,379 / 1,576 | deterministic fixture count, not applicable |
| Positive functions per kept PR | 1.142857 | deterministic fixture ratio, not applicable |
| Parse-incomplete among linked PRs | 11.111% (197/1,773) | deterministic fixture ratio, not applicable |
| Transport replay calls / mining wall time | 7,688 / 9.620 seconds | single local replay; not live API cost |
| BM25 directories without a positive in top 10 | 85.714% (n=1,379; 197 repositories) | [85.714,85.714], 2,000 repository-clustered draws, seed 0 |
| Actual pilot / CodeRankEmbed / real content audit | blocked | unavailable |

Every synthetic repository repeats the same seven retained PR templates, which explains the
degenerate BM25 interval. This is a regression fixture, not evidence of a distribution difference.
The comparison table preserves the archived E-POOL-RANKS cells with teacher, text form, weighting
and interval method: CodeRankEmbed pool 15.3% [8.8,22.2], BM25 pool 23.2% [16.4,31.0],
SweRankEmbed-Small **stored-text** never-filtered Verified 19.3% [15.7,23.2], and CodeRankEmbed
Verified 35.7% [31.3,40.3]. No Verified measurement was rerun. These are distinct teachers and
corpora; the synthetic row is not a scientific comparator.

Acquisition follows paginated repository search (Python primary language, descending stars),
closed PR listing restricted to merged PRs, and paginated GraphQL closing-issue references.
The issue title/body becomes the query; PR text and commit messages do not. Both candidate and
held-out names are resolved; unresolved coverage is explicit, and post-name-loss counts remain
incomplete when resolution is incomplete. The content audit uses the existing informative-line
hash algorithm and is reported without filtering. Without a supplied held-out content index it
reports a blocker, never zero overlap. Fork-network matching is sensitivity only (D1).

For supported histories the immutable merge commit has two parents and its second parent must
match the recorded PR head. Compare the first parent with that head to obtain their merge base;
parse that snapshot through the shared parser and use a complete Git diff to the head. A real
local Git fixture covers an upstream sync into the feature branch followed by another target
advance, demonstrating exclusion of unrelated target edits. Squash/rebase, merge queues,
unavailable identities and unverifiable merge bases are quarantined and counted as
`history_unverifiable`; broader history support needs validation. This conservatism can bias
collection by merge style and is not a pool-policy decision.

Keep **every** overlapping base function/method, including tests and collision ordinals; no rank,
score, test-change requirement or consistency filter selects examples. Other parsed functions
are candidates. Classes and module residuals are outside this function-level pool. Pure insertions
anchor the adjoining old lines; renames refer to the old file and deletions retain their old units.
Added files/functions have no base unit and are not recoverable positives; PRs with no base-unit
overlap are counted. Partial parsing/discovery quarantines the entire PR, preventing unknown
positives from becoming negatives. Per-positive provenance records CodeUnit identity, span,
touched old lines and source hash, alongside PR/issue URLs and immutable commit identities.

Each successful API response and PR is checkpointed atomically. Resume rejects changed config,
held-out document, source recording or overlap-index identity. Rate reset and Retry-After are
honored with bounded retries and sleeps of at most 60 seconds. Credentials exist only in the
live HTTP header. Output `pool.jsonl.gz` is written and read by the unchanged training pool
reader; audit ranks call the unchanged pool-rank implementation. Dense score caches validate
run, candidate, query, text and pinned-encoder identities and reject nonfinite scores.

Memory probe: five selected repositories, 41,592 recording bytes, peak RSS 39,944 KiB versus
39,432 KiB baseline. The linear 200-repository projection was 59,912 KiB; observed peak was
86,732 KiB, so the estimate **underpredicted by 45%**, while observed usage stayed below 100 MiB.
This tiny synthetic source size does not size real repositories. Before real acquisition or dense
encoding, measure real-sample memory/disk and verify account C allocation and remaining GPU budget.

Reproduce synthetic checks locally (CPU, no model runtime):

```bash
python scripts/c_mine_prs.py record --out data/raw/c_raw_pr_recording.json
python scripts/c_mine_prs.py mine --recording data/raw/c_raw_pr_recording.json --config configs/experiments/c_raw_pr_pilot.yaml --out data/raw/c_raw_pr_mock_pilot
python scripts/c_mine_prs.py ranks --out data/raw/c_raw_pr_mock_pilot
```

On Ada, after access, quota, partition/account/QOS, a Python 3.11 environment and read-only
`GITHUB_TOKEN` are verified: stage `ril`, `scripts`, `configs` and `data/held_out`, create `logs`,
set `RIL_ROOT`, `RIL_PYTHON` and optionally `RIL_OUT` in the submitting environment, then
`sbatch -p <verified-partition> -A <verified-account> -q <verified-qos> --export=ALL scripts/ada/c_raw_pr_pilot.sbatch`.
A supplied real content index can be passed to the `mine` command with `--overlap-index FILE`:
JSON fields `hashes` (integers from `ril.training.content_overlap.build_index`), `corpus_sha256`,
`complete: true`. Its hash enters the resume identity; adding it to an old run requires a new
output directory. This does not change training examples.

Only after the real pilot, pinned encoder files, supported card, memory and remaining budget
are verified, submit `scripts/ada/c_raw_pr_ranks.sbatch` with the verified Slurm flags and
`--constraint=<supported-card>`. Its 30-minute allocation bounds one attempt to 0.5 GPU-hours,
not a completion estimate; its existing teacher path performs a real CUDA operation as a gate.
Interrupted score checkpoints resume. The CPU acquisition job never reserves a GPU; GPU jobs
run offline and acquire no data/models. Record any submitted job under account C in the shared
job ledger. **No job has been submitted.**

The mock gate is passed by correctness tests and recorded yield/cost/comparison artifacts.
The actual-data gate remains blocked on access, token, content corpus and dense scores.
Both CLI and miner reject limits above 200 repositories or 2,000 PRs. Full scale requires a
real pilot review and explicit engineer go; this implementation has no full-scale bypass.

Final source-identified replay: same deterministic counts and rank interval; 7,688 mock calls in
9.601 seconds, peak RSS 86,840 KiB. Distinct initial and final logs retain both replays; final evidence is
`results/logs/c2_raw_pr_mock_final_2026-10-30.json`. The final replay records the dirty
working-tree flag and SHA-256 hashes of nine implementation/dependency files, so its base Git hash
66d0f6f is not presented as the commit containing the new miner. The source manifest also enters
resume identity. Validation: 19 focused tests; complete Python 3.11 suite 522 passed, three optional
torch skips; ruff/format and strict typing pass. The per-commit harness ran separately, recording
20 latency and four throughput rows under `results/rq2/c2_latency_smoke`; these are explicitly
synthetic stub stages, not model encoding or training measurements. Validation log:
`results/logs/c2_validation_2026-10-30.json`.

## E-C3-AGENT-PILOT: scaffold criteria and synthetic execution, apparatus, 2026-10-30

**Scope and gates.** Exploratory apparatus only, outside pre-registered RQ3 result tables.
Configuration `configs/experiments/c_agent_pilot.yaml`: seed 0, temperature 0, 20 synthetic
fixtures from four artificial repositories, each under none/BM25/oracle-gold-file context.
These are not SWE-bench Pro/Live instances. Actual development instances n=0; no Verified
execution, model service call, local model load, encoding or cluster job. ADR-007 and ADR-008
remain Proposed; the scripted fixture harness is not a replication of a published scaffold.
Model access, explicit spend cap, pinned scaffold/model/harness and staged real dev data are
missing. Live execution fails closed; scientific cost, discordance and MDE remain unavailable.

**Method stated before the recorded pilot.** The model receives issue text and one tool's
returned source files. It proposes exact source edits; a separate grader applies them in a
fresh temporary directory and executes trusted hidden fail-to-pass and pass-to-pass checks.
Unmodified/reference-patch controls fail/pass for every fixture. Reference edits and test labels
never enter the model; gold file identities enter only the oracle retrieval tool and post-run
report join. These trusted subprocess fixtures are not a sandbox for untrusted live code.

Report per-condition resolved count/rate, token surrogates, synthetic dollar totals, actual
spend zero and wall time; per-instance paired outcomes/discordance; exact McNemar; query means
with repository-clustered 95% intervals (2,000 draws, seed 0). The repeated synthetic pattern
may give degenerate intervals and is not population uncertainty. Illustrative exact MDE at
n=302/432 uses only fixture discordance, alpha .05, target .80 and .25-point grid; it is never
an empirical power estimate for real RQ3. Tokens are UTF-8 bytes rounded up after dividing by
four, not a model tokenizer. Synthetic prices are configured accounting inputs, not quotes.

**Reading and decisions.** The earlier claim of five full-paper readings is unverified.
The corresponding complete set of versioned notes is absent from the tracked tree; no new
reading or page-count verification is claimed. Candidate criteria in `docs/EVAL_API.md` are
requirements to verify, not established paper evidence.
None establishes an exclusive ready-made one-tool retrieval treatment or live seeded replay.
Current software releases and hosted prices were not reviewed. The lead must choose scaffold,
model/access/spend and treatment boundary; no ADR, final setting or RQ3 claim is settled here.

**Recorded result (measured, synthetic only).** Config SHA256
`4cf5f835395a8d01ba137a7a09e7c7e0d4bc29fecbf34314da750c062b764cb1`, source checksum
`6503d2e1c30663ed7f7afb0b79f1bd892edffd431b4c7a544e57cb9b3a074de6`, git 645925b
with dirty flag 1 and per-file source hashes. Linux aarch64 CPU, Python 3.11.18, no GPU.
Final log `results/logs/c3_fixture_pilot_guarded_2026-10-30.json`; resources in
`results/logs/c3_fixture_resources_guarded_2026-10-30.json`; tables `results/tables/c3_fixture_guarded_*.csv`.
Earlier recorded runs are retained under distinct paths and superseded by this guarded replay.
Natural-language issues exclude reference new-code text; tests enforce that boundary.

| Condition | Synthetic resolved count/rate [clustered 95%] | Surrogate input/output tokens | Synthetic dollars / actual dollars | Execution wall seconds |
|---|---|---|---|---|
| None | 4/20; 20% [20,20] | 312/98 | .000508 / 0 | .653064 |
| BM25 | 12/20; 60% [60,60] | 640/329 | .001298 / 0 | .661065 |
| Oracle gold files | 16/20; 80% [80,80] | 596/333 | .001262 / 0 | .636558 |

| Pair, first/second | Fixture discordance [clustered 95%] | Only first/second | Exact McNemar p | Illustrative fixture MDE at 302/432, pp |
|---|---|---|---|---|
| BM25/none | 40% [40,40] | 8/0 | .0078125 | 10.50/8.75 |
| BM25/oracle | 20% [20,20] | 0/4 | .125 | 7.50/6.25 |
| None/oracle | 60% [60,60] | 0/12 | .00048828125 | 12.75/10.75 |

The large constructed effects and degenerate intervals demonstrate expected fixture behavior,
not agent performance or real uncertainty. Scientific discordance/cost/MDE remain unavailable
at real n=0. Whole CLI wall time 14.86 s including exact statistics; agent/test execution 1.955611 s;
peak RSS 42,696 KiB. Single-fixture retained-object probe 1,787 bytes, linear 20-fixture projection
35,740 bytes; this does not size a real repository or model. Deterministic non-timing artifacts
reproduce. 538 unit tests pass, three optional torch tests skip; full lint/format and strict
mypy pass. Per-commit synthetic harness artifacts are under
`results/rq3/c3_fixture_pilot_guarded/commit_{latency,throughput}_log.csv` (20/4 rows); these stages are
synthetic CPU stubs, not model inference or training measurements. Actual spend and GPU-hours: 0.

## E-C4-RQ3: persistent paired fixture runner, apparatus, 2026-10-30

Registered before measured execution. `configs/agent/c_paired_fixture.yaml` specifies 10 synthetic
fixtures/two artificial repositories, BM25 and oracle through the same file retrieval boundary,
seed 0, temperature 0, fixed scripted model and scaffold, 2,000 repository-clustered draws.
ADR-007/008 remain provisional. No real development instance, Verified instance, model service,
local model, or GPU is admitted. Scientific cost/discordance/MDE remain unmeasured at real n=0.

Each requested pair is reserved durably before dispatch under an exclusive process lock.
Conservative synthetic input/output maxima bound synthetic costs; actual dollars are always zero.
Unknown dispatch outcomes retain reservations and are never automatically replayed. Config,
source, model/scaffold, task snapshots, gold/reference and hidden-grader identity must match.
Completed rows are reused unchanged; corrupt/missing state or changed identity fails closed.
Incomplete pairs block all paired statistics, with explicit requested/completed/missing counts.
Reports are immutable; recovery requires a new report path and preserves earlier evidence.

Report per-file gold hits and attempted-edit file use proxies; successes have no failure label.
Failure hierarchy: no gold retrieved; gold retrieved but no retrieved gold edited; otherwise used
wrong. Multi-file hits are retained individually. These proxies do not measure attention or causal
reasoning. Tables include outcomes, exact McNemar discordances, clustered differences and diagnostics.
The repeated synthetic fixtures may yield degenerate intervals and demonstrate plumbing only.
Resume must produce zero new model/grader calls and byte-identical checkpoints. Crash/cap/usage,
concurrency, tampering, identity drift, hidden-label isolation and multi-gold cases are tested.

Pre-execution configuration SHA-256: `017ac065f974e9e64d31768681943a1f338de2925ac0d008585d85d90ca4bdcf`; n=10 fixtures/2 artificial
repositories per retriever, seed 0, 2,000 clustered draws. Source checksums and actual dirty Git
identity are recorded by the initial durable checkpoint before any dispatch.

Registered fresh seeded replay before execution: `configs/agent/c_paired_fixture_fresh.yaml`,
SHA-256 `a3790f26eaf7b5014f5b89a1a3fcde94c858a170af57b13172a04e51d6e29c19`; same 10 fixtures/two retrievers and settings, new output path.
Compare requests/retrieval/edits/grades/usage/statistics after excluding declared timing/test-log
variations and output-dependent identity/checksum fields. Same-output resume still requires exact bytes.

**Recorded result (measured synthetic plumbing only).** Complete requested/completed pairs20/20,
complete paired instances10/10, missing0; two artificial repositories. BM25 resolves6/10 (60%,
clustered95% [60,60]); oracle8/10 (80%, [80,80]); 2,000 whole-repository draws, seed0. Oracle-minus-
BM25 effect +20pp [20,20], discordance20% [20,20], only-first/second0/2, exact McNemar p=.5.
These repeated constructed patterns do not measure population uncertainty or real agent capability.
Scientific cost, discordance and MDE remain null at real development n=0.

| Condition | Requested/completed/missing | Independently resolved | Failed: not retrieved / retrieved not used / used wrong | Surrogate input/output tokens | Synthetic / actual dollars |
|---|---|---|---|---|---|
| BM25 | 10/10/0 | 6 | 2/2/0 | 316/161 | .000638 / 0 |
| Oracle gold files | 10/10/0 | 8 | 0/2/0 | 294/163 | .000620 / 0 |

Gold hits/misses are retained individually; used-wrong is an aggregate attempted-edit proxy and
can coexist with another missing gold file. Explicit wrong-gold-edit, abstention and multi-gold
checks cover zero-count categories. Completed reservations .164734 synthetic dollars against cap1;
observed .001258, unknown dispatches0. Synthetic dollars are accounting test inputs, not model prices.
Actual spend/GPU-hours0; trusted fixture tests are not a live untrusted-code sandbox.

Main artifacts: `results/rq3/c4_paired_fixture_2026-10-30/`; source identity
`448a951830ee8b17168d99eea8ff79b8a960ef91920319af8ef1747b42cb1953`, base Git af41eb1,
dirty1 with actual per-file hashes. First CLI2.29s, peakRSS42,240KiB; stored per-pair execution totals
BM25 .314394s and oracle .317048s. Cold retrieval percentiles are separate from scaffold/grading.
No new model call occurs on either same-seed resume; 20 pairs reused and all9data files remain
byte-identical (`results/logs/c4_replay_verification_2026-10-30.json`). The empty persistent lock
coordinates concurrent invocations and carries no result content. Independent fresh10x2 replay
matches semantic requests/retrieval/edits/grades/usage, diagnostics, budgets and exact statistics;
wall/retrieval timing, elapsed test text, output-dependent execution identity and row checksums
are explicitly excluded (`results/logs/c4_fresh_verification_2026-10-30.json`).

Validation: 39 focused C4 tests; full unit577pass/3optional Torch skips in56.47s; additional CPU
integration/leakage/reproducibility60pass/5skips (four Torch, one absent checkout); ruff/format285
files, strict mypy122modules pass. Per-commit CPU stubs20latency/4throughput rows under
`results/rq3/c4_commit_stubs_2026-10-30/`; explicit per-row ledger entries, no central CSV changes.
These are synthetic stubs, not real model encoding/training measurements. No live adapter,
provider selection, scientific pilot or ADR choice is claimed.


## E-C1-LAUNCH — bounded staging preparation (2026-10-31)

Registered before the offline plan and per-commit stub measurements. Verify the exact paired
dev path manifest, transfer integrity/resume/disk guards and shell launch gates using recorded
responses only. No source acquisition, model load or cluster job; actual dev n=0, GPU-hours0,
actual dollars0. Offline full-config plan selects36files across9repository/level pairs with
artificial contents/checksums, seed0. Standard harness outputs use synthetic-v1 CPU stubs and
cannot estimate actual indexing/encoding/training or network performance. Config hash and
executed source hash are recorded with the validation artifacts; no scientific interval applies.

Completed offline checks:41focused recorded-response cases,618unit passes/3optionalTorchskips
(59.90s),lint/format288files andstrictmypy123modules,4shell syntax/local refusal checks. Full
36-file artificial plan is byte-bounded;source configSHA`1926df709c9c8e524bd00b57415b9ad749d9612f22967363d9860d9f057ad8de`,
executed sourceSHA`e7ae79960c3d955556cf810173e1b2a00a88bcef5fd533417c7200a1c8b41d0f`,seed0,no scientific
interval. Twenty latency/four throughput stub rows and the validation artifact are preserved
under `results/rq1/c_rewrite_launch_cpu_2026-10-31/` and `results/logs/c1_rewrite_*2026-10-31.json`.
All actual acquisition/evaluation/model access remains blocked;no cluster availability claim.


## E-COLAB-SETUP — isolated runtime and notebook preparation (2026-10-31)

Registered before the packaging/resource and required stub measurements. Validate explicit Colab
host-receipt admission, preservation of Slurm operation, exact CPU/GPU package profiles, committed
source ZIP verification, notebook syntax/default flags, model-free fixture execution and durable
checkpoint copies using offline constructed inputs. No actual Colab, Drive, CUDA/model or scientific
data workload is available here; real development n=0, actual external dollars/GPU-hours0. The full
source package is about47MiB before compression; a conservative local packaging memory envelope is
four source copies plus100MiB interpreter/metadata overhead (under300MiB), well below available RAM.
This is an estimate, not a measured peak. CPU stub latency/throughput uses synthetic-v1, seed0 and
own output paths; it does not estimate actual network/model/Colab performance. Actual source/config
hashes, counts and validation limitations are recorded with the resulting artifacts; no scientific
interval applies. Live data/agent choices and cross-platform parity remain unmeasured.

Recorded offline result:684unit pass/3optionalTorchskips in62.29s;60additional CPU pass/5expected
skips in2.69s;ruff/format292files and strictmypy124modules pass.33notebook/package/checkpoint
cases; source SHA`a7e7d636d9ab0a8b022ecc4ec2736434dbb826a421dae02f6b35338747dacfec` (base570cb1b,dirty1).
Twenty latency/four throughput CPU stub rows retained under `results/rq1/c_colab_setup_cpu_2026-10-31/`,
with every row in C ledger. Only personal host label normalized to local-cpu; numeric rows unchanged.
Actual Colab/Drive/GPU installs and scientific data/model runs remain unperformed.

## E-C1-COLAB-DEV — paired original/Rewrite BM25, registered 2026-10-31

Evidence class: **operator_reported**. Registered before the reported execution of `dev-v1`;
operator completion/metrics received, but query-level results, timing and the native run directory
are absent. Aggregate consistency checks do not independently reproduce the bootstrap intervals.
Retains E-C1-EVAL D13/D17, the existing dev allowlist and all stated scoring parameters.
Source kit `dcc19574386fc66c578bb42c872e38f9e95d0201`; dataset
`zhangfw123/CORE-Bench` revision `23da5d97a8a4495d4bd6d5616aa86d5a12a60699`;
manifest SHA256 `1b1e022998ab6ac7906514345ab8e82f4817a621d8e4c6a866a05915ccc385ac`.
Exact isolated-runtime config file SHA256
`451a81484271bfe5366ce499b069a650b44733cbdbfe98730c3d07f079d53e37`;
evaluator semantic config hash
`ce0c977b4f6a93cd5c0615846170090e7389ebc341825fa4bc4f2f69d8b75452`.
These include Colab-specific data/output/log paths; scientific settings are unchanged.

Expected workload: nine folder/level pairs in six DEV repositories, L2 442 and L3 238 queries
per condition according to the capacity report; actual evaluator membership must be checked.
Original corpus, qrels, candidate lists and exact paired query IDs remain authoritative.
BM25 k1=1.5,b=.75; prefilter10000; seed0; warmup1,repeats3. Report query-weighted
nDCG@10 and Recall@100 separately by level/wording and Rewrite minus original with95%
repository-clustered percentile intervals,2000draws. No Verified queries, tuning or sweep.
Both wordings share each folder index and one CPU environment. Standard index-throughput
and warm tokenization/scoring latency rows are emitted; they do not measure cold query latency.

Preflight: operator supplied36-file checksum verification and all9full-folder loader/index
capacity results,125.72s,peak2788168KiB versus12141277184bytes available. Evidence:
`results/logs/c_colab_capacity_2026-10-31.json`; capacity is not scientific performance.
Full execution uses an8GiB effective available-RAM preflight and6GiB virtual-address cap
respecting tighter inherited limits. Scoring/ranking/retained rows/bootstrap are additional;
record allocation failures and actual execution resources rather than assuming this peak is exact.

Native outputs: `runs/dev-v1/bm25/` and `runs/dev-v1/bm25-log.json` beneath the Colab work
root, followed by the existing Drive checkpoint. Existing output/log paths refuse overwrite.
Receive actual metrics/config/source/runtime evidence before appending scientific result rows.
No dense/model/GPU/mining/live-agent execution is included; compute billing remains unknown.

Operator result received 2026-10-31: stage returned complete;36 files reverified; source/config
hashes match the registration. Raw stdout, qualified JSON and exact fractional CSV are retained:
`results/logs/c1_colab_bm25_dev_v1_2026-10-31_stdout.txt`,
`results/logs/c1_colab_bm25_dev_v1_2026-10-31.json`,
`results/tables/c1_colab_bm25_dev_v1_2026-10-31.csv`.

| Level | Metric | Original (%) | Rewrite (%) | Paired difference (pp),95% interval | n / repos per condition |
|---|---|---:|---:|---|---|
| L2 | nDCG@10 | 19.7741 | 21.6999 | +1.9258 [-2.4594,+8.7810] | 442 / 6 |
| L2 | Recall@100 | 39.5668 | 41.9717 | +2.4049 [-1.3140,+8.0869] | 442 / 6 |
| L3 | nDCG@10 | 31.6875 | 29.6439 | -2.0436 [-2.6646,-0.9102] | 238 / 3 |
| L3 | Recall@100 | 37.4682 | 35.8677 | -1.6005 [-1.7655,-1.3556] | 238 / 3 |

Both L2 paired intervals include zero. Both L3 paired intervals are below zero in this DEV
workload, with only three repository clusters; do not generalize to other repositories/models
or the final test. These remain **operator_reported** actual-data summaries. Upgrade only after a native run
directory is stored under results/ and its query-level intervals are independently recomputed.
Local checks establish duplicated metric-output equality, registered identities/counts,
finite interval bounds and paired point-estimate arithmetic. Full query rows and saved
input/hardware/config/timing artifacts are not yet received: independent pairing and bootstrap
recomputation remain pending. No timing rows or elapsed runtime inferred from capacity timing.
Reported waited-child peak RSS2914944KiB(2.779907GiB). The archive Git warning was handled
through the existing pinned-source fallback. No dense/model/agent execution or paid call;
compute billing unknown. Preserve this completed run and collect artifacts rather than rerunning.

Aggregate-only audit and table extraction: `python scripts/c_review_evidence.py`. This command
checks stored summaries and evidence labels; it cannot recompute missing query-level intervals.
