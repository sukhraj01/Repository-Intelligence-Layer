# RQ3 pilot: cost, variance and feasibility of measuring resolved rate

**Status: design of the pilot, `provisional: D104`. Run finished 2026-11-07 (400 of 400 units, 565 calls); analysed in `E-RQ3-PILOT-RESULT` (D109); see "Pilot result".** The pilot measures what an RQ3 run costs and how
much it varies. It is not the RQ3 result. The language model of the final RQ3 runs is decided after the
pilot (ADR-008 stays open); the scaffold is ADR-007 (Proposed). Code: `ril/agent/providers/`,
`scripts/rq3_pilot.py`. Experiment entry: `E-RQ3-PILOT-PREP` in `docs/experiments/B.md`.

## Decision D104 (provisional; evidence class: reasoned from limits read on 2026-11-06, no call made)

Free-tier limits read from the provider's developer console on 2026-11-06 (per project, not
guaranteed, can change; stored with their date in `configs/agent/gemini_limits.yaml`):

| model | requests / min | tokens / min | requests / day |
|---|---|---|---|
| Gemini 3.5 Flash Lite | 15 | 250,000 | 500 |
| Gemini 3.6, 3.8, 3, 2.5 Flash | 5 | 250,000 | 20 |
| Gemini 2.5 Flash Lite | 10 | 250,000 | 20 |
| Gemma 4 26B and 31B | 30 | 16,000 | 14,400 |
| Pro models | 0 | 0 | 0 |

1. **Provider and model.** Gemini 3.5 Flash Lite through the developer API on the free tier. Only this
   model has a daily request limit (500) large enough for a pilot; with 20 requests a day none of the
   other Flash models can finish one instance of a multi-call scaffold per day. The two Gemma models
   have the daily request budget but 16,000 tokens a minute: a prompt at B = 8,000 is about 8,500 to
   9,500 tokens, so about one call a minute (at most about 1,400 a day, by arithmetic, not measured) and
   no call at all at B = 16,000. They are not excluded by the request limit, only by the token limit;
   they are a different model family, so a pilot on them would measure a different cost. The exact model string and the date go into every call row. Free-tier limits are not guaranteed and
   the model is a moving target, so the pilot measures cost and variance only. Declared fallback: a
   pinned paid version on Tier 1 billing with a hard spend cap. Terms of use: see "Terms of use" below.
2. **Scaffold.** Retrieval-supplied one-shot repair (edit blocks as in Agentless, no candidate selection): one prompt per instance holding the issue text
   and the assembled context (`specs/assembly.md`, ADR-014; the same assembly for every arm), one repair
   call at temperature 0 asking for edits in a fixed format (`ril/agent/providers/patch_format.py`),
   and up to two follow-ups after a reply whose format is unusable (counted, the same for every arm).
   Expected 1 to 3 calls per instance; the pilot measures it. The context budget B is 8,000 tokens
   (grid 8,000 / 16,000), stated in the model's tokens (see "Open points"); a prompt then holds about
   8,300 to 9,500 tokens with the issue.
3. **Design.** About 100 instances, two first stages (BM25; RRF(BM25, dense)), two runs each: 400 units,
   400 to 1,200 calls.

**Flip experiment.** The smoke run (at most three calls) and the first day's rows show the calls per
instance, the realised prompt tokens against the approximate count, the malformed-edit rate and the
rate of 429 answers. If calls per instance exceed 3, the unusable-reply rate exceeds a third, or the day
cap is hit before 100 units finish, the free tier is not workable and the paid fallback applies. Time-box:
one day of calls.

## Terms of use (read on the provider's terms page on 2026-11-06; decision recorded the same day)

For the unpaid API quota the provider's terms say that submitted content and responses may be used to
improve its products and may be read by human reviewers (disconnected from the account, key and project),
and they advise against submitting sensitive, confidential or personal information. Decision: the pilot
submits public repository text only (issues, code at public commits, public patches); nothing from the
team's own writing, no keys, no personal data. Enforced in code: `ril/agent/providers/screen.py` rejects a
prompt that holds a path under a home directory, a credential-shaped string, or an e-mail address not on a
reviewed list, at `prepare` and again at `run` before any call (`tests/unit/test_providers_screen.py`). Public
source files and issues do carry addresses (project contacts, author lines, placeholders): the 16 found in the
200 prompts were read where they occur and listed by SHA-256 in `configs/agent/prompt_email_digests.txt`
(no address is written to a tracked file); the operator's own git address is rejected even if listed. The
terms are also a reason for the paid fallback declared in ADR-008.

## Instances

