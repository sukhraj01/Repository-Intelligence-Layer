# Retrieval evaluation contract

The shared entry point implements D13 (Rewrite wording with original labels) and D17
(query-weighted mean with a repository-clustered interval). L2 and L3 stay separate. This
entry point scores **released chunks**; existing unit-level experiments retain their D18 gold
readings. Converting unit scores to chunk scores or changing gold readings is outside this API.

Run from the repository root:

```sh
make eval CONFIG=configs/experiments/c_eval_smoke.yaml
# Active CPU environment without Poetry:
make eval RUN= CONFIG=configs/experiments/c_eval_smoke.yaml
```

The example is synthetic and labelled `role: fixture`. It verifies plumbing and an intentionally
removed error/API anchor; its scores are not benchmark results. Actual original/Rewrite corpora
and pinned encoder scores must be acquired on the compute cluster before the scientific ablation.
A configured test split is a single stated setting; this command never sweeps parameters.

## Loader and scorer

```python
read_folder(path: str, *, rewrite_path: str | None = None) -> CoreBenchFolder
read_split(root: str, level: str, dataset: str, folder: str,
           *, rewrite: bool = False) -> CoreBenchFolder
evaluate_scores(folder: CoreBenchFolder, scorer: Callable[[CoreBenchQuery], Float],
                *, prefilter_k: int = 10000) -> list[dict[str, Any]]
evaluate_folder(folder: CoreBenchFolder, params: BM25Params | None = None,
                *, prefilter_k: int = 10000) -> list[dict[str, Any]]
```

`read_split` resolves `root/data/LEVEL-2/<dataset>/<folder>` or `LEVEL-3`; rewritten
queries come from `root/data/Rewrite-LEVEL-2/...` or `Rewrite-LEVEL-3/...`. Corpus, order,
positive labels, and candidate lists always come from the original folder. Missing/defective
Rewrite qrels are ignored. Query ids must match exactly before qrel filtering; duplicates or a
missing Rewrite query fail. Queries without positive original qrels are dropped and counted.
Original positives absent from the corpus remain in the metric denominator.

The scorer returns a finite float64 vector in original corpus order. Ranking first truncates the
whole-folder list at `prefilter_k`, then restricts to the query candidates. Ties break by corpus
order. `evaluate_scores` returns query id, candidate/positive counts, token count, and ranks of each
positive under both the protocol and filter-first readings. Reported metrics use protocol ranks,
binary-gain nDCG@10 and Recall@100, on the same original query identities for each condition.

## Cached dense adapter

```python
folder_hashes(original: CoreBenchFolder, rewrite: CoreBenchFolder) -> dict[str, str]
CachedScores(path: str, original: CoreBenchFolder, rewrite: CoreBenchFolder)
CachedScores.score(query: CoreBenchQuery, condition: str) -> Float
```

This adapter imports no model runtime. Generate actual scores on the compute cluster with one
pinned encoder, same revision/tokenization/sequence limit in both conditions. Store NPZ with
`allow_pickle=False` compatible arrays:

| Field | Shape / content |
|---|---|
| `corpus_ids` | string vector, original corpus order |
| `query_ids` | string vector, original retained query order |
| `original_scores`, `rewrite_scores` | finite float matrices, queries × corpus |
| `metadata` | JSON string scalar, including nonempty `encoder`, `revision`, `max_tokens`, `query_template`, and all `folder_hashes` fields |

Include encoder settings and upstream artifact provenance in metadata. The adapter checks content
hashes, wording, ids, orders, dimensions and configured encoder/revision/sequence limit before scoring. Cache files
live at `<cache_root>/<L2|L3>/<dataset>/<folder>.npz`. The two matrices are loaded into memory;
measure per-unit memory and size them on the cluster before a real corpus run. Synthetic test
matrices use a fixture encoder identifier and cannot support a dense-model performance claim.

## Statistics

`ril.evaluation.stats` owns the power calculations formerly in `power.py` and bootstrap helpers
formerly in `metrics.py`; those modules retain compatible exports. Exact McNemar and the 2026-10-18
minimum detectable effect cells retain their recorded precision. Effects are fractions, not points.

