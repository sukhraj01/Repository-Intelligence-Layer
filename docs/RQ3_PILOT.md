# RQ3 pilot: cost, variance and feasibility of measuring resolved rate

**Status: design of the pilot, `provisional: D104`.** The pilot measures what an RQ3 run costs and how
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
   pinned paid version on Tier 1 billing with a hard spend cap. Free-tier terms on the use of submitted
   content were not read here; the inputs are public issue texts and public source files, but the terms
   should be read before the first call.
2. **Scaffold.** Agentless-style with retrieval supplied: one prompt per instance holding the issue text
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
the 263 instances above (52.6% of Verified); which repositories they fall in is in
`results/rq3_pilot/part_a/a_env_table.csv`.

**If it is judged not enough, the options** (none chosen here): a different executor with a container
runtime and root (a machine of the engineer's own, or an account with user namespaces or the setuid
install enabled by the cluster's administrators); a smaller instance set (the 263 buildable ones, or a
subset of repositories, which changes which claim RQ3 can make); the fallback of file-level hit rate
(`gold_in_context` of the assembly manifest) as a proxy for resolved rate, which measures retrieval and
not the agent's edit.

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
  only; whether a block applies to the repository is decided by the grader.