Provisional (open question): the pilot draws its 100 instances from the dev instances (355 across five
repositories), by a seeded draw of whole instances, so that the final test (Verified) is not read
before the configuration is fixed and B is not chosen on it. The L2 query text of an instance is its
issue text, used as stored. The prompt for an instance is built from the stored ranked list; the same
instance and the same first stage give the same bytes (`prepare` checks every context against the hash
recorded by the assembly stage).

## What is measured

Per first stage: calls, input and output tokens per instance; the share of first replies in an unusable
format and the share still unusable after the follow-ups; 429 and 5xx counts; latency per call as p50,
p95 and p99; run-to-run agreement at temperature 0 (same reply text, same edits when both are usable,
same usability). The resolved rate only if the execution in "Can resolved rate be measured" is
available for the chosen instances; otherwise `gold_in_context` from the assembly manifest is the
retrieval-side reading (an instance whose gold is absent from the context failed in retrieval or
assembly; the pilot does not execute edits).

## Limiter and adapter

- Quotas are read from `configs/agent/gemini_limits.yaml` with their date; 90% of each is used
  (`margin`), so the effective limits are 13 requests a minute, 225,000 tokens a minute and 450 requests
  a day. A request counts against the day when it is sent, whatever its outcome.
- The day is the Pacific calendar day (the quota resets at midnight Pacific). At the cap, `run` stops
  cleanly and prints when to resume; the same command the next day continues, because the call log
  alone decides what is finished. A unit stopped between a reply and its follow-up resumes from the
  stored reply.
- The key is read only from `~/.ril_llm_env` (one line `export GEMINI_API_KEY=...`, mode 600; the file
  is refused if group or others can read it) or from the environment variable. It is sent only in a
  request header, held in an object with a masked text form, and removed from every string that reaches
  a log or an exception. Tests check that it never appears in logs, files or error messages.
- 429 and 5xx answers (and network faults) are retried with exponential backoff (4 s doubling, capped at
  120 s; a `Retry-After` header is honoured) and counted per call.
- Per-call row (`calls.jsonl`): instance id, arm, run index, attempt, model string, seed field,
  temperature, Pacific date and UTC time, input, output and thought tokens, latency, finish reason, HTTP
  status, retries, 429 and 5xx counts, hashes of the request and the reply, the format fault if any,
  whether the edits are usable. Prompts and replies are stored as files named by their hash.

## Commands

```
python scripts/rq3_pilot.py prepare OUT --from-cache configs/experiments/rq3_pilot_prepare.yaml
python scripts/rq3_pilot.py run OUT LOG --dry-run          # plan: units, calls, days; no key, no network
python scripts/rq3_pilot.py run OUT LOG --max-calls 3      # smoke test
python scripts/rq3_pilot.py run OUT LOG                    # resumable; stops at the daily cap
python scripts/rq3_pilot.py report LOG --out LOG/report.md
```

Estimated days: 400 units need 400 to 1,200 calls; at the effective 450 requests a day that is 1 to 3
days (a limit of 500 a day, 100% used, would give 1 to 3 days as well).

## Can resolved rate be measured on the cluster? (measured 2026-11-06, account A)

Commands, scripts and outputs: `scripts/ada/rq3_feasibility/`, `results/rq3_pilot/part_a/` (job ids in the
README there). Resolved rate needs: apply a patch, run the tests, decide.