```python
clustered_mean_ci(values, repositories, *, draws=2000, seed=0, level=.95)
clustered_paired_diff_ci(a, b, repositories, *, draws=2000, seed=0, level=.95)
exact_mcnemar_p(b: int, c: int) -> float
mde_mcnemar(n: int, d: float, alpha=.05, target=.80, step=.0025) -> float | None
```

Intervals return `(mean, low, high)`. Paired differences mean `a - b`. Callers must align identities;
the runner checks `(level, dataset, folder, query_id)` and groups clusters by canonical `repo` across
folders. Each bootstrap draws R whole repositories with replacement from R names, keeps all queries
of each drawn occurrence, then recomputes the query-weighted ratio. The point is the query mean,
never the mean of repository means. One cluster produces a degenerate interval and provides no
between-repository uncertainty. Missing pairs fail instead of silently shrinking the sample.

`Boot(repos, seed, draws=2000)` retains the existing table builder's micro, macro and cluster
weight behavior, including seeded draws, for migration. Analysis table builders remain on their
existing implementation pending owner consolidation; equivalence is tested. The legacy query-only
`mean_ci`/`paired_diff_ci` exports remain for compatibility; new primary reports use clustered helpers.
MDE checks all feasible grid effects plus the observed-discordance endpoint, including off-grid rates;
`None` means the specified target is unattainable, not zero effect.

## Configuration and output

The example lists all common YAML fields. `retriever.kind` accepts `bm25` (`k1`, `b`) or
`cached_dense` (`cache_root`, `encoder`, `revision`, `max_tokens`). Dense requires `rewrite: true`. `role` is
`dev`, `test` or `fixture`; tuning belongs on dev repositories only. Split/folder membership is
explicit; dev membership is checked against the six registered repositories, and fixture role
requires the synthetic fixture dataset and example repositories. One folder/level may appear once. `warmup_n` is discarded score calls, `repeats` is the
number of measured calls per query; batch size is one. Unknown top-level/retriever keys fail.

The configured output directory contains `config.yaml`, `hardware.json`, `results.json`,
`latency_log.csv`, and `throughput_log.csv`; optional `log_path` gets the same result JSON. Repeated
runs overwrite JSON/config and append timing rows. Use a fresh output/log path per registered run.
The SHA-256 config hash covers the supplied configuration and runner version; it includes output
paths. Results also carry the full git hash, dirty flag, seed, input text hashes, labels/candidate
hash, role, split and encoder configuration. Dense runs also record the score-file SHA-256 and
complete encoder metadata. Hashes identify inputs; they do not prove a dataset's
upstream provenance. Preserve the acquisition manifest beside real data.

| Result field | Meaning |
|---|---|
| `metrics` | level, condition, metric, n, repository count, mean/low/high in [0,1]; signed differences may be negative |
| `query_rows` | level/dataset/folder/repo/query id, condition, metric values, original/lost exact anchor counts; no issue or corpus text |
| `input_hashes` | corpus, both wording, labels/candidates hashes, dropped-unlabelled count |
| `latency_rows` | standard `LATENCY_COLUMNS`: environment, query-set id, discarded warmup count, warm state, stage, p50/p95/p99 ms, measured n |
| `throughput_rows` | standard `THROUGHPUT_COLUMNS`: environment, workload id, offline stage, units, seconds, units/s |

BM25 latency covers tokenization and scoring. Cached dense latency is explicitly named
`cached_scores_lookup`: score-row access only, excludes encoding/search and is not comparable to
BM25 latency. Offline `bm25_index` or `cached_scores_load` throughput counts corpus documents,
with the measured load/build seconds. These stage names are confined to this evaluator's per-run
CSV; additions to the central harness taxonomy require its owner's change. No retrieval timing is
presented as full interactive latency. Anchor counts are an exploratory exact-string heuristic
(backticks, URLs, dotted names, Error/Exception names), not proof that lost anchors caused a drop.