| Question | Answer |
|---|---|
| Which dataset and instances would RQ3 use? | SWE-bench Verified (ADR-005, final test): 500 instances in 12 repositories, of which 432 carry L2 labels and 302 L3 (dataset card; the RQ3 power table uses n = 432). All 500 have a base commit, a test patch, a non-empty FAIL_TO_PASS list and an install specification in the benchmark's own package (version 4.1.0). The dev instances were not checked for execution. |
| Is a container runtime available as the engineer? | **No.** None of `apptainer`, `singularity`, `docker`, `podman` is on the PATH of the login node or of a compute node. A module `u22/singularity-ce/4.2.2` is listed, but its install directory (`/usr/local/apps/singularity-ce-4.2.2`) does not exist on the login node or on the compute node probed; a tarball of that tree is on the cluster's shared data disk. Extracted node-locally (version 4.2.2), it pulls an image and builds the image file as the engineer, but running it fails: "Failed to create user namespace: maximum number of user namespaces exceeded" (`max_user_namespaces` is 0 on the node probed, and the extracted starter is not setuid root). Registry hosts are reachable (the manifest of a published per-instance Verified image answers 200), so images could be pulled but not run. |
| Can an instance environment be built without root? | **Partly.** `uv` (a static binary from GitHub releases) builds a virtual environment with the specification's Python and its pinned packages from PyPI. Of the 500 instances: 263 need Python 3.8 or newer and no pre-install step (buildable); 59 need Python 3.8 or newer and a pre-install step that is not an `apt-get` (file edits, a source build; untested); 35 need `apt-get` (root); 143 need Python 3.5 to 3.7, which `uv` cannot download (its list starts at 3.8). There are 80 distinct (repository, version) environments for the 500 instances. Hosts reachable from a compute node (HTTP status): pypi.org 200, files.pythonhosted.org (reachable; a 404 at its root), github.com 200, GitHub releases 200, codeload.github.com 301, objects.githubusercontent.com (reachable; 404 at its root), api.github.com 200, huggingface.co 200, repo.anaconda.com 200, conda.anaconda.org 302, astral.sh 200, registry-1.docker.io 401, auth.docker.io 405, ghcr.io 405, quay.io 401, hub.docker.com 200, download.pytorch.org 403; cloud.sylabs.io unreachable (000). Downloads are slow (about 100 KB/s from GitHub). |
| Does the gold patch pass its tests (three repositories)? | **Yes, on all three, and on a fourth after a pin.** requests-6028, seaborn-3187 and xarray-7393 (different repositories; the specification's own Python 3.9 / 3.9 / 3.10 and pinned packages): before the gold patch the FAIL_TO_PASS tests fail (2 of 2, 2 of 2, 2 of 2), after it they pass; time and memory below. A fourth, flask-5014, failed first because the specification leaves pytest unpinned and today's pytest no longer has `monkeypatch.notset`; with `pytest<8` it ends with 60 passed after the patch and 1 failed before it. |

| Instance (repository) | Python | Environment build | Test run (after patch) | Peak memory of any step |
|---|---|---|---|---|
| psf__requests-6028 | 3.9 | 19 s (venv 13 s, install 6 s) | 0.7 s; 2 of 2 FAIL_TO_PASS pass; 8 fixture errors in unrelated tests, also before the patch | under 0.3 GB |
| mwaskom__seaborn-3187 | 3.9 | 100 s (packages 75 s, install 25 s) | 84 s; 2 of 2 pass; 251 passed | under 0.3 GB |
| pydata__xarray-7393 | 3.10 | 138 s (packages 134 s, install 4.5 s) | 0.9 s; 2 of 2 pass; 71 passed | under 0.3 GB |

The memory figure is the largest resident size of any child process of the probe (296 MB), not per step.
Not checked: the PASS_TO_PASS tests (a resolved instance needs both lists); a patch from a model rather
than the gold patch; instances of the 143 and 35 that need an older Python or root.

**If measured on the cluster, the steps** are: one environment per (repository, version) from `uv` and the
specification's pins (with a pinned pytest where the specification leaves it open, which is a departure
from the specification to record); apply the model's edits (a block that does not apply is a failed
instance); apply the test patch; run the specification's test command on the test files; read the
PASSED lines; resolved means all FAIL_TO_PASS and all PASS_TO_PASS pass. Cost per instance in the three
measured: 1 to 5 minutes on one CPU, under 0.3 GB, dominated by the package download (shared across the
instances of one environment), and the cluster's per-user limit of 10 CPUs applies. That covers at most
the 263 instances above (52.6% of Verified; superseded by the measurement in "Executable evaluation (D106)" below); which repositories they fall in is in
`results/rq3_pilot/part_a/a_env_table.csv`.

**If it is judged not enough, the options** (none chosen here): a different executor with a container
runtime and root (a machine of the engineer's own, or an account with user namespaces or the setuid
install enabled by the cluster's administrators); a smaller instance set (the 263 buildable ones, or a
subset of repositories, which changes which claim RQ3 can make); the fallback of file-level hit rate
(`gold_in_context` of the assembly manifest) as a proxy for resolved rate, which measures retrieval and
not the agent's edit.

## Executable evaluation (D106, measured 2026-11-06 and 2026-11-07, `E-RQ3-EXEC`)

**Decision D106** (evidence class: measured counts; reasoned rule; flip experiment: the subset's difference from the 500,
reported below and in `results/rq3_exec/subset_vs_500.csv`). RQ3's resolved rate is measured on the **executable subset**:
the instances of SWE-bench Verified for which, on the cluster without root and without a container, the environment builds
from the specification (no `apt-get`), the gold patch applied to the base commit makes every FAIL_TO_PASS test pass and every
PASS_TO_PASS test still pass, in two repeated runs that agree. The subset is fixed by this procedure before any retriever's
patch is evaluated, is stored with the reason for every exclusion (`results/rq3_exec/executable_instances_v1.json`), and is
the same for all arms. Instances that need `apt-get` are excluded and counted; instances that need an older Python were tried
with `uv` and then with an interpreter from conda-forge (micromamba, node-local), and are excluded only where that failed. A
result on the subset does not carry to the excluded instances.