The published BM25 artifact regression pins Verified L2/L3 and all-L2 rows to recorded precision.
Verified uses folder means; all-L2 uses a mean of per-dataset folder means, which differs from the
plain 632-folder mean. Passing this artifact check does not reproduce retrieval from unavailable
raw corpora. A new corpus reproduction is a separate, currently blocked gate.

For the actual dev ablation, the two ready configurations include Pro openlibrary, qutebrowser,
ansible and Live conan, haystack, streamlink; L3 is available for the three Pro repositories.
Acquire all original and Rewrite query files first, then run on the verified account:

```sh
make eval RUN= CONFIG=configs/experiments/c_rewrite_bm25_dev.yaml
# GPU allocation only, after quota/card checks and cached model acquisition:
RIL_CLUSTER=1 python -m ril.evaluation.rewrite_cache --config configs/experiments/c_rewrite_dense_dev.yaml
make eval RUN= CONFIG=configs/experiments/c_rewrite_dense_dev.yaml
```

The cache preparer calls the existing DenseEncoder, gates CUDA with a real matrix product and
uses the pinned cached model (no download while holding the GPU). It rejects score matrices above
its configurable memory ceiling and writes each completed file atomically. This does not replace
measured full-process memory sizing before a new scale. Current account access/data absence blocks
these actual-data commands; no completed ablation or GPU cost is claimed.

## Bounded C1 cluster staging and launch

`python scripts/c_stage_rewrite.py {manifest,plan,fetch,verify} --config CONFIG
--manifest MANIFEST --max-total-bytes N --max-file-bytes N` stages only the existing six
registered dev repository identities and their available L2/L3 levels. The full configs need
36 files: original corpus/query/qrels plus Rewrite queries for nine repository/level pairs.
Rewrite corpora/qrels are not fetched. Repository label, dataset directory, folder and level
must all match the allowlist; relabeling Verified as a dev repository fails.

On an Ada CPU allocation, resolve the public dataset revision once, then explicitly pin it:

```sh
# Read-only lookup; this neither clones a dataset nor changes a remote.
git ls-remote https://huggingface.co/datasets/zhangfw123/CORE-Bench refs/heads/main
# Set RIL_DATA_REVISION to the returned full 40-character SHA before staging.
```

`manifest --revision SHA` reads only selected directory metadata at that pinned commit. LFS
files require the upstream SHA-256; ordinary Git files require their blob SHA-1 (including the
Git blob header). Every downloaded file additionally records SHA-256, byte size and JSONL row
count in `data_root/provenance.json`. A final line without a newline counts as a row. The plan
prints required files, pinned revision, total bytes, manifest hash and an initial conservative
free-disk bound (total plus largest file). `plan` is entirely offline with a recorded manifest;
its file/total bounds reject missing identities, unknown paths and oversized inputs before any
transfer. Source identity is durable before dispatch and cannot change within one data root.

`fetch` requires `RIL_CLUSTER=1` and a positive Slurm job id in a CPU-only allocation. These are
operational guards, not host attestation. No real acquisition was performed to validate Ada or
upstream availability. Downloads stream in bounded blocks, validate HTTP status, Content-Range,
Content-Length and encoding, resume durable `.part` files, verify upstream checksums before
atomic rename, and refuse corrupt completed files instead of replacing them. Exclusive locking
serializes acquisition. Changed source identities, orphan partials and symlink destinations or
ancestors fail closed. Restart disk checks use remaining bytes plus the largest remainder;
a fully completed recheck needs no payload space and makes no network calls. `verify` checks
all files and completed provenance without network or writes; it is also valid in the GPU job.

Four submission templates are ready but have not been submitted:

| Job | Purpose / required preparation |
|---|---|
| `scripts/ada/c_rewrite_stage.sbatch` | CPU manifest/plan/fetch/verify; pinned `RIL_DATA_REVISION`, explicit total/file byte bounds and disk/quota review |
| `scripts/ada/c_rewrite_bm25.sbatch` | CPU source verification then existing BM25 config; measured indexing memory and fresh output/log paths |
| `scripts/ada/c_rewrite_dense_cache.sbatch` | GPU cache preparation only; staged model/source, supported-card constraint, safe measured batch/score ceiling, remaining GPU-hours |
| `scripts/ada/c_rewrite_dense_eval.sbatch` | CPU source verification and cached-score evaluation; measured load memory and fresh output/log paths |

First run `sinfo`, `sacctmgr show qos`, `myallocation` and disk/quota probes for account C. Set
`RIL_ROOT`, `RIL_PYTHON`, `RIL_CONFIG`, `RIL_STAGE_MANIFEST`, `RIL_STAGE_TOTAL_BYTES`,
`RIL_STAGE_FILE_BYTES`, and `RIL_RESOURCES_VERIFIED=1` only after review. Create `logs/` before
submission. No account/partition/QOS/card is selected by the templates; pass the verified values:

```sh
sbatch --partition=VERIFIED --account=VERIFIED --qos=VERIFIED scripts/ada/c_rewrite_stage.sbatch
sbatch --partition=VERIFIED --account=VERIFIED --qos=VERIFIED scripts/ada/c_rewrite_bm25.sbatch
# After CPU-only model acquisition and source completion, GPU job also requires a supported
# --constraint, RIL_GPU_HOURS_REMAINING, RIL_BATCH_SIZE and RIL_SCORE_BYTES.
sbatch --partition=VERIFIED --account=VERIFIED --qos=VERIFIED --constraint=VERIFIED scripts/ada/c_rewrite_dense_cache.sbatch
sbatch --partition=VERIFIED --account=VERIFIED --qos=VERIFIED scripts/ada/c_rewrite_dense_eval.sbatch
```

Submit downstream steps only after their predecessors pass (or use verified `afterok` job ids).
Register actual evaluations before execution and record each job/cost in the account ledger.
The cache job requests one GPU for30minutes (.5 GPU-hours); its remaining-budget gate assumes
that submitted envelope, which must be checked if submission options override it. Requests for
1/8/16GiB and runtime limits in these templates are conservative **estimates**, not measured
capacity or permission to skip per-unit sizing. Neither source/model availability nor these
resource estimates have been validated. No source fetch or model load runs locally; the actual
BM25 reproduction, dense ablation and GPU cost remain blocked. Account C access is unavailable.

## Agent pilot boundary (provisional: ADR-007, ADR-008)

Run the model-free C3 apparatus from the repository root:

```sh
PYTHONPATH=. python scripts/c_agent_pilot.py --config configs/experiments/c_agent_pilot.yaml
```

This command admits only synthetic `fixture-*` tasks in artificial `fixture/` repositories.
It runs 20 fixtures under no context, reference BM25 file retrieval and oracle gold-file retrieval.
No real SWE-bench instance is loaded; actual dev n=0. The model is a deterministic scripted repair
stub, and this is not a replication of any published scaffold. No model service is called.

```python
RetrievalTool.search(query: str, limit: int) -> Sequence[RetrievedFile]
RepairModel.propose(request: ModelRequest) -> ModelResponse
PatchGrader.grade(task: Task, edits: Sequence[FileEdit]) -> Grade
run_instance(task, *, retriever_id, tool, model, grader, seed, temperature,
             top_k, execution_identity=None) -> dict
summarize(rows, *, draws, seed) -> dict
source_manifest() -> dict
```

`Task` contains public issue text and the source snapshot. `ModelRequest` contains only instance
identity, issue, returned source context, seed and temperature. Reference edits and executable
checks stay outside this request. Only the oracle tool receives gold file identities; other tools
reject them. Gold identities join output rows after the model call. Retrieved files must match
the snapshot, with unique paths, finite scores and a respected limit. Retrieval parameters use
RIL's existing `BM25Params`; other retrievers can implement the same tool boundary. This adapter
is file-level apparatus; a unit-level RIL adapter must explicitly preserve ranking and assembly.