**Numbers.** 500 instances, 429 built in both runs, **377 executable** (django 228 of 231, sympy 75 of 75, pytest 19 of 19,
xarray 18 of 22, astropy 15 of 22, sphinx 11 of 44, requests 4 of 8, pylint 4 of 10, seaborn 2 of 2, flask 1 of 1,
matplotlib 0 of 34, scikit-learn 0 of 32). Main exclusion causes: `apt-get` 38 (matplotlib 34), compiled installs and
packages without a wheel for the interpreter under pip 39 (scikit-learn 32, astropy 6, pylint 1), sphinx test start 28,
gold patch failing a test 18. Of the 140 instances that needed Python older than 3.8, 111 are executable (all of django's)
once micromamba supplies the interpreter. The earlier figure of 263 buildable instances (above) counted only the Python
version and the pre-install step; this measurement includes the gold run. Differences from the 500 (repository mix: django
60.5% against 46.2%; the dataset's difficulty field; L2 and L3 label availability 84.9% and 59.4% against 86.4% and
60.4%) are in `E-RQ3-EXEC`.

**Cost.** Per instance and run: p50 17.8 s, p95 197.6 s, p99 250.8 s; peak resident size of any step p50 124.5 MB, p95 299.3
MB, p99 443.5 MB. Evaluating one model patch costs one run (3.7 to 4.0 CPU-hours for one pass over the 377). With the
cluster's per-user limit of 10 CPUs that is under two hours per arm and run when parallelised over four workers per job
(arithmetic from the measured sum, not a measured wall time).

**What RQ3 still needs on this subset** (reported, not chosen). Retrieval contexts need unit records: 36 of the 377 have
them (astropy, xarray, requests, seaborn, flask); django, sympy, pytest, sphinx and pylint do not; building them is
estimated at 3.8 to 9.1 CPU-hours and 0.5 to 10.3 GPU-hours per checkpoint, nearly all django and sympy
(`results/rq3_exec/unit_build_estimate.csv`; an estimate from the eight-repository build's rates and one measured unit
count per repository). Power at N = 377 (exact McNemar): minimum detectable difference 4.75 / 5.75 / 6.75 / 8.25 points at
discordance 10 / 15 / 20 / 30%; the discordance values are placeholders and run-to-run noise is not in the model. L3
labels exist for 224 of the 377, so the L3 claim rests on fewer instances than the table's n = 302 and on a django-heavy
mix (134 of 224).

**Unit records and encoding (D107, `E-RQ3-UNITS`, 2026-11-07).** All 377 members now have unit records and BM25 scores (36 stored earlier, 341 built, 0 failures), and dense scores of the untrained base encoder at 512 tokens (`dense_L2`). Measured: 10.4 million unit slots over all snapshots hold about 221 thousand distinct texts (django and sympy distinct shares 0.011 and 0.037); the encoding rule fixed before the count (at most 6.0 GPU-hours at 109 texts per second, Block 4) allowed it and the run took 0.377 GPU-hours; summed CPU for the unit and cache build was 8.8 hours (estimate 3.8 to 9.1). Gold readings were built for 284 L2 and 202 L3 instances through the existing mapping, unchanged; none was used for a selection. Not done: encodings of trained checkpoints (their own cost, not in the 0.377), retrieval contexts for the 377, any evaluation.

**Retrieved contexts (D108, `E-RQ3-CONTEXTS`, 2026-11-07).** Contexts of all 377 instances for BM25, the untrained base encoder and RRF over both, at 8,000 (primary) and 16,000 tokens, built with the assembly stage unchanged (unit cap 1,000, approximate tokenizer, ratio 1.0 as in the pilot): 2,262 of 2,262, 0 failures, every context fills its budget; no query had to be encoded, and L3 uses the L2 vectors (identical texts). Share with a gold file in the context at 8,000 on L2 (320 labelled): BM25 69.4%, dense 73.4%, RRF 80.3% (descriptive, no interval); 30 rebuilt instances are byte-identical. The 8,000-token contexts are on the engineer's machine as one archive; trained-checkpoint arms use the same builder with their own dense scores. No agent was called.

**Code.** `ril/evaluation/executor/` (`evaluate(spec, patch, config)` serves a gold patch and a model patch alike),
`scripts/rq3_exec.py`, `scripts/ada/rq3_exec/`; tests `tests/unit/test_executor.py`.
## Run record (started 2026-11-06, 14:31 UTC, finished 2026-11-07, engineer's machine)

Model string `gemini-3.5-flash-lite`, temperature 0, seed field 0, 200 prompts (100 dev instances, BM25 and
RRF first stages, budget 8,000 model tokens), two runs each: 400 units. Daily cap used: 450 of 500 (margin
0.9), 13 requests a minute. Prepared prompts: `~/ril_rq3_pilot/prepared_dev100_b8000` (copied from the cluster
with a per-file SHA-256 comparison, 202 of 202 files equal); log directory `~/ril_rq3_pilot/log_dev100_b8000`
(outside the repository; `calls.jsonl`, `limiter.jsonl`, `run.out`, `pid`). The limiter stops the run at the
daily cap by design; the same command continues after Pacific midnight (08:00 UTC) without repeating finished
calls. Expected finish: about 620 calls (1.5 calls per unit in the first 10 minutes), so the first day stops
near 450 and the second day finishes the rest, on 2026-11-07 after 08:00 UTC.

The run stopped at the daily cap on 2026-11-06 (449 calls, 311 units final) and finished on 2026-11-07 (116 calls); the log directory is outside the repository.

First ten minutes (133 calls, 85 units started): no 429, no 5xx, no retry, all HTTP 200; latency p50 2.1 s,
p95 6.1 s; approximate tokens per model token on the first message p50 1.01 (p5 0.96, p95 1.04); first replies
unusable 35% (BM25) and 24% (RRF), unusable after re-asks 28% and 17% (mostly `no_edit_block`, then
`path_not_in_context` and `empty_reply`). Of the first 20 calls 10 were unusable, exactly half, so the stop
rule (more than half) did not fire; the unusable share is near the one-third line of the flip experiment above and is
read from the full day's rows, not from these. The prompt format was not changed.

## Pilot result (D109, `E-RQ3-PILOT-RESULT`, exploratory, 100 dev instances)

Flip criteria of D104, as written: calls per unit 1.41 (pass); unusable first reply 22.5% [18.7, 26.8] (pass; after follow-ups 12.8%); day cap hit on day one with 311 units final (pass as written; ambiguous wording, see the entry). The free tier stays workable: one arm-run of the 377 is about 533 calls, 2 days; 2 to 8 arm-runs 3 to 8 days; the 4-arm fallback grid 5 to 15 days (estimates). Unusable replies are mostly prose that says the code is not shown (40 of 51 final failures) and follow the gold being absent from the context; strict format faults are 3 of 400 units after follow-ups. BM25 against RRF: 17.0% against 8.5% unusable after follow-ups, mostly explained by gold absence (standardised gap 2.3 to 3.8 points, intervals include 0). Run-to-run at temperature 0: same reply text in 63% of pairs, same edits in 63% of usable pairs, same usability in 97.5%. No resolved rate exists; the power placeholders stay. Unusable replies count as failures for every arm. Numbers and their sources: `results/rq3_pilot/analysis/`.

## Applying edit blocks (D110, `E-RQ3-PATCHAPPLY`)

The reply's SEARCH/REPLACE blocks become a unified diff at the base commit in one place (`ril/agent/providers/patch_convert.py`), under a rule fixed before any model output is graded and the same for every arm. **Exact match is primary:** a SEARCH text must occur in its file as an exact string, exactly once; a missing file, no match or several matches fails the block; the edit set is atomic (one failing block, no patch, unresolved; no repair). **Whitespace-tolerant is a labelled sensitivity** (line endings and trailing whitespace normalised, blank lines at the ends of the SEARCH text ignored, still exactly one match, no fuzzy matching or indentation repair), reported beside the exact result wherever the resolved rate is; one switch, never per arm or instance. Blocks of a file apply in reply order to the file as earlier blocks left it. Unusable replies and apply failures are both unresolved and reported separately.

Measured on the pilot's stored edits (100 dev instances, 349 usable units): applying 129 of 200 (BM25) and 147 of 200 (RRF) units under the exact reading; the tolerant reading gives the same counts (0 of 73 failing units rescued); the failing blocks quote text found nowhere in the file. On 20 executable instances the gold patch turned into edit blocks, converted and run through the executor resolves 20 of 20, with trees identical to the gold patch's. Details and limits: the entry.

## Driver, held-out slice and analysis plan (D111 to D114, `E-RQ3-DRIVER`)

Fixed before any model output on the executable subset exists. All four decisions are `provisional` until the graded model
check. Evidence classes: D111 and D114 reasoned; D112 reasoned (the rule) with unverified prices; D113 reasoned, with the
run-to-run figures measured in the pilot and the power inputs partly assumed (listed in `results/rq3_driver/`).

**D111, held-out model-check slice.** 50 of the 377 executable instances (D106) are drawn by a seeded draw (seed 0)
stratified over repositories: a repository with at least 5 executable instances contributes at least 2; the places are
otherwise proportional to size (a large repository whose proportional share is below 2 is fixed at 2 and the rest is shared over
the others; shares are rounded by the largest remainder, ties by repository name; inside a repository the draw is uniform
over the sorted ids). Result: django 30, sympy 10, astropy 2, pytest 2, sphinx 2, xarray 2, pylint 1, requests 1, flask 0,
seaborn 0 (`results/rq3_driver/heldout_v1.json`, frozen and committed before any model call). The slice is excluded from every
confirmatory analysis and from the confirmatory N (N = 327); it is used only to choose the model (D112) and to exercise the
grading path on real replies; its results are reported separately and never enter a headline table.

**D112, model-choice rule.** Candidates: the cheapest model that can plausibly work and the next one or two stronger models on
the same API, at dated list prices read from the provider console by the engineer or at run time and stored with their date
(`configs/agent/prices.yaml`; the figures stored on 2026-11-08 are third-party and unverified: about 0.30 in / 2.50 out per
million tokens for the cheapest, 1.50 / 9.00 for a Flash-class model; a third candidate has no stored price). Each candidate runs
the RRF 8,000-token arm once on the held-out slice, temperature 0, same prompt, same follow-up policy and same thinking
configuration (recorded in the run's `meta.json`, with the thought tokens billed). The cheapest candidate whose resolved rate on
the slice (exact reading) is at least 15% is chosen (a discordance of 10% or more between arms is then attainable at N = 327);
if none reaches 15% the strongest candidate is taken, the floor is reported as not met, and the resolved-rate contrast is reported
as low-power with the retrieval-side readings carrying the weight. No other selection on resolved results is allowed
(`ril/agent/providers/model_choice.py`). Cheapest flip: the graded check itself.

**D113, scaffold and analysis plan (ADR-007 Accepted `provisional`; Q45 answered).** Scaffold as piloted: retrieval-supplied, one
repair call at temperature 0, up to two follow-ups for an unusable reply (same for all arms), edit application as D110. Unit of
analysis: the instance. k runs per arm (k = 3 if the spend allows, otherwise 2); an instance's score for an arm is the fraction of
its k runs that resolve; unusable and non-applying replies count as unresolved (D109, D110). **One primary contrast:** RAW against
the untrained encoder (the D80 declared fallback; the trained-checkpoint arms of RQ2 are added when their contexts exist), on the
327 confirmatory instances, as the paired difference in mean score with a paired bootstrap interval over instances (10,000
resamples, fixed seed) and a paired sign-flip permutation test (10,000 flips). Every other contrast (BM25, RRF, the RQ2 arms
against RAW) is an estimate with an interval and no test claim, so the family of tests is one and no multiplicity correction is
needed. Both patch readings are reported (exact primary, tolerant sensitivity), overall and by repository
(`ril/analysis/rq3_results.py`). A null result stays a null result: if retrieval differs and resolved rate does not, it is reported with the
outcome-class breakdown (unusable, apply failure, executed but unresolved), not reframed.

**D121, addendum to D113 (wording and a secondary reading; D113 is otherwise unchanged).** The scaffold is named
*retrieval-supplied one-shot repair* (edit blocks as in Agentless, no candidate selection); "Agentless-style" is retired. Beside the
mean resolved fraction every arm also reports the **any-of-k resolved share** (an instance counts if at least one of its k runs
resolves), and every contrast the paired difference of that share, with bootstrap intervals and no test, labelled secondary and
exploratory, at no extra calls (`ril/analysis/rq3_results.py`: columns `any_of_k_*` of the arm and contrast tables). The primary
contrast above is unchanged.

**D114, spend guard.** The driver keeps its own running cost from billed input, output and thought tokens at the stored dated
prices and stops before a call whose worst case (input estimated at 3 characters per token plus the full output allowance billed as
output) would pass a cap given on the command line; it refuses to start without a cap; a resumed run counts the cost already in the
call log; a run records the cap and the realised cost in `meta.json`. The provider-side hard cap, set by the engineer, is the second layer.

### The driver

`ril/agent/providers/driver.py`; command line `scripts/rq3_driver.py`. A unit is (instance, arm, run index). The driver takes the
final reply (a call through the provider client and limiter, resumable and logged as in the pilot; a reply already in a call log; or,
in replay mode, a stored or synthetic reply with no provider), converts it under both readings, executes the patch in the instance's
environment, reads FAIL_TO_PASS and PASS_TO_PASS and appends one row per unit to `results.jsonl`. Outcome classes: `unusable`,
`apply_failed:<class>` (`file_missing`, `no_match`, `multiple_matches`, `git_apply`), `executed_unresolved` (the patch applied and a named test
did not pass, including a patch after which no test output exists, and an empty diff, which is not executed), `resolved`; and
`exec_error:<stage>` for an environment failure before the patch is involved: tactical addition to the four classes, such a row is not
final, a restart reruns it with the stored reply, and the analysis counts what is left as unresolved and lists it apart (it must be
empty before a result is reported). A step that fails on a name-resolution outage is retried with backoff (3 retries, 30 s doubling) and
logged; a failure of the tests themselves is never retried. Both readings are stored (`outcome`, `outcome_tolerant`); a diff that is
the same under both runs once. Known limit: `no_test_output` after a patch is classed `executed_unresolved`; the 377 instances
passed the gold patch twice, so it means the patch broke the code, but an environment fault that looks the same would be counted
against the model.

### Prompts of the 377 (8,000-token set; job 64598)

The contexts of E-RQ3-CONTEXTS go through the pilot's builder (`build_prompt`) and screen. Issue text: the benchmark table's
`problem_statement` for all 377 (the 57 instances without an L2 label have no query folder; for the 320 that have one, the folder text
equals the table text, 320 of 320). Of 1,131 prompts (377 x BM25, untrained dense, RRF) **887 pass the screen and 244 are rejected**:
135 for an e-mail address that is not on the reviewed list (228 distinct addresses or path strings in all), 101 for a home-directory path, 8 for both
(`results/rq3_driver/prepare_report.json`). 109 instances have at least one rejected prompt and 57 have all three rejected; 232 of the 327
confirmatory instances and 36 of the 50 held-out ones have all three arms sendable, and 258 and 39 have the RRF prompt sendable
(`prepare_sendable_by_set.csv`). The matches are mostly placeholders in code excerpts (`example.com`, `foo@bar.com`), maintainer
addresses in headers and user names in tracebacks quoted in issues: public repository text, but the screen was written for the unpaid
quota's terms and has no reviewed list for path strings. **Nothing was added to the reviewed list and the screen was not changed**:
the options were open question Q70 (settled by D120, see "Pseudonymised prompts" below, which supersedes the counts of this paragraph). The prompt text before the excerpts is byte-identical across arms for every instance that has a
prompt (320 of 320). The 16,000-token set was not prepared (not run).

### Pseudonymised prompts (D120, `E-RQ3-PSEUDONYMISE`; closes Q70)

Terms read on 2026-11-08 (effective 2026-03-23): for unpaid services content may be used to improve products and read by
reviewers, and personal information must not be submitted; for paid services (a Cloud project with an active billing account) prompts
and responses are not used to improve products and are logged for a limited period to detect violations. The screen was written for
the unpaid terms. **Decision D120 (reasoned; evidence class: terms read, counts of E-RQ3-DRIVER): pseudonymise and restore, the same for
every arm and instance, on whichever tier is used.** After the context is assembled and before the screen, every e-mail address becomes
`person<N>@example.invalid` and the user-name segment of every home-directory path becomes `user<N>` (N by first occurrence in the prompt,
issue and excerpts alike); the per-prompt mapping is kept outside tracked paths. The driver applies the inverse to the reply before both
readings of the converter, so an edit that quotes a placeholder matches the original file and writes the original text. The screen
accepts exactly those two forms and nothing new, the reviewed list is unchanged. Result: **1,131 of 1,131 prompts pass** (244 touched: email 135,
path 101, both 8), restore gives back the original prompt for all, 377 of 377 instances have three sendable arms (327 confirmatory,
50 held-out), the text before the excerpts is identical across arms, tokens change by +0.72 per prompt on average (max +91) and the
largest context overshoot of 8,000 is 72 approximate tokens (tolerance fixed in advance: 80). Round trips on real data and the replay
of 10 touched instances (20 of 20 as expected) are in the experiment entry. Prompts sent in the free-tier pilot passed the old screen
and are unaffected. The tables `prepare_report.json` and `prepare_sendable_by_set.csv` in `results/rq3_driver/` describe the earlier
screen; the current ones are in `results/rq3_pseudonymise/`.

### Replay test (job 64590, account A, CPU, node-local scratch, nothing deleted)

The 20 gold-derived edit sets of E-RQ3-PATCHAPPLY (regenerated from the gold patches) and 10 deliberately broken variants went through the
driver in replay mode on the real executor: **30 of 30 outcome classes as expected** (`replay/replay_table.csv`).

| variant | n | expected | observed |
|---|---|---|---|
| gold-derived edits | 20 | `resolved` | 20 `resolved` (FAIL_TO_PASS and PASS_TO_PASS all pass; no environment failure this time) |
| a SEARCH text altered to match nothing | 4 | `apply_failed:no_match` | 4 as expected, no execution |
| a SEARCH text cut to a fragment that occurs twice | 3 | `apply_failed:multiple_matches` | 3 as expected, no execution |
| a top-level `raise` added after an import line (valid syntax) | 3 | `executed_unresolved` | 3 as expected: sphinx-7910 ran its tests (0 of 1 and 0 of 16 pass); the two pytest instances produced no test output (the module fails on import) |

### Power with run-to-run noise (`results/rq3_driver/rq3_power_run_noise*.csv`; estimated by simulation, 500 datasets per cell)

The old McNemar table (placeholder discordance, one pass; `rq3_power_placeholder.csv`: 5.25 to 8.75 points at N = 327) is kept beside it.
Simulation of the primary contrast as analysed: N = 327 (and 232, the complete-case count under the current screen), k = 1, 2, 3, resolved rate
10, 20, 30%, arm effect 0 to 10 points, instance heterogeneity kappa 1 and 4, repeated runs repeating the previous reply with probability 0.635
(**measured**: same first-reply text in 63.5% of pairs; same usability in 97.5%, folded into the resolve probability). **Assumptions, not
measurements:** the resolved rate, the effect, kappa (no resolved rate exists), independence of the arms given the instance. Size of the test
(effect 0): 2.4 to 5.0% across the 18 cells (nominal 5%). **Minimum detectable difference at power 0.8, N = 327:** k = 1: 5.5 to 9.7 points; k = 2: 4.9 to 8.8;
k = 3: 4.4 to 7.7 (the low end is rate 10% and kappa 1; the high end rate 30% and kappa 4). At N = 232: k = 1: 6.4 to over 10; k = 3: 5.4 to 9.8. A third run
buys about 1 to 2 points of detectable difference over one run; instance count matters more. A difference of 4 points or less is not
detectable at power 0.8 in any scenario of the grid (the lowest minimum is 4.4 points).

### Cost model (`results/rq3_driver/rq3_cost_model.csv`; tokens measured in the pilot, prices estimated and unverified)

From the pilot (1.41 calls and 12,629 input and 933 output tokens per unit, 400 units). One arm-run of 327 on the cheapest candidate: 462 calls, about
2.0 dollars (3.8 in the high scenario: upper calls interval and three times the output tokens); the 50 held-out: about 0.31 (0.59). A Flash-class
model at the stored price: 8.9 (15.7) and 1.4 (2.4). Grids at 327 on the cheapest: 3 arms x k = 2: about 12, x k = 3: 18; 4 arms x k = 2: 16, x k = 3: 24; on a Flash-class model
roughly 4.5 times that. A model that thinks longer than the pilot model is the main uncertainty (the pilot billed no thought tokens).

### Not done, limits

No model was called on any executable instance; no resolved rate exists. The graded check needs the engineer's billing, cap and limits. The 16,000-token
prompts are not prepared. Trained-checkpoint arms have no contexts. The screen's policy (Q70, settled by D120: pseudonymisation) decided how many confirmatory instances can be sent.

## Smoke test (2026-11-06, three calls, `results/rq3_pilot/smoke_2026-11-06/`)

Three calls on the first prepared prompts (a budget of 8,000 times 1.22 approximate tokens, since
replaced; see "Open points"): the model string `gemini-3.5-flash-lite` was accepted, all three replies
were usable edits on the first attempt (no re-ask), input 10,001 to 10,099 tokens, output 348 to 1,143,
latency 1.7 to 3.7 s, no 429 and no 5xx. Three calls say nothing about rates; they show that the
adapter, the format and the log work end to end. The smoke calls used 3 of the day's requests in a log
directory that is not the pilot's, so a pilot run the same day may exceed the day's count by up to 3
(the margin of 10% absorbs it).

## Open points (design questions, not decided here)

- **Tokens of the budget.** The assembly counts approximate tokens (`approx-words-v1`); the model's own
  tokenizer is not available offline. The 1.22 ratio measured in E-ASSEMBLY is against a different
  tokenizer. Three smoke-test prompts (one repository, 2026-11-06) had approximate counts of 1.000,
  1.001 and 1.000 times the model's reported input tokens, so the prepared budget uses a ratio of 1.0
  (8,000 model tokens = 8,000 approximate tokens). Three prompts are thin evidence; `report` prints the
  realised ratio over all first attempts, and a value far from 1.0 means the budget is restated before
  anything is reported.
- **Instance source.** Dev instances (recommended above) against Verified; Verified is the final test.
- **Choice of B.** Choosing between 8,000 and 16,000 from pilot results would be a selection on the
  pilot instances; the pilot runs one value and states it in advance.
- **Format of the edits.** The edit blocks are checked for format and for paths among the shown files
  only; whether a block applies to the repository is decided by the converter (D110, "Applying edit blocks").