The response contains exact old/new source edits and usage, with no resolved field. The grader
applies edits only to existing snapshot files, requiring one exact old-text occurrence. It writes
a fresh temporary directory, runs hidden trusted Python unittest checks in a separate process,
keeps return status/output and removes the directory. Every baseline/reference control fails/
passes as intended. This is trusted-fixture execution, not a live untrusted-code sandbox or the
official benchmark harness. The live gate refuses missing access, spend cap, pinned model,
scaffold and harness; it also refuses a live adapter because none has been installed/reviewed.
Supplying access fields alone never permits a call. Real data must follow the registered dev
membership and single-look final-test rules before a future harness can admit it.

Rows store instance/retriever identity, fixed seed/temperature/execution identity, issue and
snapshot digests, retrieved paths/content digests/scores, attempted edits and patch digest,
independently graded outcome/status/test output, token/cost accounting and wall/retrieval time.
The execution identity carries model/scaffold/config/source identities; paired summaries reject
missing/duplicate pairs or mismatched task/fixed settings. Source checksums resolve from the
package location rather than the caller's directory. Config and source checksums are separate.
A dirty git run records the actual executed source manifest rather than claiming the base commit
alone describes it. Stored fixture inputs can be reconstructed; raw model conversation is not
persisted by this stub. Future live adapters must preserve complete request/response/failure logs.

Tokens are explicitly synthetic UTF-8-byte/4 surrogates. Configured per-million rates produce
nonzero synthetic dollar values to exercise accounting; actual dollars are zero. Neither is an
estimate of a chosen model's cost. `wall_seconds` at result level is execution time before
statistical summarization; condition totals include retrieval, scripted proposal and test grading.
CLI wall time including exact power calculations is recorded separately. Retrieval percentiles
exclude index build and grading and use a tiny cold synthetic workload, without warmup; they are
not end-to-end agent latency. Timing and test-log elapsed text may vary on replay, while patch,
request, usage, resolved outcomes and paired statistics reproduce for this deterministic stub.

Output `results.json` and the configured log contain condition summaries, all individual rows,
per-instance discordance rows and exact McNemar comparisons. Effects mean second minus first.
Condition ordering in comparisons is lexical and explicitly named. Clustered intervals use
query-weighted means and whole artificial repositories (2,000 draws, seed 0). Four identical
synthetic patterns produce degenerate intervals; they do not measure real sampling uncertainty.
`illustrative_fixture_mde` calls the shared exact statistics at n=302 and 432 using the observed
fixture discordance. These are arithmetic smoke checks. `real_instances=0` and
`scientific_cost_discordance_mde=null` prevent their promotion to RQ3 empirical power evidence.
C4 owns the full paired/resumable/idempotent/spend-capped orchestration and failure reports.

## Scaffold options: historical source evidence, no selection

Five versioned papers were read in full, including appendices, result tables and numerical
figures (216 PDF pages total); all five notes pass numeric/page checks. The table below separates
paper-supported extensibility from an unimplemented controlled retrieval intervention. Costs
are **paper_reported historical** values with their stated scope, not current prices or limits.
No current release, dependency installation, hosted availability or local memory feasibility was
verified. Paper-version evidence does not establish present software behavior.

| Candidate | One replaceable RIL retrieval tool | Seed/temperature and reproducibility | Cost and logs; hosted/local scope |
|---|---|---|---|
| SWE-agent | Configurable Bash/Python command files make integration plausible; several native searches and shell access can bypass the added retriever. Exclusive boundary needs a pinned-source test (Appendix A.2–A.3, pp.21–24). | Temperature zero was selected, yet repeated outcomes vary; decoding seed contract absent (Appendix B.1 p.25; Table 10 p.35). | Episode trajectories/patches and a historical $4 cutoff are described; full failure/token/retry schema needs audit. Table 1 p.6 cost averages are **success-only**, not all-attempt budgets. API/local adapters claimed, local replication unestablished ([v3](https://arxiv.org/pdf/2405.15793v3), pp.5,21,37–38). |
| OpenHands / fixed CodeActAgent | Python AgentSkills extension is explicit; ordinary shell/search paths remain. Platform must be reduced to one pinned agent/configuration and tested at the chosen boundary (pp.3–5). | Exact-input mocked tests are deterministic; no live seed/temperature/repeatability guarantee (Appendix E p.19). | Ordered actions/observations and cumulative cost state are documented; raw retry/usage/termination completeness and hard caps are unverified. Hosted historical averages $1.72/$1.10 per issue are not ceilings; no controlled local replica ([v3](https://arxiv.org/pdf/2407.16741v3), Table 4 p.8, pp.3,19–22). |
| Agentless | Staged tree localization, folder filtering, embedding retrieval and fusion; no native single retrieval tool. Choose and audit a stage adapter before a causal swap (pp.6–7). | Some greedy stages plus stochastic edit sets, patches and tests; temperature .8, no seed/replay guarantee (p.9). | Historical $0.70 and 78,166 tokens per issue average; no cap/full failure log contract. Dated hosted generator and separate embedding service, no demonstrated local equivalent ([v2](https://arxiv.org/pdf/2407.01489v2), Table 1 p.10, pp.9,18). |
| LocAgent + fixed repair | Three localization tools; SearchEntity alone leaves traversal and direct code reads. Downstream repair uses Agentless; not itself a patch scaffold (Table 2 p.5; p.11). | Temperature 1.0, two interactions and reciprocal-rank aggregation; no seed guarantee (Appendix A.2 p.14). | Localizer averages $0.05/$0.09 with fine-tuned open models and $0.66 with a closed-source model; excludes fixed repair and is based on service prices. Event log diagram, full audit schema/cap absent; native/text tool modes differ ([v2](https://arxiv.org/pdf/2503.09089v2), Table 5 p.9, pp.14–15). |
| CoSIL + Agentless-1.5 repair | Multi-stage graph localizer with pruner/reflection; its reported repair agent is Agentless. A fixed repair-stage adapter is plausible; one native interchangeable retrieval tool is not shown (pp.4–6). | Greedy localization; repair uses one greedy plus nine sampled patches at .8. No seed guarantee; published/reproduced repair totals differ (pp.6,10). | Localization mini-sample service costs $0.022/$0.341 are not whole-repair budgets; message history exists, full trace/cap unestablished. Local vLLM and hosted supplementary modes are described, equivalence untested ([v3](https://arxiv.org/pdf/2503.22424v3), Table VII p.9, pp.5–6). |

Reasoned recommendation pending the lead: retain Agentless as the existing provisional ADR-007
candidate, and compare a narrowly specified stage adapter with an extensible SWE-agent or
OpenHands adapter. First inspect a pinned revision and prove the same tool signature, alternative
search policy, context assembly and repair/grading settings remain fixed in an offline fixture.
Then repeat an authorized paired dev subset to measure real cost, discordance and run noise.
Local or hosted model selection and spend remain ADR-008 questions. The scripted pilot clears
apparatus checks only and cannot select any candidate or supply those real measurements.

## Durable paired runner (C4 apparatus)

```sh
PYTHONPATH=. python scripts/c_paired_runner.py --config configs/agent/c_paired_fixture.yaml \
  --audit-output results/logs/c4_fixture_first_2026-10-30.json
# Same config/output: exact stored pair reuse, zero new model or grading calls.
PYTHONPATH=. python scripts/c_paired_runner.py --config configs/agent/c_paired_fixture.yaml \
  --audit-output results/logs/c4_fixture_resume_2026-10-30.json
```

`ril.agent.paired.run_config(path, *, report_dir=None)` reuses C3's `run_instance`, independent
trusted fixture grader, RIL BM25 parameters and shared statistics. The configuration fixes scaffold,
scripted model, seed, temperature, tasks and synthetic pricing; each retriever has an explicit unique
id plus kind/top-k/BM25 parameters. `none`, `bm25`, and oracle-gold-file kinds are supported.
Only fixtures are admitted. This adds no reviewed live adapter, benchmark harness or code sandbox;
access keys alone cannot enable real execution. Actual development n=0 and actual dollars=0.

The output contains checksummed `checkpoint.json`, `results.json`, `paired.csv`, `conditions.csv`,
`mcnemar.csv`, `diagnostics.csv`, `latency_log.csv`, config and hardware metadata. Every row is
keyed by instance/retriever id and includes all C3 request, patch, retrieval, grade and usage data.
Gold files join only after model execution/grading. `gold_file_hits` retains every gold file's
retrieved/attempted-edit booleans separately, including partial misses; `gold_files_missing` counts
absent gold files. `attempted_edit_file` is an observable file-use proxy, never model attention,
correct application or a causal reasoning label. Independently resolved successes get no failure
label, including successful edits inferred without retrieved context.

For a failed row the aggregate hierarchy is: no gold file retrieved => `not_retrieved`; at least
one gold retrieved but no retrieved gold file edited => `retrieved_not_used`; otherwise `used_wrong`.
Thus an aggregate used-wrong row can still have another gold file missing; use individual flags and
missing count for multi-file interpretation. Failed exact-edit application also counts as attempted
use. Default fixtures may produce zero rows in some categories; explicit abstention, wrong-gold-edit
and multi-gold tests exercise all branches without manufacturing table counts.

An exclusive filesystem lock spans checkpoint inspection, reservation, model/grader execution and
report writing. Atomic temporary-file replacement with file and directory synchronization protects
checkpoints. Config/version/source, fixed model/scaffold/seed/temperature, source snapshots, issue,
reference edits, gold files and hidden grader hashes must match on resume. Changing a retriever's
parameters under the same id fails. Missing keys, corrupted envelopes or changed rows fail closed.
Checksums detect accidental corruption; they are not signatures against an adversarial file editor.
Do not delete checkpoints or lock files to recover a potentially charged dispatch.

The runner durably reserves a conservative synthetic maximum before calling the scripted model:
input bounds cover the entire public snapshot/issue and output tokens have an explicit ceiling.
Nonzero synthetic prices test accounting only. Completed and unknown reservations remain charged
against the configured synthetic cap; known completion does not reclaim headroom. Exceptions or
interruptions never replay an ambiguous dispatch. A response exceeding quoted token/dollar maxima
is retained as observed usage, blocks the whole run across restarts and records an observed cap
breach when applicable. Unknown usage is counted separately; zero actual dollars does not estimate
what a real model would cost. Future live adapters need reviewed billing/retry/idempotency handling.

Requested/completed pair counts, complete paired-instance count and each missing reason are explicit.
An unknown outcome is absent from completed rows and never becomes resolved=false. Any incomplete
pair blocks all paired statistics (`summary=null`, `statistics_status=blocked_incomplete_pairs`);
the CLI returns status 2. Diagnostic counts still name requested/completed/missing denominators.
Reports are immutable. Recovery that changes completion requires `--report-dir` naming a fresh
path; prior reports remain. Completed-run resume preserves checkpoint and report bytes, recording
new/reused call counts only in a new invocation audit. Fresh replay compares semantic fields while
excluding wall/retrieval timing, test-log elapsed text, output-dependent execution identity and row
checksum; model requests, edits, grades, usage and paired statistics must agree. Cold retrieval
percentiles exclude index building/model/grading, discard no warmups, and measure tiny fixtures.


## Google Colab development kit

The selected development runtime can be Colab without fabricating Slurm identifiers.
Build an uploadable kit from a clean committed checkout:

```sh
python scripts/c_colab.py package --out data/processed/c_colab_kit
```

Upload `ril-cpu.ipynb` through Colab's File / Upload notebook, select a CPU runtime and run
cells top to bottom. Mount Google Drive through its consent dialog and choose the matching
`ril-colab-source.zip` when prompted. No GitHub push/read credentials are needed for this source
transfer. The notebooks verify the whole ZIP plus every committed source file and manifest before
execution. Existing modified local source is refused. Private or untracked files are excluded
by packaging the committed tree only. `kit.json` identifies the original commit and ZIP SHA-256.
Source archives contain no Git repository; evaluation logs retain the original commit fallback
and explicit unknown/dirty Git status. Mining explicitly reports `archive_without_git`, requires
a full pinned source commit and records actual implementation checksums before dispatch.

Default CPU cells install Python3.11.18 and the exact25CPU lock pins plus a pinned build backend
in an isolated environment. They execute retrieval and paired synthetic checks, including a
zero-new-call replay, and finish with `COLAB_READY`. Real data, mining and model preparation
flags default to false. The report verifies every expected installed package and interpreter;
model API cost is zero, while compute billing is unmeasured. No hosted repair service or
real grading harness is configured by this kit.

`configs/experiments/c_colab_environment.yaml` pins the separate CodeRankEmbed environment:
Torch2.4.1+cu121, NumPy1.26.4, transformers4.44.2, sentence-transformers3.1.1 and tokenizers0.19.1,
matching the recorded Ada compatibility path. Its47-package closure was resolved from metadata;
actual Colab installation, Drive behavior and CUDA execution were not performed here. CPU
NumPy remains the project lock version. The declared official indexes and exact requirements
are used; the pinned build backend prevents an unbounded build-dependency substitution.

For dense preparation, enable the CPU notebook's explicit environment/weight preparation cell.
It acquires the existing pinned encoder revision on CPU and stores a checksum-identified portable
Python/GPU-environment snapshot in Drive. Only then open `ril-gpu.ipynb` in an NVIDIA GPU runtime.
It restores the snapshot without package/model downloads, rechecks profile/architecture/source
identity, verifies the installed pins and runs a real CUDA matrix product. Dense encoding remains
opt-in, refuses existing cache artifacts, verifies every staged upstream source first and reserves
0.5 of the8encoding hours per30-minute subprocess attempt. Unknown interrupted reservations are
not refunded. This does not meter idle notebook GPU allocation or cloud billing. Return to the
CPU notebook's explicit `RUN_DENSE_EVAL` cell for cached-score evaluation with the same run id.

Local native `/content` storage holds working files, locks and environments; Drive receives
immutable checksum blobs and an atomic completed-file index. Source acquisition checkpoints after
each verified completed file; an unfinished transfer can need replay after VM loss. Mining snapshots
stable API/instance files every60seconds and omits regenerable bare Git caches. Sudden VM loss can
lose work since the last completed snapshot. Corrupt blobs, partial restore targets, symlinks and
source drift fail closed. Only one active VM may use a persistent work area: a local lock does not
coordinate independent Colab VMs. Environment snapshots and model caches can consume several GiB;
Drive capacity and actual full-process memory still need checking on the real runtime.

Operational runtime proof is issued by the original `google.colab` kernel and re-probed from
that host interpreter when the project uses its isolated Python3.11 environment:

```python
from ril.evaluation.runtime import issue_colab_receipt
issue_colab_receipt('/content/ril-runtime.json')
# Project subprocess environment: RIL_RUNTIME=colab,
# RIL_COLAB_RECEIPT=/content/ril-runtime.json; no Slurm or cluster flags.
```

A receipt matches the current VM boot identity and actual accelerator inventory. Reissue it
after a restart or accelerator change. CPU acquisition refuses an attached NVIDIA GPU even when
CUDA visibility is masked. GPU encoding requires an attached GPU and retains the existing CUDA
test. These are operational guards, not security attestation against the notebook owner. Slurm
remains supported through its existing explicit job/cluster admission; account/card selection
and allocation review are unchanged.

The real dev source plan stays at the existing36files, original labels and candidate identities.
The notebook's initial transfer bounds are2GiB total/512MiB per file; a bound failure requires a
reviewed sizing change. No final test repository or full-scale mining option was added. Scientific
runs require measured memory sizing and registration before execution. Colab/Ada agreement has not
been measured; use a shared dev overlap before pooling accuracy and label hardware-sensitive timing
separately. The actual live agent/scaffold/model/harness/spend gates remain open.
